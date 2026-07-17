"""Truth tables for independent execution and review status domains."""

import pytest

from knowledge_engine.import_runs.statuses import (
    ImportCounts,
    ReviewStatus,
    RunStatus,
    derive_review_status,
    derive_run_status,
)


@pytest.mark.parametrize(
    ("imported", "failed", "expected"),
    [
        pytest.param(0, 0, RunStatus.SUCCEEDED, id="nothing-failed"),
        pytest.param(10, 0, RunStatus.SUCCEEDED, id="all-imported"),
        pytest.param(8, 2, RunStatus.PARTIALLY_SUCCEEDED, id="mixed-result"),
        pytest.param(0, 10, RunStatus.FAILED, id="all-failed"),
    ],
)
def test_execution_status_truth_table(
    imported: int,
    failed: int,
    expected: RunStatus,
) -> None:
    assert derive_run_status(imported=imported, failed=failed) is expected


@pytest.mark.parametrize(
    ("needs_review", "expected"),
    [
        pytest.param(0, ReviewStatus.CLEAR, id="clear"),
        pytest.param(1, ReviewStatus.NEEDS_REVIEW, id="one-review"),
        pytest.param(100, ReviewStatus.NEEDS_REVIEW, id="many-reviews"),
    ],
)
def test_review_status_truth_table(
    needs_review: int,
    expected: ReviewStatus,
) -> None:
    assert derive_review_status(needs_review=needs_review) is expected


def test_import_counts_require_exact_terminal_accounting() -> None:
    counts = ImportCounts(
        total=10,
        imported=6,
        failed=1,
        skipped=2,
        needs_review=1,
        warnings=4,
    )

    assert counts.run_status is RunStatus.PARTIALLY_SUCCEEDED
    assert counts.review_status is ReviewStatus.NEEDS_REVIEW


@pytest.mark.parametrize(
    "kwargs",
    [
        {"total": 10, "imported": 8, "failed": 1, "skipped": 0, "needs_review": 0},
        {"total": 1, "imported": -1, "failed": 1, "skipped": 1, "needs_review": 0},
    ],
)
def test_import_counts_reject_invalid_accounting(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        ImportCounts(**kwargs)
