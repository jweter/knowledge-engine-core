"""Explicitly opt-in loopback-only CLI integration fixture for Core consumers.

This facility is never selected by ordinary online-research. It supports a
separately started, documented fixture server in AI/Web CI via the INSTALLED
ke CLI instead of the private pytest harness. No production URL policy is
relaxed: normal requests still use SafeHttpsFetcher with standard DNS/TLS.
"""

from __future__ import annotations

import contextlib
import http.client
import socket
from typing import cast

from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.online_evidence_fixture_server import (
    BROKEN_PATH,
    GOOD_PATH,
    HUGE_PATH,
)
from knowledge_engine.online_retrieval import (
    ConnectionFactory,
    RetrievalLimits,
    SafeHttpsFetcher,
)

SOURCE_HOST = "source.example.org"
PINNED_TEST_ADDRESS = "93.184.216.34"
FIXTURE_PATHS = (("good", GOOD_PATH), ("broken", BROKEN_PATH), ("huge", HUGE_PATH))


class _LocalFixtureConnection(http.client.HTTPConnection):
    """Locally pinned HTTP connection implementing the SafeHttpsFetcher protocol."""

    def set_timeout(self, seconds: float) -> None:
        self.timeout = seconds
        if self.sock is not None:
            self.sock.settimeout(seconds)

    def abort(self) -> None:
        if self.sock is not None:
            with contextlib.suppress(OSError):
                self.sock.shutdown(socket.SHUT_RDWR)


class _FixtureProvider:
    name = "openalex"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        candidates = []
        for key, path in FIXTURE_PATHS:
            observation = ProviderObservation(
                provider="openalex",
                provider_id=f"id-{key}",
                title=f"Source {key}",
                full_text_url=f"https://{SOURCE_HOST}{path}",
                doi=f"10.1/{key}",
            )
            candidates.append(
                FederatedCandidate(
                    canonical_id=key,
                    title=f"Source {key}",
                    observations=(observation,),
                    doi=f"10.1/{key}",
                )
            )
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus("openalex", ProviderOutcome.SUCCESS, True, len(candidates)),
            ),
            candidates=tuple(candidates),
        )


def fixture_components(
    port: int, limits: RetrievalLimits
) -> tuple[DiscoveryProviderRegistry, SafeHttpsFetcher]:
    """Only connects to localhost, on the explicit fixture port; no public DNS."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Fixture server port must be an integer in 1..65535.")

    def resolve(host: str, requested_port: int) -> tuple[str, ...]:
        if host != SOURCE_HOST or requested_port != 443:
            raise OSError("Fixture host is not allowed.")
        return (PINNED_TEST_ADDRESS,)

    def connect(host: str, address: str, timeout: float) -> _LocalFixtureConnection:
        if host != SOURCE_HOST or address != PINNED_TEST_ADDRESS:
            raise OSError("Unexpected fixture connection target.")
        return _LocalFixtureConnection("127.0.0.1", port, timeout=timeout)

    return DiscoveryProviderRegistry((_FixtureProvider(),)), SafeHttpsFetcher(
        # The stdlib HTTPConnection stub does not declare our abort/set_timeout
        # extension; _LocalFixtureConnection implements both at runtime.
        limits,
        resolver=resolve,
        connection_factory=cast(ConnectionFactory, connect),
    )
