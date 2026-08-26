from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.core_acquisition import (
    CoreAcquisitionReceipt,
    CoreAcquisitionReceiptItem,
    CoreOaAcquisitionService,
)
from knowledge_engine.core_discovery import CoreCandidate
from knowledge_engine.database import Database
from knowledge_engine.general_question_acquisition import (
    AcquisitionIdentity,
    AcquisitionPlanItem,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.general_question_core_acquisition import (
    GeneralQuestionCoreAcquisitionError,
    execute_core_acquisition_plan,
    persist_core_acquisition_execution,
)
from knowledge_engine.models import ImportItem, ImportRun, Paper
from knowledge_engine.parser import DocumentParser, ParsedPaper


class FakeResolver:
    def __init__(self, candidate: CoreCandidate) -> None:
        self.candidate = candidate
        self.calls: list[tuple[str, ...]] = []

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[CoreCandidate, ...]:
        self.calls.append(dois)
        return (self.candidate,)


class FakeAcquisitionService:
    def __init__(self, *, receipt_core_id: str = "123") -> None:
        self.calls = 0
        self.receipt_core_id = receipt_core_id

    def acquire(self, *, candidates, approvals, output_directory: Path) -> CoreAcquisitionReceipt:
        self.calls += 1
        assert len(candidates) == 1
        assert len(approvals) == 1
        payload = b"%PDF-1.7\nCORE body"
        output_directory.mkdir(parents=True, exist_ok=True)
        filename = "core-123.pdf"
        (output_directory / filename).write_bytes(payload)
        return CoreAcquisitionReceipt(
            schema_version=1,
            acquired_count=1,
            items=(
                CoreAcquisitionReceiptItem(
                    core_id=self.receipt_core_id,
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
            title="Parsed CORE paper",
            authors=["Ada Researcher"],
            abstract="A CORE abstract.",
            doi=None,
            page_count=1,
            word_count=4,
            raw_text="Creatine improved maximal strength.",
            body_text="Creatine improved maximal strength.",
            pages=[],
        )


class FakePdfResponse:
    def __init__(self, body: bytes, status_code: int = 200) -> None:
        self.body = body
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class FakePdfTransport:
    def __init__(self, body: bytes = b"%PDF-1.7\nCORE body") -> None:
        self.body = body
        self.urls: list[str] = []

    def get(self, *, url, headers, timeout_seconds, max_response_bytes):
        self.urls.append(url)
        return FakePdfResponse(self.body)


def _candidate(*, pdf_url: str = "https://core.ac.uk/download/123.pdf") -> CoreCandidate:
    return CoreCandidate(
        core_id="123",
        doi="10.1000/creatine",
        title="Creatine from CORE",
        abstract=None,
        authors=(),
        publication_year=2025,
        venue=None,
        document_type="article",
        pdf_url=pdf_url,
        pdf_host="core.ac.uk",
        source_fulltext_urls=(),
    )


def _plan(
    *,
    route: str | None = AcquisitionRoute.CORE.value,
    license_name: str | None = "cc by",
    open_access: bool | None = True,
    full_text_url: str = "https://core.ac.uk/download/123.pdf",
) -> GeneralQuestionAcquisitionPlan:
    item = AcquisitionPlanItem(
        candidate_id="doi:10.1000/creatine",
        title="Creatine from CORE",
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
        selected_observation_provider="core",
        acquisition_route=route,
        full_text_url=full_text_url,
        xml_url=None,
        license=license_name,
        open_access=open_access,
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


def test_executes_exact_core_route_and_preserves_plan_provenance(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    result = execute_core_acquisition_plan(
        _plan(),
        resolver=resolver,
        acquisition_service=service,
        output_directory=tmp_path / "papers",
    )

    assert resolver.calls == [("10.1000/creatine",)]
    assert service.calls == 1
    assert result.receipt.search_run_id == "run-123"
    assert result.receipt.research_question_id == "rq-creatine"
    assert result.receipt.acquisition_route == "core"
    assert result.receipt.items[0].candidate_id == "doi:10.1000/creatine"
    assert result.receipt.items[0].core_id == "123"


def test_oa_signal_without_reusable_license_still_fails_closed(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionCoreAcquisitionError, match="explicit reusable license"):
        execute_core_acquisition_plan(
            _plan(license_name=None, open_access=True),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert resolver.calls == []
    assert service.calls == 0


def test_rejects_stale_core_download_url_after_exact_doi_refresh(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate(pdf_url="https://core.ac.uk/download/current.pdf"))
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionCoreAcquisitionError, match="did not reconcile"):
        execute_core_acquisition_plan(
            _plan(full_text_url="https://core.ac.uk/download/stale.pdf"),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert service.calls == 0


def test_rejects_and_rolls_back_mismatched_provider_receipt(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    with pytest.raises(GeneralQuestionCoreAcquisitionError, match="receipt evidence"):
        execute_core_acquisition_plan(
            _plan(),
            resolver=FakeResolver(_candidate()),
            acquisition_service=FakeAcquisitionService(receipt_core_id="999"),
            output_directory=papers_dir,
        )
    assert not (papers_dir / "core-123.pdf").exists()


def test_core_service_rejects_non_pdf_and_rolls_back(tmp_path: Path) -> None:
    service = CoreOaAcquisitionService(FakePdfTransport(body=b"not-a-pdf"))
    candidate = _candidate()
    from knowledge_engine.core_acquisition import CoreAcquisitionApproval, CoreAcquisitionError

    approval = CoreAcquisitionApproval(
        core_id="123",
        doi="10.1000/creatine",
        license="cc by",
        pdf_url="https://core.ac.uk/download/123.pdf",
        filename="core-123.pdf",
    )
    with pytest.raises(CoreAcquisitionError, match="not a PDF"):
        service.acquire(
            candidates=(candidate,),
            approvals=(approval,),
            output_directory=tmp_path / "papers",
        )
    assert not (tmp_path / "papers" / "core-123.pdf").exists()


def test_persists_verified_core_acquisition_with_import_lineage(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_core_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_candidate()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )

    with database.session() as session:
        result = persist_core_acquisition_execution(
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
        assert paper.title == "Creatine from CORE"
        assert paper.doi == "10.1000/creatine"
        import_run = session.scalar(select(ImportRun))
        assert import_run is not None
        assert import_run.validation_mode == "gqr_core_acquisition"
        snapshot = json.loads(import_run.manifest_snapshot.corpus_json_text)
        assert snapshot["kind"] == "general_question_core_import"
        assert snapshot["plan"]["search_run_id"] == "run-123"
        item = session.scalar(select(ImportItem))
        assert item is not None
        assert item.matched_paper_id == paper.id
        evidence = json.loads(item.duplicate_evidence_json or "{}")
        assert evidence["core_id"] == "123"


def test_rejects_tampered_core_file_before_persistence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_core_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_candidate()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )
    (papers_dir / "core-123.pdf").write_bytes(b"tampered")

    with (
        pytest.raises(GeneralQuestionCoreAcquisitionError, match="size did not match"),
        database.session() as session,
    ):
        persist_core_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    with database.session() as session:
        assert session.scalar(select(Paper)) is None
        assert session.scalar(select(ImportRun)) is None
