from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Decision(StrEnum):
    READY = "ready"
    READY_WITH_CONDITIONS = "ready_with_conditions"
    NOT_READY = "not_ready"


class DimensionStatus(StrEnum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    FAIL = "fail"
    UNKNOWN = "unknown"


class MeasurementSource(StrEnum):
    PERSISTED = "persisted"
    OPERATOR = "operator"
    DERIVED = "derived"
    POLICY = "policy"


@dataclass(frozen=True)
class ScaleMeasurements:
    declared_sources: int
    persisted_items: int
    imported_items: int
    duplicate_items: int
    skipped_items: int
    failed_items: int
    review_required_items: int
    persisted_issues: int
    papers_after_fresh: int
    papers_after_resume: int | None
    resume_items: int | None
    resume_linked_items: int | None
    unexpected_resume_papers: int | None
    fresh_elapsed_seconds: float | None
    resume_elapsed_seconds: float | None
    database_bytes_before: int | None
    database_bytes_after: int | None
    prohibited_artifacts_found: bool
    private_path_leak_found: bool


@dataclass(frozen=True)
class ReadinessThresholds:
    proposed_next_corpus_size: int = 500
    maximum_failure_rate: float = 0.01
    maximum_issue_rate: float = 0.02
    minimum_import_rate: float | None = None
    maximum_bytes_per_paper: float | None = None
    require_storage_measurement: bool = True


@dataclass(frozen=True)
class DimensionResult:
    status: DimensionStatus
    explanation: str


@dataclass(frozen=True)
class ScaleAssessment:
    decision: Decision
    correctness: DimensionResult
    recovery: DimensionResult
    reliability: DimensionResult
    performance: DimensionResult
    storage: DimensionResult
    privacy: DimensionResult
    imported_per_second: float | None
    resume_items_per_second: float | None
    database_growth_bytes: int | None
    bytes_per_imported_paper: float | None
    failure_rate: float
    issue_rate: float
    proposed_next_corpus_size: int


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _timed_rate(count: int, seconds: float | None) -> float | None:
    if seconds is None or seconds <= 0:
        return None
    return count / seconds


def _database_growth(before: int | None, after: int | None) -> int | None:
    if before is None or after is None:
        return None
    return after - before


def _counts_are_valid(measurements: ScaleMeasurements) -> bool:
    required_counts = (
        measurements.declared_sources,
        measurements.persisted_items,
        measurements.imported_items,
        measurements.duplicate_items,
        measurements.skipped_items,
        measurements.failed_items,
        measurements.review_required_items,
        measurements.persisted_issues,
        measurements.papers_after_fresh,
    )
    optional_counts = (
        measurements.papers_after_resume,
        measurements.resume_items,
        measurements.resume_linked_items,
        measurements.unexpected_resume_papers,
        measurements.database_bytes_before,
        measurements.database_bytes_after,
    )
    has_declared_sources = measurements.declared_sources > 0
    required_counts_are_valid = all(value >= 0 for value in required_counts)
    optional_counts_are_valid = all(value is None or value >= 0 for value in optional_counts)
    return has_declared_sources and required_counts_are_valid and optional_counts_are_valid


def assess_scale_readiness(
    measurements: ScaleMeasurements,
    thresholds: ReadinessThresholds | None = None,
) -> ScaleAssessment:
    thresholds = thresholds or ReadinessThresholds()
    outcome_total = (
        measurements.imported_items
        + measurements.duplicate_items
        + measurements.skipped_items
        + measurements.failed_items
        + measurements.review_required_items
    )
    counts_are_valid = _counts_are_valid(measurements)
    declared_matches_items = measurements.declared_sources == measurements.persisted_items
    item_count_matches_outcomes = measurements.persisted_items == outcome_total
    counts_reconcile = declared_matches_items and item_count_matches_outcomes
    correctness_ok = counts_are_valid and counts_reconcile
    correctness = DimensionResult(
        status=DimensionStatus.PASS if correctness_ok else DimensionStatus.FAIL,
        explanation=(
            "Declared sources, persisted items, and item outcomes are valid and reconcile exactly."
            if correctness_ok
            else "Measurement counts are invalid or do not reconcile."
        ),
    )

    if (
        measurements.papers_after_resume is None
        or measurements.resume_items is None
        or measurements.resume_linked_items is None
        or measurements.unexpected_resume_papers is None
    ):
        recovery = DimensionResult(
            status=DimensionStatus.UNKNOWN,
            explanation="Resume measurements are incomplete.",
        )
    else:
        recovery_ok = (
            measurements.papers_after_resume == measurements.papers_after_fresh
            and measurements.unexpected_resume_papers == 0
            and measurements.resume_linked_items == measurements.resume_items
        )
        recovery = DimensionResult(
            status=DimensionStatus.PASS if recovery_ok else DimensionStatus.FAIL,
            explanation=(
                "Resume is idempotent and every resume item has prior-item lineage."
                if recovery_ok
                else "Resume created unexpected papers or lacks complete prior-item lineage."
            ),
        )

    failure_rate = _safe_rate(measurements.failed_items, measurements.persisted_items)
    issue_rate = _safe_rate(measurements.persisted_issues, measurements.persisted_items)
    reliability_ok = (
        counts_are_valid
        and failure_rate <= thresholds.maximum_failure_rate
        and issue_rate <= thresholds.maximum_issue_rate
    )
    reliability = DimensionResult(
        status=DimensionStatus.PASS if reliability_ok else DimensionStatus.FAIL,
        explanation=(
            "Failure and persisted-issue rates are within policy thresholds."
            if reliability_ok
            else "Measurement counts are invalid or a reliability rate exceeds its threshold."
        ),
    )

    imported_per_second = _timed_rate(
        measurements.imported_items, measurements.fresh_elapsed_seconds
    )
    resume_items_per_second = _timed_rate(
        measurements.resume_items or 0, measurements.resume_elapsed_seconds
    )
    if imported_per_second is None:
        performance = DimensionResult(
            status=DimensionStatus.UNKNOWN,
            explanation="Fresh elapsed time is unavailable or invalid.",
        )
    elif (
        thresholds.minimum_import_rate is not None
        and imported_per_second < thresholds.minimum_import_rate
    ):
        performance = DimensionResult(
            status=DimensionStatus.FAIL,
            explanation="Measured import rate is below the configured policy threshold.",
        )
    else:
        performance = DimensionResult(
            status=DimensionStatus.CONDITIONAL,
            explanation=(
                "Measured import rate is available, but one corpus size cannot prove scaling."
            ),
        )

    database_growth_bytes = _database_growth(
        measurements.database_bytes_before, measurements.database_bytes_after
    )
    bytes_per_imported_paper = (
        database_growth_bytes / measurements.imported_items
        if database_growth_bytes is not None and measurements.imported_items > 0
        else None
    )
    if database_growth_bytes is None:
        storage = DimensionResult(
            status=(
                DimensionStatus.UNKNOWN
                if thresholds.require_storage_measurement
                else DimensionStatus.CONDITIONAL
            ),
            explanation="Database-size evidence is unavailable.",
        )
    elif database_growth_bytes < 0:
        storage = DimensionResult(
            status=DimensionStatus.FAIL,
            explanation="Database size decreased during the measured fresh import.",
        )
    elif (
        thresholds.maximum_bytes_per_paper is not None
        and bytes_per_imported_paper is not None
        and bytes_per_imported_paper > thresholds.maximum_bytes_per_paper
    ):
        storage = DimensionResult(
            status=DimensionStatus.FAIL,
            explanation="Measured database growth per paper exceeds the policy threshold.",
        )
    else:
        storage = DimensionResult(
            status=DimensionStatus.PASS,
            explanation="Database growth is measured and within configured policy thresholds.",
        )

    privacy_ok = not (
        measurements.prohibited_artifacts_found or measurements.private_path_leak_found
    )
    privacy = DimensionResult(
        status=DimensionStatus.PASS if privacy_ok else DimensionStatus.FAIL,
        explanation=(
            "No prohibited artifacts or private paths were found."
            if privacy_ok
            else "Prohibited artifacts or private paths were found."
        ),
    )

    dimension_results = (
        correctness,
        recovery,
        reliability,
        performance,
        storage,
        privacy,
    )
    if any(result.status is DimensionStatus.FAIL for result in dimension_results):
        decision = Decision.NOT_READY
    elif all(result.status is DimensionStatus.PASS for result in dimension_results):
        decision = Decision.READY
    else:
        decision = Decision.READY_WITH_CONDITIONS

    return ScaleAssessment(
        decision=decision,
        correctness=correctness,
        recovery=recovery,
        reliability=reliability,
        performance=performance,
        storage=storage,
        privacy=privacy,
        imported_per_second=imported_per_second,
        resume_items_per_second=resume_items_per_second,
        database_growth_bytes=database_growth_bytes,
        bytes_per_imported_paper=bytes_per_imported_paper,
        failure_rate=failure_rate,
        issue_rate=issue_rate,
        proposed_next_corpus_size=thresholds.proposed_next_corpus_size,
    )
