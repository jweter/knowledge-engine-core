from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.models import Base, Paper


def _in_memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _record_run(tmp_path: Path, *, research_question_id: str | None = "rq-creatine") -> str:
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
                outcome=ProviderOutcome.FAILED,
                attempted=True,
                result_count=0,
                latency_ms=20,
                reason="provider unavailable",
            ),
        ),
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


def test_restrictive_license_is_not_full_text_eligible(tmp_path: Path) -> None:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/nc-nd",
        title="Non-commercial no-derivatives paper",
        doi="10.1000/nc-nd",
        observations=(
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/nc-nd",
                title="Non-commercial no-derivatives paper",
                doi="10.1000/nc-nd",
                full_text_url="https://example.org/paper.pdf",
                license="CC BY-NC-ND 4.0",
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
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("doi:10.1000/nc-nd",),
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.items[0].disposition == AcquisitionDisposition.METADATA_ONLY.value
    assert plan.items[0].reason == "no_eligible_open_full_text_location"


def test_retraction_reported_by_a_different_observation_blocks_eligibility(
    tmp_path: Path,
) -> None:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/cross-provider-retraction",
        title="Cross-provider retraction paper",
        doi="10.1000/cross-provider-retraction",
        observations=(
            # This is the observation `_best_acquisition_observation` selects
            # (PMCID + full text + OA) and it does not itself report retracted.
            ProviderObservation(
                provider="pubmed",
                provider_id="99999",
                title="Cross-provider retraction paper",
                doi="10.1000/cross-provider-retraction",
                pmcid="PMC99999",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC99999/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
            # A different provider's observation of the same work reports the
            # retraction. The candidate as a whole must still be blocked.
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/cross-provider-retraction",
                title="Cross-provider retraction paper",
                doi="10.1000/cross-provider-retraction",
                retracted=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
            ProviderStatus(
                provider="crossref",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
        ),
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("doi:10.1000/cross-provider-retraction",),
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.items[0].disposition == AcquisitionDisposition.METADATA_ONLY.value
    assert plan.items[0].reason == "no_eligible_open_full_text_location"


def test_run_without_a_bound_research_question_id_is_rejected(tmp_path: Path) -> None:
    run_id = _record_run(tmp_path, research_question_id=None)
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        candidate_ids=("doi:10.1000/creatine",),
    )

    with pytest.raises(ValueError, match="does not match"):
        build_acquisition_plan(request, ledger_root=tmp_path)


def test_already_indexed_candidate_is_reported_instead_of_reacquired(tmp_path: Path) -> None:
    run_id = _record_run(tmp_path)
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        candidate_ids=("doi:10.1000/creatine",),
    )

    with _in_memory_session() as session:
        existing = Paper(
            title="Creatine supplementation and maximal strength",
            doi="10.1000/creatine",
            source_path="creatine.pdf",
            content_hash="a" * 64,
            publication_year=2025,
            page_count=1,
            word_count=10,
        )
        session.add(existing)
        session.flush()

        plan = build_acquisition_plan(request, ledger_root=tmp_path, session=session)

        assert plan.items[0].disposition == AcquisitionDisposition.ALREADY_INDEXED.value
        assert plan.items[0].existing_paper_id == existing.id
        assert plan.items[0].reason == "candidate_doi_matches_existing_indexed_paper"
        assert plan.already_indexed_count == 1
        assert plan.full_text_selected_count == 0
        assert plan.resolved_candidate_count == 1


def test_already_indexed_candidate_does_not_consume_full_text_budget(tmp_path: Path) -> None:
    # Two candidates are each independently full-text eligible, but only one
    # full-text acquisition is budgeted. The first is already indexed; if
    # that consumed the full-text budget slot, the genuinely new second
    # candidate would be starved (skipped_budget) even though nothing new
    # actually needed to be acquired for the first.
    already_indexed_candidate = FederatedCandidate(
        canonical_id="doi:10.1000/creatine",
        title="Creatine supplementation and maximal strength",
        doi="10.1000/creatine",
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="12345",
                title="Creatine supplementation and maximal strength",
                doi="10.1000/creatine",
                pmcid="PMC12345",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    new_candidate = FederatedCandidate(
        canonical_id="doi:10.1000/new-creatine-trial",
        title="A new creatine trial",
        doi="10.1000/new-creatine-trial",
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="67890",
                title="A new creatine trial",
                doi="10.1000/new-creatine-trial",
                pmcid="PMC67890",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC67890/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine", limit_per_provider=10),
        candidates=(already_indexed_candidate, new_candidate),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=2,
                latency_ms=1,
                reason=None,
            ),
        ),
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("doi:10.1000/creatine", "doi:10.1000/new-creatine-trial"),
        max_candidates=2,
        max_full_text_acquisitions=1,
    )

    with _in_memory_session() as session:
        existing = Paper(
            title="Creatine supplementation and maximal strength",
            doi="10.1000/creatine",
            source_path="creatine.pdf",
            content_hash="a" * 64,
            publication_year=2025,
            page_count=1,
            word_count=10,
        )
        session.add(existing)
        session.flush()

        plan = build_acquisition_plan(request, ledger_root=tmp_path, session=session)

    assert [item.disposition for item in plan.items] == [
        AcquisitionDisposition.ALREADY_INDEXED.value,
        AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value,
    ]
    assert plan.already_indexed_count == 1
    assert plan.full_text_selected_count == 1


