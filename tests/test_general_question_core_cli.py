from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import knowledge_engine.command_surface as command_surface
import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.command_surface import app
from knowledge_engine.config import Settings
from knowledge_engine.core_acquisition import (
    CoreAcquisitionReceipt,
    CoreAcquisitionReceiptItem,
)
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
from knowledge_engine.general_question_core_acquisition import (
    GeneralQuestionCoreExecution,
    GeneralQuestionCoreReceipt,
    GeneralQuestionCoreReceiptItem,
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


def _record_core_run(ledger_root: Path) -> str:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/core-example",
        title="CORE-routed example",
        doi="10.1000/core-example",
        observations=(
            ProviderObservation(
                provider="core",
                provider_id="core-123",
                title="CORE-routed example",
                doi="10.1000/core-example",
                full_text_url="https://core.ac.uk/download/123.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="core routed example", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="core",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
    )
    return (
        FederatedSearchLedger(ledger_root)
        .record(
            result,
            research_question_id="rq-core",
        )
        .search_run_id
    )


def _write_request(path: Path, *, search_run_id: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "search_run_id": search_run_id,
                "research_question_id": "rq-core",
                "candidate_ids": ["doi:10.1000/core-example"],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_command_surface_preserves_existing_entrypoint_app() -> None:
    assert app is entrypoint.app

    result = CliRunner().invoke(app, ["general-question-acquire-europe-pmc", "--help"])

    assert result.exit_code == 0, result.output
    assert "general-question-acquire-europe-pmc" in result.output


def test_cli_executes_planned_core_route_and_writes_durable_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_core_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    resolver = object()
    service = object()
    monkeypatch.setattr(command_surface, "_core_doi_resolver", lambda: resolver)
    monkeypatch.setattr(command_surface, "_core_acquisition_service", lambda: service)
    calls: list[tuple[object, object, Path]] = []

    raw_receipt = CoreAcquisitionReceipt(
        schema_version=1,
        acquired_count=1,
        items=(
            CoreAcquisitionReceiptItem(
                core_id="core-123",
                doi="10.1000/core-example",
                license="CC BY 4.0",
                filename="core-core123.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )
    public_receipt = GeneralQuestionCoreReceipt(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-core",
        acquisition_route="core",
        acquired_count=1,
        items=(
            GeneralQuestionCoreReceiptItem(
                candidate_id="doi:10.1000/core-example",
                core_id="core-123",
                doi="10.1000/core-example",
                license="CC BY 4.0",
                filename="core-core123.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )

    def fake_execute(
        plan: object,
        *,
        resolver: object,
        acquisition_service: object,
        output_directory: Path,
    ) -> GeneralQuestionCoreExecution:
        del plan
        calls.append((resolver, acquisition_service, output_directory))
        return GeneralQuestionCoreExecution(
            receipt=public_receipt,
            acquisition_receipt=raw_receipt,
        )

    monkeypatch.setattr(command_surface, "execute_core_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        command_surface,
        "persist_core_acquisition_execution",
        lambda *args, **kwargs: SimpleNamespace(
            parsed_count=1,
            persisted_count=1,
            reused_count=0,
            to_json=public_receipt.to_json,
        ),
    )

    receipt_path = tmp_path / "receipt.json"
    papers_dir = tmp_path / "papers"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-core",
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
    assert payload["acquisition_route"] == "core"
    assert payload["items"][0]["core_id"] == "core-123"
