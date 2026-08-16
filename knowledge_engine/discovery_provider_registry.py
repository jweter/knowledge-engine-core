"""Deterministic runtime composition for federated discovery providers."""

from __future__ import annotations

from collections.abc import Iterable

from knowledge_engine.discovery_broker import DiscoveryProvider, FederatedDiscoveryBroker
from knowledge_engine.federated_discovery_service import (
    FederatedDiscoveryService,
    FederatedSearchRecorder,
)

_PROVIDER_PRIORITY = {
    "pubmed": 0,
    "crossref": 1,
    "openalex": 2,
    "arxiv": 3,
    "semantic_scholar": 4,
}


class DiscoveryProviderRegistry:
    """Own configured discovery providers and construct brokers deterministically.

    The registry is intentionally provider-instance based. Transport creation,
    credentials, and provider-specific configuration stay at their existing
    boundaries; this object only composes already-constructed FRD providers.
    """

    def __init__(self, providers: Iterable[DiscoveryProvider]) -> None:
        by_name: dict[str, DiscoveryProvider] = {}
        for provider in providers:
            name = _normalize_provider_name(provider.name)
            if name in by_name:
                raise ValueError(f"Duplicate discovery provider: {name}")
            by_name[name] = provider

        self._providers = by_name
        self._provider_names = tuple(sorted(by_name, key=_provider_sort_key))

    @property
    def provider_names(self) -> tuple[str, ...]:
        """Return configured provider names in stable runtime order."""

        return self._provider_names

    def get(self, provider_name: str) -> DiscoveryProvider:
        """Return one configured provider by normalized name."""

        normalized = _normalize_provider_name(provider_name)
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise KeyError(f"Discovery provider is not configured: {normalized}") from exc

    def select(self, provider_names: Iterable[str] | None = None) -> tuple[DiscoveryProvider, ...]:
        """Resolve an optional provider subset without hiding unknown names."""

        if provider_names is None:
            names = self._provider_names
        else:
            requested = tuple(_normalize_provider_name(name) for name in provider_names)
            if len(requested) != len(set(requested)):
                raise ValueError("Requested discovery providers must be unique.")
            missing = tuple(name for name in requested if name not in self._providers)
            if missing:
                raise KeyError(f"Discovery provider is not configured: {missing[0]}")
            names = requested

        return tuple(self._providers[name] for name in names)

    def build_broker(
        self,
        provider_names: Iterable[str] | None = None,
    ) -> FederatedDiscoveryBroker:
        """Build a broker from all configured providers or an explicit subset."""

        return FederatedDiscoveryBroker(self.select(provider_names))

    def build_recorded_service(
        self,
        recorder: FederatedSearchRecorder,
        provider_names: Iterable[str] | None = None,
    ) -> FederatedDiscoveryService:
        """Build the runtime service that records every returned federated search."""

        return FederatedDiscoveryService(self.build_broker(provider_names), recorder)


def _normalize_provider_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if not normalized:
        raise ValueError("Discovery provider name must not be blank.")
    return normalized


def _provider_sort_key(name: str) -> tuple[int, str]:
    return (_PROVIDER_PRIORITY.get(name, len(_PROVIDER_PRIORITY)), name)
