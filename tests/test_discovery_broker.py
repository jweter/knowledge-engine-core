from __future__ import annotations

from dataclasses import dataclass

from knowledge_engine.discovery_broker import FederatedDiscoveryBroker
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
    SearchCompleteness,
)


@dataclass(frozen=True)
class FakeProvider:
    name: str
    result: FederatedSearchResult | None = None
    error: Exception | None = None

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _candidate(provider: str, provider_id: str, title: str) -> FederatedCandidate:
    observation = ProviderObservation(
        provider=provider,
        provider_id=provider_id,
        title=title,
    )
    return FederatedCandidate(
        canonical_id=f"{provider}:{provider_id}",
        title=title,
        observations=(observation,),
    )


def _result(
    query: DiscoveryQuery,
    provider: str,
    outcome: ProviderOutcome,
    candidates: tuple[FederatedCandidate, ...] = (),
    *,
    attempted: bool = True,
    reason: str | None = None,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider=provider,
                outcome=outcome,
                attempted=attempted,
                result_count=len(candidates),
                reason=reason,
            ),
        ),
        candidates=candidates,
    )


def test_broker_aggregates_successful_providers_without_deduplicating() -> None:
    query = DiscoveryQuery(text="mitochondrial aging")
    openalex = _candidate("openalex", "W1", "Shared title")
    crossref = _candidate("crossref", "10.1/example", "Shared title")
    broker = FederatedDiscoveryBroker(
        (
            FakeProvider(
                "openalex", _result(query, "openalex", ProviderOutcome.SUCCESS, (openalex,))
            ),
            FakeProvider(
                "crossref", _result(query, "crossref", ProviderOutcome.SUCCESS, (crossref,))
            ),
        )
    )

    result = broker.search(query)

    assert result.completeness is SearchCompleteness.COMPLETE
    assert result.candidates == (openalex, crossref)
    assert tuple(status.provider for status in result.provider_statuses) == ("openalex", "crossref")


def test_broker_marks_run_partial_when_one_provider_fails() -> None:
    query = DiscoveryQuery(text="protein folding")
    candidate = _candidate("crossref", "10.2/example", "Protein folding")
    broker = FederatedDiscoveryBroker(
        (
            FakeProvider("openalex", error=TimeoutError()),
            FakeProvider(
                "crossref", _result(query, "crossref", ProviderOutcome.SUCCESS, (candidate,))
            ),
        )
    )

    result = broker.search(query)

    assert result.completeness is SearchCompleteness.PARTIAL
    assert result.candidates == (candidate,)
    assert result.failed_providers == ("openalex",)
    assert result.provider_statuses[0].reason == "provider_exception"


def test_disabled_provider_does_not_make_successful_run_partial() -> None:
    query = DiscoveryQuery(text="sleep apnea")
    candidate = _candidate("crossref", "10.3/example", "Sleep apnea")
    broker = FederatedDiscoveryBroker(
        (
            FakeProvider(
                "openalex",
                _result(
                    query,
                    "openalex",
                    ProviderOutcome.DISABLED,
                    attempted=False,
                    reason="missing_api_key",
                ),
            ),
            FakeProvider(
                "crossref", _result(query, "crossref", ProviderOutcome.SUCCESS, (candidate,))
            ),
        )
    )

    result = broker.search(query)

    assert result.completeness is SearchCompleteness.COMPLETE
    assert result.candidates == (candidate,)
    assert result.provider_statuses[0].outcome is ProviderOutcome.DISABLED


def test_broker_rejects_duplicate_provider_names() -> None:
    query = DiscoveryQuery(text="test")
    empty = _result(query, "openalex", ProviderOutcome.EMPTY)

    try:
        FederatedDiscoveryBroker((FakeProvider("OpenAlex", empty), FakeProvider("openalex", empty)))
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate provider names should fail")


def test_broker_records_contract_mismatch_without_accepting_candidates() -> None:
    query = DiscoveryQuery(text="current query")
    wrong_query = DiscoveryQuery(text="wrong query")
    candidate = _candidate("openalex", "W2", "Wrong query result")
    broker = FederatedDiscoveryBroker(
        (
            FakeProvider(
                "openalex",
                _result(wrong_query, "openalex", ProviderOutcome.SUCCESS, (candidate,)),
            ),
        )
    )

    result = broker.search(query)

    assert result.completeness is SearchCompleteness.FAILED
    assert result.candidates == ()
    assert result.provider_statuses[0].reason == "query_contract_mismatch"
