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
            status, provider_candidates = _search_provider(provider, name=name, query=query)
            statuses.append(status)
            candidates.extend(provider_candidates)

        return FederatedSearchResult(
            query=query,
            provider_statuses=tuple(statuses),
            candidates=tuple(candidates),
        )


def _search_provider(
    provider: DiscoveryProvider,
    *,
    name: str,
    query: DiscoveryQuery,
) -> tuple[ProviderStatus, tuple[FederatedCandidate, ...]]:
    """Execute and validate one provider without allowing it to collapse the run."""
    try:
        result = provider.search(query)
        if not isinstance(result, FederatedSearchResult):
            return _failed_status(name, "provider_result_contract_mismatch"), ()
        if result.query != query:
            return _failed_status(name, "query_contract_mismatch"), ()
        if len(result.provider_statuses) != 1:
            return _failed_status(name, "provider_status_contract_mismatch"), ()

        status = result.provider_statuses[0]
        if _normalize_provider_name(status.provider) != name:
            return _failed_status(name, "provider_identity_mismatch"), ()

        normalized_status = replace(status, provider=name)
        return normalized_status, result.candidates
    except Exception:  # noqa: BLE001 - runtime provider boundary must contain malformed adapters
        return _failed_status(name, "provider_exception"), ()


def _failed_status(provider: str, reason: str) -> ProviderStatus:
    return ProviderStatus(
        provider=provider,
        outcome=ProviderOutcome.FAILED,
        attempted=True,
        reason=reason,
    )


def _normalize_provider_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not normalized:
        raise ValueError("Discovery provider name must not be blank.")
    return normalized
