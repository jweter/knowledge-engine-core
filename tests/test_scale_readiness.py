from knowledge_engine.scale_readiness import (
    Decision,
    DimensionStatus,
    ReadinessThresholds,
    ScaleMeasurements,
    assess_scale_readiness,
)


def _m12_measurements(**overrides: object) -> ScaleMeasurements:
    values: dict[str, object] = {
        "declared_sources": 100,
        "persisted_items": 100,
        "imported_items": 100,
        "duplicate_items": 0,
        "skipped_items": 0,
        "failed_items": 0,
        "review_required_items": 0,
        "persisted_issues": 0,
        "papers_after_fresh": 100,
        "papers_after_resume": 100,
        "resume_items": 100,
        "resume_linked_items": 100,
        "unexpected_resume_papers": 0,
        "fresh_elapsed_seconds": 9.0,
        "resume_elapsed_seconds": 1.0,
        "database_bytes_before": None,
        "database_bytes_after": None,
        "prohibited_artifacts_found": False,
        "private_path_leak_found": False,
    }
    values.update(overrides)
    return ScaleMeasurements(**values)  # type: ignore[arg-type]


def test_m12_baseline_is_ready_with_conditions_when_storage_is_unknown() -> None:
    assessment = assess_scale_readiness(_m12_measurements())

    assert assessment.decision is Decision.READY_WITH_CONDITIONS
    assert assessment.correctness.status is DimensionStatus.PASS
    assert assessment.recovery.status is DimensionStatus.PASS
    assert assessment.reliability.status is DimensionStatus.PASS
    assert assessment.performance.status is DimensionStatus.CONDITIONAL
    assert assessment.storage.status is DimensionStatus.UNKNOWN
    assert assessment.privacy.status is DimensionStatus.PASS
    assert assessment.imported_per_second == 100 / 9
    assert assessment.resume_items_per_second == 100.0
    assert assessment.proposed_next_corpus_size == 500


def test_reconciliation_failure_is_not_ready() -> None:
    assessment = assess_scale_readiness(_m12_measurements(persisted_items=99))

    assert assessment.decision is Decision.NOT_READY
    assert assessment.correctness.status is DimensionStatus.FAIL


def test_resume_reimport_is_not_ready() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(papers_after_resume=101, unexpected_resume_papers=1)
    )

    assert assessment.decision is Decision.NOT_READY
    assert assessment.recovery.status is DimensionStatus.FAIL


def test_missing_resume_measurements_remain_unknown() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(
            papers_after_resume=None,
            resume_items=None,
            resume_linked_items=None,
            unexpected_resume_papers=None,
            resume_elapsed_seconds=None,
        )
    )

    assert assessment.decision is Decision.READY_WITH_CONDITIONS
    assert assessment.recovery.status is DimensionStatus.UNKNOWN
    assert assessment.resume_items_per_second is None


def test_failure_rate_threshold_is_inclusive() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(imported_items=99, failed_items=1),
        ReadinessThresholds(maximum_failure_rate=0.01),
    )

    assert assessment.reliability.status is DimensionStatus.PASS
    assert assessment.failure_rate == 0.01


def test_failure_rate_above_threshold_is_not_ready() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(imported_items=98, failed_items=2),
        ReadinessThresholds(maximum_failure_rate=0.01),
    )

    assert assessment.decision is Decision.NOT_READY
    assert assessment.reliability.status is DimensionStatus.FAIL


def test_measured_storage_can_pass() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(database_bytes_before=1_000, database_bytes_after=11_000),
        ReadinessThresholds(maximum_bytes_per_paper=101.0),
    )

    assert assessment.database_growth_bytes == 10_000
    assert assessment.bytes_per_imported_paper == 100.0
    assert assessment.storage.status is DimensionStatus.PASS


def test_storage_threshold_failure_is_not_ready() -> None:
    assessment = assess_scale_readiness(
        _m12_measurements(database_bytes_before=1_000, database_bytes_after=11_000),
        ReadinessThresholds(maximum_bytes_per_paper=99.0),
    )

    assert assessment.decision is Decision.NOT_READY
    assert assessment.storage.status is DimensionStatus.FAIL


def test_private_path_leak_is_not_ready() -> None:
    assessment = assess_scale_readiness(_m12_measurements(private_path_leak_found=True))

    assert assessment.decision is Decision.NOT_READY
    assert assessment.privacy.status is DimensionStatus.FAIL


def test_zero_or_missing_elapsed_time_does_not_invent_rate() -> None:
    zero = assess_scale_readiness(_m12_measurements(fresh_elapsed_seconds=0.0))
    missing = assess_scale_readiness(_m12_measurements(fresh_elapsed_seconds=None))

    assert zero.imported_per_second is None
    assert missing.imported_per_second is None
    assert zero.performance.status is DimensionStatus.UNKNOWN
    assert missing.performance.status is DimensionStatus.UNKNOWN
