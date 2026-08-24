from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_engine.general_question_acquisition import (
    AcquisitionIdentity,
    AcquisitionPlanItem,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.general_question_pmc_acquisition import (
    GeneralQuestionPmcAcquisitionError,
    execute_pmc_acquisition_plan,
)
from knowledge_engine.pmc_acquisition import AcquisitionReceipt, AcquisitionReceiptItem
from knowledge_engine.pubmed_discovery import PubmedCandidate


class FakeResolver:
    def __init__(self, candidate: PubmedCandidate) -> None:
        self.candidate = candidate
        self.calls: list[tuple[str, ...]] = []

    def resolve_pmids(self, pmids: tuple[str, ...]) -> tuple[PubmedCandidate, ...]:
        self.calls.append(pmids)
        return (self.candidate,)


class FakeAcquisitionService:
    def __init__(self) -> None:
        self.expected_count: int | None = None
        self.candidates: dict[str, object] | None = None
        self.approvals: dict[str, object] | None = None

    def acquire(
        self,
        *,
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
        expected_count: int | None = None,
    ) -> AcquisitionReceipt:
        self.expected_count = expected_count
        self.candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        self.approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "PMC12345.pdf").write_bytes(b"%PDF-1.7\nbody")
        return AcquisitionReceipt(
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


def _plan(*, route: str | None = AcquisitionRoute.PMC_OA.value) -> GeneralQuestionAcquisitionPlan:
    item = AcquisitionPlanItem(
        candidate_id="doi:10.1000/creatine",
        title="Creatine trial",
        disposition="eligible_full_text",
        identity=AcquisitionIdentity(
            canonical_id="doi:10.1000/creatine",
            doi="10.1000/creatine",
            pmid="12345",
            pmcid=None,
            arxiv_id=None,
            openalex_id=None,
            semantic_scholar_id=None,
        ),
        selected_observation_provider="pubmed",
        acquisition_route=route,
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


def _candidate(*, license_name: str | None = "CC BY 4.0") -> PubmedCandidate:
    return PubmedCandidate(
        pmid="12345",
        title="Creatine trial",
        abstract=None,
        authors=(),
        publication_year=2025,
        venue=None,
        doi="10.1000/creatine",
        pmcid="PMC12345",
        open_access=True,
        license=license_name,
        pdf_url="https://pmc-oa-opendata.s3.amazonaws.com/PMC12345.1/PMC12345.1.pdf",
        xml_url=None,
        status="oa_verified",
        metadata_source="pubmed_efetch",
        pmcid_source="pmc_id_converter",
        oa_source="pmc_cloud_service",
    )


def test_executes_exact_pmc_route_and_preserves_plan_provenance(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    result = execute_pmc_acquisition_plan(
        _plan(),
        resolver=resolver,
        acquisition_service=service,
        output_directory=tmp_path / "papers",
    )

    assert resolver.calls == [("12345",)]
    assert service.expected_count == 1
    assert service.approvals is not None
    assert service.approvals["selected_count"] == 1
    assert result.receipt.search_run_id == "run-123"
    assert result.receipt.research_question_id == "rq-creatine"
    assert result.receipt.items[0].candidate_id == "doi:10.1000/creatine"
    assert result.receipt.items[0].pmcid == "PMC12345"
    assert result.acquisition_receipt.items[0].filename == "PMC12345.pdf"


def test_rejects_plan_without_pmc_route_before_resolution(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate())
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionPmcAcquisitionError, match="no eligible PMC"):
        execute_pmc_acquisition_plan(
            _plan(route=AcquisitionRoute.UNPAYWALL.value),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert resolver.calls == []
    assert service.expected_count is None


def test_rejects_resolved_candidate_without_reusable_license(tmp_path: Path) -> None:
    resolver = FakeResolver(_candidate(license_name=None))
    service = FakeAcquisitionService()

    with pytest.raises(GeneralQuestionPmcAcquisitionError, match="reusable full-text"):
        execute_pmc_acquisition_plan(
            _plan(),
            resolver=resolver,
            acquisition_service=service,
            output_directory=tmp_path / "papers",
        )

    assert service.expected_count is None
