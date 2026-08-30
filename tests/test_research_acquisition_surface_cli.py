from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.research_acquisition_surface as research_acquisition_surface
from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.research_runtime import app


def _build_database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def _record_run(ledger_root: Path) -> str:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/slim-example",
        title="Slim-routed example",
        doi="10.1000/slim-example",
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="54321",
                title="Slim-routed example",
                doi="10.1000/slim-example",
                pmid="54321",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC54321/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="slim routed example", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
    )
    return (
        FederatedSearchLedger(ledger_root)
        .record(result, research_question_id="rq-slim")
        .search_run_id
    )


def _write_request(path: Path, *, search_run_id: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "search_run_id": search_run_id,
                "research_question_id": "rq-slim",
                "candidate_ids": ["doi:10.1000/slim-example"],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_pmc_cli_writes_durable_failure_record_when_search_run_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id="00000000-0000-0000-0000-000000000999",
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(research_acquisition_surface, "_local_database", lambda: database)

    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-pmc",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt_path),
        ],
    )

    assert result.exit_code == 1
    assert not receipt_path.exists()
    failure = json.loads((tmp_path / "receipt.json.failure.json").read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "pmc_oa"
    assert failure["stage"] == "build_plan"
    assert failure["search_run_id"] == "00000000-0000-0000-0000-000000000999"
    assert failure["candidate_ids"] == ["doi:10.1000/slim-example"]


def test_europepmc_cli_writes_durable_failure_record_when_search_run_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id="00000000-0000-0000-0000-000000000999",
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(research_acquisition_surface, "_local_database", lambda: database)

    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-europe-pmc",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt_path),
        ],
    )

    assert result.exit_code == 1
    assert not receipt_path.exists()
    failure = json.loads((tmp_path / "receipt.json.failure.json").read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "europe_pmc_oa"
    assert failure["stage"] == "build_plan"
