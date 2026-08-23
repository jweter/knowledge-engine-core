from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
    SearchCompleteness,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)


def _record_run(tmp_path: Path, *, research_question_id: str = "rq-creatine") -> str:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/creatine",
        title="Creatine supplementation and maximal strength",
        doi="10.1000/creatine",
        publication_year=2025,
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="12345",
                title="Creatine supplementation and maximal strength",
                doi="10.1000/creatine",
                pmid="12345",
                pmcid="PMC12345",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    metadata_candidate = FederatedCandidate(
        canonical_id="doi:10.1000/metadata",
        title="Creatine metadata-only result",
        doi="10.1000/metadata",
        publication_year=2024,
        observations=(
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/metadata",
                title="Creatine metadata-only result",
                doi="10.1000/metadata",
                landing_url="https://doi.org/10.1000/metadata",
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine maximal strength", limit_per_provider=10),
        candidates=(candidate, metadata_candidate),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=2,
                latency_ms=12,
                reason=None,
            ),
            ProviderStatus(
                provider="openalex",
                outcome=ProviderOutcome.ERROR,
                attempted=True,
                result_count=0,
                latency_ms=20,
                reason="provider unavailable",
            ),
        ),
        completeness=SearchCompleteness.PARTIAL,
    )
    ledger = FederatedSearchLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 23, 3, 0, tzinfo=UTC),
        id_factory=lambda: UUID("00000000-0000-0000-0000-000000000123"),
    )
    return ledger.record(result, research_question_id=research_question_id).search_run_id


def test_request_round_trip_and_budget_validation() -> None:
    request = GeneralQuestionAcquisitionRequest.from_json(
        """{
          "schema_version": 1,
          "search_run_id": "run",
          "research_question_id": "rq",
          "candidate_ids": ["doi:10.1/a"],
          "max_candidates": 4,
          "max_full_text_acquisitions": 2,
          "max_elapsed_seconds": 60,
          "allow_metadata_only": false
        }"""
    )

    assert request.candidate_ids == ("doi:10.1/a",)
    assert request.max_candidates == 4
    assert request.max_full_text_acquisitions == 2
    assert request.allow_metadata_only is False

    with pytest.raises(ValueError, match="max_full_text_acquisitions"):
        GeneralQuestionAcquisitionRequest(
            schema_version=1,
            search_run_id="run",
            research_question_id="rq",
            candidate_ids=("one",),
            max_candidates=1,
            max_full_text_acquisitions=2,
        )


def test_plan_resolves_only_persisted_candidates_and_preserves_provider_failure(
    tmp_path: Path,
) -> None:
    run_id = _record_run(tmp_path)
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        candidate_ids=(
            "doi:10.1000/creatine",
            "doi:10.1000/metadata",
            "doi:10.1000/not-in-run",
        ),
        max_candidates=3,
        max_full_text_acquisitions=1,
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.query_text == "creatine maximal strength"
    assert plan.full_text_selected_count == 1
    assert plan.metadata_only_count == 1
    assert plan.missing_candidate_count == 1
    assert plan.provider_failures == ("openalex",)
    assert [item.disposition for item in plan.items] == [
        AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value,
        AcquisitionDisposition.METADATA_ONLY.value,
        AcquisitionDisposition.NOT_FOUND_IN_RUN.value,
    ]
    assert plan.items[0].identity is not None
    assert plan.items[0].identity.pmcid == "PMC12345"
    assert plan.items[0].selected_observation_provider == "pubmed"


def test_full_text_budget_is_enforced_deterministically(tmp_path: Path) -> None:
    run_id = _record_run(tmp_path)
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        candidate_ids=("doi:10.1000/creatine",),
        max_candidates=1,
        max_full_text_acquisitions=0,
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.full_text_selected_count == 0
    assert plan.skipped_budget_count == 1
    assert plan.items[0].disposition == AcquisitionDisposition.SKIPPED_BUDGET.value
    assert plan.items[0].reason == "full_text_acquisition_budget_exhausted"


def test_retracted_or_withdrawn_candidate_is_not_full_text_eligible(tmp_path: Path) -> None:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/retracted",
        title="Retracted creatine paper",
        doi="10.1000/retracted",
        observations=(
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/retracted",
                title="Retracted creatine paper",
                doi="10.1000/retracted",
                full_text_url="https://example.org/paper.pdf",
                license="CC BY",
                open_access=True,
                retracted=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="crossref",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
        ),
        completeness=SearchCompleteness.COMPLETE,
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("doi:10.1000/retracted",),
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.items[0].disposition == AcquisitionDisposition.METADATA_ONLY.value
    assert plan.items[0].reason == "no_eligible_open_full_text_location"


def test_request_cannot_cross_research_question_boundary(tmp_path: Path) -> None:
    run_id = _record_run(tmp_path, research_question_id="rq-original")
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-other",
        candidate_ids=("doi:10.1000/creatine",),
    )

    with pytest.raises(ValueError, match="does not match"):
        build_acquisition_plan(request, ledger_root=tmp_path)
