from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedSearchResult,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_discovery_service import FederatedDiscoveryService
from knowledge_engine.federated_search_ledger import FederatedSearchLedger


@dataclass(frozen=True)
class FakeProvider:
    name: str

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider=self.name,
                    outcome=ProviderOutcome.EMPTY,
                    attempted=True,
                ),
            ),
        )


def test_registry_uses_stable_core_provider_order_then_sorted_extensions() -> None:
    registry = DiscoveryProviderRegistry(
        (
            FakeProvider("zeta"),
            FakeProvider("Semantic Scholar"),
            FakeProvider("OpenAlex"),
            FakeProvider("pubmed"),
            FakeProvider("arxiv"),
            FakeProvider("alpha"),
            FakeProvider("crossref"),
        )
    )

    assert registry.provider_names == (
        "pubmed",
        "crossref",
        "openalex",
        "arxiv",
        "semantic_scholar",
        "alpha",
        "zeta",
    )


def test_registry_normalizes_names_and_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="Duplicate discovery provider: pubmed"):
        DiscoveryProviderRegistry((FakeProvider("PubMed"), FakeProvider(" pubmed ")))


def test_registry_rejects_blank_provider_names() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        DiscoveryProviderRegistry((FakeProvider("   "),))


def test_registry_get_resolves_normalized_provider_name() -> None:
    provider = FakeProvider("OpenAlex")
    registry = DiscoveryProviderRegistry((provider,))

    assert registry.get(" openalex ") is provider


def test_registry_get_does_not_hide_unconfigured_provider() -> None:
    registry = DiscoveryProviderRegistry((FakeProvider("pubmed"),))

    with pytest.raises(KeyError, match="not configured: crossref"):
        registry.get("crossref")


def test_registry_explicit_subset_preserves_requested_order() -> None:
    registry = DiscoveryProviderRegistry(
        (FakeProvider("pubmed"), FakeProvider("crossref"), FakeProvider("openalex"))
    )

    selected = registry.select(("openalex", "pubmed"))

    assert tuple(provider.name for provider in selected) == ("openalex", "pubmed")


def test_registry_rejects_duplicate_requested_provider_names() -> None:
    registry = DiscoveryProviderRegistry((FakeProvider("pubmed"),))

    with pytest.raises(ValueError, match="must be unique"):
        registry.select(("pubmed", "PubMed"))


def test_registry_rejects_unknown_requested_provider() -> None:
    registry = DiscoveryProviderRegistry((FakeProvider("pubmed"),))

    with pytest.raises(KeyError, match="not configured: openalex"):
        registry.select(("pubmed", "openalex"))


def test_registry_builds_broker_with_explicit_provider_order() -> None:
    registry = DiscoveryProviderRegistry(
        (FakeProvider("pubmed"), FakeProvider("crossref"), FakeProvider("openalex"))
    )
    broker = registry.build_broker(("openalex", "pubmed"))

    assert broker.provider_names == ("openalex", "pubmed")

    result = broker.search(DiscoveryQuery(text="example"))
    assert tuple(status.provider for status in result.provider_statuses) == ("openalex", "pubmed")
    assert result.completeness.value == "complete"


def test_registry_builds_recorded_service_from_selected_providers(tmp_path: Path) -> None:
    registry = DiscoveryProviderRegistry(
        (FakeProvider("pubmed"), FakeProvider("crossref"), FakeProvider("openalex"))
    )
    service = registry.build_recorded_service(
        FederatedSearchLedger(tmp_path),
        ("crossref", "pubmed"),
    )

    assert isinstance(service, FederatedDiscoveryService)
    execution = service.search(DiscoveryQuery(text="recorded registry search"))
    assert execution.coverage.providers_requested == ("crossref", "pubmed")
