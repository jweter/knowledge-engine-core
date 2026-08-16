"""Semantic Scholar adapter for provider-neutral federated scholarly discovery.

The adapter keeps Semantic Scholar transport details behind an injected bounded
transport. Public Academic Graph access works without a key; an optional key is
sent only as an authentication header. Provider-generated TLDR/summary content
is deliberately not requested or mapped into the scientific-evidence contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Any, Protocol
from urllib.parse import quote, urlencode

from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.utils import normalize_doi

SEMANTIC_SCHOLAR_GRAPH_URL = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_SEARCH_URL = f"{SEMANTIC_SCHOLAR_GRAPH_URL}/paper/search"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_USER_AGENT = "knowledge-engine-core/0.2 federated-discovery"
_FIELDS = "title,authors,year,venue,abstract,externalIds,url,openAccessPdf,citationCount"


class ResponseTooLargeError(OSError):
    """Raised when a provider response exceeds the configured byte limit."""


@dataclass(frozen=True)
class TransportResponse:
    """Bounded HTTP response returned by an injected Semantic Scholar transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True)
class _RequestFailure:
    outcome: ProviderOutcome
    reason: str


class SemanticScholarTransport(Protocol):
    """Minimal transport contract required by the Semantic Scholar adapter."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


class SemanticScholarProvider:
    """Provider-neutral Semantic Scholar search, lookup, and citation adapter."""

    def __init__(
        self,
        *,
        transport: SemanticScholarTransport,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        api_key: str | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Semantic Scholar timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("Semantic Scholar response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("Semantic Scholar User-Agent must not be blank.")
        if api_key is not None and not api_key.strip():
            raise ValueError("Semantic Scholar API key must not be blank when provided.")

        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent
        self._api_key = api_key.strip() if api_key is not None else None

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def authenticated(self) -> bool:
        """Whether optional Semantic Scholar API-key authentication is configured."""

        return self._api_key is not None

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        params = {
            "query": query.normalized_text,
            "limit": str(query.limit_per_provider),
            "fields": _FIELDS,
        }
        year_filter = _year_filter(query)
        if year_filter is not None:
            params["year"] = year_filter
        return self._fetch_list(
            query=query,
            url=f"{SEMANTIC_SCHOLAR_SEARCH_URL}?{urlencode(params)}",
        )

    def lookup(self, identifier: str) -> FederatedSearchResult:
        """Look up one work by Semantic Scholar paper ID or DOI."""

        normalized = identifier.strip()
        if not normalized:
            raise ValueError("Semantic Scholar lookup identifier must not be blank.")

        paper_id = _lookup_paper_id(normalized)
        query = DiscoveryQuery(text=f"semantic scholar lookup {normalized}", limit_per_provider=1)
        url = (
            f"{SEMANTIC_SCHOLAR_GRAPH_URL}/paper/{quote(paper_id, safe=':')}?"
            f"{urlencode({'fields': _FIELDS})}"
        )
        return self._fetch_single(query=query, url=url)

    def references(
        self,
        identifier: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> CitationTraversalResult:
        """Return one bounded page of works referenced by the seed paper."""

        return self.traverse(
            CitationTraversalQuery(
                seed_identifier=identifier,
                direction=CitationDirection.REFERENCES,
                limit=limit,
                offset=offset,
            )
        )

    def citations(
        self,
        identifier: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> CitationTraversalResult:
        """Return one bounded page of works that cite the seed paper."""

        return self.traverse(
            CitationTraversalQuery(
                seed_identifier=identifier,
                direction=CitationDirection.CITATIONS,
                limit=limit,
                offset=offset,
            )
        )

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        """Execute one replayable citation/reference page request."""

        paper_id = _lookup_paper_id(query.normalized_seed_identifier)
        params = {
            "offset": str(query.offset),
            "limit": str(query.limit),
            "fields": _FIELDS,
        }
        url = (
            f"{SEMANTIC_SCHOLAR_GRAPH_URL}/paper/{quote(paper_id, safe=':')}/"
            f"{query.direction.value}?{urlencode(params)}"
        )
        return self._fetch_traversal_page(query=query, url=url)

    def _fetch_single(self, *, query: DiscoveryQuery, url: str) -> FederatedSearchResult:
        response_or_result = self._request(query=query, url=url)
        if isinstance(response_or_result, FederatedSearchResult):
            return response_or_result

        payload = _decode_mapping(response_or_result.body)
        if payload is None:
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        candidate = _parse_paper(payload, retrieved_at=self._clock())
        if candidate is None:
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        return _success_result(query, (candidate,))

    def _fetch_list(self, *, query: DiscoveryQuery, url: str) -> FederatedSearchResult:
        response_or_result = self._request(query=query, url=url)
        if isinstance(response_or_result, FederatedSearchResult):
            return response_or_result

        payload = _decode_mapping(response_or_result.body)
        if payload is None:
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        raw_data = payload.get("data")
        if not isinstance(raw_data, list):
            return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
        if len(raw_data) > query.limit_per_provider:
            return _failure_result(query, ProviderOutcome.FAILED, "oversized_result_page")

        retrieved_at = self._clock()
        candidates: list[FederatedCandidate] = []
        for item in raw_data:
            if not isinstance(item, Mapping):
                return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
            candidate = _parse_paper(item, retrieved_at=retrieved_at)
            if candidate is None:
                return _failure_result(query, ProviderOutcome.FAILED, "malformed_response")
            candidates.append(candidate)

        if not candidates:
            return _empty_result(query)
        return _success_result(query, tuple(candidates))

    def _fetch_traversal_page(
        self,
        *,
        query: CitationTraversalQuery,
        url: str,
    ) -> CitationTraversalResult:
        response_or_failure = self._raw_request(url=url)
        if isinstance(response_or_failure, _RequestFailure):
            if response_or_failure.reason == "not_found":
                return _traversal_failure_result(
                    query,
                    ProviderOutcome.FAILED,
                    "seed_not_found",
                )
            return _traversal_failure_result(
                query,
                response_or_failure.outcome,
                response_or_failure.reason,
            )

        payload = _decode_mapping(response_or_failure.body)
        if payload is None:
            return _traversal_failure_result(
                query,
                ProviderOutcome.FAILED,
                "malformed_response",
            )
        raw_data = payload.get("data")
        if not isinstance(raw_data, list):
            return _traversal_failure_result(
                query,
                ProviderOutcome.FAILED,
                "malformed_response",
            )
        if len(raw_data) > query.limit:
            return _traversal_failure_result(
                query,
                ProviderOutcome.FAILED,
                "oversized_result_page",
            )

        next_offset = payload.get("next")
        if next_offset is not None and (not isinstance(next_offset, int) or next_offset < 0):
            return _traversal_failure_result(
                query,
                ProviderOutcome.FAILED,
                "malformed_response",
            )

        retrieved_at = self._clock()
        retrieved_at_text = retrieved_at.astimezone(UTC).isoformat()
        paper_key = (
            "citedPaper" if query.direction is CitationDirection.REFERENCES else "citingPaper"
        )
        candidates: list[FederatedCandidate] = []
        edges: list[CitationEdge] = []
        for item in raw_data:
            if not isinstance(item, Mapping):
                return _traversal_failure_result(
                    query,
                    ProviderOutcome.FAILED,
                    "malformed_response",
                )
            raw_paper = item.get(paper_key)
            if not isinstance(raw_paper, Mapping):
                return _traversal_failure_result(
                    query,
                    ProviderOutcome.FAILED,
                    "malformed_response",
                )
            candidate = _parse_paper(raw_paper, retrieved_at=retrieved_at)
            if candidate is None:
                return _traversal_failure_result(
                    query,
                    ProviderOutcome.FAILED,
                    "malformed_response",
                )
            related_provider_id = candidate.observations[0].provider_id
            candidates.append(candidate)
            edges.append(
                CitationEdge(
                    provider="semantic_scholar",
                    seed_identifier=query.normalized_seed_identifier,
                    related_provider_id=related_provider_id,
                    direction=query.direction,
                    retrieved_at=retrieved_at_text,
                )
            )

        if not candidates:
            return _traversal_empty_result(query, next_offset=next_offset)
        return _traversal_success_result(
            query,
            candidates=tuple(candidates),
            edges=tuple(edges),
            next_offset=next_offset,
        )

    def _request(
        self,
        *,
        query: DiscoveryQuery,
        url: str,
    ) -> TransportResponse | FederatedSearchResult:
        response_or_failure = self._raw_request(url=url)
        if isinstance(response_or_failure, TransportResponse):
            return response_or_failure
        if response_or_failure.reason == "not_found":
            return _empty_result(query)
        return _failure_result(
            query,
            response_or_failure.outcome,
            response_or_failure.reason,
        )

    def _raw_request(self, *, url: str) -> TransportResponse | _RequestFailure:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

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
        if response.status_code == 404:
            return _RequestFailure(ProviderOutcome.EMPTY, "not_found")
        if response.status_code == 429:
            return _RequestFailure(ProviderOutcome.RATE_LIMITED, "rate_limited")
        if response.status_code in {401, 403}:
            return _RequestFailure(ProviderOutcome.FAILED, "authentication_failed")
        if 500 <= response.status_code <= 599:
            return _RequestFailure(ProviderOutcome.UNAVAILABLE, "provider_unavailable")
        if response.status_code < 200 or response.status_code >= 300:
            return _RequestFailure(ProviderOutcome.FAILED, "unsupported_http_status")
        return response


def _decode_mapping(body: bytes) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(body)
    except (JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _parse_paper(
    payload: Mapping[str, Any],
    *,
    retrieved_at: datetime,
) -> FederatedCandidate | None:
    paper_id = _optional_text(payload.get("paperId"))
    title = _optional_text(payload.get("title"))
    if paper_id is None or title is None:
        return None

    authors: list[str] = []
    raw_authors = payload.get("authors")
    if isinstance(raw_authors, list):
        for author in raw_authors:
            if isinstance(author, Mapping):
                name = _optional_text(author.get("name"))
                if name is not None:
                    authors.append(name)

    publication_year = payload.get("year")
    if not isinstance(publication_year, int) or not 1000 <= publication_year <= 9999:
        publication_year = None

    external_ids = payload.get("externalIds")
    if not isinstance(external_ids, Mapping):
        external_ids = {}
    doi = _normalized_optional_doi(external_ids.get("DOI"))
    pmid = _optional_text(external_ids.get("PubMed"))
    arxiv_id = _optional_text(external_ids.get("ArXiv"))

    open_access_pdf = payload.get("openAccessPdf")
    full_text_url: str | None = None
    if isinstance(open_access_pdf, Mapping):
        full_text_url = _optional_text(open_access_pdf.get("url"))

    citation_count = payload.get("citationCount")
    if not isinstance(citation_count, int) or citation_count < 0:
        citation_count = None

    observation = ProviderObservation(
        provider="semantic_scholar",
        provider_id=paper_id,
        title=title,
        authors=tuple(authors),
        publication_year=publication_year,
        venue=_optional_text(payload.get("venue")),
        abstract=_optional_text(payload.get("abstract")),
        doi=doi,
        pmid=pmid,
        arxiv_id=arxiv_id,
        semantic_scholar_id=paper_id,
        landing_url=_optional_text(payload.get("url")),
        full_text_url=full_text_url,
        citation_count=citation_count,
        open_access=True if full_text_url is not None else None,
        open_access_source="semantic_scholar" if full_text_url is not None else None,
        retrieved_at=retrieved_at.astimezone(UTC).isoformat(),
    )
    return FederatedCandidate(
        canonical_id=f"semantic_scholar:{paper_id}",
        title=title,
        observations=(observation,),
        doi=doi,
        publication_year=publication_year,
    )


def _lookup_paper_id(identifier: str) -> str:
    doi = normalize_doi(identifier)
    if doi.startswith("10.") and "/" in doi:
        return f"DOI:{doi}"
    return identifier


def _year_filter(query: DiscoveryQuery) -> str | None:
    if query.year_from is not None and query.year_to is not None:
        return f"{query.year_from}-{query.year_to}"
    if query.year_from is not None:
        return f"{query.year_from}-"
    if query.year_to is not None:
        return f"-{query.year_to}"
    return None


def _normalized_optional_doi(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = normalize_doi(text)
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
                provider="semantic_scholar",
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
                provider="semantic_scholar",
                outcome=ProviderOutcome.EMPTY,
                attempted=True,
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
                provider="semantic_scholar",
                outcome=outcome,
                attempted=True,
                reason=reason,
            ),
        ),
    )


def _traversal_success_result(
    query: CitationTraversalQuery,
    *,
    candidates: tuple[FederatedCandidate, ...],
    edges: tuple[CitationEdge, ...],
    next_offset: int | None,
) -> CitationTraversalResult:
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="semantic_scholar",
            outcome=ProviderOutcome.SUCCESS,
            attempted=True,
            result_count=len(candidates),
        ),
        candidates=candidates,
        edges=edges,
        next_offset=next_offset,
    )


def _traversal_empty_result(
    query: CitationTraversalQuery,
    *,
    next_offset: int | None,
) -> CitationTraversalResult:
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="semantic_scholar",
            outcome=ProviderOutcome.EMPTY,
            attempted=True,
        ),
        next_offset=next_offset,
    )


def _traversal_failure_result(
    query: CitationTraversalQuery,
    outcome: ProviderOutcome,
    reason: str,
) -> CitationTraversalResult:
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="semantic_scholar",
            outcome=outcome,
            attempted=True,
            reason=reason,
        ),
    )
