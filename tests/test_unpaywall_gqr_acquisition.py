from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
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
from knowledge_engine.general_question_unpaywall_acquisition import (
    GeneralQuestionUnpaywallAcquisitionError,
    execute_unpaywall_acquisition_plan,
    persist_unpaywall_acquisition_execution,
)
from knowledge_engine.models import ImportItem, ImportRun, Paper
from knowledge_engine.parser import DocumentParser, ParsedPaper
from knowledge_engine.unpaywall_acquisition import (
    UnpaywallAcquisitionApproval,
    UnpaywallAcquisitionError,
    UnpaywallAcquisitionReceipt,
    UnpaywallAcquisitionReceiptItem,
    UnpaywallDoiResolver,
    UnpaywallOaAcquisitionService,
    UnpaywallPdfResponse,
    UnpaywallResolvedPdf,
    deterministic_pdf_filename,
)
from knowledge_engine.unpaywall_lookup import UnpaywallLookupResult, UnpaywallRecord


class FakeLookup:
    def __init__(self, result: UnpaywallLookupResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def lookup(self, doi: str) -> UnpaywallLookupResult:
        self.calls.append(doi)
        return self.result


class FakeResolver:
    def __init__(self, resolved: UnpaywallResolvedPdf) -> None:
        self.resolved = resolved
        self.calls: list[tuple[str, ...]] = []

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[UnpaywallResolvedPdf, ...]:
        self.calls.append(dois)
        return (self.resolved,)


class FakeAcquisitionService:
    def __init__(self) -> None:
        self.calls = 0

    def acquire(
        self,
        *,
        resolved: tuple[UnpaywallResolvedPdf, ...],
        approvals: tuple[UnpaywallAcquisitionApproval, ...],
        output_directory: Path,
    ) -> UnpaywallAcquisitionReceipt:
        self.calls += 1
        assert len(resolved) == 1
        assert len(approvals) == 1
        payload = b"%PDF-1.7\nUnpaywall body"
        output_directory.mkdir(parents=True, exist_ok=True)
        filename = approvals[0].filename
        (output_directory / filename).write_bytes(payload)
        return UnpaywallAcquisitionReceipt(
            schema_version=1,
            acquired_count=1,
            items=(
                UnpaywallAcquisitionReceiptItem(
                    doi=resolved[0].doi,
                    pdf_url=resolved[0].pdf_url,
                    source_host=resolved[0].source_host,
                    license=resolved[0].license,
                    filename=filename,
                    byte_count=len(payload),
                    sha256=sha256(payload).hexdigest(),
                ),
            ),
        )


@dataclass(frozen=True)
class FakePdfTransport:
    body: bytes = b"%PDF-1.7\nUnpaywall body"
    status_code: int = 200

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> UnpaywallPdfResponse:
        del url, headers, timeout_seconds, max_response_bytes
        return UnpaywallPdfResponse(status_code=self.status_code, body=self.body, headers={})


class FakeParser(DocumentParser):
    def parse(self, path: Path) -> ParsedPaper:
        content = path.read_bytes()
        return ParsedPaper(
            source_path=path,
            content_hash=sha256(content).hexdigest(),
            title="Parsed Unpaywall paper",
            authors=["Ada Researcher"],
            abstract="An abstract.",
            doi=None,
            page_count=1,
            word_count=4,
            raw_text="Creatine improved maximal strength.",
            body_text="Creatine improved maximal strength.",
            pages=[],
        )


def _lookup_result(
    *,
    pdf_url: str | None = "https://core.ac.uk/download/123.pdf",
    license_name: str | None = "cc-by",
    is_oa: bool = True,
) -> UnpaywallLookupResult:
    return UnpaywallLookupResult(
        doi="10.1000/creatine",
        found=True,
        record=UnpaywallRecord(
            title="Creatine from Unpaywall",
            is_oa=is_oa,
            oa_status="green",
            best_oa_location_url="https://core.ac.uk/works/123",
            best_oa_location_pdf_url=pdf_url,
            best_oa_location_license=license_name,
            license_rule_result="passed"
            if license_name == "cc-by"
            else "unsupported_license_basis",
            oa_locations=(),
        ),
    )


def _resolved(*, pdf_url: str = "https://core.ac.uk/download/123.pdf") -> UnpaywallResolvedPdf:
    return UnpaywallResolvedPdf(
        doi="10.1000/creatine",
        landing_url="https://core.ac.uk/works/123",
        pdf_url=pdf_url,
        license="CC BY",
        source_host="core.ac.uk",
    )


def _plan(
    *,
    full_text_url: str = "https://core.ac.uk/download/123.pdf",
    license_name: str | None = "CC BY",
) -> GeneralQuestionAcquisitionPlan:
    item = AcquisitionPlanItem(
        candidate_id="doi:10.1000/creatine",
        title="Creatine from Unpaywall",
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
        selected_observation_provider="unpaywall",
        acquisition_route=AcquisitionRoute.UNPAYWALL.value,
        full_text_url=full_text_url,
        xml_url=None,
        license=license_name,
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


def test_resolver_requires_direct_pdf_on_reviewed_host() -> None:
    lookup = FakeLookup(_lookup_result())
    result = UnpaywallDoiResolver(lookup).resolve_dois(("10.1000/CREATINE",))

    assert lookup.calls == ["10.1000/creatine"]
    assert result == (_resolved(),)

    unsafe_lookup = FakeLookup(_lookup_result(pdf_url="https://repository.example/paper.pdf"))
    with pytest.raises(UnpaywallAcquisitionError, match="approved acquisition boundary"):
        UnpaywallDoiResolver(unsafe_lookup).resolve_dois(("10.1000/creatine",))


def test_resolver_requires_reusable_license_and_direct_pdf() -> None:
    with pytest.raises(UnpaywallAcquisitionError, match="reusable-license direct-PDF"):
        UnpaywallDoiResolver(FakeLookup(_lookup_result(pdf_url=None))).resolve_dois(
            ("10.1000/creatine",)
        )
    with pytest.raises(UnpaywallAcquisitionError, match="reusable-license direct-PDF"):
        UnpaywallDoiResolver(FakeLookup(_lookup_result(license_name="cc-by-nc-nd"))).resolve_dois(
            ("10.1000/creatine",)
        )


def test_acquisition_service_commits_pdf_and_receipt_atomically(tmp_path: Path) -> None:
    service = UnpaywallOaAcquisitionService(FakePdfTransport())
    resolved = _resolved()
    approval = UnpaywallAcquisitionApproval(
        doi=resolved.doi,
        pdf_url=resolved.pdf_url,
        license=resolved.license,
        filename=deterministic_pdf_filename(resolved.doi),
    )

    receipt = service.acquire(
        resolved=(resolved,),
        approvals=(approval,),
        output_directory=tmp_path / "papers",
    )

    assert receipt.acquired_count == 1
    assert receipt.items[0].source_host == "core.ac.uk"
    assert (tmp_path / "papers" / approval.filename).read_bytes().startswith(b"%PDF-")


def test_acquisition_service_rejects_non_pdf_and_rolls_back(tmp_path: Path) -> None:
    service = UnpaywallOaAcquisitionService(FakePdfTransport(body=b"not-a-pdf"))
    resolved = _resolved()
    approval = UnpaywallAcquisitionApproval(
        doi=resolved.doi,
        pdf_url=resolved.pdf_url,
        license=resolved.license,
        filename=deterministic_pdf_filename(resolved.doi),
    )

    with pytest.raises(UnpaywallAcquisitionError, match="not a PDF"):
        service.acquire(
            resolved=(resolved,),
            approvals=(approval,),
            output_directory=tmp_path / "papers",
        )

    assert not (tmp_path / "papers" / approval.filename).exists()


def test_execute_reconciles_current_url_and_plan_license(tmp_path: Path) -> None:
    resolver = FakeResolver(_resolved())
    service = FakeAcquisitionService()
    execution = execute_unpaywall_acquisition_plan(
        _plan(),
        resolver=resolver,
        acquisition_service=service,
        output_directory=tmp_path / "papers",
    )

    assert resolver.calls == [("10.1000/creatine",)]
    assert service.calls == 1
    assert execution.receipt.search_run_id == "run-123"
    assert execution.receipt.items[0].candidate_id == "doi:10.1000/creatine"
    assert execution.receipt.items[0].source_host == "core.ac.uk"


def test_execute_rejects_stale_url_and_missing_license(tmp_path: Path) -> None:
    with pytest.raises(GeneralQuestionUnpaywallAcquisitionError, match="did not reconcile"):
        execute_unpaywall_acquisition_plan(
            _plan(full_text_url="https://core.ac.uk/download/stale.pdf"),
            resolver=FakeResolver(_resolved()),
            acquisition_service=FakeAcquisitionService(),
            output_directory=tmp_path / "papers",
        )

    resolver = FakeResolver(_resolved())
    with pytest.raises(GeneralQuestionUnpaywallAcquisitionError, match="reusable license"):
        execute_unpaywall_acquisition_plan(
            _plan(license_name=None),
            resolver=resolver,
            acquisition_service=FakeAcquisitionService(),
            output_directory=tmp_path / "papers2",
        )
    assert resolver.calls == []


def test_persists_verified_unpaywall_acquisition_with_import_lineage(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_unpaywall_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_resolved()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )

    with database.session() as session:
        result = persist_unpaywall_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    assert result.parsed_count == 1
    assert result.persisted_count == 1
    assert result.items[0].import_item_id is not None
    with database.session() as session:
        paper = session.scalar(select(Paper))
        assert paper is not None
        assert paper.doi == "10.1000/creatine"
        import_run = session.scalar(select(ImportRun))
        assert import_run is not None
        assert import_run.validation_mode == "gqr_unpaywall_acquisition"
        snapshot = json.loads(import_run.manifest_snapshot.corpus_json_text)
        assert snapshot["kind"] == "general_question_unpaywall_import"
        import_item = session.scalar(select(ImportItem))
        assert import_item is not None
        evidence = json.loads(import_item.duplicate_evidence_json or "{}")
        assert evidence["source_host"] == "core.ac.uk"


def test_persistence_rejects_tampered_pdf(tmp_path: Path) -> None:
    database = _database(tmp_path)
    papers_dir = tmp_path / "papers"
    execution = execute_unpaywall_acquisition_plan(
        _plan(),
        resolver=FakeResolver(_resolved()),
        acquisition_service=FakeAcquisitionService(),
        output_directory=papers_dir,
    )
    filename = execution.receipt.items[0].filename
    (papers_dir / filename).write_bytes(b"tampered")

    with (
        pytest.raises(GeneralQuestionUnpaywallAcquisitionError, match="size did not match"),
        database.session() as session,
    ):
        persist_unpaywall_acquisition_execution(
            session,
            _plan(),
            execution,
            output_directory=papers_dir,
            parser=FakeParser(),
        )

    with database.session() as session:
        assert session.scalar(select(Paper)) is None
        assert session.scalar(select(ImportRun)) is None
