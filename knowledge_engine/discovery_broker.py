"""Orchestrate provider-neutral scholarly discovery without hiding degraded coverage."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderOutcome,
    ProviderStatus,
)


class DiscoveryProvider(Protocol):
    """Minimal provider capability required by the federated discovery broker."""

    @property
    def name(self) -> str:
        """Return the provider's stable identifier."""

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        """Search one provider and return its FRD result contract."""


class FederatedDiscoveryBroker:
    """Fan out one query across providers and aggregate explicit provider state."""

    def __init__(self, providers: tuple[DiscoveryProvider, ...]) -> None:
        names = tuple(_normalize_provider_name(provider.name) for provider in providers)
        if len(names) != len(set(names)):
            raise ValueError("Federated discovery providers must have unique names.")
        self._providers = providers

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(_normalize_provider_name(provider.name) for provider in self._providers)

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        statuses: list[ProviderStatus] = []
        candidates: list[FederatedCandidate] = []

        for provider in self._providers:
            name = _normalize_provider_name(provider.name)
            try:
                result = provider.search(query)
            except Exception:  # noqa: BLE001 - provider boundary must not collapse the run
                statuses.append(
                    ProviderStatus(
                        provider=name,
                        outcome=ProviderOutcome.FAILED,
                        attempted=True,
                        reason="provider_exception",
                    )
                )
                continue

            if result.query != query:
                statuses.append(
                    ProviderStatus(
                        provider=name,
                        outcome=ProviderOutcome.FAILED,
                        attempted=True,
                        reason="query_contract_mismatch",
                    )
                )
                continue

            if len(result.provider_statuses) != 1:
                statuses.append(
                    ProviderStatus(
                        provider=name,
                        outcome=ProviderOutcome.FAILED,
                        attempted=True,
                        reason="provider_status_contract_mismatch",
                    )
                )
                continue

            status = result.provider_statuses[0]
            if _normalize_provider_name(status.provider) != name:
                statuses.append(
                    ProviderStatus(
                        provider=name,
                        outcome=ProviderOutcome.FAILED,
                        attempted=True,
                        reason="provider_identity_mismatch",
                    )
                )
                continue

            normalized_status = replace(status, provider=name)
            statuses.append(normalized_status)
            candidates.extend(result.candidates)

        return FederatedSearchResult(
            query=query,
            provider_statuses=tuple(statuses),
            candidates=tuple(candidates),
        )


def _normalize_provider_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not normalized:
        raise ValueError("Discovery provider name must not be blank.")
    return normalized
