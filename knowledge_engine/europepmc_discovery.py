"""Review-first Europe PMC candidate discovery.

The second automated discovery source (M34), alongside M14's PubMed/PMC
pipeline (`pubmed_discovery.py`). Deliberately scoped to what Europe PMC adds
that PMC does not already reach: for records already in PMC (`pmcid` set,
`inPMC: "Y"`), Europe PMC's own "PDF" is just a rendered view of the exact
same PMC content `pubmed_discovery.py` already acquires via NCBI's official
S3 bucket -- rediscovering it here would only duplicate that pipeline through
a less-official endpoint. This module still discovers and returns those
records (never silently drops evidence), but `europepmc_candidate_review.py`
explicitly rejects them as out of this pipeline's scope, with a clear reason
code, the same way a corpus-scope-insufficient PubMed candidate is rejected
rather than dropped.

No new host-allowlist risk: unlike heterogeneous third-party OA repositories
(Unpaywall mirrors, publisher sites) that a candidate's `fullTextUrlList` may
also list, this module only ever treats `europepmc.org`-hosted PDF URLs as
acquirable evidence -- Europe PMC's own hosted full-text repository, the
closest analogue to PMC's official S3 bucket. A candidate whose only OA PDF
is at a third-party host is discovered and reported, never auto-accepted;
see `europepmc_candidate_review.py`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from http.client import IncompleteRead
from typing import Protocol
from urllib.parse import urlencode, urlsplit

from knowledge_engine.europepmc_http import EUROPEPMC_PDF_HOST, TransportResponse

EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class EuropePmcDiscoveryError(RuntimeError):
    """Sanitized provider or response failure."""


class GetTransport(Protocol):
    """Structural transport interface used by the discovery service."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


@dataclass(frozen=True)
class EuropePmcCandidate:
    """One reviewable bibliographic candidate."""

    europepmc_id: str
    source: str
    pmid: str | None
    pmcid: str | None
    doi: str | None
    title: str
    abstract: str | None
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    in_pmc: bool
    open_access: bool
    license: str | None
    pdf_url: str | None
    pdf_host: str | None


