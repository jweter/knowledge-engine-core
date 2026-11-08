"""Subprocess entry point (no tests here) for the online-research CLI end-to-end proof.

Runs the *shipped* ``ke`` Typer app unchanged (argument parsing, ``online-research``,
``online-evidence-validate``) with exactly two test seams, installed only in this process:

* discovery: one stub provider replaces the production registry (no external search);
* transport: ``SafeHttpsFetcher`` keeps all of its production logic (URL policy, address
  checks, deadline, size cap) but resolves every host to a documentation-style public address
  and connects to the loopback source server instead of dialling that address.

Production code gains no bypass: the environment variable below is read only here.
On exit it records which forbidden heavy modules were imported.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import sys
from functools import partial
from pathlib import Path

FORBIDDEN_MODULES = ("faiss", "qdrant_client", "sentence_transformers", "torch")
SOURCE_HOST = "source.example.org"  # served by the loopback server, resolved to a public address
PUBLIC_ADDRESS = "93.184.216.34"  # never dialled: the connection factory ignores it


class _LoopbackConnection(http.client.HTTPConnection):
    def set_timeout(self, seconds: float) -> None:
        self.timeout = seconds
        if self.sock is not None:
            self.sock.settimeout(seconds)

    def abort(self) -> None:
        if self.sock is not None:
            with contextlib.suppress(OSError):
                self.sock.shutdown(2)


def _install_seams(port: int) -> None:
    import knowledge_engine.entrypoint as entrypoint
    import knowledge_engine.online_retrieval as retrieval
    from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
    from knowledge_engine.federated_discovery import (
        FederatedCandidate,
        FederatedSearchResult,
        ProviderObservation,
        ProviderOutcome,
        ProviderStatus,
    )

    def candidate(key: str, path: str) -> FederatedCandidate:
        observation = ProviderObservation(
            provider="openalex",
            provider_id=f"id-{key}",
            title=f"Source {key}",
            full_text_url=f"https://{SOURCE_HOST}{path}",
            doi=f"10.1/{key}",
        )
        return FederatedCandidate(
            canonical_id=key, title=f"Source {key}", observations=(observation,), doi=f"10.1/{key}"
        )

    class StubProvider:
        name = "openalex"

        def search(self, query):  # type: ignore[no-untyped-def]
            candidates = (
                candidate("good", "/good"),
                candidate("broken", "/broken"),
                candidate("huge", "/huge"),
            )
            return FederatedSearchResult(
                query=query,
                provider_statuses=(
                    ProviderStatus("openalex", ProviderOutcome.SUCCESS, True, len(candidates)),
                ),
                candidates=candidates,
            )

    entrypoint._federated_discovery_registry = lambda **_: DiscoveryProviderRegistry(
        [StubProvider()]
    )

    def connect(host: str, address: str, timeout: float) -> _LoopbackConnection:
        if host != SOURCE_HOST or address != PUBLIC_ADDRESS:
            raise OSError(f"unexpected connection target {host} {address}")
        return _LoopbackConnection("127.0.0.1", port, timeout=timeout)

    retrieval.SafeHttpsFetcher = partial(  # type: ignore[misc,assignment]
        retrieval.SafeHttpsFetcher,
        resolver=lambda host, _port: (PUBLIC_ADDRESS,),
        connection_factory=connect,  # type: ignore[arg-type]
    )


def main() -> int:
    report = Path(os.environ["KE_HARNESS_IMPORT_REPORT"])
    if "KE_HARNESS_SOURCE_PORT" in os.environ:
        _install_seams(int(os.environ["KE_HARNESS_SOURCE_PORT"]))
    import knowledge_engine.entrypoint as entrypoint

    code = 0
    try:
        entrypoint.app(args=sys.argv[1:])
    except SystemExit as exit_:
        code = exit_.code if isinstance(exit_.code, int) else 1
    finally:
        imported = [name for name in FORBIDDEN_MODULES if name in sys.modules]
        report.write_text(json.dumps(imported), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
