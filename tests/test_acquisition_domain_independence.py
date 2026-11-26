"""Unrelated-domain acquisition is independent of the GLP-1 benchmark corpus (#402).

Core's evidence corpus is reusable across questions, but a populated golden corpus (the
GLP-1/body-weight benchmark) must never block, reorder or mutate acquisition planning for
a question from a completely different domain. These tests pin that: new candidates are
planned exactly as they would be against an empty corpus, an already-indexed duplicate is
reused rather than re-queued, and planning never writes to the corpus.
"""

from __future__ import annotations

from pathlib import Path

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
    GeneralQuestionAcquisitionPlan,
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.models import Base, Paper

_GLP1_DOIS = (
    "10.1056/NEJMoa2032183",  # STEP 1 style golden-corpus record
    "10.1056/NEJMoa2206038",
    "10.1056/NEJMoa2307563",
)
_MATERIALS_QUESTION = "perovskite solar cell thermal degradation mechanisms"
_NEW_ONE = "doi:10.9999/materials-1"
_NEW_TWO = "doi:10.9999/materials-2"
_DUPLICATE = f"doi:{_GLP1_DOIS[0].lower()}"


def _candidate(canonical_id: str, doi: str, title: str, pmc: str) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=canonical_id,
        title=title,
        doi=doi,
        publication_year=2025,
        observations=(
            ProviderObservation(
                provider="pubmed",
                provider_id=pmc,
                title=title,
                doi=doi,
                pmid=pmc.removeprefix("PMC"),
                pmcid=pmc,
                full_text_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/pdf/test.pdf",
                license="CC BY 4.0",
                open_access=True,
            ),
        ),
    )


def _record_materials_run(ledger_root: Path) -> str:
    result = FederatedSearchResult(
        query=DiscoveryQuery(text=_MATERIALS_QUESTION, limit_per_provider=10),
        candidates=(
            _candidate(
                _NEW_ONE, "10.9999/materials-1", "Thermal degradation of perovskites", "PMC9001"
            ),
            _candidate(
                _NEW_TWO, "10.9999/materials-2", "Encapsulation of perovskite cells", "PMC9002"
            ),
            _candidate(
                _DUPLICATE,
                _GLP1_DOIS[0].lower(),
                "A candidate that is already in the corpus",
                "PMC9003",
            ),
        ),
        provider_statuses=(
            ProviderStatus(
                provider="pubmed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=3,
                latency_ms=5,
                reason=None,
            ),
        ),
    )
    return (
        FederatedSearchLedger(ledger_root)
        .record(result, research_question_id="rq-materials")
        .search_run_id
    )


def _request(run_id: str) -> GeneralQuestionAcquisitionRequest:
    return GeneralQuestionAcquisitionRequest(
        schema_version=1,
        search_run_id=run_id,
        research_question_id="rq-materials",
        candidate_ids=(_NEW_ONE, _NEW_TWO, _DUPLICATE),
        max_candidates=3,
        max_full_text_acquisitions=2,
    )


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _golden_papers() -> list[Paper]:
    return [
        Paper(
            title=f"GLP-1 golden record {index}",
            doi=doi,
            source_path=f"glp1-{index}.pdf",
            content_hash=f"{index}" * 64,
            publication_year=2021,
            page_count=10,
            word_count=5000,
        )
        for index, doi in enumerate(_GLP1_DOIS, start=1)
    ]


def _corpus_snapshot(session: Session) -> list[tuple[int, str | None, str, str]]:
    return [
        (paper.id, paper.doi, paper.content_hash, paper.title)
        for paper in session.query(Paper).order_by(Paper.id).all()
    ]


def _dispositions(plan: GeneralQuestionAcquisitionPlan) -> list[tuple[str, str]]:
    return [(item.candidate_id, item.disposition) for item in plan.items]


