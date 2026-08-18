from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.discovery_broker import DiscoveryProvider
from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeProvider:
    def __init__(
        self, name: str, result_factory: Callable[[DiscoveryQuery], FederatedSearchResult]
    ) -> None:
        self._name = name
        self._result_factory = result_factory
        self.calls: list[DiscoveryQuery] = []

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        self.calls.append(query)
        return self._result_factory(query)


def _success_result(
    provider: str, *, candidate_id: str, doi: str | None
) -> Callable[[DiscoveryQuery], FederatedSearchResult]:
    def build(query: DiscoveryQuery) -> FederatedSearchResult:
        observation = ProviderObservation(
            provider=provider,
            provider_id=candidate_id,
            title=f"A paper found by {provider}",
            doi=doi,
        )
        candidate = FederatedCandidate(
            canonical_id=f"{provider}:{candidate_id}",
            title=observation.title,
            observations=(observation,),
            doi=doi,
        )
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider=provider,
                    outcome=ProviderOutcome.SUCCESS,
                    attempted=True,
                    result_count=1,
                ),
            ),
            candidates=(candidate,),
        )

    return build


def _failed_result(
    provider: str, *, reason: str
) -> Callable[[DiscoveryQuery], FederatedSearchResult]:
    def build(query: DiscoveryQuery) -> FederatedSearchResult:
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider=provider,
                    outcome=ProviderOutcome.FAILED,
                    attempted=True,
                    result_count=0,
                    reason=reason,
                ),
            ),
        )

    return build


def _registry_with(*providers: DiscoveryProvider) -> DiscoveryProviderRegistry:
    return DiscoveryProviderRegistry(providers)


def test_federated_discover_persists_a_run_and_reports_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    provider_b = FakeProvider("beta", _failed_result("beta", reason="rate_limited"))
    monkeypatch.setattr(
        entrypoint,
        "_federated_discovery_registry",
        lambda **kwargs: _registry_with(provider_a, provider_b),
    )

    ledger_root = tmp_path / "ledger"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "semaglutide weight loss",
            "--ledger-root",
            str(ledger_root),
            "--limit",
            "5",
            "--initiated-by",
            "test-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert provider_a.calls and provider_a.calls[0].text == "semaglutide weight loss"
    assert provider_b.calls

    unwrapped = _unwrapped(result.output)
    assert "Coverage: partial" in unwrapped
    assert "1 deduplicated candidate" in unwrapped
    assert "A paper found by alpha" in unwrapped

    persisted = list(ledger_root.glob("*.json"))
    assert len(persisted) == 1
    payload = json.loads(persisted[0].read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["completeness"] == "partial"
    assert payload["initiated_by"] == "test-run"
    provider_outcomes = {entry["provider"]: entry["outcome"] for entry in payload["providers"]}
    assert provider_outcomes == {"alpha": "success", "beta": "failed"}


def test_federated_discover_respects_a_provider_subset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    provider_b = FakeProvider(
        "beta", _success_result("beta", candidate_id="B1", doi="10.1000/beta-1")
    )
    monkeypatch.setattr(
        entrypoint,
        "_federated_discovery_registry",
        lambda **kwargs: _registry_with(provider_a, provider_b),
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "obesity treatment",
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--providers",
            "alpha",
        ],
    )

    assert result.exit_code == 0, result.output
    assert provider_a.calls
    assert not provider_b.calls


def test_federated_discover_rejects_an_unknown_provider_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "obesity treatment",
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--providers",
            "not-a-real-provider",
        ],
    )

    assert result.exit_code != 0
    assert "not-a-real-provider" in _unwrapped(result.output)


def test_federated_coverage_report_reads_back_a_persisted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
    )

    ledger_root = tmp_path / "ledger"
    discover_result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "obesity treatment",
            "--ledger-root",
            str(ledger_root),
        ],
    )
    assert discover_result.exit_code == 0, discover_result.output
    search_run_id = list(ledger_root.glob("*.json"))[0].stem

    report_result = CliRunner().invoke(
        entrypoint.app,
        ["federated-coverage-report", search_run_id, "--ledger-root", str(ledger_root)],
    )

    assert report_result.exit_code == 0, report_result.output
    unwrapped = _unwrapped(report_result.output)
    assert search_run_id in unwrapped
    assert "Coverage: complete" in unwrapped


def test_federated_coverage_report_handles_an_unknown_run_id(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-coverage-report",
            "00000000-0000-0000-0000-000000000000",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code != 0
    assert "No federated search run found" in _unwrapped(result.output)


def test_federated_discover_writes_a_machine_readable_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
    )

    output_path = tmp_path / "result.json"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "obesity treatment",
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["completeness"] == "complete"
    assert payload["candidates"][0]["title"] == "A paper found by alpha"
    assert payload["candidates"][0]["doi"] == "10.1000/alpha-1"
    assert "search_run_id" in payload


def test_production_registry_wires_every_transport_backed_provider() -> None:
    """No network call -- just proves the real factory composes what it claims to.

    A cheap regression check for the wiring itself (a provider silently
    dropped, or a constructor argument mismatch) that the CLI tests above
    can't catch since they replace `_federated_discovery_registry` entirely.
    """

    registry = entrypoint._federated_discovery_registry(
        openalex_api_key=None, semantic_scholar_api_key=None
    )

    assert registry.provider_names == (
        "pubmed",
        "crossref",
        "openalex",
        "arxiv",
        "semantic_scholar",
    )
