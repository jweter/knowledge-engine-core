from knowledge_engine.scale_readiness import (
    Decision,
    DimensionResult,
    DimensionStatus,
    ScaleAssessment,
    ScaleMeasurements,
)
from knowledge_engine.scale_report import render_scale_assessment


def _measurements() -> ScaleMeasurements:
    return ScaleMeasurements(
        declared_sources=100,
        persisted_items=100,
        imported_items=100,
        duplicate_items=0,
        skipped_items=0,
        failed_items=0,
        review_required_items=0,
        persisted_issues=0,
        papers_after_fresh=100,
        papers_after_resume=100,
        resume_items=100,
        resume_linked_items=100,
        unexpected_resume_papers=0,
        fresh_elapsed_seconds=9.0,
        resume_elapsed_seconds=1.0,
        database_bytes_before=None,
        database_bytes_after=None,
        prohibited_artifacts_found=False,
        private_path_leak_found=False,
    )


def _assessment() -> ScaleAssessment:
    passing = DimensionResult(DimensionStatus.PASS, "Measured evidence passed.")
    conditional = DimensionResult(
        DimensionStatus.CONDITIONAL,
        "One corpus size cannot prove scaling.",
    )
    unknown = DimensionResult(DimensionStatus.UNKNOWN, "Measurement unavailable.")
    return ScaleAssessment(
        decision=Decision.READY_WITH_CONDITIONS,
        correctness=passing,
        recovery=passing,
        reliability=passing,
        performance=conditional,
        storage=unknown,
        privacy=passing,
        imported_per_second=100 / 9,
        resume_items_per_second=100.0,
        database_growth_bytes=None,
        bytes_per_imported_paper=None,
        failure_rate=0.0,
        issue_rate=0.0,
        proposed_next_corpus_size=500,
    )


def test_report_labels_measurement_sources_and_unknowns() -> None:
    report = render_scale_assessment(_measurements(), _assessment())

    assert "Decision: `ready_with_conditions` _(source: derived)_" in report
    assert "Proposed next corpus size: `500` _(source: policy)_" in report
    assert "Declared sources: `100` _(source: persisted)_" in report
    assert "Fresh elapsed seconds: `9.0000` _(source: operator)_" in report
    assert "Database growth bytes: `unknown` _(source: derived)_" in report
    assert "Unknown values are intentionally not inferred." in report


def test_report_output_is_deterministic() -> None:
    first = render_scale_assessment(_measurements(), _assessment())
    second = render_scale_assessment(_measurements(), _assessment())

    assert first == second
    assert first.endswith("\n")