def test_new_domain_candidates_are_planned_despite_a_populated_golden_corpus(
    tmp_path: Path,
) -> None:
    run_id = _record_materials_run(tmp_path)

    with _session() as session:
        session.add_all(_golden_papers())
        session.flush()

        plan = build_acquisition_plan(_request(run_id), ledger_root=tmp_path, session=session)

    assert plan.query_text == _MATERIALS_QUESTION
    assert dict(_dispositions(plan)) == {
        _NEW_ONE: AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value,
        _NEW_TWO: AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value,
        _DUPLICATE: AcquisitionDisposition.ALREADY_INDEXED.value,
    }
    assert plan.full_text_selected_count == 2
    assert plan.already_indexed_count == 1
    assert plan.missing_candidate_count == 0


def test_corpus_presence_does_not_change_how_new_candidates_are_planned(tmp_path: Path) -> None:
    run_id = _record_materials_run(tmp_path)

    with _session() as empty:
        against_empty = build_acquisition_plan(
            _request(run_id), ledger_root=tmp_path, session=empty
        )
    with _session() as populated:
        populated.add_all(_golden_papers())
        populated.flush()
        against_golden = build_acquisition_plan(
            _request(run_id), ledger_root=tmp_path, session=populated
        )

    new_only = {_NEW_ONE, _NEW_TWO}
    empty_items = {i.candidate_id: i for i in against_empty.items if i.candidate_id in new_only}
    golden_items = {i.candidate_id: i for i in against_golden.items if i.candidate_id in new_only}
    for candidate_id in new_only:
        assert empty_items[candidate_id].disposition == golden_items[candidate_id].disposition
        assert (
            empty_items[candidate_id].acquisition_route
            == golden_items[candidate_id].acquisition_route
        )
        assert empty_items[candidate_id].identity == golden_items[candidate_id].identity
    # With an empty corpus the duplicate is just a third candidate competing for the two
    # full-text slots, so the budget skips it; reuse of an indexed paper is what frees a slot.
    assert dict(_dispositions(against_empty))[_DUPLICATE] == (
        AcquisitionDisposition.SKIPPED_BUDGET.value
    )
    assert against_empty.full_text_selected_count == 2


def test_an_already_indexed_duplicate_is_reused_and_costs_no_full_text_budget(
    tmp_path: Path,
) -> None:
    run_id = _record_materials_run(tmp_path)

    with _session() as session:
        golden = _golden_papers()
        session.add_all(golden)
        session.flush()

        plan = build_acquisition_plan(_request(run_id), ledger_root=tmp_path, session=session)

        duplicate = next(item for item in plan.items if item.candidate_id == _DUPLICATE)
        assert duplicate.existing_paper_id == golden[0].id
        assert duplicate.reason == "candidate_doi_matches_existing_indexed_paper"
        # Budget of two full-text slots is fully available to the two genuinely new papers.
        assert plan.full_text_selected_count == 2


def test_planning_never_mutates_the_golden_corpus(tmp_path: Path) -> None:
    run_id = _record_materials_run(tmp_path)

    with _session() as session:
        session.add_all(_golden_papers())
        session.flush()
        before = _corpus_snapshot(session)

        build_acquisition_plan(_request(run_id), ledger_root=tmp_path, session=session)

        assert not session.new
        assert not session.dirty
        assert not session.deleted
        assert _corpus_snapshot(session) == before
        assert len(before) == len(_GLP1_DOIS)


def test_planning_is_deterministic_across_repeated_calls(tmp_path: Path) -> None:
    run_id = _record_materials_run(tmp_path)

    with _session() as session:
        session.add_all(_golden_papers())
        session.flush()
        first = build_acquisition_plan(_request(run_id), ledger_root=tmp_path, session=session)
        second = build_acquisition_plan(_request(run_id), ledger_root=tmp_path, session=session)

    assert _dispositions(first) == _dispositions(second)
    assert first.full_text_selected_count == second.full_text_selected_count
