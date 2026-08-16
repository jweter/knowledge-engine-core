from __future__ import annotations

from collections import deque

import pytest

from knowledge_engine.citation_snowball import (
    CitationSnowballDiscovery,
    CitationSnowballPlan,
)
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
    SearchCompleteness,
)


class FakeCitationProvider:
    def __init__(self, results: list[CitationTraversalResult]) -> None:
        self._results = deque(results)
        self.queries: list[CitationTraversalQuery] = []

    @property
    def name(self) -> str:
        return "openalex"

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        self.queries.append(query)
        result = self._results.popleft()
        assert result.query == query
        return result


def _candidate(provider_id: str) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"openalex:{provider_id}",
        title=f"Paper {provider_id}",
        observations=(
            ProviderObservation(
                provider="openalex",
                provider_id=provider_id,
                title=f"Paper {provider_id}",
                openalex_id=provider_id,
            ),
        ),
    )


def _result(
    seed: str,
    direction: CitationDirection,
    discovered: tuple[str, ...],
    *,
    outcome: ProviderOutcome = ProviderOutcome.SUCCESS,
    reason: str | None = None,
) -> CitationTraversalResult:
    query = CitationTraversalQuery(seed_identifier=seed, direction=direction, limit=2)
    candidates = tuple(_candidate(provider_id) for provider_id in discovered)
    edges = tuple(
        CitationEdge(
            provider="openalex",
            seed_identifier=seed,
            related_provider_id=provider_id,
            direction=direction,
            retrieved_at="2026-08-16T12:00:00+00:00",
        )
        for provider_id in discovered
    )
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="openalex",
            outcome=outcome,
            attempted=True,
            result_count=len(discovered),
            reason=reason,
        ),
        candidates=candidates,
        edges=edges,
    )


def test_snowball_runs_explicit_directions_for_seed() -> None:
    provider = FakeCitationProvider(
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result("W1", CitationDirection.CITATIONS, ("W3",)),
        ]
    )
    plan = CitationSnowballPlan(
        seed_identifiers=("W1",),
        max_depth=1,
        limit_per_traversal=2,
        max_candidates=10,
    )

    result = CitationSnowballDiscovery(provider).run(plan)

    assert [candidate.canonical_id for candidate in result.candidates] == [
        "openalex:W2",
        "openalex:W3",
    ]
    assert [edge.related_provider_id for edge in result.edges] == ["W2", "W3"]
    assert result.completeness is SearchCompleteness.COMPLETE
    assert result.truncated is False


def test_snowball_expands_breadth_first_and_does_not_revisit_seed_ids() -> None:
    provider = FakeCitationProvider(
        [
            _result("W1", CitationDirection.REFERENCES, ("W2", "W3")),
            _result("W2", CitationDirection.REFERENCES, ("W1", "W4")),
            _result("W3", CitationDirection.REFERENCES, ("W4",)),
        ]
    )
    plan = CitationSnowballPlan(
        seed_identifiers=("W1",),
        directions=(CitationDirection.REFERENCES,),
        max_depth=2,
        limit_per_traversal=2,
        max_candidates=10,
    )

    result = CitationSnowballDiscovery(provider).run(plan)

    assert [query.normalized_seed_identifier for query in provider.queries] == [
        "W1",
        "W2",
        "W3",
    ]
    assert [candidate.canonical_id for candidate in result.candidates] == [
        "openalex:W2",
        "openalex:W3",
        "openalex:W1",
        "openalex:W4",
    ]
    assert [edge.related_provider_id for edge in result.edges] == [
        "W2",
        "W3",
        "W1",
        "W4",
        "W4",
    ]


def test_snowball_preserves_success_when_another_traversal_fails() -> None:
    provider = FakeCitationProvider(
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result(
                "W1",
                CitationDirection.CITATIONS,
                (),
                outcome=ProviderOutcome.RATE_LIMITED,
                reason="rate_limited",
            ),
        ]
    )
    plan = CitationSnowballPlan(
        seed_identifiers=("W1",),
        max_depth=1,
        limit_per_traversal=2,
    )

    result = CitationSnowballDiscovery(provider).run(plan)

    assert [candidate.canonical_id for candidate in result.candidates] == ["openalex:W2"]
    assert result.completeness is SearchCompleteness.PARTIAL
    assert len(result.failed_traversals) == 1
    assert result.failed_traversals[0].provider_status.reason == "rate_limited"


def test_snowball_stops_at_global_candidate_bound() -> None:
    provider = FakeCitationProvider(
        [
            _result("W1", CitationDirection.REFERENCES, ("W2", "W3")),
        ]
    )
    plan = CitationSnowballPlan(
        seed_identifiers=("W1",),
        directions=(CitationDirection.REFERENCES,),
        max_depth=2,
        limit_per_traversal=2,
        max_candidates=1,
    )

    result = CitationSnowballDiscovery(provider).run(plan)

    assert [candidate.canonical_id for candidate in result.candidates] == ["openalex:W2"]
    assert [edge.related_provider_id for edge in result.edges] == ["W2"]
    assert result.truncated is True
    assert len(provider.queries) == 1


def test_snowball_plan_rejects_duplicate_or_unbounded_inputs() -> None:
    with pytest.raises(ValueError, match="seed identifiers must be unique"):
        CitationSnowballPlan(seed_identifiers=("W1", "W1"))

    with pytest.raises(ValueError, match="max_depth must be between 1 and 3"):
        CitationSnowballPlan(seed_identifiers=("W1",), max_depth=4)
