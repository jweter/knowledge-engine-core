"""Truth-table coverage for corpus-import run status derivation."""

import pytest

from knowledge_engine.import_runs.ingestion import _final_run_status


@pytest.mark.parametrize(
    ("imported_count", "failed_count", "needs_review_count", "expected_status"),
    [
        pytest.param(0, 0, 0, "succeeded", id="no-importable-items"),
        pytest.param(1, 0, 0, "succeeded", id="imported-only"),
        pytest.param(0, 1, 0, "failed", id="failed-only"),
        pytest.param(1, 1, 0, "partially_succeeded", id="imported-and-failed"),
        pytest.param(0, 0, 1, "needs_review", id="review-only"),
        pytest.param(1, 0, 1, "needs_review", id="imported-and-review"),
        pytest.param(0, 1, 1, "failed", id="failed-and-review"),
        pytest.param(1, 1, 1, "partially_succeeded", id="imported-failed-and-review"),
        pytest.param(5, 0, 3, "needs_review", id="counts-do-not-change-review-precedence"),
        pytest.param(5, 2, 3, "partially_succeeded", id="failure-precedence-with-imports"),
    ],
)
def test_final_run_status_truth_table(
    imported_count: int,
    failed_count: int,
    needs_review_count: int,
    expected_status: str,
) -> None:
    assert _final_run_status(imported_count, failed_count, needs_review_count) == expected_status
