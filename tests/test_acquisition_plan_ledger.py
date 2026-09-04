from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.acquisition_plan_ledger import AcquisitionPlanLedger
from knowledge_engine.general_question_acquisition import GeneralQuestionAcquisitionPlan

_PLAN_ID = UUID("00000000-0000-0000-0000-0000000004a1")
_OTHER_PLAN_ID = UUID("00000000-0000-0000-0000-0000000004a2")


def _plan(
    *,
    search_run_id: str = "00000000-0000-0000-0000-000000000001",
    research_question_id: str = "rq-1",
    duration_ms: int = 12,
) -> GeneralQuestionAcquisitionPlan:
    return GeneralQuestionAcquisitionPlan(
        schema_version=1,
        search_run_id=search_run_id,
        research_question_id=research_question_id,
        query_text="glp-1 weight loss",
        requested_candidate_count=5,
        resolved_candidate_count=4,
        already_indexed_count=1,
        full_text_selected_count=2,
        metadata_only_count=1,
        skipped_budget_count=0,
        missing_candidate_count=1,
        provider_failures=("crossref",),
        items=(),
        duration_ms=duration_ms,
    )


def test_record_and_load_round_trip(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(
        tmp_path,
        clock=lambda: datetime(2026, 9, 3, 20, 0, tzinfo=UTC),
        id_factory=lambda: _PLAN_ID,
    )

    recorded = ledger.record(_plan())
    loaded = ledger.load(str(_PLAN_ID))

    assert loaded == recorded
    assert loaded.search_run_id == "00000000-0000-0000-0000-000000000001"
    assert loaded.research_question_id == "rq-1"
    assert loaded.already_indexed_count == 1
    assert loaded.full_text_selected_count == 2
    assert loaded.metadata_only_count == 1
    assert loaded.skipped_budget_count == 0
    assert loaded.missing_candidate_count == 1
    assert loaded.provider_failures == ("crossref",)
    assert loaded.duration_ms == 12

    payload = json.loads((tmp_path / f"{_PLAN_ID}.json").read_text(encoding="utf-8"))
    assert payload["already_indexed_count"] == 1
    assert payload["provider_failures"] == ["crossref"]


def test_record_rejects_naive_clock(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(tmp_path, clock=lambda: datetime(2026, 9, 3, 20, 0))

    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.record(_plan())


def test_write_once_refuses_to_overwrite_an_existing_record(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(
        tmp_path,
        clock=lambda: datetime(2026, 9, 3, 20, 0, tzinfo=UTC),
        id_factory=lambda: _PLAN_ID,
    )

    ledger.record(_plan())
    with pytest.raises(FileExistsError):
        ledger.record(_plan())


def test_load_raises_on_malformed_json(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(tmp_path)
    (tmp_path / f"{_PLAN_ID}.json").write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed"):
        ledger.load(str(_PLAN_ID))


def test_list_by_search_run_id_returns_matches_newest_first(tmp_path: Path) -> None:
    ids = iter([_PLAN_ID, _OTHER_PLAN_ID])
    clocks = iter(
        [
            datetime(2026, 9, 3, 20, 0, tzinfo=UTC),
            datetime(2026, 9, 3, 21, 0, tzinfo=UTC),
        ]
    )
    ledger = AcquisitionPlanLedger(
        tmp_path, clock=lambda: next(clocks), id_factory=lambda: next(ids)
    )

    ledger.record(_plan(search_run_id="run-a"))
    ledger.record(_plan(search_run_id="run-a"))

    matches = ledger.list_by_search_run_id("run-a")

    assert [record.acquisition_plan_id for record in matches] == [
        str(_OTHER_PLAN_ID),
        str(_PLAN_ID),
    ]


def test_list_by_search_run_id_filters_out_other_runs(tmp_path: Path) -> None:
    ids = iter([_PLAN_ID, _OTHER_PLAN_ID])
    ledger = AcquisitionPlanLedger(tmp_path, id_factory=lambda: next(ids))

    ledger.record(_plan(search_run_id="run-a"))
    ledger.record(_plan(search_run_id="run-b"))

    matches = ledger.list_by_search_run_id("run-a")

    assert len(matches) == 1
    assert matches[0].search_run_id == "run-a"


def test_list_by_search_run_id_returns_empty_tuple_when_root_missing(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(tmp_path / "does-not-exist")

    assert ledger.list_by_search_run_id("run-a") == ()


def test_list_by_search_run_id_rejects_blank_id(tmp_path: Path) -> None:
    ledger = AcquisitionPlanLedger(tmp_path)

    with pytest.raises(ValueError, match="non-blank"):
        ledger.list_by_search_run_id("   ")