def test_already_indexed_candidate_matches_by_pmid_when_no_doi(tmp_path: Path) -> None:
    candidate = FederatedCandidate(
        canonical_id="pmid:99999",
        title="A creatine trial known only by PMID",
        doi=None,
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id="99999",
                title="A creatine trial known only by PMID",
                pmid="99999",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC99999/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
        ),
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("pmid:99999",),
    )

    with _in_memory_session() as session:
        existing = Paper(
            title="A creatine trial known only by PMID",
            doi=None,
            pmid="99999",
            source_path="pmid-only.pdf",
            content_hash="b" * 64,
            page_count=1,
            word_count=10,
        )
        session.add(existing)
        session.flush()

        plan = build_acquisition_plan(request, ledger_root=tmp_path, session=session)

        assert plan.items[0].disposition == AcquisitionDisposition.ALREADY_INDEXED.value
        assert plan.items[0].existing_paper_id == existing.id
        assert plan.items[0].reason == "candidate_pmid_matches_existing_indexed_paper"
        assert plan.already_indexed_count == 1


def test_already_indexed_candidate_matches_by_arxiv_id_when_no_doi_or_pmid(
    tmp_path: Path,
) -> None:
    candidate = FederatedCandidate(
        canonical_id="arxiv:2301.12345",
        title="A preprint known only by arXiv ID",
        doi=None,
        observations=(
            ProviderObservation(
                provider="arxiv",
                provider_id="2301.12345",
                title="A preprint known only by arXiv ID",
                arxiv_id="2301.12345",
                full_text_url="https://arxiv.org/pdf/2301.12345",
                open_access=True,
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="creatine", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="arxiv",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
        ),
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("arxiv:2301.12345",),
    )

    with _in_memory_session() as session:
        existing = Paper(
            title="A preprint known only by arXiv ID",
            doi=None,
            arxiv_id="2301.12345",
            source_path="arxiv-only.pdf",
            content_hash="c" * 64,
            page_count=1,
            word_count=10,
        )
        session.add(existing)
        session.flush()

        plan = build_acquisition_plan(request, ledger_root=tmp_path, session=session)

        assert plan.items[0].disposition == AcquisitionDisposition.ALREADY_INDEXED.value
        assert plan.items[0].existing_paper_id == existing.id
        assert plan.items[0].reason == "candidate_arxiv_id_matches_existing_indexed_paper"
        assert plan.already_indexed_count == 1


def test_no_session_preserves_prior_snapshot_only_behavior(tmp_path: Path) -> None:
    run_id = _record_run(tmp_path)
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-creatine",
        candidate_ids=("doi:10.1000/creatine",),
    )

    plan = build_acquisition_plan(request, ledger_root=tmp_path)

    assert plan.items[0].disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
    assert plan.items[0].existing_paper_id is None
    assert plan.already_indexed_count == 0


