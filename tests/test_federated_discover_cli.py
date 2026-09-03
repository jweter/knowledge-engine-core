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


def test_federated_discover_persists_project_and_research_question_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
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
            "--project-id",
            "project-7",
            "--research-question-id",
            "rq-42",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(list(ledger_root.glob("*.json"))[0].read_text(encoding="utf-8"))
    assert payload["project_id"] == "project-7"
    assert payload["research_question_id"] == "rq-42"


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


def test_federated_coverage_report_labels_retry_count_as_retries_not_total_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`total_retry_attempts` counts retries only (excludes each provider's
    initial request); the console line must say so, not "total attempt(s)",
    which would understate real request count (issue #433 item 2, Codex
    review finding 3)."""

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
    assert "retry attempt(s)" in unwrapped
    assert "total attempt" not in unwrapped


def test_federated_coverage_report_output_includes_candidate_snapshot(
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

    output_path = tmp_path / "coverage.json"
    report_result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-coverage-report",
            search_run_id,
            "--ledger-root",
            str(ledger_root),
            "--output",
            str(output_path),
        ],
    )

    assert report_result.exit_code == 0, report_result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["search_run_id"] == search_run_id
    assert payload["coverage"]["candidate_count"] == 1
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["doi"] == "10.1000/alpha-1"
    assert candidate["observations"][0]["provider"] == "alpha"
    assert candidate["observations"][0]["title"] == "A paper found by alpha"
    # Internal run context never enters this public payload.
    assert "initiated_by" not in payload["coverage"]
    assert "project_id" not in payload["coverage"]


def test_federated_coverage_report_without_output_flag_writes_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
    )

    ledger_root = tmp_path / "ledger"
    CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "obesity treatment",
            "--ledger-root",
            str(ledger_root),
        ],
    )
    search_run_id = list(ledger_root.glob("*.json"))[0].stem

    report_result = CliRunner().invoke(
        entrypoint.app,
        ["federated-coverage-report", search_run_id, "--ledger-root", str(ledger_root)],
    )

    assert report_result.exit_code == 0, report_result.output
    assert not (tmp_path / "coverage.json").exists()


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


def test_federated_discover_history_lists_runs_for_a_tracked_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider_a = FakeProvider(
        "alpha", _success_result("alpha", candidate_id="A1", doi="10.1000/alpha-1")
    )
    monkeypatch.setattr(
        entrypoint, "_federated_discovery_registry", lambda **kwargs: _registry_with(provider_a)
    )

    ledger_root = tmp_path / "ledger"
    runner = CliRunner()
    for query in ("semaglutide weight loss", "semaglutide weight loss follow-up"):
        first_run = runner.invoke(
            entrypoint.app,
            [
                "federated-discover",
                "--query",
                query,
                "--ledger-root",
                str(ledger_root),
                "--research-question-id",
                "rq-42",
            ],
        )
        assert first_run.exit_code == 0, first_run.output

    other_question_run = runner.invoke(
        entrypoint.app,
        [
            "federated-discover",
            "--query",
            "unrelated question",
            "--ledger-root",
            str(ledger_root),
            "--research-question-id",
            "rq-other",
        ],
    )
    assert other_question_run.exit_code == 0, other_question_run.output

    output_path = tmp_path / "history.json"
    history_result = runner.invoke(
        entrypoint.app,
        [
            "federated-discover-history",
            "rq-42",
            "--ledger-root",
            str(ledger_root),
            "--output",
            str(output_path),
        ],
    )

    assert history_result.exit_code == 0, history_result.output
    unwrapped = _unwrapped(history_result.output)
    assert "2 run(s)" in unwrapped

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["research_question_id"] == "rq-42"
    assert payload["run_count"] == 2
    assert len(payload["runs"]) == 2
    for run in payload["runs"]:
        assert "initiated_by" not in run
        assert "project_id" not in run
        assert "research_question_id" not in run
    # Newest first: created_at is non-increasing across the listed runs.
    created_at_values = [run["created_at"] for run in payload["runs"]]
    assert created_at_values == sorted(created_at_values, reverse=True)


def test_federated_discover_history_reports_no_runs_without_erroring(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover-history",
            "rq-never-searched",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "No federated-discover runs found" in _unwrapped(result.output)


def test_federated_discover_history_rejects_blank_research_question_id(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "federated-discover-history",
            "   ",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code != 0


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
    assert payload["coverage"]["search_run_id"] == payload["search_run_id"]
    assert payload["coverage"]["query_text"] == "obesity treatment"
    assert payload["coverage"]["completeness"] == "complete"
    assert payload["provider_disagreements"] == {"candidates": [], "disagreement_count": 0}


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
