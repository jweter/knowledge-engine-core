from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session
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
    GeneralQuestionCoreAcquisitionError,
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


def _execution(run_id: str) -> GeneralQuestionCoreExecution:
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
    return GeneralQuestionCoreExecution(
        receipt=public_receipt,
        acquisition_receipt=raw_receipt,
    )


class _CommitFailingDatabase:
    """Delegate real sessions but fail before the second session can commit."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.session_calls = 0

    def initialize(self) -> None:
        self.database.initialize()

    @contextmanager
    def session(self) -> Iterator[Session]:
        self.session_calls += 1
        call_number = self.session_calls
        with self.database.session() as session:
            yield session
            if call_number == 2:
                raise RuntimeError("simulated database commit failure")


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
    execution = _execution(run_id)

    def fake_execute(
        plan: object,
        *,
        resolver: object,
        acquisition_service: object,
        output_directory: Path,
    ) -> GeneralQuestionCoreExecution:
        del plan
        calls.append((resolver, acquisition_service, output_directory))
        return execution

    monkeypatch.setattr(command_surface, "execute_core_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        command_surface,
        "persist_core_acquisition_execution",
        lambda *args, **kwargs: SimpleNamespace(
            parsed_count=1,
            persisted_count=1,
            reused_count=0,
            to_json=execution.receipt.to_json,
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


def test_cli_rejects_receipt_path_that_acquisition_just_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_core_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    monkeypatch.setattr(command_surface, "_core_doi_resolver", object)
    monkeypatch.setattr(command_surface, "_core_acquisition_service", object)
    execution = _execution(run_id)

    def fake_execute(
        plan: object,
        *,
        resolver: object,
        acquisition_service: object,
        output_directory: Path,
    ) -> GeneralQuestionCoreExecution:
        del plan, resolver, acquisition_service
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "core-core123.pdf").write_bytes(b"%PDF-1.4 test")
        return execution

    def fail_persistence(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("persistence must not run after a receipt/PDF path collision")

    monkeypatch.setattr(command_surface, "execute_core_acquisition_plan", fake_execute)
    monkeypatch.setattr(command_surface, "persist_core_acquisition_execution", fail_persistence)

    papers_dir = tmp_path / "papers"
    receipt_path = papers_dir / "core-core123.pdf"
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

    assert result.exit_code != 0
    assert "must not overwrite an acquired CORE PDF" in result.output
    assert not receipt_path.exists()


def test_cli_restores_forced_receipt_when_second_transaction_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_core_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    real_database = _build_database(tmp_path)
    database = _CommitFailingDatabase(real_database)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    monkeypatch.setattr(command_surface, "_core_doi_resolver", object)
    monkeypatch.setattr(command_surface, "_core_acquisition_service", object)
    execution = _execution(run_id)

    def fake_execute(
        plan: object,
        *,
        resolver: object,
        acquisition_service: object,
        output_directory: Path,
    ) -> GeneralQuestionCoreExecution:
        del plan, resolver, acquisition_service
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "core-core123.pdf").write_bytes(b"%PDF-1.4 test")
        return execution

    monkeypatch.setattr(command_surface, "execute_core_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        command_surface,
        "persist_core_acquisition_execution",
        lambda *args, **kwargs: SimpleNamespace(
            parsed_count=1,
            persisted_count=1,
            reused_count=0,
            to_json=execution.receipt.to_json,
        ),
    )

    papers_dir = tmp_path / "papers"
    receipt_path = tmp_path / "receipt.json"
    original_receipt = b'{"previous": true}\n'
    receipt_path.write_bytes(original_receipt)
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
            "--force",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert receipt_path.read_bytes() == original_receipt
    assert not (papers_dir / "core-core123.pdf").exists()

    failure_path = tmp_path / "receipt.json.failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "core"
    assert failure["stage"] == "persist"
    assert failure["reason"] == "Unexpected error: RuntimeError."
    assert failure["candidate_ids"] == ["doi:10.1000/core-example"]


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
            "general-question-acquire-core",
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
    failure_path = tmp_path / "receipt.json.failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "core"
    assert failure["stage"] == "build_plan"
    assert failure["search_run_id"] == "00000000-0000-0000-0000-000000000999"
    assert failure["research_question_id"] == "rq-core"
    assert failure["candidate_ids"] == ["doi:10.1000/core-example"]


def test_cli_clears_a_stale_failure_record_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_core_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    monkeypatch.setattr(command_surface, "_core_doi_resolver", lambda: object())
    monkeypatch.setattr(command_surface, "_core_acquisition_service", lambda: object())
    execution = _execution(run_id)
    monkeypatch.setattr(
        command_surface,
        "execute_core_acquisition_plan",
        lambda *args, **kwargs: execution,
    )
    monkeypatch.setattr(
        command_surface,
        "persist_core_acquisition_execution",
        lambda *args, **kwargs: SimpleNamespace(
            parsed_count=1,
            persisted_count=1,
            reused_count=0,
            to_json=execution.receipt.to_json,
        ),
    )

    receipt_path = tmp_path / "receipt.json"
    failure_path = tmp_path / "receipt.json.failure.json"
    failure_path.write_text('{"stale": true}\n', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-core",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert not failure_path.exists()


def test_cli_writes_failure_record_even_when_rollback_itself_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_core_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(command_surface, "_local_database", lambda: database)
    monkeypatch.setattr(command_surface, "_core_doi_resolver", lambda: object())
    monkeypatch.setattr(command_surface, "_core_acquisition_service", lambda: object())
    execution = _execution(run_id)
    monkeypatch.setattr(
        command_surface,
        "execute_core_acquisition_plan",
        lambda *args, **kwargs: execution,
    )

    def fail_persistence(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise GeneralQuestionCoreAcquisitionError("simulated persistence failure")

    monkeypatch.setattr(command_surface, "persist_core_acquisition_execution", fail_persistence)

    def fail_cleanup(**kwargs: object) -> None:
        del kwargs
        raise RuntimeError("simulated rollback failure")

    monkeypatch.setattr(command_surface, "_cleanup_failed_persistence", fail_cleanup)

    receipt_path = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquire-core",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt_path),
        ],
    )

    # The rollback/cleanup failure propagates (it is not swallowed), but the
    # durable failure record for the *original* persistence error must still
    # have been written before cleanup ran.
    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    failure_path = tmp_path / "receipt.json.failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failure["acquisition_route"] == "core"
    assert failure["stage"] == "persist"
    assert failure["reason"] == "simulated persistence failure"
