from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from knowledge_engine.citation_discovery import (
    CitationDirection as LegacyCitationDirection,
)
from knowledge_engine.citation_discovery import CitationEdge as LegacyCitationEdge
from knowledge_engine.citation_discovery import (
    CitationTraversalResult as LegacyCitationTraversalResult,
)
from knowledge_engine.citation_traversal import CitationDirection, CitationTraversalQuery
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.openalex_citation_adapter import OpenAlexCitationAdapter

_OBSERVED_AT = "2026-08-16T04:00:00+00:00"


@dataclass
class FakeCitationSource:
    result: LegacyCitationTraversalResult
    calls: list[tuple[str, str, int]] = field(default_factory=list)

    def references(self, seed_id: str, *, limit: int = 25) -> LegacyCitationTraversalResult:
        self.calls.append(("references", seed_id, limit))
        return self.result

    def cited_by(self, seed_id: str, *, limit: int = 25) -> LegacyCitationTraversalResult:
        self.calls.append(("cited_by", seed_id, limit))
        return self.result


@dataclass
class FakeWorkLookup:
    results: dict[str, FederatedSearchResult]
    calls: list[str] = field(default_factory=list)

    def lookup(self, identifier: str) -> FederatedSearchResult:
        self.calls.append(identifier)
        return self.results[identifier]


def _candidate(provider_id: str, *, title: str | None = None) -> FederatedCandidate:
    resolved_title = title or f"OpenAlex work {provider_id}"
    return FederatedCandidate(
        canonical_id=f"openalex:{provider_id}",
        title=resolved_title,
        observations=(
            ProviderObservation(
                provider="openalex",
                provider_id=provider_id,
                title=resolved_title,
                openalex_id=provider_id,
            ),
        ),
    )


def _lookup_result(
    provider_id: str,
    *,
    outcome: ProviderOutcome = ProviderOutcome.SUCCESS,
    candidate: FederatedCandidate | None = None,
    provider: str = "openalex",
) -> FederatedSearchResult:
    candidates = () if candidate is None and outcome is not ProviderOutcome.SUCCESS else (
        candidate or _candidate(provider_id),
    )
    return FederatedSearchResult(
        query=DiscoveryQuery(text=f"lookup {provider_id}", limit_per_provider=1),
        provider_statuses=(
            ProviderStatus(
                provider=provider,
                outcome=outcome,
                attempted=True,
                result_count=len(candidates),
                reason=None if outcome in {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY} else "failed",
            ),
        ),
        candidates=candidates,
    )


def _legacy_references(
    seed: str,
    targets: tuple[str, ...],
    *,
    limit: int,
    outcome: ProviderOutcome | None = None,
    provider: str = "openalex",
) -> LegacyCitationTraversalResult:
    edges = tuple(
        LegacyCitationEdge(
            provider=provider,
            source_id=seed,
            target_id=target,
            observed_at=_OBSERVED_AT,
        )
        for target in targets
    )
    resolved_outcome = outcome or (ProviderOutcome.SUCCESS if edges else ProviderOutcome.EMPTY)
    return LegacyCitationTraversalResult(
        provider=provider,
        seed_id=seed,
        direction=LegacyCitationDirection.REFERENCES,
        requested_limit=limit,
        provider_status=ProviderStatus(
            provider=provider,
            outcome=resolved_outcome,
            attempted=resolved_outcome not in {ProviderOutcome.DISABLED, ProviderOutcome.SKIPPED},
            result_count=len(edges),
            reason=(
                "missing_api_key"
                if resolved_outcome is ProviderOutcome.DISABLED
                else None
            ),
        ),
        edges=edges,
    )


def _legacy_citations(seed: str, sources: tuple[str, ...], *, limit: int) -> LegacyCitationTraversalResult:
    edges = tuple(
        LegacyCitationEdge(
            provider="openalex",
            source_id=source,
            target_id=seed,
            observed_at=_OBSERVED_AT,
        )
        for source in sources
    )
    return LegacyCitationTraversalResult(
        provider="openalex",
        seed_id=seed,
        direction=LegacyCitationDirection.CITED_BY,
        requested_limit=limit,
        provider_status=ProviderStatus(
            provider="openalex",
            outcome=ProviderOutcome.SUCCESS if edges else ProviderOutcome.EMPTY,
            attempted=True,
            result_count=len(edges),
        ),
        edges=edges,
    )


