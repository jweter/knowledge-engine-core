from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.entrypoint import app
from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionReceipt,
    EuropePmcAcquisitionReceiptItem,
)
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.general_question_europepmc_acquisition import (
    GeneralQuestionEuropePmcExecution,
    GeneralQuestionEuropePmcReceipt,
    GeneralQuestionEuropePmcReceiptItem,
)
from knowledge_engine.general_question_pmc_acquisition import (
    GeneralQuestionPmcExecution,
    GeneralQuestionPmcReceipt,
    GeneralQuestionPmcReceiptItem,
)
from knowledge_engine.models import Paper
from knowledge_engine.pmc_acquisition import AcquisitionReceipt, AcquisitionReceiptItem


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


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


def _record_creatine_run(ledger_root: Path, *, research_question_id: str = "rq-creatine") -> str:
    eligible = FederatedCandidate(
        canonical_id="doi:10.1000/creatine",
        title="Creatine supplementation and maximal strength",
        doi="10.1000/creatine",
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="12345",
                title="Creatine supplementation and maximal strength",
                doi="10.1000/creatine",
                pmid="12345",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    metadata_only = FederatedCandidate(
        canonical_id="doi:10.1000/metadata",
        title="Creatine metadata-only result",
        doi="10.1000/metadata",
        observations=(
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/metadata",
                title="Creatine metadata-only result",
                doi="10.1000/metadata",
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine maximal strength", limit_per_provider=10),
        candidates=(eligible, metadata_only),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=2,
            ),
            ProviderStatus(
                provider="openalex",
                outcome=ProviderOutcome.FAILED,
                attempted=True,
                result_count=0,
                reason="provider unavailable",
            ),
        ),
    )
    ledger = FederatedSearchLedger(ledger_root)
    return ledger.record(result, research_question_id=research_question_id).search_run_id


def _write_request(path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "schema_version": 1,
        "search_run_id": overrides.pop("search_run_id"),
        "research_question_id": "rq-creatine",
        "candidate_ids": ["doi:10.1000/creatine", "doi:10.1000/metadata"],
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_plans_new_domain_without_glp1_interference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root)
    request_path = _write_request(tmp_path / "request.json", search_run_id=run_id)
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Full text eligible: 1" in unwrapped
    assert "Metadata only: 1" in unwrapped
    assert "Provider failures" in unwrapped
    assert "no full text was downloaded and nothing was ingested" in unwrapped


def test_cli_reports_already_indexed_candidate_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root)
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id=run_id,
        candidate_ids=["doi:10.1000/creatine"],
    )
    database = _build_database(tmp_path)
    with database.session() as session:
        session.add(
            Paper(
                title="Creatine supplementation and maximal strength",
                doi="10.1000/creatine",
                source_path="creatine.pdf",
                content_hash="a" * 64,
                page_count=1,
                word_count=10,
            )
        )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output_path = tmp_path / "plan.json"
    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Already indexed: 1" in _unwrapped(result.output)

    plan = json.loads(output_path.read_text(encoding="utf-8"))
    assert plan["already_indexed_count"] == 1
    assert plan["full_text_selected_count"] == 0
    assert plan["items"][0]["disposition"] == "already_indexed"
    assert plan["items"][0]["existing_paper_id"] is not None


def test_cli_no_database_flag_skips_already_indexed_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root)
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id=run_id,
        candidate_ids=["doi:10.1000/creatine"],
    )
    database = _build_database(tmp_path)
    with database.session() as session:
        session.add(
            Paper(
                title="Creatine supplementation and maximal strength",
                doi="10.1000/creatine",
                source_path="creatine.pdf",
                content_hash="a" * 64,
                page_count=1,
                word_count=10,
            )
        )

    called = False

    def _unexpected_database() -> Database:
        nonlocal called
        called = True
        return database

    monkeypatch.setattr(entrypoint, "_local_database", _unexpected_database)

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--no-database",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert called is False
    assert "Already indexed: 0" in unwrapped
    assert "Full text eligible: 1" in unwrapped
    assert "already_indexed" not in unwrapped


