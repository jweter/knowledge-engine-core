"""Adapt the mature PubMed/PMC discovery service to the FRD provider contract."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.pubmed_discovery import DiscoveryResult, NcbiDiscoveryError, PubmedCandidate

PUBMED_MAX_RESULTS = 100


class PubmedDiscoveryService(Protocol):
    """Structural subset of the existing PubMed discovery service used by FRD."""

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        """Return one bounded PubMed discovery page."""


class PubmedFederatedAdapter:
    """Expose existing PubMed discovery through the provider-neutral FRD contract."""

    def __init__(
        self,
        service: PubmedDiscoveryService,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return "pubmed"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        if query.limit_per_provider > PUBMED_MAX_RESULTS:
            return _failure_result(query, ProviderOutcome.FAILED, "unsupported_limit")

        provider_query = _pubmed_query(query)
        try:
            result = self._service.discover(
                provider_query,
                limit=query.limit_per_provider,
                retstart=0,
            )
        except NcbiDiscoveryError as exc:
            outcome, reason = _classify_ncbi_failure(str(exc))
            return _failure_result(query, outcome, reason)

        if (
            result.query != provider_query
            or result.retstart != 0
            or result.limit != query.limit_per_provider
            or len(result.candidates) > query.limit_per_provider
        ):
            return _failure_result(query, ProviderOutcome.FAILED, "provider_result_mismatch")

        retrieved_at = self._clock().astimezone(UTC).isoformat()
        try:
            candidates = tuple(
                _to_federated_candidate(candidate, retrieved_at=retrieved_at)
                for candidate in result.candidates
            )
        except ValueError:
            return _failure_result(query, ProviderOutcome.FAILED, "candidate_contract_mismatch")

        if not candidates:
            return FederatedSearchResult(
                query=query,
                provider_statuses=(
                    ProviderStatus(
                        provider="pubmed",
                        outcome=ProviderOutcome.EMPTY,
                        attempted=True,
                    ),
                ),
            )

        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider="pubmed",
                    outcome=ProviderOutcome.SUCCESS,
                    attempted=True,
                    result_count=len(candidates),
                ),
            ),
            candidates=candidates,
        )


def _pubmed_query(query: DiscoveryQuery) -> str:
    text = query.normalized_text
    if query.year_from is None and query.year_to is None:
        return text

    year_from = query.year_from if query.year_from is not None else 1000
    year_to = query.year_to if query.year_to is not None else 9999
    return f"({text}) AND {year_from:04d}:{year_to:04d}[dp]"


def _to_federated_candidate(
    candidate: PubmedCandidate,
    *,
    retrieved_at: str,
) -> FederatedCandidate:
    observation = ProviderObservation(
        provider="pubmed",
        provider_id=candidate.pmid,
        title=candidate.title,
        authors=candidate.authors,
        publication_year=candidate.publication_year,
        venue=candidate.venue,
        abstract=candidate.abstract,
        doi=candidate.doi,
        pmid=candidate.pmid,
        pmcid=candidate.pmcid,
        full_text_url=candidate.pdf_url,
        xml_url=candidate.xml_url,
        license=candidate.license,
        metadata_source=candidate.metadata_source,
        pmcid_source=candidate.pmcid_source,
        open_access_source=candidate.oa_source,
        open_access=candidate.open_access,
        retrieved_at=retrieved_at,
    )
    return FederatedCandidate(
        canonical_id=f"pubmed:{candidate.pmid}",
        title=observation.title,
        observations=(observation,),
        doi=candidate.doi,
        publication_year=candidate.publication_year,
    )


def _classify_ncbi_failure(message: str) -> tuple[ProviderOutcome, str]:
    if "(429)" in message:
        return ProviderOutcome.RATE_LIMITED, "rate_limited"
    if any(f"({status})" in message for status in (500, 502, 503, 504)):
        return ProviderOutcome.UNAVAILABLE, "provider_unavailable"
    if "request failed" in message:
        return ProviderOutcome.UNAVAILABLE, "transport_error"
    return ProviderOutcome.FAILED, "provider_error"


def _failure_result(
    query: DiscoveryQuery,
    outcome: ProviderOutcome,
    reason: str,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=outcome,
                attempted=True,
                reason=reason,
            ),
        ),
    )