def test_references_hydrate_ordinary_candidates_and_preserve_edge_provenance() -> None:
    source = FakeCitationSource(_legacy_references("W1", ("W2", "W3"), limit=2))
    lookup = FakeWorkLookup(
        {
            "W2": _lookup_result("W2"),
            "W3": _lookup_result("W3"),
        }
    )
    adapter = OpenAlexCitationAdapter(source, lookup)

    result = adapter.references(" W1 ", limit=2)

    assert result.provider_status.outcome is ProviderOutcome.SUCCESS
    assert result.provider_status.result_count == 2
    assert tuple(candidate.observations[0].provider_id for candidate in result.candidates) == (
        "W2",
        "W3",
    )
    assert tuple(edge.related_provider_id for edge in result.edges) == ("W2", "W3")
    assert all(edge.direction is CitationDirection.REFERENCES for edge in result.edges)
    assert all(edge.retrieved_at == _OBSERVED_AT for edge in result.edges)
    assert source.calls == [("references", "W1", 2)]
    assert lookup.calls == ["W2", "W3"]


def test_citations_map_legacy_cited_by_direction_without_losing_identity() -> None:
    source = FakeCitationSource(_legacy_citations("W1", ("W4",), limit=1))
    lookup = FakeWorkLookup({"W4": _lookup_result("W4")})
    adapter = OpenAlexCitationAdapter(source, lookup)

    result = adapter.citations("W1", limit=1)

    assert result.query.direction is CitationDirection.CITATIONS
    assert result.edges[0].related_provider_id == "W4"
    assert result.edges[0].direction is CitationDirection.CITATIONS
    assert source.calls == [("cited_by", "W1", 1)]


def test_disabled_legacy_provider_is_propagated_without_hydration() -> None:
    source = FakeCitationSource(
        _legacy_references(
            "W1",
            (),
            limit=2,
            outcome=ProviderOutcome.DISABLED,
        )
    )
    lookup = FakeWorkLookup({})

    result = OpenAlexCitationAdapter(source, lookup).references("W1", limit=2)

    assert result.provider_status.outcome is ProviderOutcome.DISABLED
    assert result.provider_status.attempted is False
    assert result.provider_status.reason == "missing_api_key"
    assert result.candidates == ()
    assert lookup.calls == []


def test_nonzero_offset_fails_closed_instead_of_faking_pagination() -> None:
    source = FakeCitationSource(_legacy_references("W1", (), limit=2))
    lookup = FakeWorkLookup({})
    query = CitationTraversalQuery(
        seed_identifier="W1",
        direction=CitationDirection.REFERENCES,
        limit=2,
        offset=2,
    )

    result = OpenAlexCitationAdapter(source, lookup).traverse(query)

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "unsupported_offset"
    assert source.calls == []


def test_hydration_failure_marks_the_traversal_failed() -> None:
    source = FakeCitationSource(_legacy_references("W1", ("W2",), limit=1))
    lookup = FakeWorkLookup(
        {
            "W2": _lookup_result(
                "W2",
                outcome=ProviderOutcome.UNAVAILABLE,
                candidate=None,
            )
        }
    )

    result = OpenAlexCitationAdapter(source, lookup).references("W1", limit=1)

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "candidate_hydration_failed"
    assert result.candidates == ()
    assert result.edges == ()


def test_hydration_provider_identity_mismatch_fails_closed() -> None:
    source = FakeCitationSource(_legacy_references("W1", ("W2",), limit=1))
    lookup = FakeWorkLookup(
        {
            "W2": _lookup_result(
                "W2",
                provider="semantic_scholar",
            )
        }
    )

    result = OpenAlexCitationAdapter(source, lookup).references("W1", limit=1)

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "candidate_hydration_failed"


def test_wrong_legacy_provider_identity_is_rejected() -> None:
    source = FakeCitationSource(
        _legacy_references(
            "W1",
            (),
            limit=1,
            provider="not_openalex",
        )
    )
    lookup = FakeWorkLookup({})

    with pytest.raises(ValueError, match="wrong provider identity"):
        OpenAlexCitationAdapter(source, lookup).references("W1", limit=1)


def test_changed_legacy_limit_is_rejected() -> None:
    source = FakeCitationSource(_legacy_references("W1", (), limit=2))
    lookup = FakeWorkLookup({})

    with pytest.raises(ValueError, match="changed the requested traversal limit"):
        OpenAlexCitationAdapter(source, lookup).references("W1", limit=1)
