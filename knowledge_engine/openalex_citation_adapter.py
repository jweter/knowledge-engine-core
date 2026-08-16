"""Adapt existing OpenAlex citation traversal into the shared FRD citation contract.

This adapter preserves the proven OpenAlex transport/citation implementation and
hydrates discovered OpenAlex work IDs through the existing work provider. Public
callers receive ordinary ``FederatedCandidate`` objects plus provider-neutral
citation edge provenance; no OpenAlex-native response object crosses the boundary.
"""

from __future__ import annotations

from typing import Protocol

from knowledge_engine.citation_discovery import (
    CitationDirection as LegacyCitationDirection,
)
from knowledge_engine.citation_discovery import (
    CitationTraversalResult as LegacyCitationTraversalResult,
)
from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    FederatedCandidate,
    FederatedSearchResult,
    ProviderOutcome,
    ProviderStatus,
)


class OpenAlexCitationSource(Protocol):
    """Existing bounded OpenAlex citation capability required by the adapter."""

    def references(self, seed_id: str, *, limit: int = 25) -> LegacyCitationTraversalResult:
        """Return bounded OpenAlex reference edges."""

    def cited_by(self, seed_id: str, *, limit: int = 25) -> LegacyCitationTraversalResult:
        """Return bounded OpenAlex citing-work edges."""


class OpenAlexWorkLookup(Protocol):
    """Existing OpenAlex work hydration capability required by the adapter."""

    def lookup(self, identifier: str) -> FederatedSearchResult:
        """Return one OpenAlex work through the federated candidate contract."""


class OpenAlexCitationAdapter:
    """Expose OpenAlex citation traversal through the shared FRD contract."""

    def __init__(
        self,
        citation_source: OpenAlexCitationSource,
        work_lookup: OpenAlexWorkLookup,
    ) -> None:
        self._citation_source = citation_source
        self._work_lookup = work_lookup

    @property
    def name(self) -> str:
        return "openalex"

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        """Execute one bounded OpenAlex citation traversal and hydrate its works."""

        if query.offset != 0:
            return _failure_result(query, "unsupported_offset")

        legacy = self._legacy_traverse(query)
        _validate_legacy_result(query, legacy)
        if legacy.provider_status.outcome not in {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY}:
            return CitationTraversalResult(
                query=query,
                provider_status=legacy.provider_status,
            )
        if legacy.provider_status.outcome is ProviderOutcome.EMPTY:
            return CitationTraversalResult(
                query=query,
                provider_status=_status(ProviderOutcome.EMPTY),
            )

        candidates: list[FederatedCandidate] = []
        edges: list[CitationEdge] = []
        for discovered_id, legacy_edge in zip(legacy.discovered_ids, legacy.edges, strict=True):
            lookup = self._work_lookup.lookup(discovered_id)
            candidate = _single_openalex_candidate(lookup, expected_provider_id=discovered_id)
            if candidate is None:
                return _failure_result(query, "candidate_hydration_failed")
            candidates.append(candidate)
            edges.append(
                CitationEdge(
                    provider="openalex",
                    seed_identifier=query.normalized_seed_identifier,
                    related_provider_id=discovered_id,
                    direction=query.direction,
                    retrieved_at=legacy_edge.observed_at,
                )
            )

        return CitationTraversalResult(
            query=query,
            provider_status=_status(ProviderOutcome.SUCCESS, result_count=len(candidates)),
            candidates=tuple(candidates),
            edges=tuple(edges),
        )

    def references(self, identifier: str, *, limit: int = 25) -> CitationTraversalResult:
        """Return one bounded page of works referenced by the seed work."""

        return self.traverse(
            CitationTraversalQuery(
                seed_identifier=identifier,
                direction=CitationDirection.REFERENCES,
                limit=limit,
            )
        )

    def citations(self, identifier: str, *, limit: int = 25) -> CitationTraversalResult:
        """Return one bounded page of works citing the seed work."""

        return self.traverse(
            CitationTraversalQuery(
                seed_identifier=identifier,
                direction=CitationDirection.CITATIONS,
                limit=limit,
            )
        )

    def _legacy_traverse(self, query: CitationTraversalQuery) -> LegacyCitationTraversalResult:
        if query.direction is CitationDirection.REFERENCES:
            return self._citation_source.references(
                query.normalized_seed_identifier,
                limit=query.limit,
            )
        return self._citation_source.cited_by(
            query.normalized_seed_identifier,
            limit=query.limit,
        )


def _validate_legacy_result(
    query: CitationTraversalQuery,
    result: LegacyCitationTraversalResult,
) -> None:
    if result.provider.strip().lower().replace(" ", "_") != "openalex":
        raise ValueError("OpenAlex citation source returned the wrong provider identity.")
    if result.provider_status.provider.strip().lower().replace(" ", "_") != "openalex":
        raise ValueError("OpenAlex citation source status returned the wrong provider identity.")
    if result.requested_limit != query.limit:
        raise ValueError("OpenAlex citation source changed the requested traversal limit.")
    expected_direction = (
        LegacyCitationDirection.REFERENCES
        if query.direction is CitationDirection.REFERENCES
        else LegacyCitationDirection.CITED_BY
    )
    if result.direction is not expected_direction:
        raise ValueError("OpenAlex citation source returned the wrong traversal direction.")
    if len(result.edges) > query.limit:
        raise ValueError("OpenAlex citation source exceeded the requested traversal limit.")


def _single_openalex_candidate(
    result: FederatedSearchResult,
    *,
    expected_provider_id: str,
) -> FederatedCandidate | None:
    if len(result.provider_statuses) != 1:
        return None
    status = result.provider_statuses[0]
    if status.provider.strip().lower().replace(" ", "_") != "openalex":
        return None
    if status.outcome is not ProviderOutcome.SUCCESS or status.result_count != 1:
        return None
    if len(result.candidates) != 1:
        return None
    candidate = result.candidates[0]
    observations = [
        observation
        for observation in candidate.observations
        if observation.normalized_provider == "openalex"
    ]
    if len(observations) != 1 or observations[0].provider_id != expected_provider_id:
        return None
    return candidate


def _status(
    outcome: ProviderOutcome,
    *,
    result_count: int = 0,
    reason: str | None = None,
) -> ProviderStatus:
    return ProviderStatus(
        provider="openalex",
        outcome=outcome,
        attempted=True,
        result_count=result_count,
        reason=reason,
    )


def _failure_result(query: CitationTraversalQuery, reason: str) -> CitationTraversalResult:
    return CitationTraversalResult(
        query=query,
        provider_status=_status(ProviderOutcome.FAILED, reason=reason),
    )
