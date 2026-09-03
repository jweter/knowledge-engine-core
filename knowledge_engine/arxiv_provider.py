"""Bounded arXiv discovery behind the provider-neutral federated contract."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlencode

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_USER_AGENT = "knowledge-engine-core/0.2 federated-discovery"
MAX_RESULTS = 100

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_ARXIV_ID_RE = re.compile(
    r"^(?P<base>(?:\d{4}\.\d{4,5}|[A-Za-z0-9.\-]+/\d{7}))"
    r"(?:v(?P<version>[1-9]\d*))?$"
)

# Issue #433 item 2's third per-provider slice, following
# semantic_scholar_provider.py/openalex_provider.py's established pattern: a
# bounded, exponential-backoff retry for transient failures only.
# `DEFAULT_MAX_ATTEMPTS` counts the *first* attempt plus every retry (3 ==
# up to 2 retries). Retries are triggered only by outcomes that genuinely
# indicate a transient condition -- an HTTP 429 rate-limit response or a
# provider-unavailable/connection-level failure -- never a non-transient 4xx
# client error, an oversized result page, or a malformed response body,
# which are real outcomes rather than transient conditions worth retrying.
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5
_TRANSIENT_OUTCOMES = frozenset({ProviderOutcome.RATE_LIMITED, ProviderOutcome.UNAVAILABLE})


class ResponseTooLargeError(OSError):
    """Raised when an arXiv response exceeds the configured byte limit."""


@dataclass(frozen=True)
class TransportResponse:
    """Bounded HTTP response returned by an injected arXiv transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True)
class _RequestFailure:
    outcome: ProviderOutcome
    reason: str


@dataclass(frozen=True)
class _RequestOutcome:
    """Result of one logical (possibly retried) request.

    Exactly one of ``response``/``failure`` is set. ``retry_attempt_count`` and
    ``rate_limited_observed`` describe the whole retry loop, not just the final
    attempt, so a caller building a `ProviderStatus` from either branch reports
    accurate retry/rate-limit facts either way.
    """

    response: TransportResponse | None
    failure: _RequestFailure | None
    retry_attempt_count: int
    rate_limited_observed: bool


