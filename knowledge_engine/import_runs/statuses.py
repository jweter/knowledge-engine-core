"""Typed import-run status derivation and accounting invariants."""

from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    """Operational result of an import run."""

    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
    IMPORT_BLOCKED = "import_blocked"


class ReviewStatus(StrEnum):
    """Human-review disposition of an import run."""

    CLEAR = "clear"
    NEEDS_REVIEW = "needs_review"


def derive_run_status(*, imported: int, failed: int) -> RunStatus:
    """Derive operational status without conflating review disposition."""

    if imported < 0 or failed < 0:
        raise ValueError("Import counters cannot be negative")
    if failed == 0:
        return RunStatus.SUCCEEDED
    if imported > 0:
        return RunStatus.PARTIALLY_SUCCEEDED
    return RunStatus.FAILED


def derive_review_status(*, needs_review: int) -> ReviewStatus:
    """Derive review disposition independently from execution status."""

    if needs_review < 0:
        raise ValueError("Review counters cannot be negative")
    if needs_review > 0:
        return ReviewStatus.NEEDS_REVIEW
    return ReviewStatus.CLEAR


@dataclass(frozen=True, slots=True)
class ImportCounts:
    """Mutually exclusive terminal item counts for one completed run."""

    total: int
    imported: int
    failed: int
    skipped: int
    needs_review: int
    warnings: int = 0

    def __post_init__(self) -> None:
        values = (
            self.total,
            self.imported,
            self.failed,
            self.skipped,
            self.needs_review,
            self.warnings,
        )
        if any(value < 0 for value in values):
            raise ValueError("Import counters cannot be negative")

        terminal_total = self.imported + self.failed + self.skipped + self.needs_review
        if terminal_total != self.total:
            raise ValueError("Every item must have exactly one terminal outcome")

    @property
    def run_status(self) -> RunStatus:
        return derive_run_status(imported=self.imported, failed=self.failed)

    @property
    def review_status(self) -> ReviewStatus:
        return derive_review_status(needs_review=self.needs_review)
