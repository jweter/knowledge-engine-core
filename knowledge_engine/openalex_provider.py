"""OpenAlex adapter for provider-neutral federated scholarly discovery.

The adapter keeps OpenAlex transport details behind an injected bounded transport,
normalizes only fields actually reported by OpenAlex, and maps failures into the
FRD provider-status contract without leaking provider-specific response objects.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any, Protocol
from urllib.parse import quote, urlencode

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_USER_AGENT = "knowledge-engine-core/0.2 federated-discovery"


class ResponseTooLargeError(OSError):
    """Raised when a provider response exceeds the configured byte limit."""


@dataclass(frozen=True)
class TransportResponse:
    """Bounded HTTP response returned by an injected OpenAlex transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


class OpenAlexTransport(Protocol):
    """Minimal transport contract required by the OpenAlex adapter."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


class OpenAlexProvider:
    """Provider-neutral OpenAlex search and work lookup adapter."""

    def __init__(
        self,
        *,
        transport: OpenAlexTransport,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        api_key: str | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OpenAlex timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("OpenAlex response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("OpenAlex User-Agent must not be blank.")
        if api_key is not None and not api_key.strip():
            raise ValueError("OpenAlex API key must not be blank when provided.")

        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent
        self._api_key = api_key.strip() if api_key is not None else None

    @property
    def name(self) -> str:
        return "openalex"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        params: dict[str, str] = {
            "search": query.normalized_text,
            "per-page": str(query.limit_per_provider),
        }
        filters: list[str] = []
        if query.year_from is not None:
            filters.append(f"from_publication_date:{query.year_from:04d}-01-01")
        if query.year_to is not None:
            filters.append(f"to_publication_date:{query.year_to:04d}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if self._api_key is not None:
            params["api_key"] = self._api_key

        return self._fetch_list(query=query, url=f"{OPENALEX_WORKS_URL}?{urlencode(params)}")

    def lookup(self, identifier: str) -> FederatedSearchResult:
        """Look up one work by OpenAlex ID or DOI using the same FRD result contract."""
        normalized = identifier.strip()
        if not normalized:
            raise ValueError("OpenAlex lookup identifier must not be blank.")

        openalex_id = _normalize_openalex_id(normalized)
        query = DiscoveryQuery(text=f"openalex lookup {normalized}", limit_per_provider=1)
        if openalex_id is not None:
            url = f"{OPENALEX_WORKS_URL}/{quote(openalex_id, safe='')}"
            return self._fetch_single(query=query, url=self._with_api_key(url))

        doi = _normalize_doi(normalized)
        if doi is None:
            raise ValueError("OpenAlex lookup requires an OpenAlex work ID or DOI.")

        url = f"{OPENALEX_WORKS_URL}/doi:{quote(doi, safe='/')}"
        return self._fetch_single(query=query, url=self._with_api_key(url))

    def _with_api_key(self, url: str) -> str:
        if self._api_key is None:
            return url
        return f"{url}?{urlencode({'api_key': self._api_key})}"

    def _fetch_single(self, *, query: DiscoveryQuery, url: str) -> FederatedSearchResult:
        response_or_result = self._request(query=query, url=url)
        if isinstance(response_or_result, FederatedSearchResult):
            return response_or_result

        response = response_or_result
        try:
            payload = json.loads(response.body)
        except (JSONDecodeError, UnicodeDecodeError):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        if not isinstance(payload, Mapping):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")

        candidate = _parse_work(payload, retrieved_at=self._clock())
        if candidate is None:
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        return _success_result(query, (candidate,))

    def _fetch_list(self, *, query: DiscoveryQuery, url: str) -> FederatedSearchResult:
        response_or_result = self._request(query=query, url=url)
        if isinstance(response_or_result, FederatedSearchResult):
            return response_or_result

        response = response_or_result
        try:
            payload = json.loads(response.body)
        except (JSONDecodeError, UnicodeDecodeError):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        if not isinstance(payload, Mapping):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")

        retrieved_at = self._clock()
        candidates = tuple(
            candidate
            for item in raw_results
            if isinstance(item, Mapping)
            for candidate in [_parse_work(item, retrieved_at=retrieved_at)]
            if candidate is not None
        )
        if not candidates:
            return _empty_result(query)
        return _success_result(query, candidates)

    def _request(
        self,
        *,
        query: DiscoveryQuery,
        url: str,
    ) -> TransportResponse | FederatedSearchResult:
        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        try:
            response = self._transport.get(
                url=url,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
                max_response_bytes=self._max_response_bytes,
            )
        except ResponseTooLargeError:
            return _failure_result(query, ProviderOutcome.FAILED, "oversized_response")
        except TimeoutError:
            return _failure_result(query, ProviderOutcome.UNAVAILABLE, "timeout")
        except OSError:
            return _failure_result(query, ProviderOutcome.UNAVAILABLE, "transport_error")

        if len(response.body) > self._max_response_bytes:
            return _failure_result(query, ProviderOutcome.FAILED, "oversized_response")
        if response.status_code == 404:
            return _empty_result(query)
        if response.status_code == 429:
            return _failure_result(query, ProviderOutcome.RATE_LIMITED, "rate_limited")
        if 500 <= response.status_code <= 599:
            return _failure_result(query, ProviderOutcome.UNAVAILABLE, "provider_unavailable")
        if response.status_code < 200 or response.status_code >= 300:
            return _failure_result(query, ProviderOutcome.FAILED, "unsupported_http_status")
        return response


def _parse_work(
    payload: Mapping[str, Any],
    *,
    retrieved_at: datetime,
) -> FederatedCandidate | None:
    raw_id = payload.get("id")
    title = payload.get("title") or payload.get("display_name")
    if not isinstance(raw_id, str) or not raw_id.strip():
        return None
    if not isinstance(title, str) or not title.strip():
        return None

    openalex_id = _normalize_openalex_id(raw_id)
    if openalex_id is None:
        return None

    authors: list[str] = []
    raw_authorships = payload.get("authorships")
    if isinstance(raw_authorships, list):
        for authorship in raw_authorships:
            if not isinstance(authorship, Mapping):
                continue
            author = authorship.get("author")
            if not isinstance(author, Mapping):
                continue
            display_name = author.get("display_name")
            if isinstance(display_name, str) and display_name.strip():
                authors.append(display_name.strip())

    publication_year = payload.get("publication_year")
    if not isinstance(publication_year, int):
        publication_year = None

    primary_location = payload.get("primary_location")
    venue: str | None = None
    landing_url: str | None = None
    full_text_url: str | None = None
    if isinstance(primary_location, Mapping):
        landing_url = _optional_text(primary_location.get("landing_page_url"))
        full_text_url = _optional_text(primary_location.get("pdf_url"))
        source = primary_location.get("source")
        if isinstance(source, Mapping):
            venue = _optional_text(source.get("display_name"))

    doi = _normalize_doi(_optional_text(payload.get("doi")) or "")
    citation_count = payload.get("cited_by_count")
    if not isinstance(citation_count, int) or citation_count < 0:
        citation_count = None

    open_access: bool | None = None
    raw_oa = payload.get("open_access")
    if isinstance(raw_oa, Mapping) and isinstance(raw_oa.get("is_oa"), bool):
        open_access = raw_oa["is_oa"]

    retracted = payload.get("is_retracted")
    if not isinstance(retracted, bool):
        retracted = None

    observation = ProviderObservation(
        provider="openalex",
        provider_id=openalex_id,
        title=title.strip(),
        authors=tuple(authors),
        publication_year=publication_year,
        venue=venue,
        abstract=_reconstruct_abstract(payload.get("abstract_inverted_index")),
        doi=doi,
        openalex_id=openalex_id,
        landing_url=landing_url,
        full_text_url=full_text_url,
        citation_count=citation_count,
        open_access=open_access,
        retracted=retracted,
        retrieved_at=retrieved_at.astimezone(UTC).isoformat(),
    )
    return FederatedCandidate(
        canonical_id=f"openalex:{openalex_id}",
        title=observation.title,
        observations=(observation,),
        doi=doi,
        publication_year=publication_year,
    )


def _reconstruct_abstract(raw: object) -> str | None:
    if not isinstance(raw, Mapping):
        return None
    positioned_words: list[tuple[int, str]] = []
    for word, positions in raw.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int) and position >= 0:
                positioned_words.append((position, word))
    if not positioned_words:
        return None
    positioned_words.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned_words)


def _normalize_openalex_id(value: str) -> str | None:
    normalized = value.strip().rstrip("/")
    if normalized.lower().startswith("https://openalex.org/"):
        normalized = normalized.rsplit("/", 1)[-1]
    if len(normalized) >= 2 and normalized[0].upper() == "W" and normalized[1:].isdigit():
        return f"W{normalized[1:]}"
    return None


def _normalize_doi(value: str) -> str | None:
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = normalized.strip()
    return normalized if normalized.startswith("10.") and "/" in normalized else None


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _success_result(
    query: DiscoveryQuery,
    candidates: tuple[FederatedCandidate, ...],
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="openalex",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=len(candidates),
            ),
        ),
        candidates=candidates,
    )


def _empty_result(query: DiscoveryQuery) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="openalex",
                outcome=ProviderOutcome.EMPTY,
                attempted=True,
                result_count=0,
            ),
        ),
    )


def _failure_result(
    query: DiscoveryQuery,
    outcome: ProviderOutcome,
    reason: str,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="openalex",
                outcome=outcome,
                attempted=True,
                result_count=0,
                reason=reason,
            ),
        ),
    )