class ArxivTransport(Protocol):
    """Minimal transport contract required by the arXiv adapter."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


class ArxivProvider:
    """Provider-neutral arXiv discovery with explicit preprint version semantics."""

    def __init__(
        self,
        *,
        transport: ArxivTransport,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("arXiv timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("arXiv response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("arXiv User-Agent must not be blank.")
        if max_attempts < 1:
            raise ValueError("arXiv max_attempts must be at least 1.")
        if retry_backoff_seconds < 0:
            raise ValueError("arXiv retry backoff must not be negative.")

        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep or time.sleep

    @property
    def name(self) -> str:
        return "arxiv"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        """Search arXiv and return version-explicit preprint candidates."""

        if query.limit_per_provider > MAX_RESULTS:
            return _failure_result(query, "unsupported_limit")

        params = {
            "search_query": _build_search_query(query),
            "start": "0",
            "max_results": str(query.limit_per_provider),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_URL}?{urlencode(params)}"
        outcome = self._raw_request(url=url)
        if outcome.failure is not None:
            return _failure_result(
                query, outcome.failure.reason, outcome.failure.outcome, outcome=outcome
            )
        response = outcome.response
        assert response is not None

        try:
            root = ET.fromstring(response.body)
        except (ET.ParseError, UnicodeDecodeError):
            return _failure_result(query, "malformed_response", outcome=outcome)

        entries = root.findall(f"{_ATOM}entry")
        if len(entries) > query.limit_per_provider:
            return _failure_result(query, "oversized_result_page", outcome=outcome)
        if not entries:
            return _empty_result(query, outcome=outcome)

        retrieved_at = self._clock()
        candidates: list[FederatedCandidate] = []
        for entry in entries:
            candidate = _parse_entry(entry, retrieved_at=retrieved_at)
            if candidate is None:
                return _failure_result(query, "malformed_response", outcome=outcome)
            candidates.append(candidate)

        return _success_result(query, tuple(candidates), outcome=outcome)

    def _raw_request(self, *, url: str) -> _RequestOutcome:
        """Perform one logical request, retrying transient failures in place.

        A bounded loop (`self._max_attempts` total attempts, exponential
        backoff between them via `self._sleep`) retries only
        `_TRANSIENT_OUTCOMES` (HTTP 429 rate-limiting, provider-unavailable/
        connection-level failures) -- never a non-transient 4xx client error
        or an oversized/malformed response, both of which indicate a real
        outcome rather than a transient condition worth retrying. The final
        response or failure is returned alongside how many retries were
        actually needed and whether any attempt observed a rate-limit
        response, so a caller can build an honest `ProviderStatus` regardless
        of which branch it takes.
        """

        headers: dict[str, str] = {
            "Accept": "application/atom+xml, application/xml;q=0.9",
            "User-Agent": self._user_agent,
        }

        retry_attempt_count = 0
        rate_limited_observed = False
        attempt = 0
        while True:
            attempt += 1
            attempt_result = self._attempt(url=url, headers=headers)
            if isinstance(attempt_result, TransportResponse):
                return _RequestOutcome(
                    response=attempt_result,
                    failure=None,
                    retry_attempt_count=retry_attempt_count,
                    rate_limited_observed=rate_limited_observed,
                )
            if attempt_result.outcome is ProviderOutcome.RATE_LIMITED:
                rate_limited_observed = True
            if attempt_result.outcome in _TRANSIENT_OUTCOMES and attempt < self._max_attempts:
                retry_attempt_count += 1
                self._sleep(self._retry_backoff_seconds * (2 ** (attempt - 1)))
                continue
            return _RequestOutcome(
                response=None,
                failure=attempt_result,
                retry_attempt_count=retry_attempt_count,
                rate_limited_observed=rate_limited_observed,
            )

    def _attempt(
        self, *, url: str, headers: Mapping[str, str]
    ) -> TransportResponse | _RequestFailure:
        """Perform exactly one HTTP attempt and map it to a response or failure."""

        try:
            response = self._transport.get(
                url=url,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
                max_response_bytes=self._max_response_bytes,
            )
        except ResponseTooLargeError:
            return _RequestFailure(ProviderOutcome.FAILED, "oversized_response")
        except TimeoutError:
            return _RequestFailure(ProviderOutcome.UNAVAILABLE, "timeout")
        except OSError:
            return _RequestFailure(ProviderOutcome.UNAVAILABLE, "transport_error")

        if len(response.body) > self._max_response_bytes:
            return _RequestFailure(ProviderOutcome.FAILED, "oversized_response")
        if response.status_code == 429:
            return _RequestFailure(ProviderOutcome.RATE_LIMITED, "rate_limited")
        if 500 <= response.status_code <= 599:
            return _RequestFailure(ProviderOutcome.UNAVAILABLE, "provider_unavailable")
        if response.status_code < 200 or response.status_code >= 300:
            return _RequestFailure(ProviderOutcome.FAILED, "unsupported_http_status")
        return response


def _build_search_query(query: DiscoveryQuery) -> str:
    clauses = [f"all:{query.normalized_text}"]
    if query.year_from is not None or query.year_to is not None:
        year_from = query.year_from if query.year_from is not None else 1000
        year_to = query.year_to if query.year_to is not None else 9999
        clauses.append(f"submittedDate:[{year_from:04d}01010000 TO {year_to:04d}12312359]")
    return " AND ".join(clauses)


def _parse_entry(entry: ET.Element, *, retrieved_at: datetime) -> FederatedCandidate | None:
    raw_id = _text(entry.find(f"{_ATOM}id"))
    title = _normalized_text(entry.find(f"{_ATOM}title"))
    if raw_id is None or title is None:
        return None

    normalized = _normalize_arxiv_identifier(raw_id)
    if normalized is None:
        return None
    arxiv_id, version, provider_id = normalized

    authors = tuple(
        name
        for author in entry.findall(f"{_ATOM}author")
        for name in [_normalized_text(author.find(f"{_ATOM}name"))]
        if name is not None
    )
    published = _text(entry.find(f"{_ATOM}published"))
    publication_year = _year_from_timestamp(published)
    abstract = _normalized_text(entry.find(f"{_ATOM}summary"))
    landing_url, pdf_url = _entry_links(entry)
    related_journal_doi = _normalize_doi(_text(entry.find(f"{_ARXIV}doi")))
    related_journal_reference = _normalized_text(entry.find(f"{_ARXIV}journal_ref"))
    license_url = _text(entry.find(f"{_ARXIV}license"))

    observation = ProviderObservation(
        provider="arxiv",
        provider_id=provider_id,
        title=title,
        authors=authors,
        publication_year=publication_year,
        abstract=abstract,
        arxiv_id=arxiv_id,
        landing_url=landing_url,
        full_text_url=pdf_url,
        license=license_url,
        metadata_source="arxiv_atom",
        open_access_source="arxiv",
        open_access=True,
        preprint=True,
        preprint_version=version,
        related_journal_doi=related_journal_doi,
        related_journal_reference=related_journal_reference,
        retrieved_at=retrieved_at.astimezone(UTC).isoformat(),
    )
    canonical_id = f"arxiv:{provider_id}"
    return FederatedCandidate(
        canonical_id=canonical_id,
        title=title,
        observations=(observation,),
        publication_year=publication_year,
    )


def _normalize_arxiv_identifier(value: str) -> tuple[str, int | None, str] | None:
    normalized = value.strip().rstrip("/")
    for marker in ("/abs/", "/pdf/"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[1]
            break
    if normalized.endswith(".pdf"):
        normalized = normalized[:-4]
    match = _ARXIV_ID_RE.fullmatch(normalized)
    if match is None:
        return None
    base = match.group("base")
    raw_version = match.group("version")
    version = int(raw_version) if raw_version is not None else None
    provider_id = f"{base}v{version}" if version is not None else base
    return base, version, provider_id


def _entry_links(entry: ET.Element) -> tuple[str | None, str | None]:
    landing_url: str | None = None
    pdf_url: str | None = None
    for link in entry.findall(f"{_ATOM}link"):
        href = link.get("href")
        if not href:
            continue
        rel = link.get("rel")
        link_type = link.get("type")
        title = link.get("title")
        if rel == "alternate" and landing_url is None:
            landing_url = href
        if (title == "pdf" or link_type == "application/pdf") and pdf_url is None:
            pdf_url = href
    return landing_url, pdf_url


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _normalized_text(element: ET.Element | None) -> str | None:
    value = _text(element)
    return " ".join(value.split()) if value is not None else None


def _year_from_timestamp(value: str | None) -> int | None:
    if value is None or len(value) < 4 or not value[:4].isdigit():
        return None
    year = int(value[:4])
    return year if 1000 <= year <= 9999 else None


def _normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = normalized.strip()
    return normalized if normalized.startswith("10.") and "/" in normalized else None


def _success_result(
    query: DiscoveryQuery,
    candidates: tuple[FederatedCandidate, ...],
    *,
    outcome: _RequestOutcome,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="arxiv",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=len(candidates),
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            ),
        ),
        candidates=candidates,
    )


def _empty_result(query: DiscoveryQuery, *, outcome: _RequestOutcome) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="arxiv",
                outcome=ProviderOutcome.EMPTY,
                attempted=True,
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            ),
        ),
    )


def _failure_result(
    query: DiscoveryQuery,
    reason: str,
    provider_outcome: ProviderOutcome = ProviderOutcome.FAILED,
    *,
    outcome: _RequestOutcome | None = None,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="arxiv",
                outcome=provider_outcome,
                attempted=True,
                reason=reason,
                retry_attempt_count=outcome.retry_attempt_count if outcome is not None else 0,
                rate_limited_observed=(
                    outcome.rate_limited_observed if outcome is not None else False
                ),
            ),
        ),
    )
