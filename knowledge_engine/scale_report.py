from __future__ import annotations

from knowledge_engine.scale_readiness import (
    MeasurementSource,
    ScaleAssessment,
    ScaleMeasurements,
)


def _display(value: object | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).lower() if isinstance(value, bool) else str(value)


def format_measurement(label: str, value: object | None, source: MeasurementSource) -> str:
    return f"- {label}: `{_display(value)}` _(source: {source.value})_"


def render_scale_assessment(
    measurements: ScaleMeasurements,
    assessment: ScaleAssessment,
) -> str:
    lines = [
        "# Scale Readiness Assessment",
        "",
        "## Decision",
        "",
        format_measurement("Decision", assessment.decision.value, MeasurementSource.DERIVED),
        format_measurement(
            "Proposed next corpus size",
            assessment.proposed_next_corpus_size,
            MeasurementSource.POLICY,
        ),
        "",
        "## Readiness dimensions",
        "",
    ]
    dimensions = (
        ("Correctness", assessment.correctness),
        ("Recovery", assessment.recovery),
        ("Reliability", assessment.reliability),
        ("Performance", assessment.performance),
        ("Storage", assessment.storage),
        ("Privacy", assessment.privacy),
    )
    for label, result in dimensions:
        lines.append(format_measurement(label, result.status.value, MeasurementSource.DERIVED))
        lines.append(f"  - {result.explanation}")

    lines.extend(
        [
            "",
            "## Persisted measurements",
            "",
            format_measurement(
                "Declared sources", measurements.declared_sources, MeasurementSource.PERSISTED
            ),
            format_measurement(
                "Persisted items", measurements.persisted_items, MeasurementSource.PERSISTED
            ),
            format_measurement(
                "Imported items", measurements.imported_items, MeasurementSource.PERSISTED
            ),
            format_measurement(
                "Persisted issues", measurements.persisted_issues, MeasurementSource.PERSISTED
            ),
            "",
            "## Operator measurements",
            "",
            format_measurement(
                "Fresh elapsed seconds",
                measurements.fresh_elapsed_seconds,
                MeasurementSource.OPERATOR,
            ),
            format_measurement(
                "Resume elapsed seconds",
                measurements.resume_elapsed_seconds,
                MeasurementSource.OPERATOR,
            ),
            format_measurement(
                "Database bytes before",
                measurements.database_bytes_before,
                MeasurementSource.OPERATOR,
            ),
            format_measurement(
                "Database bytes after",
                measurements.database_bytes_after,
                MeasurementSource.OPERATOR,
            ),
            "",
            "## Derived measurements",
            "",
            format_measurement(
                "Imported per second",
                assessment.imported_per_second,
                MeasurementSource.DERIVED,
            ),
            format_measurement(
                "Resume items per second",
                assessment.resume_items_per_second,
                MeasurementSource.DERIVED,
            ),
            format_measurement(
                "Database growth bytes",
                assessment.database_growth_bytes,
                MeasurementSource.DERIVED,
            ),
            format_measurement(
                "Bytes per imported paper",
                assessment.bytes_per_imported_paper,
                MeasurementSource.DERIVED,
            ),
            format_measurement("Failure rate", assessment.failure_rate, MeasurementSource.DERIVED),
            format_measurement("Issue rate", assessment.issue_rate, MeasurementSource.DERIVED),
            "",
            "Unknown values are intentionally not inferred.",
        ]
    )
    return "\n".join(lines) + "\n"
