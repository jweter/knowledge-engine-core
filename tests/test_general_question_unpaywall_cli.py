from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import knowledge_engine.command_surface as command_surface
from knowledge_engine.command_surface import app
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
from knowledge_engine.general_question_unpaywall_acquisition import (
    GeneralQuestionUnpaywallAcquisitionError,
    GeneralQuestionUnpaywallExecution,
    GeneralQuestionUnpaywallReceipt,
    GeneralQuestionUnpaywallReceiptItem,
)
from knowledge_engine.unpaywall_acquisition import (
    UnpaywallAcquisitionReceipt,
    UnpaywallAcquisitionReceiptItem,
)


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


def _record_unpaywall_run(ledger_root: Path) -> str:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/unpaywall-example",
        title="Unpaywall-routed example",
        doi="10.1000/unpaywall-example",
        observations=(
            ProviderObservation(
                provider="unpaywall",
                provider_id="10.1000/unpaywall-example",
                title="Unpaywall-routed example",
                doi="10.1000/unpaywall-example",
                full_text_url="https://core.ac.uk/download/123.pdf",
                license="CC BY",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="unpaywall routed example", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="unpaywall",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
    )
    return (
        FederatedSearchLedger(ledger_root)
        .record(result, research_question_id="rq-unpaywall")
        .search_run_id
    )


def _write_request(path: Path, *, search_run_id: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "search_run_id": search_run_id,
                "research_question_id": "rq-unpaywall",
                "candidate_ids": ["doi:10.1000/unpaywall-example"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _execution(run_id: str) -> GeneralQuestionUnpaywallExecution:
    raw_receipt = UnpaywallAcquisitionReceipt(
        schema_version=1,
        acquired_count=1,
        items=(
            UnpaywallAcquisitionReceiptItem(
                doi="10.1000/unpaywall-example",
                pdf_url="https://core.ac.uk/download/123.pdf",
                source_host="core.ac.uk",
                license="CC BY",
                filename="unpaywall-test.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )
    public_receipt = GeneralQuestionUnpaywallReceipt(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-unpaywall",
        acquisition_route="unpaywall",
        acquired_count=1,
        items=(
            GeneralQuestionUnpaywallReceiptItem(
                candidate_id="doi:10.1000/unpaywall-example",
                doi="10.1000/unpaywall-example",
                pdf_url="https://core.ac.uk/download/123.pdf",
                source_host="core.ac.uk",
                plan_license="CC BY",
                resolved_license="CC BY",
                filename="unpaywall-test.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )
    return GeneralQuestionUnpaywallExecution(
        receipt=public_receipt,
        acquisition_receipt=raw_receipt,
    )


def test_command_surface_exposes_unpaywall_executor() -> None:
    result = CliRunner().invoke(app, ["general-question-acquire-unpaywall", "--help"])

    assert result.exit_code == 0, result.output
    assert "general-question-acquire-unpaywall" in result.output


def test_cli_executes_unpaywall_route_and_writes_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_unpaywall_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    resolver = object()
    service = object()
    monkeypatch.setattr(command_surface, "_unpaywall_doi_resolver", lambda: resolver)
    monkeypatch.setattr(command_surface, "_unpaywall_acquisition_service", lambda: service)
    execution = _execution(run_id)
    calls: list[tuple[object, object, Path]] = []

    def fake_execute(
        plan: object,
        *,
        resolver: object,
        acquisition_service: object,
        output_directory: Path,
    ) -> GeneralQuestionUnpaywallExecution:
        del plan
        calls.append((resolver, acquisition_service, output_directory))
        return execution

    monkeypatch.setattr(command_surface, "execute_unpaywall_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        command_surface,
        "persist_unpaywall_acquisition_execution",
        lambda *args, **kwargs: SimpleNamespace(
            parsed_count=1,
            persisted_count=1,
            reused_count=0,
            to_json=execution.receipt.to_json,
        ),
    )

    papers_dir = tmp_path / "papers"
    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-unpaywall",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--papers-dir",
            str(papers_dir),
            "--receipt",
            str(receipt_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(resolver, service, papers_dir)]
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["search_run_id"] == run_id
    assert payload["acquisition_route"] == "unpaywall"
    assert payload["items"][0]["source_host"] == "core.ac.uk"
    assert not (tmp_path / "receipt.json.failure.json").exists()


def test_cli_writes_durable_failure_record_when_search_run_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id="00000000-0000-0000-0000-000000000999",
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)

    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-unpaywall",
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
    assert failure["acquisition_route"] == "unpaywall"
    assert failure["stage"] == "build_plan"
    assert failure["search_run_id"] == "00000000-0000-0000-0000-000000000999"
    assert failure["candidate_ids"] == ["doi:10.1000/unpaywall-example"]


def test_cli_writes_durable_failure_record_when_persistence_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_unpaywall_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    monkeypatch.setattr(command_surface, "_unpaywall_doi_resolver", lambda: object())
    monkeypatch.setattr(command_surface, "_unpaywall_acquisition_service", lambda: object())
    execution = _execution(run_id)
    monkeypatch.setattr(
        command_surface,
        "execute_unpaywall_acquisition_plan",
        lambda *args, **kwargs: execution,
    )

    def fail_persistence(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise GeneralQuestionUnpaywallAcquisitionError("simulated persistence failure")

    monkeypatch.setattr(
        command_surface, "persist_unpaywall_acquisition_execution", fail_persistence
    )

    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-unpaywall",
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
    failure = json.loads((tmp_path / "receipt.json.failure.json").read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "unpaywall"
    assert failure["stage"] == "persist"
    assert failure["reason"] == "simulated persistence failure"
