from __future__ import annotations

import json
from pathlib import Path

from knowledge_engine.general_question_acquisition_failures import (
    FAILURE_RECORD_SCHEMA_VERSION,
    clear_acquisition_failure_record,
    failure_record_path,
    write_acquisition_failure_record,
)


def test_failure_record_path_is_derived_alongside_the_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"

    assert failure_record_path(receipt) == tmp_path / "receipt.json.failure.json"


def test_write_acquisition_failure_record_persists_sanitized_fields(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"

    path = write_acquisition_failure_record(
        receipt,
        search_run_id="run-1",
        research_question_id="rq-1",
        acquisition_route="pmc_oa",
        stage="acquire",
        reason="A planned PMC candidate lacks verified reusable full-text evidence.",
        candidate_ids=("doi:10.1000/a", "doi:10.1000/b"),
    )

    assert path == failure_record_path(receipt)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == FAILURE_RECORD_SCHEMA_VERSION
    assert payload["search_run_id"] == "run-1"
    assert payload["research_question_id"] == "rq-1"
    assert payload["acquisition_route"] == "pmc_oa"
    assert payload["stage"] == "acquire"
    assert payload["reason"] == (
        "A planned PMC candidate lacks verified reusable full-text evidence."
    )
    assert payload["candidate_ids"] == ["doi:10.1000/a", "doi:10.1000/b"]
    assert payload["occurred_at"]


def test_write_acquisition_failure_record_is_best_effort_on_unwritable_path(
    tmp_path: Path,
) -> None:
    # A receipt path whose parent is a file (not a directory) cannot be created;
    # writing the failure record must not raise and must not mask the caller's
    # original error.
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("x", encoding="utf-8")
    receipt = blocked_parent / "receipt.json"

    write_acquisition_failure_record(
        receipt,
        search_run_id="run-1",
        research_question_id="rq-1",
        acquisition_route="core",
        stage="persist",
        reason="Unexpected error: RuntimeError.",
        candidate_ids=("doi:10.1000/a",),
    )


def test_clear_acquisition_failure_record_removes_a_stale_record(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    write_acquisition_failure_record(
        receipt,
        search_run_id="run-1",
        research_question_id="rq-1",
        acquisition_route="unpaywall",
        stage="acquire",
        reason="Planned Unpaywall identifiers could not be resolved.",
        candidate_ids=("doi:10.1000/a",),
    )
    assert failure_record_path(receipt).exists()

    clear_acquisition_failure_record(receipt)

    assert not failure_record_path(receipt).exists()


def test_clear_acquisition_failure_record_is_a_noop_when_nothing_to_clear(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "receipt.json"

    clear_acquisition_failure_record(receipt)

    assert not failure_record_path(receipt).exists()
