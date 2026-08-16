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
)


@dataclass(frozen=True)
class FakeProvider:
    name: str
    candidate: FederatedCandidate

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider=self.name,
                    outcome=ProviderOutcome.SUCCESS,
                    attempted=True,
                    result_count=1,
                ),
            ),
            candidates=(self.candidate,),
        )


def _candidate(provider: str, provider_id: str, doi: str) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"{provider}:{provider_id}",
        title=f"{provider} title",
        doi=doi,
        observations=(
            ProviderObservation(
                provider=provider,
                provider_id=provider_id,
                title=f"{provider} title",
                doi=doi,
            ),
        ),
    )


def test_broker_reports_provider_counts_before_dedup_and_one_canonical_candidate() -> None:
    query = DiscoveryQuery(text="same work")
    broker = FederatedDiscoveryBroker(
        (
            FakeProvider("pubmed", _candidate("pubmed", "123", "10.1000/example")),
            FakeProvider(
                "crossref",
                _candidate("crossref", "10.1000/example", "https://doi.org/10.1000/EXAMPLE"),
            ),
        )
    )

    result = broker.search(query)

    assert tuple(status.result_count for status in result.provider_statuses) == (1, 1)
    assert len(result.candidates) == 1
    assert result.candidates[0].canonical_id == "doi:10.1000/example"
    assert result.candidates[0].providers == ("pubmed", "crossref")
