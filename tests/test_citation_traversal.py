from __future__ import annotations

import pytest

from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    FederatedCandidate,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)


def _candidate() -> FederatedCandidate:
    observation = ProviderObservation(
        provider="semantic_scholar",
        provider_id="paper-2",
        title="Related work",
    )
    return FederatedCandidate(
        canonical_id="semantic_scholar:paper-2",
        title="Related work",
        observations=(observation,),
    )


def test_traversal_query_is_bounded_and_replayable() -> None:
    query = CitationTraversalQuery(
        seed_identifier="  DOI:10.1000/example  ",
        direction=CitationDirection.REFERENCES,
        limit=250,
        offset=500,
    )

    assert query.normalized_seed_identifier == "DOI:10.1000/example"
    assert query.limit == 250
    assert query.offset == 500


@pytest.mark.parametrize("limit", [0, 1001])
def test_traversal_query_rejects_out_of_bounds_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 1000"):
        CitationTraversalQuery(
            seed_identifier="seed",
            direction=CitationDirection.CITATIONS,
            limit=limit,
        )


def test_traversal_result_requires_one_edge_per_candidate() -> None:
    query = CitationTraversalQuery(
        seed_identifier="seed",
        direction=CitationDirection.CITATIONS,
    )
    status = ProviderStatus(
        provider="semantic_scholar",
        outcome=ProviderOutcome.SUCCESS,
        attempted=True,
        result_count=1,
    )

    with pytest.raises(ValueError, match="one provenance edge per candidate"):
        CitationTraversalResult(
            query=query,
            provider_status=status,
            candidates=(_candidate(),),
        )


def test_traversal_result_rejects_edge_direction_mismatch() -> None:
    query = CitationTraversalQuery(
        seed_identifier="seed",
        direction=CitationDirection.CITATIONS,
    )
    candidate = _candidate()
    status = ProviderStatus(
        provider="semantic_scholar",
        outcome=ProviderOutcome.SUCCESS,
        attempted=True,
        result_count=1,
    )
    edge = CitationEdge(
        provider="semantic_scholar",
        seed_identifier="seed",
        related_provider_id="paper-2",
        direction=CitationDirection.REFERENCES,
        retrieved_at="2026-08-16T03:00:00+00:00",
    )

    with pytest.raises(ValueError, match="direction must match"):
        CitationTraversalResult(
            query=query,
            provider_status=status,
            candidates=(candidate,),
            edges=(edge,),
        )