@dataclass(frozen=True)
class EuropePmcDiscoveryResult:
    """Deterministic discovery output for one cursor-paginated page."""

    query: str
    cursor_mark: str
    next_cursor_mark: str | None
    limit: int
    candidates: tuple[EuropePmcCandidate, ...]

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        payload = {
            "query": self.query,
            "cursor_mark": self.cursor_mark,
            "next_cursor_mark": self.next_cursor_mark,
            "limit": self.limit,
            "candidate_count": len(self.candidates),
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


class EuropePmcDiscoveryService:
    """Discover Europe PMC records without downloading papers."""

    def __init__(
        self,
        transport: GetTransport,
        *,
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 5_000_000,
        request_interval_seconds: float = 0.5,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if request_interval_seconds < 0:
            raise ValueError("Europe PMC request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("Europe PMC max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("Europe PMC retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def discover(
        self, query: str, *, limit: int, cursor_mark: str = "*"
    ) -> EuropePmcDiscoveryResult:
        """Return a bounded, deterministic page of candidates."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Europe PMC query must not be empty.")
        if not 1 <= limit <= 100:
            raise ValueError("Discovery limit must be between 1 and 100.")
        if not cursor_mark:
            raise ValueError("Europe PMC cursor_mark must not be empty.")

        body = self._get_json(
            f"{EUROPEPMC_SEARCH_URL}?"
            + urlencode(
                {
                    "query": normalized_query,
                    "format": "json",
                    "resultType": "core",
                    "pageSize": limit,
                    "cursorMark": cursor_mark,
                }
            )
        )
        result_list = body.get("resultList")
        if not isinstance(result_list, dict):
            raise EuropePmcDiscoveryError("Europe PMC search response was malformed.")
        raw_results = result_list.get("result")
        if not isinstance(raw_results, list):
            raise EuropePmcDiscoveryError("Europe PMC search response was malformed.")
        next_cursor_mark = body.get("nextCursorMark")
        if next_cursor_mark is not None and not isinstance(next_cursor_mark, str):
            raise EuropePmcDiscoveryError("Europe PMC search response was malformed.")

        candidates = tuple(_parse_candidate(raw) for raw in raw_results)
        return EuropePmcDiscoveryResult(
            query=normalized_query,
            cursor_mark=cursor_mark,
            next_cursor_mark=next_cursor_mark if next_cursor_mark != cursor_mark else None,
            limit=limit,
            candidates=candidates,
        )

    def _get_json(self, url: str) -> dict[str, object]:
        response = self._get(url)
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EuropePmcDiscoveryError("Europe PMC returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise EuropePmcDiscoveryError("Europe PMC returned malformed JSON.")
        return value

    def _get(self, url: str) -> TransportResponse:
        for attempt in range(self.max_attempts):
            if attempt == 0:
                if self._request_count and self.request_interval_seconds:
                    self.sleep(self.request_interval_seconds)
            elif self.retry_backoff_seconds:
                self.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
            self._request_count += 1
            try:
                response = self.transport.get(
                    url=url,
                    headers=DEFAULT_HEADERS,
                    timeout_seconds=self.timeout_seconds,
                    max_response_bytes=self.max_response_bytes,
                )
            except (IncompleteRead, OSError, TimeoutError) as exc:
                if attempt + 1 == self.max_attempts:
                    raise EuropePmcDiscoveryError(
                        f"Europe PMC search request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise EuropePmcDiscoveryError(
                    "Europe PMC search request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise EuropePmcDiscoveryError("Europe PMC search request retry state was invalid.")


def _parse_candidate(raw: object) -> EuropePmcCandidate:
    if not isinstance(raw, dict):
        raise EuropePmcDiscoveryError("Europe PMC search response contained a malformed result.")

    europepmc_id = _required_string(raw, "id")
    source = _required_string(raw, "source")
    title = _required_string(raw, "title")
    is_open_access = _required_yn(raw, "isOpenAccess")
    in_pmc = _required_yn(raw, "inPMC")
    pdf_url, pdf_host = _best_pdf_url(raw)

    return EuropePmcCandidate(
        europepmc_id=europepmc_id,
        source=source,
        pmid=_optional_string(raw, "pmid"),
        pmcid=_optional_string(raw, "pmcid"),
        doi=_optional_string(raw, "doi"),
        title=title,
        abstract=_optional_string(raw, "abstractText"),
        authors=_authors(raw),
        publication_year=_optional_year(raw),
        venue=_venue(raw),
        in_pmc=in_pmc,
        open_access=is_open_access,
        license=_optional_string(raw, "license"),
        pdf_url=pdf_url,
        pdf_host=pdf_host,
    )


def _best_pdf_url(raw: dict[str, object]) -> tuple[str | None, str | None]:
    """Return the most trustworthy OA PDF URL, preferring Europe PMC's own host.

    See module docstring: only `EUROPEPMC_PDF_HOST` is treated as this
    module's preferred, adjudication-acceptable evidence. A third-party OA
    PDF URL (Unpaywall, a publisher, a preprint server) is still returned
    for transparency, but flagged as a different host so adjudication can
    hold rather than auto-accept it.
    """

    full_text_url_list = raw.get("fullTextUrlList")
    if not isinstance(full_text_url_list, dict):
        return None, None
    entries = full_text_url_list.get("fullTextUrl")
    if not isinstance(entries, list):
        return None, None

    fallback: tuple[str, str] | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("availabilityCode") != "OA" or entry.get("documentStyle") != "pdf":
            continue
        url = entry.get("url")
        if not isinstance(url, str) or not url:
            continue
        hostname = urlsplit(url).hostname
        if hostname == EUROPEPMC_PDF_HOST:
            return url, hostname
        if fallback is None and hostname is not None:
            fallback = (url, hostname)
    return fallback if fallback is not None else (None, None)


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EuropePmcDiscoveryError("Europe PMC search response was missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EuropePmcDiscoveryError("Europe PMC search response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _required_yn(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if value not in ("Y", "N"):
        raise EuropePmcDiscoveryError("Europe PMC search response contained malformed evidence.")
    return value == "Y"


def _authors(payload: dict[str, object]) -> tuple[str, ...]:
    author_list = payload.get("authorList")
    if not isinstance(author_list, dict):
        return ()
    authors = author_list.get("author")
    if not isinstance(authors, list):
        return ()
    names: list[str] = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        full_name = author.get("fullName")
        if isinstance(full_name, str) and full_name.strip():
            names.append(full_name.strip())
    return tuple(names)


def _optional_year(payload: dict[str, object]) -> int | None:
    value = payload.get("pubYear")
    if value is None:
        return None
    if isinstance(value, str) and value.isdigit() and len(value) == 4:
        return int(value)
    raise EuropePmcDiscoveryError("Europe PMC search response contained malformed evidence.")


def _venue(payload: dict[str, object]) -> str | None:
    journal_info = payload.get("journalInfo")
    if not isinstance(journal_info, dict):
        return None
    journal = journal_info.get("journal")
    if not isinstance(journal, dict):
        return None
    title = journal.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None
