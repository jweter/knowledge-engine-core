from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionReceipt,
    EuropePmcAcquisitionReceiptItem,
)
from knowledge_engine.europepmc_discovery import EuropePmcCandidate
from knowledge_engine.general_question_acquisition import (
    AcquisitionIdentity,
    AcquisitionPlanItem,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.general_question_europepmc_acquisition import (
    GeneralQuestionEuropePmcAcquisitionError,
    execute_europepmc_acquisition_plan,
    persist_europepmc_acquisition_execution,
)
from knowledge_engine.models import ImportItem, ImportRun, Paper
from knowledge_engine.parser import DocumentParser, ParsedPaper


class FakeResolver:
    def __init__(self, candidate: EuropePmcCandidate) -> None:
        self.candidate = candidate
        self.calls: list[tuple[str, ...]] = []

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[EuropePmcCandidate, ...]:
        self.calls.append(dois)
        return (self.candidate,)


class FakeAcquisitionService:
    def __init__(self, *, receipt_europepmc_id: str = "PPR123") -> None:
        self.expected_count: int | None = None
        self.candidates: dict[str, object] | None = None
        self.approvals: dict[str, object] | None = None
        self.receipt_europepmc_id = receipt_europepmc_id

    def acquire(
        self,
        *,
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
        expected_count: int | None = None,
    ) -> EuropePmcAcquisitionReceipt:
        self.expected_count = expected_count
        self.candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        self.approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
        payload = b"%PDF-1.7\nEurope PMC body"
        output_directory.mkdir(parents=True, exist_ok=True)
        filename = "europepmc-PPR123.pdf"
        (output_directory / filename).write_bytes(payload)
        return EuropePmcAcquisitionReceipt(
            schema_version=1,
            acquired_count=1,
            items=(
                EuropePmcAcquisitionReceiptItem(
                    europepmc_id=self.receipt_europepmc_id,
                    doi="10.1000/creatine",
                    license="cc by",
                    filename=filename,
                    byte_count=len(payload),
                    sha256=sha256(payload).hexdigest(),
                ),
            ),
        )


class FakeParser(DocumentParser):
    def parse(self, path: Path) -> ParsedPaper:
        content = path.read_bytes()
        return ParsedPaper(
            source_path=path,
            content_hash=sha256(content).hexdigest(),
            title="Parsed creatine preprint",
            authors=["Ada Researcher"],
            abstract="A preprint abstract.",
            doi=None,
            page_count=1,
            word_count=4,
            raw_text="Creatine improved maximal strength.",
            body_text="Creatine improved maximal strength.",
            pages=[],
        )


def _candidate(*, license_name: str | None = "cc by") -> EuropePmcCandidate:
    return EuropePmcCandidate(
        europepmc_id="PPR123",
        source="PPR",
        pmid=None,
        pmcid=None,
        doi="10.1000/creatine",
        title="Creatine preprint",
        abstract=None,
        authors=(),
        publication_year=2025,
        venue=None,
        in_pmc=False,
        open_access=True,
        license=license_name,
        pdf_url="https://plus.europepmc.org/download/current-pdf.pdf",
        pdf_host="plus.europepmc.org",
    )


def _plan(
    *, route: str | None = AcquisitionRoute.EUROPE_PMC_OA.value
) -> GeneralQuestionAcquisitionPlan:
    item = AcquisitionPlanItem(
        candidate_id="doi:10.1000/creatine",
        title="Creatine preprint",
        disposition="eligible_full_text",
        identity=AcquisitionIdentity(
            canonical_id="doi:10.1000/creatine",
            doi="10.1000/creatine",
            pmid=None,
            pmcid=None,
            arxiv_id=None,
            openalex_id=None,
            semantic_scholar_id=None,
        ),
        selected_observation_provider="europepmc",
        acquisition_route=route,
        full_text_url="https://europepmc.org/api/fulltextRepo?pprId=PPR123",
        xml_url=None,
        license="cc by",
        open_access=True,
        existing_paper_id=None,
        reason=None,
    )
    return GeneralQuestionAcquisitionPlan(
        schema_version=1,
        search_run_id="run-123",
        research_question_id="rq-creatine",
        query_text="creatine strength",
        requested_candidate_count=1,
        resolved_candidate_count=1,
        already_indexed_count=0,
        full_text_selected_count=1,
        metadata_only_count=0,
        skipped_budget_count=0,
        missing_candidate_count=0,
        provider_failures=(),
        items=(item,),
    )


def _database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def test_executes_exact_europepmc_route_and_preserves_plan_provenance(
    tmp_path: Path,
) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    result = execute_europepmc_acquisition_plan(
        _plan(),
        resolver=resolver,
        acquisition_service=service,
        output_directory=tmp_path / "papers",
    )

    assert resolver.calls == [("10.1000/creatine",)]
    assert service.expected_count == 1
    assert service.approvals is not None
    assert service.approvals["selected_count"] == 1
    approvals = cast(list[dict[str, Any]], service.approvals["approvals"])
    assert approvals[0]["pdf_url"].startswith("https://plus.europepmc.org/download/")
    assert result.receipt.search_run_id == "run-123"
    assert result.receipt.research_question_id == "rq-creatine"
    assert result.receipt.acquisition_route == "europe_pmc_oa"
    assert result.receipt.items[0].candidate_id == "doi:10.1000/creatine"
    assert result.receipt.items[0].europepmc_id == "PPR123"


def test_rejects_plan_without_europepmc_route_before_resolution(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionEuropePmcAcquisitionError, match="no eligible Europe"):
        execute_europepmc_acquisition_plan(
            _plan(route=AcquisitionRoute.CORE.value),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert resolver.calls == []
    assert service.expected_count is None


def test_rejects_resolved_candidate_without_reusable_license(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate(license_name=None))
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionEuropePmcAcquisitionError, match="reusable full-text"):
        execute_europepmc_acquisition_plan(
            _plan(),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert service.expected_count is None


def test_rejects_and_rolls_back_mismatched_provider_receipt(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"

    with pytest.raises(
        GeneralQuestionEuropePmcAcquisitionError,
        match="receipt evidence did not reconcile",
    ):
        execute_europepmc_acquisition_plan(
            _plan(),
            resolver=FakeResolver(_candidate()),
            acquisition_service=FakeAcquisitionService(receipt_europepmc_id="PPR999"),
            output_directory=papers_dir,
        )

    assert not (papers_dir / "europepmc-PPR123.pdf").exists()


def test_persists_verified_acquisition_with_import_lineage(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_europepmc_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_candidate()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )

    with database.session() as session:
        result = persist_europepmc_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    assert result.parsed_count == 1
    assert result.persisted_count == 1
    assert result.reused_count == 0
    assert result.items[0].import_item_id is not None
    with database.session() as session:
        paper = session.scalar(select(Paper))
        assert paper is not None
        assert paper.title == "Creatine preprint"
        assert paper.doi == "10.1000/creatine"
        import_run = session.scalar(select(ImportRun))
        assert import_run is not None
        assert import_run.validation_mode == "gqr_europepmc_acquisition"
        snapshot = json.loads(import_run.manifest_snapshot.corpus_json_text)
        assert snapshot["kind"] == "general_question_europepmc_import"
        assert snapshot["plan"]["search_run_id"] == "run-123"
        item = session.scalar(select(ImportItem))
        assert item is not None
        assert item.matched_paper_id == paper.id
        evidence = json.loads(item.duplicate_evidence_json or "{}")
        assert evidence["europepmc_id"] == "PPR123"


def test_rejects_tampered_file_before_persistence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_europepmc_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_candidate()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )
    (papers_dir / "europepmc-PPR123.pdf").write_bytes(b"tampered")

    with (
        pytest.raises(GeneralQuestionEuropePmcAcquisitionError, match="size did not match"),
        database.session() as session,
    ):
        persist_europepmc_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    with database.session() as session:
        assert session.scalar(select(Paper)) is None
        assert session.scalar(select(ImportRun)) is None
