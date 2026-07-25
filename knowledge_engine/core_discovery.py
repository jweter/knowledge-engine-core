"""Review-first CORE candidate discovery.

The third automated discovery source (M35), alongside M14's PubMed/PMC
pipeline (`pubmed_discovery.py`) and M34's Europe PMC pipeline
(`europepmc_discovery.py`). CORE (https://core.ac.uk, operated by The Open
University) aggregates open-access content from thousands of repositories
and journals worldwide -- a materially different reach than either PubMed
Central or Europe PMC, both of which are biomedical-literature-specific.

CORE's public API (https://api.core.ac.uk/docs/v3) differs from both prior
sources in ways that shape this module and its adjudication engine
(`core_candidate_review.py`):

- Pagination is offset-based (`offset`/`limit`, echoed back in the response
  alongside `totalHits`), closer to PubMed's `retstart` than to Europe PMC's
  cursor-mark pagination.
- An API key is optional, not required: unauthenticated requests work but
  are capped at a low rate limit (~10 requests per ~10-minute window,
  confirmed against the live API); a bearer token raises that limit. See
  `CoreDiscoveryService`'s `api_key` parameter -- unlike
  `OpenAiEmbeddingGenerator`, which unconditionally requires
  `KE_OPENAI_API_KEY`, this integration must keep working (at low volume)
  with no key configured, matching CORE's own behavior.
- Critically, CORE's work records carry no license field at all (confirmed
  by enumerating every key in a real response) and no `isOpenAccess`-style
  boolean either -- CORE's OA-ness comes from only aggregating OA
  repositories, not from a per-record flag. `core_candidate_review.py`
  therefore always holds CORE candidates on the license rule pending human
  verification; see that module's docstring.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from http.client import IncompleteRead
from typing import Protocol
from urllib.parse import urlencode, urlsplit

from knowledge_engine.core_http import TransportResponse

CORE_SEARCH_URL = "https://api.core.ac.uk/v3/search/works/"
CORE_PDF_HOST = "core.ac.uk"
"""CORE's own hosted full-text mirror (the `downloadUrl` field) -- the only
PDF host this module treats as preferred, adjudication-acceptable evidence.
See module docstring."""
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class CoreDiscoveryError(RuntimeError):
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
class CoreCandidate:
    """One reviewable bibliographic candidate."""

    core_id: str
    doi: str | None
    title: str
    abstract: str | None
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    document_type: str | None
    pdf_url: str | None
    pdf_host: str | None
    source_fulltext_urls: tuple[str, ...]


@dataclass(frozen=True)
class CoreDiscoveryResult:
    """Deterministic discovery output for one offset-paginated page."""

    query: str
    offset: int
    next_offset: int | None
    limit: int
    total_hits: int
    candidates: tuple[CoreCandidate, ...]

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        payload = {
            "query": self.query,
            "offset": self.offset,
            "next_offset": self.next_offset,
            "limit": self.limit,
            "total_hits": self.total_hits,
            "candidate_count": len(self.candidates),
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


class CoreDiscoveryService:
    """Discover CORE records without downloading papers."""

    def __init__(
        self,
        transport: GetTransport,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 5_000_000,
        request_interval_seconds: float = 0.5,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if request_interval_seconds < 0:
            raise ValueError("CORE request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("CORE max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("CORE retry backoff must be non-negative.")
        self.transport = transport
        self.api_key = api_key or None
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def discover(self, query: str, *, limit: int, offset: int = 0) -> CoreDiscoveryResult:
        """Return a bounded, deterministic page of candidates."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("CORE query must not be empty.")
        if not 1 <= limit <= 100:
            raise ValueError("Discovery limit must be between 1 and 100.")
        if offset < 0:
            raise ValueError("CORE offset must be non-negative.")

        body = self._get_json(
            f"{CORE_SEARCH_URL}?"
            + urlencode({"q": normalized_query, "limit": limit, "offset": offset})
        )
        total_hits = body.get("totalHits")
        if not isinstance(total_hits, int) or isinstance(total_hits, bool) or total_hits < 0:
            raise CoreDiscoveryError("CORE search response was malformed.")
        raw_results = body.get("results")
        if not isinstance(raw_results, list):
            raise CoreDiscoveryError("CORE search response was malformed.")

        candidates = tuple(_parse_candidate(raw) for raw in raw_results)
        next_offset = offset + len(candidates)
        return CoreDiscoveryResult(
            query=normalized_query,
            offset=offset,
            next_offset=next_offset if next_offset < total_hits else None,
            limit=limit,
            total_hits=total_hits,
            candidates=candidates,
        )

    def _get_json(self, url: str) -> dict[str, object]:
        response = self._get(url)
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoreDiscoveryError("CORE returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise CoreDiscoveryError("CORE returned malformed JSON.")
        return value

    def _get(self, url: str) -> TransportResponse:
        headers = dict(DEFAULT_HEADERS)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
                    headers=headers,
                    timeout_seconds=self.timeout_seconds,
                    max_response_bytes=self.max_response_bytes,
                )
            except (IncompleteRead, OSError, TimeoutError) as exc:
                if attempt + 1 == self.max_attempts:
                    raise CoreDiscoveryError(
                        f"CORE search request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise CoreDiscoveryError(
                    "CORE search request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise CoreDiscoveryError("CORE search request retry state was invalid.")


def _parse_candidate(raw: object) -> CoreCandidate:
    if not isinstance(raw, dict):
        raise CoreDiscoveryError("CORE search response contained a malformed result.")

    core_id = _required_id(raw)
    title = _required_string(raw, "title")
    source_fulltext_urls = _string_list(raw, "sourceFulltextUrls")
    pdf_url, pdf_host = _best_pdf_url(raw, source_fulltext_urls)

    return CoreCandidate(
        core_id=core_id,
        doi=_optional_string(raw, "doi"),
        title=title,
        abstract=_optional_string(raw, "abstract"),
        authors=_authors(raw),
        publication_year=_optional_year(raw),
        venue=_optional_string(raw, "publisher"),
        document_type=_optional_string(raw, "documentType"),
        pdf_url=pdf_url,
        pdf_host=pdf_host,
        source_fulltext_urls=source_fulltext_urls,
    )


def _best_pdf_url(
    raw: dict[str, object], source_fulltext_urls: tuple[str, ...]
) -> tuple[str | None, str | None]:
    """Return the most trustworthy full-text URL, preferring CORE's own host.

    See module docstring: only `CORE_PDF_HOST` (CORE's own `downloadUrl`
    mirror) is treated as this module's preferred, adjudication-acceptable
    evidence. A third-party `sourceFulltextUrls` entry is still returned
    (both here and in full, via `source_fulltext_urls`) for transparency,
    but flagged as a different host so adjudication holds rather than
    auto-accepts it.
    """

    download_url = raw.get("downloadUrl")
    if isinstance(download_url, str) and download_url.strip():
        url = download_url.strip()
        return url, urlsplit(url).hostname
    if source_fulltext_urls:
        url = source_fulltext_urls[0]
        return url, urlsplit(url).hostname
    return None, None


def _required_id(payload: dict[str, object]) -> str:
    value = payload.get("id")
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise CoreDiscoveryError("CORE search response was missing required evidence.")
    text = str(value).strip()
    if not text:
        raise CoreDiscoveryError("CORE search response was missing required evidence.")
    return text


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CoreDiscoveryError("CORE search response was missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CoreDiscoveryError("CORE search response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _string_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise CoreDiscoveryError("CORE search response contained malformed evidence.")
    return tuple(item.strip() for item in value)


def _authors(payload: dict[str, object]) -> tuple[str, ...]:
    value = payload.get("authors", [])
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        name = author.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return tuple(names)


def _optional_year(payload: dict[str, object]) -> int | None:
    value = payload.get("yearPublished")
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 1000 <= value <= 9999:
        return value
    raise CoreDiscoveryError("CORE search response contained malformed evidence.")
