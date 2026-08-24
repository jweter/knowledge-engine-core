from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.general_question_acquisition import (
    AcquisitionIdentity,
    AcquisitionPlanItem,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.general_question_pmc_acquisition import (
    GeneralQuestionPmcAcquisitionError,
    GeneralQuestionPmcExecution,
    GeneralQuestionPmcReceipt,
    GeneralQuestionPmcReceiptItem,
    persist_pmc_acquisition_execution,
)
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPaper
from knowledge_engine.pmc_acquisition import AcquisitionReceipt, AcquisitionReceiptItem


class FakeParser:
    def parse(self, path: Path) -> ParsedPaper:
        content = path.read_bytes()
        digest = sha256(content).hexdigest()
        return ParsedPaper(
            source_path=path,
            content_hash=digest,
            title="Parsed creatine trial",
            authors=["Ada Researcher"],
            abstract="A trial abstract.",
            doi=None,
            page_count=1,
            word_count=4,
            raw_text="Creatine improved maximal strength.",
            body_text="Creatine improved maximal strength.",
            pages=[],
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


def _plan() -> GeneralQuestionAcquisitionPlan:
    item = AcquisitionPlanItem(
        candidate_id="doi:10.1000/creatine",
        title="Creatine trial",
        disposition="eligible_full_text",
        identity=AcquisitionIdentity(
            canonical_id="doi:10.1000/creatine",
            doi="10.1000/creatine",
            pmid="12345",
            pmcid="PMC12345",
            arxiv_id=None,
            openalex_id=None,
            semantic_scholar_id=None,
        ),
        selected_observation_provider="pubmed",
        acquisition_route=AcquisitionRoute.PMC_OA.value,
        full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/pdf/test.pdf",
        xml_url=None,
        license="CC BY 4.0",
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


def _execution(papers_dir: Path) -> GeneralQuestionPmcExecution:
    payload = b"%PDF-1.7\ncreatine"
    papers_dir.mkdir()
    (papers_dir / "PMC12345.pdf").write_bytes(payload)
    digest = sha256(payload).hexdigest()
    acquisition_item = AcquisitionReceiptItem(
        pmid="12345",
        pmcid="PMC12345",
        license="CC BY 4.0",
        filename="PMC12345.pdf",
        byte_count=len(payload),
        sha256=digest,
    )
    return GeneralQuestionPmcExecution(
        receipt=GeneralQuestionPmcReceipt(
            schema_version=1,
            search_run_id="run-123",
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
                    byte_count=len(payload),
                    sha256=digest,
                ),
            ),
        ),
        acquisition_receipt=AcquisitionReceipt(
            schema_version=1,
            acquired_count=1,
            items=(acquisition_item,),
        ),
    )


def test_persists_verified_acquisition_with_plan_identity(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = _execution(papers_dir)

    with database.session() as session:
        result = persist_pmc_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    assert result.parsed_count == 1
    assert result.persisted_count == 1
    assert result.reused_count == 0
    assert result.items[0].persistence_status == "persisted"
    with database.session() as session:
        paper = session.scalar(select(Paper))
        assert paper is not None
        assert paper.title == "Creatine trial"
        assert paper.doi == "10.1000/creatine"
        assert paper.pmid == "12345"
        assert paper.source_path.endswith("PMC12345.pdf")


def test_rejects_tampered_acquisition_before_parsing_or_persistence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = _execution(papers_dir)
    (papers_dir / "PMC12345.pdf").write_bytes(b"tampered")

    with pytest.raises(GeneralQuestionPmcAcquisitionError, match="size did not match"):
        with database.session() as session:
            persist_pmc_acquisition_execution(
                session,
                _plan(),
                execution,
                output_directory=papers_dir,
                parser=FakeParser(),
            )

    with database.session() as session:
        assert session.scalar(select(Paper)) is None


def test_reuses_existing_paper_by_stable_identity(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = _execution(papers_dir)
    with database.session() as session:
        session.add(
            Paper(
                title="Existing creatine trial",
                doi="10.1000/existing",
                pmid="12345",
                source_path="existing.pdf",
                content_hash="f" * 64,
                page_count=1,
                word_count=10,
            )
        )

    with database.session() as session:
        result = persist_pmc_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    assert result.persisted_count == 0
    assert result.reused_count == 1
    assert result.items[0].persistence_status == "reused"
    with database.session() as session:
        assert len(list(session.scalars(select(Paper)))) == 1
