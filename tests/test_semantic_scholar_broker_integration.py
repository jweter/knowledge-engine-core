from __future__ import annotations

import json
from collections.abc import Mapping
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
from knowledge_engine.semantic_scholar_provider import (
    SemanticScholarProvider,
    TransportResponse,
)


@dataclass(frozen=True)
class SemanticTransport:
    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        payload = {
            "data": [
                {
                    "paperId": "s2-1",
                    "title": "Semantic Scholar title",
                    "externalIds": {"DOI": "10.1000/shared"},
                }
            ]
        }
        return TransportResponse(200, json.dumps(payload).encode(), {})


@dataclass(frozen=True)
class ExistingProvider:
    name: str = "crossref"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        observation = ProviderObservation(
            provider="crossref",
            provider_id="10.1000/shared",
            title="Crossref title",
            doi="https://doi.org/10.1000/shared",
        )
        candidate = FederatedCandidate(
            canonical_id="crossref:10.1000/shared",
            title=observation.title,
            observations=(observation,),
            doi="10.1000/shared",
        )
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider="crossref",
                    outcome=ProviderOutcome.SUCCESS,
                    attempted=True,
                    result_count=1,
                ),
            ),
            candidates=(candidate,),
        )


def test_semantic_scholar_composes_with_exact_doi_deduplication() -> None:
    broker = FederatedDiscoveryBroker(
        (ExistingProvider(), SemanticScholarProvider(transport=SemanticTransport()))
    )

    result = broker.search(DiscoveryQuery(text="shared work"))

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.canonical_id == "doi:10.1000/shared"
    assert candidate.providers == ("crossref", "semantic_scholar")
    assert tuple(observation.title for observation in candidate.observations) == (
        "Crossref title",
        "Semantic Scholar title",
    )
    assert tuple(status.result_count for status in result.provider_statuses) == (1, 1)