def test_already_indexed_lookup_requires_some_known_identity(tmp_path: Path) -> None:
    candidate = FederatedCandidate(
        canonical_id="no-doi:local-1",
        title="A candidate without any DOI, PMID, or arXiv ID",
        doi=None,
        observations=(
            ProviderObservation(
                provider="arxiv",
                provider_id="local-1",
                title="A candidate without any DOI, PMID, or arXiv ID",
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="no doi", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="arxiv",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            ),
        ),
    )
    ledger = FederatedSearchLedger(tmp_path)
    run_id = ledger.record(result, research_question_id="rq").search_run_id
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq",
        candidate_ids=("no-doi:local-1",),
    )

    with _in_memory_session() as session:
        plan = build_acquisition_plan(request, ledger_root=tmp_path, session=session)

    assert plan.items[0].disposition != AcquisitionDisposition.ALREADY_INDEXED.value
    assert plan.already_indexed_count == 0


@pytest.mark.parametrize(
    ("provider", "pmcid", "full_text_url", "expected_route"),
    (
        (
            "pubmed",
            "PMC777",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC777/pdf/test.pdf",
            AcquisitionRoute.PMC_OA,
        ),
        (
            "europepmc",
            None,
            "https://europepmc.org/articles/EPMC777?pdf=render",
            AcquisitionRoute.EUROPE_PMC_OA,
        ),
        (
            "core",
            None,
            "https://core.ac.uk/download/777.pdf",
            AcquisitionRoute.CORE,
        ),
        (
            "unpaywall",
            None,
            "https://repository.example/paper.pdf",
            AcquisitionRoute.UNPAYWALL,
        ),
    ),
)
def test_supported_full_text_routes_are_explicit(
    tmp_path: Path,
    provider: str,
    pmcid: str | None,
    full_text_url: str,
    expected_route: AcquisitionRoute,
) -> None:
    observation = ProviderObservation(
        provider=provider,
        provider_id="route-777",
        title="Routed paper",
        doi="10.1000/routed",
        pmcid=pmcid,
        full_text_url=full_text_url,
        license="CC BY 4.0",
        open_access=True,
    )
    plan = _plan_for_observations(tmp_path, (observation,))

    assert plan.items[0].disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
    assert plan.items[0].acquisition_route == expected_route.value


def test_arbitrary_oa_url_without_supported_route_degrades_to_metadata_only(
    tmp_path: Path,
) -> None:
    observation = ProviderObservation(
        provider="crossref",
        provider_id="10.1000/unsupported",
        title="Unsupported direct URL",
        doi="10.1000/unsupported",
        full_text_url="https://publisher.example/paper.pdf",
        license="CC BY 4.0",
        open_access=True,
    )

    plan = _plan_for_observations(tmp_path, (observation,))

    assert plan.items[0].disposition == AcquisitionDisposition.METADATA_ONLY.value
    assert plan.items[0].acquisition_route is None
    assert plan.items[0].full_text_url is None


def test_pmc_route_wins_over_less_authoritative_supported_location(tmp_path: Path) -> None:
    observations = (
        ProviderObservation(
            provider="unpaywall",
            provider_id="10.1000/routed",
            title="Routed paper",
            doi="10.1000/routed",
            full_text_url="https://repository.example/paper.pdf",
            license="CC BY 4.0",
            open_access=True,
        ),
        ProviderObservation(
            provider="pubmed",
            provider_id="777",
            title="Routed paper",
            doi="10.1000/routed",
            pmcid="PMC777",
            full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC777/pdf/test.pdf",
            license="CC BY 4.0",
            open_access=True,
        ),
    )

    plan = _plan_for_observations(tmp_path, observations)

    assert plan.items[0].acquisition_route == AcquisitionRoute.PMC_OA.value
    assert plan.items[0].selected_observation_provider == "pubmed"


def _plan_for_observations(
    tmp_path: Path,
    observations: tuple[ProviderObservation, ...],
) -> GeneralQuestionAcquisitionPlan:
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/routed",
        title="Routed paper",
        doi="10.1000/routed",
        observations=observations,
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="routing", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=tuple(
            ProviderStatus(
                provider=provider,
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=1,
                reason=None,
            )
            for provider in sorted({item.provider for item in observations})
        ),
    )
    run_id = (
        FederatedSearchLedger(tmp_path)
        .record(result, research_question_id="rq-routing")
        .search_run_id
    )
    request = GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-routing",
        candidate_ids=("doi:10.1000/routed",),
    )
    return build_acquisition_plan(request, ledger_root=tmp_path)
