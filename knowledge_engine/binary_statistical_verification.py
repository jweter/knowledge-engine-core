"""Typed verification of explicitly curated binary-outcome counts.

Version 1 verifies reported arm percentages and derives one crude risk ratio
with a log-Wald interval. It never treats that derived measure as equivalent to
a source paper's adjusted model estimate.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from knowledge_engine.utils import normalize_doi

BINARY_INPUT_SCHEMA_VERSION = 1
SUPPORTED_EFFECT_MEASURE = "crude_risk_ratio"
SUPPORTED_OUTCOME = "achievement_of_at_least_5_percent_weight_loss"
SUPPORTED_TIME_UNIT = "weeks"
SUPPORTED_REVIEW_STATUS = "source_verified"
SUPPORTED_METHOD = "crude_risk_ratio_log_wald"
SUPPORTED_CONFIDENCE_LEVEL = Decimal("95")
SUPPORTED_CRITICAL_VALUE = Decimal("1.96")
SUPPORTED_CORRECTION_POLICY = "none"
SUPPORTED_REPORTED_MEASURE = "adjusted_odds_ratio"
SUPPORTED_COMPARISON_POLICY = "display_only_not_compared"
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "binary_input_id",
        "evidence_record_id",
        "source_doi",
        "review_status",
        "effect_measure",
        "outcome",
        "timepoint",
        "analysis_population",
        "intervention",
        "comparator",
        "calculation",
        "source_reported_comparison",
        "source_span",
        "method_source_span",
        "provenance",
    }
)
_TIMEPOINT_FIELDS = frozenset({"value", "unit"})
_ARM_FIELDS = frozenset({"label", "events", "total", "reported_percentage"})
_CALCULATION_FIELDS = frozenset(
    {
        "method",
        "confidence_level",
        "critical_value",
        "continuity_correction",
        "continuity_correction_value",
        "reported_percentage_tolerance",
        "assumption_note",
    }
)
_REPORTED_COMPARISON_FIELDS = frozenset(
    {"measure", "estimate", "confidence_interval", "method_note", "comparison_policy"}
)
_CONFIDENCE_INTERVAL_FIELDS = frozenset({"level", "lower", "upper"})
_SOURCE_SPAN_FIELDS = frozenset({"page_number", "section", "table_or_figure", "locator_note"})
_PROVENANCE_FIELDS = frozenset({"created_by", "created_date", "method", "source_basis"})


class DuplicateJsonFieldError(ValueError):
    """One JSON object declared the same field more than once."""


@dataclass(frozen=True)
class BinarySourceSpan:
    """One source locator for binary numerical or method inputs."""

    page_number: int
    section: str
    table_or_figure: str | None
    locator_note: str | None


@dataclass(frozen=True)
class BinaryArm:
    """Explicit events, denominator, and source-reported percentage for one arm."""

    label: str
    events: int
    total: int
    reported_percentage: Decimal


@dataclass(frozen=True)
class BinaryCalculationInput:
    """Declared method and assumptions for one crude risk-ratio calculation."""

    method: str
    confidence_level: Decimal
    critical_value: Decimal
    continuity_correction: str
    continuity_correction_value: Decimal
    reported_percentage_tolerance: Decimal
    assumption_note: str


@dataclass(frozen=True)
class SourceReportedComparison:
    """A source model estimate retained for display, never equivalence testing."""

    measure: str
    estimate: Decimal
    confidence_level: Decimal
    confidence_lower: Decimal
    confidence_upper: Decimal
    method_note: str
    comparison_policy: str


@dataclass(frozen=True)
class BinaryStatisticalInput:
    """One source-linked binary-outcome record with explicit count inputs."""

    schema_version: int
    binary_input_id: str
    evidence_record_id: str
    source_doi: str
    review_status: str
    effect_measure: str
    outcome: str
    timepoint_value: Decimal
    timepoint_unit: str
    analysis_population: str
    intervention: BinaryArm
    comparator: BinaryArm
    calculation: BinaryCalculationInput
    source_reported_comparison: SourceReportedComparison
    source_span: BinarySourceSpan
    method_source_span: BinarySourceSpan
    provenance_created_by: str
    provenance_created_date: str
    provenance_method: str
    provenance_source_basis: str
    line_number: int


@dataclass(frozen=True)
class BinaryInputValidationResult:
    """Deterministic validation result for one binary-input JSONL file."""

    records: tuple[BinaryStatisticalInput, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class BinaryStatisticalVerification:
    """Count-derived arm percentages, crude risk ratio, and log-Wald interval."""

    record: BinaryStatisticalInput
    intervention_percentage: Decimal
    comparator_percentage: Decimal
    intervention_percentage_difference: Decimal
    comparator_percentage_difference: Decimal
    risk_ratio: Decimal
    log_risk_ratio_standard_error: Decimal
    confidence_lower: Decimal
    confidence_upper: Decimal
    status: str

    @property
    def has_discrepancy(self) -> bool:
        return self.status == "discrepant"


def validate_binary_statistical_inputs(
    path: Path,
    *,
    evidence_records: Sequence[Mapping[str, Any]],
) -> BinaryInputValidationResult:
    """Load and validate binary statistical inputs against reviewed evidence."""

    evidence_by_id = {
        str(record.get("evidence_record_id")): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
    }
    errors: list[str] = []
    records: list[BinaryStatisticalInput] = []
    seen_ids: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return BinaryInputValidationResult((), (f"Could not read {path.name}.",))

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        context = f"line {line_number}"
        try:
            payload: Any = json.loads(
                raw_line,
                parse_float=Decimal,
                object_pairs_hook=_unique_json_object,
            )
        except DuplicateJsonFieldError as exc:
            errors.append(f"{context}: {exc}.")
            continue
        except (json.JSONDecodeError, InvalidOperation):
            errors.append(f"{context}: invalid JSON object.")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{context}: record must be a JSON object.")
            continue
        record_errors: list[str] = []
        record = _parse_record(payload, line_number, record_errors)
        if record is None:
            errors.extend(record_errors)
            continue
        if record.binary_input_id in seen_ids:
            record_errors.append(
                f"{context}: duplicate binary_input_id {record.binary_input_id!r}."
            )
        else:
            seen_ids.add(record.binary_input_id)
        _validate_evidence_reference(record, evidence_by_id, record_errors)
        if record_errors:
            errors.extend(record_errors)
            continue
        records.append(record)

    if not records and not errors:
        errors.append("Binary statistical input file contains no records.")
    return BinaryInputValidationResult(tuple(records), tuple(errors))


def verify_binary_statistical_inputs(
    records: Sequence[BinaryStatisticalInput],
) -> tuple[BinaryStatisticalVerification, ...]:
    """Verify arm percentages and derive the declared crude risk ratio."""

    results: list[BinaryStatisticalVerification] = []
    for record in records:
        with localcontext() as context:
            context.prec = 28
            intervention_events = Decimal(record.intervention.events)
            intervention_total = Decimal(record.intervention.total)
            comparator_events = Decimal(record.comparator.events)
            comparator_total = Decimal(record.comparator.total)
            intervention_risk = intervention_events / intervention_total
            comparator_risk = comparator_events / comparator_total
            intervention_percentage = intervention_risk * Decimal(100)
            comparator_percentage = comparator_risk * Decimal(100)
            intervention_difference = abs(
                intervention_percentage - record.intervention.reported_percentage
            )
            comparator_difference = abs(
                comparator_percentage - record.comparator.reported_percentage
            )
            risk_ratio = intervention_risk / comparator_risk
            variance = (
                (Decimal(1) / intervention_events)
                - (Decimal(1) / intervention_total)
                + (Decimal(1) / comparator_events)
                - (Decimal(1) / comparator_total)
            )
            log_standard_error = variance.sqrt(context=context)
            margin = record.calculation.critical_value * log_standard_error
            confidence_lower = (risk_ratio.ln(context=context) - margin).exp(context=context)
            confidence_upper = (risk_ratio.ln(context=context) + margin).exp(context=context)
        tolerance = record.calculation.reported_percentage_tolerance
        status = (
            "consistent"
            if max(intervention_difference, comparator_difference) <= tolerance
            else "discrepant"
        )
        results.append(
            BinaryStatisticalVerification(
                record=record,
                intervention_percentage=intervention_percentage,
                comparator_percentage=comparator_percentage,
                intervention_percentage_difference=intervention_difference,
                comparator_percentage_difference=comparator_difference,
                risk_ratio=risk_ratio,
                log_risk_ratio_standard_error=log_standard_error,
                confidence_lower=confidence_lower,
                confidence_upper=confidence_upper,
                status=status,
            )
        )
    return tuple(results)


def render_binary_verification_sections(
    results: Sequence[BinaryStatisticalVerification], *, start_index: int
) -> list[str]:
    """Render binary results as report sections after continuous results."""

    lines: list[str] = []
    for index, result in enumerate(results, start=start_index):
        record = result.record
        source_comparison = record.source_reported_comparison
        lines.extend(
            [
                f"## {index}. `{_md_code(record.binary_input_id)}`",
                "",
                f"- **Contract:** binary statistical input version {record.schema_version}",
                f"- **Evidence Record:** `{_md_code(record.evidence_record_id)}`",
                f"- **Source DOI:** `{_md_code(record.source_doi)}`",
                f"- **Review status:** {_md_text(record.review_status)}",
                f"- **Outcome:** `{_md_code(record.outcome)}`",
                f"- **Time point:** {_decimal(record.timepoint_value)} "
                f"{_md_text(record.timepoint_unit)}",
                f"- **Analysis population:** {_md_text(record.analysis_population)}",
                f"- **Intervention counts:** {_md_text(record.intervention.label)}; "
                f"`{record.intervention.events}/{record.intervention.total}`",
                f"- **Intervention percentage:** reported "
                f"`{_decimal(record.intervention.reported_percentage)}%`; calculated "
                f"`{_decimal(result.intervention_percentage)}%`; absolute difference "
                f"`{_decimal(result.intervention_percentage_difference)}` percentage points",
                f"- **Comparator counts:** {_md_text(record.comparator.label)}; "
                f"`{record.comparator.events}/{record.comparator.total}`",
                f"- **Comparator percentage:** reported "
                f"`{_decimal(record.comparator.reported_percentage)}%`; calculated "
                f"`{_decimal(result.comparator_percentage)}%`; absolute difference "
                f"`{_decimal(result.comparator_percentage_difference)}` percentage points",
                f"- **Percentage tolerance:** "
                f"`{_decimal(record.calculation.reported_percentage_tolerance)}` "
                "percentage points",
                f"- **Binary status:** **{result.status}**",
                f"- **Derived effect measure:** `{_md_code(record.effect_measure)}`",
                f"- **Interval method:** `{_md_code(record.calculation.method)}`",
                f"- **Confidence level:** `{_decimal(record.calculation.confidence_level)}%`",
                f"- **Normal critical value:** `{_decimal(record.calculation.critical_value)}`",
                f"- **Continuity correction:** "
                f"`{_md_code(record.calculation.continuity_correction)}` "
                f"(value `{_decimal(record.calculation.continuity_correction_value)}`)",
                f"- **Calculated crude risk ratio:** `{_decimal(result.risk_ratio)}`",
                f"- **SE(log risk ratio):** `{_decimal(result.log_risk_ratio_standard_error)}`",
                f"- **Calculated 95% confidence interval:** "
                f"`{_decimal(result.confidence_lower)}` to "
                f"`{_decimal(result.confidence_upper)}`",
                f"- **Calculation assumption:** {_md_text(record.calculation.assumption_note)}",
                f"- **Source-reported comparison:** "
                f"`{_md_code(source_comparison.measure)}` "
                f"`{_decimal(source_comparison.estimate)}` "
                f"({_decimal(source_comparison.confidence_level)}% CI "
                f"`{_decimal(source_comparison.confidence_lower)}` to "
                f"`{_decimal(source_comparison.confidence_upper)}`; display only)",
                f"- **Source method context:** {_md_text(source_comparison.method_note)}",
                f"- **Comparison policy:** `{_md_code(source_comparison.comparison_policy)}`",
                f"- **Numerical source span:** page {record.source_span.page_number}, "
                f"{_md_text(record.source_span.section)}",
                f"- **Method source span:** page {record.method_source_span.page_number}, "
                f"{_md_text(record.method_source_span.section)}",
            ]
        )
        if record.source_span.table_or_figure:
            lines.append(
                f"- **Numerical table or figure:** {_md_text(record.source_span.table_or_figure)}"
            )
        if record.source_span.locator_note:
            lines.append(
                f"- **Numerical locator note:** {_md_text(record.source_span.locator_note)}"
            )
        if record.method_source_span.table_or_figure:
            lines.append(
                f"- **Method table or figure:** "
                f"{_md_text(record.method_source_span.table_or_figure)}"
            )
        if record.method_source_span.locator_note:
            lines.append(
                f"- **Method locator note:** {_md_text(record.method_source_span.locator_note)}"
            )
        lines.extend(
            [
                f"- **Curated by:** {_md_text(record.provenance_created_by)}",
                f"- **Curation method:** {_md_text(record.provenance_method)}",
                f"- **Source basis:** {_md_text(record.provenance_source_basis)}",
                "",
                "**Interpretation:** `consistent` means only that the declared counts "
                "reproduce the source-reported arm percentages within the declared "
                "rounding tolerance. The calculated crude risk ratio is not the "
                "source-reported adjusted odds ratio and the two are not compared.",
                "",
            ]
        )
    return lines


def _parse_record(
    payload: Mapping[str, Any], line_number: int, errors: list[str]
) -> BinaryStatisticalInput | None:
    context = f"line {line_number}"
    _reject_unknown_fields(payload, _TOP_LEVEL_FIELDS, context, errors)
    raw_version = payload.get("schema_version")
    schema_version: int | None = None
    if isinstance(raw_version, bool) or raw_version != BINARY_INPUT_SCHEMA_VERSION:
        errors.append(f"{context}: schema_version must be integer 1.")
    else:
        schema_version = raw_version

    binary_input_id = _required_text(payload, "binary_input_id", context, errors)
    evidence_record_id = _required_text(payload, "evidence_record_id", context, errors)
    source_doi = _required_text(payload, "source_doi", context, errors)
    review_status = _required_text(payload, "review_status", context, errors)
    effect_measure = _required_text(payload, "effect_measure", context, errors)
    outcome = _required_text(payload, "outcome", context, errors)
    analysis_population = _required_text(payload, "analysis_population", context, errors)

    if binary_input_id and not _IDENTIFIER_PATTERN.fullmatch(binary_input_id):
        errors.append(f"{context}: binary_input_id has an invalid format.")
    if review_status and review_status != SUPPORTED_REVIEW_STATUS:
        errors.append(f"{context}: review_status must be {SUPPORTED_REVIEW_STATUS!r}.")
    if effect_measure and effect_measure != SUPPORTED_EFFECT_MEASURE:
        errors.append(f"{context}: effect_measure must be {SUPPORTED_EFFECT_MEASURE!r}.")
    if outcome and outcome != SUPPORTED_OUTCOME:
        errors.append(f"{context}: outcome must be {SUPPORTED_OUTCOME!r}.")

    timepoint = _required_object(payload, "timepoint", context, errors)
    _reject_unknown_fields(timepoint, _TIMEPOINT_FIELDS, f"{context}.timepoint", errors)
    timepoint_value = _decimal_field(timepoint, "value", f"{context}.timepoint", errors)
    timepoint_unit = _required_text(timepoint, "unit", f"{context}.timepoint", errors)
    if timepoint_value is not None and timepoint_value <= 0:
        errors.append(f"{context}.timepoint.value must be positive.")
    if timepoint_unit and timepoint_unit != SUPPORTED_TIME_UNIT:
        errors.append(f"{context}.timepoint.unit must be {SUPPORTED_TIME_UNIT!r}.")

    intervention = _parse_arm(payload, "intervention", context, errors)
    comparator = _parse_arm(payload, "comparator", context, errors)
    calculation = _parse_calculation(payload, context, errors)
    source_comparison = _parse_source_reported_comparison(payload, context, errors)
    source_span = _parse_source_span(payload, "source_span", context, errors)
    method_source_span = _parse_source_span(payload, "method_source_span", context, errors)

    provenance = _required_object(payload, "provenance", context, errors)
    _reject_unknown_fields(provenance, _PROVENANCE_FIELDS, f"{context}.provenance", errors)
    created_by = _required_text(provenance, "created_by", f"{context}.provenance", errors)
    created_date = _required_text(provenance, "created_date", f"{context}.provenance", errors)
    provenance_method = _required_text(provenance, "method", f"{context}.provenance", errors)
    source_basis = _required_text(provenance, "source_basis", f"{context}.provenance", errors)
    if created_date:
        try:
            date.fromisoformat(created_date)
        except ValueError:
            errors.append(f"{context}.provenance.created_date must be an ISO 8601 date.")

    if errors:
        return None
    assert schema_version is not None
    assert timepoint_value is not None
    assert intervention is not None
    assert comparator is not None
    assert calculation is not None
    assert source_comparison is not None
    assert source_span is not None
    assert method_source_span is not None
    return BinaryStatisticalInput(
        schema_version=schema_version,
        binary_input_id=binary_input_id,
        evidence_record_id=evidence_record_id,
        source_doi=source_doi,
        review_status=review_status,
        effect_measure=effect_measure,
        outcome=outcome,
        timepoint_value=timepoint_value,
        timepoint_unit=timepoint_unit,
        analysis_population=analysis_population,
        intervention=intervention,
        comparator=comparator,
        calculation=calculation,
        source_reported_comparison=source_comparison,
        source_span=source_span,
        method_source_span=method_source_span,
        provenance_created_by=created_by,
        provenance_created_date=created_date,
        provenance_method=provenance_method,
        provenance_source_basis=source_basis,
        line_number=line_number,
    )


def _parse_arm(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> BinaryArm | None:
    arm_context = f"{context}.{field}"
    raw = _required_object(payload, field, context, errors)
    _reject_unknown_fields(raw, _ARM_FIELDS, arm_context, errors)
    label = _required_text(raw, "label", arm_context, errors)
    events = _integer_field(raw, "events", arm_context, errors)
    total = _positive_integer_field(raw, "total", arm_context, errors)
    reported_percentage = _decimal_field(raw, "reported_percentage", arm_context, errors)
    if events is not None and events <= 0:
        errors.append(
            f"{arm_context}.events must be positive when continuity_correction is 'none'."
        )
    if events is not None and total is not None and events > total:
        errors.append(f"{arm_context}.events must not exceed total.")
    if reported_percentage is not None and not Decimal(0) <= reported_percentage <= Decimal(100):
        errors.append(f"{arm_context}.reported_percentage must be between 0 and 100.")
    if events is None or total is None or reported_percentage is None:
        return None
    return BinaryArm(label, events, total, reported_percentage)


def _parse_calculation(
    payload: Mapping[str, Any], context: str, errors: list[str]
) -> BinaryCalculationInput | None:
    calculation_context = f"{context}.calculation"
    raw = _required_object(payload, "calculation", context, errors)
    _reject_unknown_fields(raw, _CALCULATION_FIELDS, calculation_context, errors)
    method = _required_text(raw, "method", calculation_context, errors)
    confidence_level = _decimal_field(raw, "confidence_level", calculation_context, errors)
    critical_value = _decimal_field(raw, "critical_value", calculation_context, errors)
    correction = _required_text(raw, "continuity_correction", calculation_context, errors)
    correction_value = _decimal_field(
        raw, "continuity_correction_value", calculation_context, errors
    )
    tolerance = _decimal_field(raw, "reported_percentage_tolerance", calculation_context, errors)
    assumption_note = _required_text(raw, "assumption_note", calculation_context, errors)
    if method and method != SUPPORTED_METHOD:
        errors.append(f"{calculation_context}.method must be {SUPPORTED_METHOD!r}.")
    if confidence_level is not None and confidence_level != SUPPORTED_CONFIDENCE_LEVEL:
        errors.append(f"{calculation_context}.confidence_level must be 95.")
    if critical_value is not None and critical_value != SUPPORTED_CRITICAL_VALUE:
        errors.append(f"{calculation_context}.critical_value must be 1.96.")
    if correction and correction != SUPPORTED_CORRECTION_POLICY:
        errors.append(
            f"{calculation_context}.continuity_correction must be {SUPPORTED_CORRECTION_POLICY!r}."
        )
    if correction_value is not None and correction_value != 0:
        errors.append(f"{calculation_context}.continuity_correction_value must be 0.")
    if tolerance is not None and tolerance <= 0:
        errors.append(f"{calculation_context}.reported_percentage_tolerance must be positive.")
    if any(
        value is None for value in (confidence_level, critical_value, correction_value, tolerance)
    ):
        return None
    assert confidence_level is not None
    assert critical_value is not None
    assert correction_value is not None
    assert tolerance is not None
    return BinaryCalculationInput(
        method,
        confidence_level,
        critical_value,
        correction,
        correction_value,
        tolerance,
        assumption_note,
    )


def _parse_source_reported_comparison(
    payload: Mapping[str, Any], context: str, errors: list[str]
) -> SourceReportedComparison | None:
    comparison_context = f"{context}.source_reported_comparison"
    raw = _required_object(payload, "source_reported_comparison", context, errors)
    _reject_unknown_fields(raw, _REPORTED_COMPARISON_FIELDS, comparison_context, errors)
    measure = _required_text(raw, "measure", comparison_context, errors)
    estimate = _decimal_field(raw, "estimate", comparison_context, errors)
    method_note = _required_text(raw, "method_note", comparison_context, errors)
    policy = _required_text(raw, "comparison_policy", comparison_context, errors)
    if measure and measure != SUPPORTED_REPORTED_MEASURE:
        errors.append(f"{comparison_context}.measure must be {SUPPORTED_REPORTED_MEASURE!r}.")
    if estimate is not None and estimate <= 0:
        errors.append(f"{comparison_context}.estimate must be positive.")
    if policy and policy != SUPPORTED_COMPARISON_POLICY:
        errors.append(
            f"{comparison_context}.comparison_policy must be {SUPPORTED_COMPARISON_POLICY!r}."
        )
    confidence = _required_object(raw, "confidence_interval", comparison_context, errors)
    _reject_unknown_fields(
        confidence,
        _CONFIDENCE_INTERVAL_FIELDS,
        f"{comparison_context}.confidence_interval",
        errors,
    )
    level = _decimal_field(confidence, "level", f"{comparison_context}.confidence_interval", errors)
    lower = _decimal_field(confidence, "lower", f"{comparison_context}.confidence_interval", errors)
    upper = _decimal_field(confidence, "upper", f"{comparison_context}.confidence_interval", errors)
    if level is not None and level != SUPPORTED_CONFIDENCE_LEVEL:
        errors.append(f"{comparison_context}.confidence_interval.level must be 95.")
    if lower is not None and lower <= 0:
        errors.append(f"{comparison_context}.confidence_interval.lower must be positive.")
    if upper is not None and upper <= 0:
        errors.append(f"{comparison_context}.confidence_interval.upper must be positive.")
    if lower is not None and upper is not None and lower > upper:
        errors.append(f"{comparison_context}.confidence_interval lower must not exceed upper.")
    if (
        estimate is not None
        and lower is not None
        and upper is not None
        and not lower <= estimate <= upper
    ):
        errors.append(
            f"{comparison_context}.estimate must fall within the reported confidence interval."
        )
    if any(value is None for value in (estimate, level, lower, upper)):
        return None
    assert estimate is not None
    assert level is not None
    assert lower is not None
    assert upper is not None
    return SourceReportedComparison(measure, estimate, level, lower, upper, method_note, policy)


def _parse_source_span(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> BinarySourceSpan | None:
    span_context = f"{context}.{field}"
    raw = _required_object(payload, field, context, errors)
    _reject_unknown_fields(raw, _SOURCE_SPAN_FIELDS, span_context, errors)
    page_number = _positive_integer_field(raw, "page_number", span_context, errors)
    section = _required_text(raw, "section", span_context, errors)
    table_or_figure = _optional_text(raw, "table_or_figure", span_context, errors)
    locator_note = _optional_text(raw, "locator_note", span_context, errors)
    if page_number is None:
        return None
    return BinarySourceSpan(page_number, section, table_or_figure, locator_note)


def _validate_evidence_reference(
    record: BinaryStatisticalInput,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    context = f"line {record.line_number}"
    evidence = evidence_by_id.get(record.evidence_record_id)
    if evidence is None:
        errors.append(f"{context}: unknown evidence_record_id {record.evidence_record_id!r}.")
        return
    if evidence.get("review_status") != "reviewed":
        errors.append(f"{context}: referenced Evidence Record must be reviewed.")
    evidence_doi = evidence.get("source_doi")
    if not isinstance(evidence_doi, str) or normalize_doi(evidence_doi) != normalize_doi(
        record.source_doi
    ):
        errors.append(f"{context}: source_doi does not match the referenced Evidence Record.")
    outcome = evidence.get("outcome")
    if not isinstance(outcome, str) or "body weight" not in outcome.lower():
        errors.append(
            f"{context}: referenced Evidence Record does not declare a body-weight outcome."
        )
    source_span = evidence.get("source_span")
    if (
        not isinstance(source_span, dict)
        or isinstance(source_span.get("page_number"), bool)
        or not isinstance(source_span.get("page_number"), int)
        or source_span["page_number"] <= 0
        or not isinstance(source_span.get("section"), str)
        or not source_span["section"].strip()
    ):
        errors.append(f"{context}: referenced Evidence Record must have a valid source span.")


def _reject_unknown_fields(
    payload: Mapping[str, Any], allowed: frozenset[str], context: str, errors: list[str]
) -> None:
    for field in sorted(set(payload) - allowed):
        errors.append(f"{context}: unsupported field {field!r}.")


def _required_object(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> Mapping[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        errors.append(f"{context}.{field} must be an object.")
        return {}
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonFieldError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _required_text(payload: Mapping[str, Any], field: str, context: str, errors: list[str]) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}.{field} must be non-empty text.")
        return ""
    return value.strip()


def _optional_text(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}.{field} must be non-empty text when present.")
        return None
    return value.strip()


def _decimal_field(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> Decimal | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        errors.append(f"{context}.{field} must be a finite JSON number.")
        return None
    decimal_value = Decimal(value) if isinstance(value, int) else value
    if not decimal_value.is_finite():
        errors.append(f"{context}.{field} must be a finite JSON number.")
        return None
    return decimal_value


def _integer_field(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> int | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{context}.{field} must be a JSON integer.")
        return None
    return value


def _positive_integer_field(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> int | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.append(f"{context}.{field} must be a positive integer.")
        return None
    return value


def _decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _md_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    for character in ("*", "_", "[", "]", "<", ">", "#"):
        text = text.replace(character, f"\\{character}")
    return text


def _md_code(value: object) -> str:
    return str(value).replace("`", "\\`").replace("\n", " ").replace("\r", " ")