def test_cli_reports_missing_search_run_as_a_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id="00000000-0000-0000-0000-000000000999",
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert result.exit_code == 1
    assert "No federated search run found" in _unwrapped(result.output)


def test_cli_rejects_a_request_naming_the_wrong_research_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root, research_question_id="rq-original")
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id=run_id,
        research_question_id="rq-other",
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert result.exit_code == 1
    assert "could not be resolved" in _unwrapped(result.output)


def test_cli_rejects_malformed_request_json(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code != 0


def test_cli_executes_planned_pmc_route_and_writes_durable_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root)
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id=run_id,
        candidate_ids=["doi:10.1000/creatine"],
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    resolver = object()
    service = object()
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: resolver)
    monkeypatch.setattr(entrypoint, "_pmc_acquisition_service", lambda: service)
    calls: list[tuple[object, object, Path]] = []

    raw_receipt = AcquisitionReceipt(
        schema_version=1,
        acquired_count=1,
        items=(
            AcquisitionReceiptItem(
                pmid="12345",
                pmcid="PMC12345",
                license="CC BY 4.0",
                filename="PMC12345.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )
    public_receipt = GeneralQuestionPmcReceipt(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        acquisition_route="pmc_oa",
        acquired_count=1,
        items=(
            GeneralQuestionPmcReceiptItem(
                candidate_id="doi:10.1000/creatine",
                pmid="12345",
                pmcid="PMC12345",
                license="CC BY 4.0",
                filename="PMC12345.pdf",
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
    ) -> GeneralQuestionPmcExecution:
        del plan
        calls.append((resolver, acquisition_service, output_directory))
        return GeneralQuestionPmcExecution(
            receipt=public_receipt,
            acquisition_receipt=raw_receipt,
        )

    monkeypatch.setattr(entrypoint, "execute_pmc_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        entrypoint,
        "persist_pmc_acquisition_execution",
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
            "general-question-acquire-pmc",
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
    assert payload["items"][0]["candidate_id"] == "doi:10.1000/creatine"


def test_cli_executes_planned_europepmc_route_and_writes_durable_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_root = tmp_path / "ledger"
    run_id = _record_creatine_run(ledger_root)
    request_path = _write_request(
        tmp_path / "request.json",
        search_run_id=run_id,
        candidate_ids=["doi:10.1000/creatine"],
    )
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    resolver = object()
    service = object()
    monkeypatch.setattr(entrypoint, "_europepmc_discovery_service", lambda: resolver)
    monkeypatch.setattr(entrypoint, "_europepmc_acquisition_service", lambda: service)
    calls: list[tuple[object, object, Path]] = []

    raw_receipt = EuropePmcAcquisitionReceipt(
        schema_version=1,
        acquired_count=1,
        items=(
            EuropePmcAcquisitionReceiptItem(
                europepmc_id="PPR123",
                doi="10.1000/creatine",
                license="cc by",
                filename="europepmc-PPR123.pdf",
                byte_count=13,
                sha256="a" * 64,
            ),
        ),
    )
    public_receipt = GeneralQuestionEuropePmcReceipt(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        acquisition_route="europe_pmc_oa",
        acquired_count=1,
        items=(
            GeneralQuestionEuropePmcReceiptItem(
                candidate_id="doi:10.1000/creatine",
                europepmc_id="PPR123",
                doi="10.1000/creatine",
                license="cc by",
                filename="europepmc-PPR123.pdf",
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
    ) -> GeneralQuestionEuropePmcExecution:
        del plan
        calls.append((resolver, acquisition_service, output_directory))
        return GeneralQuestionEuropePmcExecution(
            receipt=public_receipt,
            acquisition_receipt=raw_receipt,
        )

    monkeypatch.setattr(entrypoint, "execute_europepmc_acquisition_plan", fake_execute)
    monkeypatch.setattr(
        entrypoint,
        "persist_europepmc_acquisition_execution",
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
            "general-question-acquire-europe-pmc",
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
    assert payload["items"][0]["europepmc_id"] == "PPR123"
