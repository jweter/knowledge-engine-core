"""Truth-table coverage for persisted import run status derivation."""

import pytest

from knowledge_engine.import_runs.ingestion import _final_run_status


@pytest.mark.parametrize(
    ("imported_count", "failed_count", "needs_review_count", "expected_status"),
    [
        (0, 0, 0, "succeeded"),
        (1, 0, 0, "succeeded"),
        (0, 1, 0, "failed"),
        (1, 1, 0, "partially_succeeded"),
        (0, 0, 1, "succeeded"),
        (1, 0, 1, "succeeded"),
        (0, 1, 1, "failed"),
        (1, 1, 1, "partially_succeeded"),
        (3, 0, 2, "succeeded"),
        (3, 2, 0, "partially_succeeded"),
    ],
)
def test_final_run_status_truth_table(
    imported_count: int,
    failed_count: int,
    needs_review_count: int,
    expected_status: str,
) -> None:
    assert _final_run_status(imported_count, failed_count, needs_review_count) == expected_status
