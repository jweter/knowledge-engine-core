"""Typed, deterministic verification of explicitly curated statistical inputs.

Version 1 supports one arithmetic identity: the difference between intervention
and comparator mean changes. Version 2 may additionally approximate a two-sided
95% interval from explicit arm standard errors under a declared independent-arm
normal assumption. Values are never extracted from prose, and a compatible
result is not a judgment about the source model or scientific validity.
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

from knowledge_engine.binary_statistical_verification import (
    BinaryStatisticalVerification,
    render_binary_verification_sections,
)
from knowledge_engine.utils import normalize_doi

STATISTICAL_INPUT_SCHEMA_VERSION = 2
SUPPORTED_STATISTICAL_INPUT_SCHEMA_VERSIONS = frozenset({1, 2})
SUPPORTED_EFFECT_MEASURE = "difference_in_mean_change"
SUPPORTED_FORMULA = "intervention_minus_comparator"
SUPPORTED_OUTCOME = "body_weight_change_from_baseline"
SUPPORTED_UNIT = "percentage_points"
SUPPORTED_TIME_UNIT = "weeks"
SUPPORTED_REVIEW_STATUS = "source_verified"
SUPPORTED_CONFIDENCE_INTERVAL_METHOD = "independent_arm_standard_errors_normal"
SUPPORTED_CONFIDENCE_LEVEL = Decimal("95")
SUPPORTED_CRITICAL_VALUE = Decimal("1.96")
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class DuplicateJsonFieldError(ValueError):
    """One JSON object declared the same field more than once."""


@dataclass(frozen=True)
class SourceSpan:
    """Source locator for manually curated numerical inputs."""

    page_number: int
    section: str
    table_or_figure: str | None
    locator_note: str | None


@dataclass(frozen=True)
class ConfidenceIntervalVerificationInput:
    """Declared inputs for one bounded interval approximation."""

    method: str
    intervention_standard_error: Decimal
    comparator_standard_error: Decimal
    intervention_sample_size: int
    comparator_sample_size: int
    critical_value: Decimal
    endpoint_tolerance: Decimal
    assumption_note: str


@dataclass(frozen=True)
class StatisticalInput:
    """One source-linked reported effect with explicit formula inputs."""

    schema_version: int
    statistical_input_id: str
    evidence_record_id: str
    source_doi: str
    review_status: str
    effect_measure: str
    outcome: str
    unit: str
    timepoint_value: Decimal
    timepoint_unit: str
    analysis_population: str
    intervention_label: str
    intervention_mean_change: Decimal
    comparator_label: str
    comparator_mean_change: Decimal
    reported_effect: Decimal
    confidence_level: Decimal | None
    confidence_lower: Decimal | None
    confidence_upper: Decimal | None
    confidence_interval_verification: ConfidenceIntervalVerificationInput | None
    formula: str
    tolerance: Decimal
    source_span: SourceSpan
    provenance_created_by: str
    provenance_created_date: str
    provenance_method: str
    provenance_source_basis: str
    line_number: int


@dataclass(frozen=True)
class StatisticalInputValidationResult:
    """Deterministic validation result for one JSONL file."""

    records: tuple[StatisticalInput, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class StatisticalVerification:
    """One independently recomputed arithmetic identity."""

    record: StatisticalInput
    recomputed_effect: Decimal
    absolute_difference: Decimal
    status: str
    interval_approximation: ConfidenceIntervalApproximation | None

    @property
    def has_discrepancy(self) -> bool:
        """Return whether either requested deterministic check is discrepant."""

        return self.status == "discrepant" or (
            self.interval_approximation is not None
            and self.interval_approximation.status == "discrepant"
        )


@dataclass(frozen=True)
class ConfidenceIntervalApproximation:
    """One independent-arm normal approximation and endpoint comparison."""

    difference_standard_error: Decimal
    margin: Decimal
    lower: Decimal
    upper: Decimal
    lower_difference: Decimal
    upper_difference: Decimal
    status: str


def validate_statistical_inputs(
    path: Path,
    *,
    evidence_records: Sequence[Mapping[str, Any]],
) -> StatisticalInputValidationResult:
    """Load and validate version 1 JSONL inputs against reviewed evidence."""

    evidence_by_id = {
        str(record.get("evidence_record_id")): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
    }
    errors: list[str] = []
    records: list[StatisticalInput] = []
    seen_ids: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return StatisticalInputValidationResult((), (f"Could not read {path.name}.",))

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
        if record.statistical_input_id in seen_ids:
            record_errors.append(
                f"{context}: duplicate statistical_input_id {record.statistical_input_id!r}."
            )
        else:
            seen_ids.add(record.statistical_input_id)
        _validate_evidence_reference(record, evidence_by_id, record_errors)
        if record_errors:
            errors.extend(record_errors)
            continue
        records.append(record)

    if not records and not errors:
        errors.append("Statistical input file contains no records.")
    return StatisticalInputValidationResult(tuple(records), tuple(errors))


def verify_statistical_inputs(
    records: Sequence[StatisticalInput],
) -> tuple[StatisticalVerification, ...]:
    """Recompute every supported effect in input order."""

    results: list[StatisticalVerification] = []
    for record in records:
        recomputed = record.intervention_mean_change - record.comparator_mean_change
        absolute_difference = abs(recomputed - record.reported_effect)
        status = "consistent" if absolute_difference <= record.tolerance else "discrepant"
        interval_approximation = _approximate_confidence_interval(record)
        results.append(
            StatisticalVerification(
                record=record,
                recomputed_effect=recomputed,
                absolute_difference=absolute_difference,
                status=status,
                interval_approximation=interval_approximation,
            )
        )
    return tuple(results)


def render_statistical_verification_report(
    results: Sequence[StatisticalVerification],
    *,
    binary_results: Sequence[BinaryStatisticalVerification] = (),
) -> str:
    """Render deterministic Markdown for already-validated results."""

    consistent_count = sum(result.status == "consistent" for result in results)
    discrepant_count = len(results) - consistent_count
    interval_results = [
        result.interval_approximation
        for result in results
        if result.interval_approximation is not None
    ]
    compatible_interval_count = sum(result.status == "compatible" for result in interval_results)
    interval_discrepancy_count = len(interval_results) - compatible_interval_count
    contract_versions = ", ".join(
        str(version) for version in sorted({r.record.schema_version for r in results})
    )
    lines = [
        "# Statistical Verification Report",
        "",
        "## Summary",
        "",
        f"- **Contract versions present:** {contract_versions}",
        f"- **Typed inputs:** {len(results)}",
        f"- **Consistent arithmetic checks:** {consistent_count}",
        f"- **Discrepancies:** {discrepant_count}",
        f"- **Arithmetic discrepancies:** {discrepant_count}",
        f"- **Interval approximations:** {len(interval_results)}",
        f"- **Compatible interval approximations:** {compatible_interval_count}",
        f"- **Interval discrepancies:** {interval_discrepancy_count}",
        "",
        "These checks use only explicitly curated formula inputs. No numerical value "
        "was extracted from Evidence Record prose.",
        "",
    ]
    if binary_results:
        consistent_binary_count = sum(result.status == "consistent" for result in binary_results)
        binary_discrepancy_count = len(binary_results) - consistent_binary_count
        overall_discrepancy_count = (
            discrepant_count + interval_discrepancy_count + binary_discrepancy_count
        )
        lines[-1:-1] = [
            f"- **Binary count checks:** {len(binary_results)}",
            f"- **Consistent binary percentage checks:** {consistent_binary_count}",
            f"- **Binary percentage discrepancies:** {binary_discrepancy_count}",
            f"- **Overall requested-check discrepancies:** {overall_discrepancy_count}",
        ]
    for index, result in enumerate(results, start=1):
        record = result.record
        lines.extend(
            [
                f"## {index}. `{_md_code(record.statistical_input_id)}`",
                "",
                f"- **Contract version:** {record.schema_version}",
                f"- **Evidence Record:** `{_md_code(record.evidence_record_id)}`",
                f"- **Source DOI:** `{_md_code(record.source_doi)}`",
                f"- **Review status:** {_md_text(record.review_status)}",
                f"- **Outcome:** `{_md_code(record.outcome)}`",
                f"- **Time point:** {_decimal(record.timepoint_value)} "
                f"{_md_text(record.timepoint_unit)}",
                f"- **Analysis population:** {_md_text(record.analysis_population)}",
                f"- **Intervention:** {_md_text(record.intervention_label)}; mean change "
                f"`{_decimal(record.intervention_mean_change)}` "
                f"{_unit_label(record.unit)}",
                f"- **Comparator:** {_md_text(record.comparator_label)}; mean change "
                f"`{_decimal(record.comparator_mean_change)}` "
                f"{_unit_label(record.unit)}",
                f"- **Formula:** `{_md_code(record.formula)}`",
                f"- **Calculation:** `{_decimal(record.intervention_mean_change)} - "
                f"({_decimal(record.comparator_mean_change)}) = "
                f"{_decimal(result.recomputed_effect)}` {_unit_label(record.unit)}",
                f"- **Reported effect:** `{_decimal(record.reported_effect)}` "
                f"{_unit_label(record.unit)}",
                f"- **Recomputed effect:** `{_decimal(result.recomputed_effect)}` "
                f"{_unit_label(record.unit)}",
                f"- **Absolute difference:** `{_decimal(result.absolute_difference)}`",
                f"- **Tolerance:** `{_decimal(record.tolerance)}`",
                f"- **Status:** **{result.status}**",
            ]
        )
        if record.confidence_level is not None and result.interval_approximation is None:
            lines.append(
                f"- **Reported confidence interval:** "
                f"{_decimal(record.confidence_level)}% CI "
                f"`{_decimal(record.confidence_lower)}` to "
                f"`{_decimal(record.confidence_upper)}` (displayed only; not recomputed)"
            )
        elif record.confidence_level is not None:
            lines.append(
                f"- **Reported confidence interval:** "
                f"{_decimal(record.confidence_level)}% CI "
                f"`{_decimal(record.confidence_lower)}` to "
                f"`{_decimal(record.confidence_upper)}`"
            )
        if result.interval_approximation is not None:
            interval_input = record.confidence_interval_verification
            assert interval_input is not None
            interval = result.interval_approximation
            lines.extend(
                [
                    f"- **Interval method:** `{_md_code(interval_input.method)}`",
                    f"- **Arm standard errors:** intervention "
                    f"`{_decimal(interval_input.intervention_standard_error)}`; comparator "
                    f"`{_decimal(interval_input.comparator_standard_error)}`",
                    f"- **Arm sample sizes:** intervention "
                    f"`{interval_input.intervention_sample_size}`; comparator "
                    f"`{interval_input.comparator_sample_size}`",
                    f"- **Normal critical value:** `{_decimal(interval_input.critical_value)}`",
                    f"- **Approximate difference standard error:** "
                    f"`{_decimal(interval.difference_standard_error)}`",
                    f"- **Approximate margin:** `{_decimal(interval.margin)}`",
                    f"- **Approximate confidence interval:** "
                    f"`{_decimal(interval.lower)}` to `{_decimal(interval.upper)}`",
                    f"- **Endpoint differences:** lower "
                    f"`{_decimal(interval.lower_difference)}`; upper "
                    f"`{_decimal(interval.upper_difference)}`",
                    f"- **Endpoint tolerance:** `{_decimal(interval_input.endpoint_tolerance)}`",
                    f"- **Interval status:** **{interval.status}**",
                    f"- **Approximation assumption:** {_md_text(interval_input.assumption_note)}",
                ]
            )
        lines.extend(
            [
                f"- **Source span:** page {record.source_span.page_number}, "
                f"{_md_text(record.source_span.section)}",
            ]
        )
        if record.source_span.table_or_figure:
            lines.append(f"- **Table or figure:** {_md_text(record.source_span.table_or_figure)}")
        if record.source_span.locator_note:
            lines.append(f"- **Locator note:** {_md_text(record.source_span.locator_note)}")
        lines.extend(
            [
                f"- **Curated by:** {_md_text(record.provenance_created_by)}",
                f"- **Curation method:** {_md_text(record.provenance_method)}",
                f"- **Source basis:** {_md_text(record.provenance_source_basis)}",
                "",
                "**Interpretation:** `consistent` means only that the declared arithmetic "
                "inputs reproduce the declared reported effect within the declared tolerance.",
                "",
            ]
        )

    if binary_results:
        lines.extend(
            render_binary_verification_sections(binary_results, start_index=len(results) + 1)
        )

    binary_trust_boundary = (
        [
            "- Binary count calculations derive crude risk ratios only under their declared "
            "method and correction policy; they are not compared with source-adjusted odds "
            "ratios."
        ]
        if binary_results
        else []
    )
    lines.extend(
        [
            "## Trust Boundary",
            "",
            "- No value was parsed from prose or inferred from a missing field.",
            "- Confidence intervals are approximated only for records with explicit "
            "source-audited standard errors and declared assumptions; all others are "
            "display-only.",
            "- An interval marked compatible is not a reconstruction or validation of the "
            "source paper's model-based analysis.",
            *binary_trust_boundary,
            "- No cross-study pooling, ranking, sensitivity analysis, or meta-analysis was "
            "performed.",
            "- No Evidence Quality, Consensus, or Claim Confidence value was calculated or "
            "changed.",
            "- No scientific synthesis was performed.",
            "- Arithmetic consistency is not replication, legal approval, scientific review, "
            "clinical guidance, or truth determination.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_record(
    payload: Mapping[str, Any], line_number: int, errors: list[str]
) -> StatisticalInput | None:
    context = f"line {line_number}"
    raw_schema_version = payload.get("schema_version")
    schema_version: int | None = None
    if (
        isinstance(raw_schema_version, bool)
        or not isinstance(raw_schema_version, int)
        or raw_schema_version not in SUPPORTED_STATISTICAL_INPUT_SCHEMA_VERSIONS
    ):
        errors.append(f"{context}: schema_version must be integer 1 or 2.")
    else:
        schema_version = raw_schema_version

    statistical_input_id = _required_text(payload, "statistical_input_id", context, errors)
    evidence_record_id = _required_text(payload, "evidence_record_id", context, errors)
    source_doi = _required_text(payload, "source_doi", context, errors)
    review_status = _required_text(payload, "review_status", context, errors)
    effect_measure = _required_text(payload, "effect_measure", context, errors)
    outcome = _required_text(payload, "outcome", context, errors)
    unit = _required_text(payload, "unit", context, errors)
    analysis_population = _required_text(payload, "analysis_population", context, errors)
    formula = _required_text(payload, "formula", context, errors)

    if statistical_input_id and not _IDENTIFIER_PATTERN.fullmatch(statistical_input_id):
        errors.append(f"{context}: statistical_input_id has an invalid format.")
    if review_status and review_status != SUPPORTED_REVIEW_STATUS:
        errors.append(f"{context}: review_status must be {SUPPORTED_REVIEW_STATUS!r}.")
    for field, value, supported in (
        ("effect_measure", effect_measure, SUPPORTED_EFFECT_MEASURE),
        ("outcome", outcome, SUPPORTED_OUTCOME),
        ("unit", unit, SUPPORTED_UNIT),
        ("formula", formula, SUPPORTED_FORMULA),
    ):
        if value and value != supported:
            errors.append(f"{context}: {field} must be {supported!r}.")

    timepoint = _required_object(payload, "timepoint", context, errors)
    timepoint_value = _decimal_field(timepoint, "value", f"{context}.timepoint", errors)
    timepoint_unit = _required_text(timepoint, "unit", f"{context}.timepoint", errors)
    if timepoint_value is not None and timepoint_value <= 0:
        errors.append(f"{context}.timepoint.value must be positive.")
    if timepoint_unit and timepoint_unit != SUPPORTED_TIME_UNIT:
        errors.append(f"{context}.timepoint.unit must be {SUPPORTED_TIME_UNIT!r}.")

    intervention = _required_object(payload, "intervention", context, errors)
    intervention_label = _required_text(intervention, "label", f"{context}.intervention", errors)
    intervention_mean = _decimal_field(
        intervention, "mean_change", f"{context}.intervention", errors
    )
    comparator = _required_object(payload, "comparator", context, errors)
    comparator_label = _required_text(comparator, "label", f"{context}.comparator", errors)
    comparator_mean = _decimal_field(comparator, "mean_change", f"{context}.comparator", errors)
    reported_effect = _decimal_field(payload, "reported_effect", context, errors)
    tolerance = _decimal_field(payload, "tolerance", context, errors)
    if tolerance is not None and tolerance <= 0:
        errors.append(f"{context}.tolerance must be positive.")

    confidence_level: Decimal | None = None
    confidence_lower: Decimal | None = None
    confidence_upper: Decimal | None = None
    raw_ci = payload.get("reported_confidence_interval")
    if raw_ci is not None:
        if not isinstance(raw_ci, dict):
            errors.append(f"{context}.reported_confidence_interval must be an object.")
        else:
            confidence_level = _decimal_field(
                raw_ci, "level", f"{context}.reported_confidence_interval", errors
            )
            confidence_lower = _decimal_field(
                raw_ci, "lower", f"{context}.reported_confidence_interval", errors
            )
            confidence_upper = _decimal_field(
                raw_ci, "upper", f"{context}.reported_confidence_interval", errors
            )
            if confidence_level is not None and not 0 < confidence_level < 100:
                errors.append(
                    f"{context}.reported_confidence_interval.level must be between 0 and 100."
                )
            if (
                confidence_lower is not None
                and confidence_upper is not None
                and confidence_lower > confidence_upper
            ):
                errors.append(
                    f"{context}.reported_confidence_interval lower must not exceed upper."
                )
            if (
                confidence_lower is not None
                and confidence_upper is not None
                and reported_effect is not None
                and not confidence_lower <= reported_effect <= confidence_upper
            ):
                errors.append(
                    f"{context}.reported_effect must fall within the reported confidence interval."
                )

    interval_verification = _parse_confidence_interval_verification(
        payload,
        schema_version=schema_version,
        confidence_level=confidence_level,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        context=context,
        errors=errors,
    )

    source_span_payload = _required_object(payload, "source_span", context, errors)
    page_number = _positive_integer_field(
        source_span_payload, "page_number", f"{context}.source_span", errors
    )
    section = _required_text(source_span_payload, "section", f"{context}.source_span", errors)
    table_or_figure = _optional_text(
        source_span_payload, "table_or_figure", f"{context}.source_span", errors
    )
    locator_note = _optional_text(
        source_span_payload, "locator_note", f"{context}.source_span", errors
    )

    provenance = _required_object(payload, "provenance", context, errors)
    created_by = _required_text(provenance, "created_by", f"{context}.provenance", errors)
    created_date = _required_text(provenance, "created_date", f"{context}.provenance", errors)
    method = _required_text(provenance, "method", f"{context}.provenance", errors)
    source_basis = _required_text(provenance, "source_basis", f"{context}.provenance", errors)
    if created_date:
        try:
            date.fromisoformat(created_date)
        except ValueError:
            errors.append(f"{context}.provenance.created_date must be an ISO 8601 date.")

    if errors:
        return None
    assert timepoint_value is not None
    assert intervention_mean is not None
    assert comparator_mean is not None
    assert reported_effect is not None
    assert tolerance is not None
    assert page_number is not None
    assert schema_version is not None
    return StatisticalInput(
        schema_version=schema_version,
        statistical_input_id=statistical_input_id,
        evidence_record_id=evidence_record_id,
        source_doi=source_doi,
        review_status=review_status,
        effect_measure=effect_measure,
        outcome=outcome,
        unit=unit,
        timepoint_value=timepoint_value,
        timepoint_unit=timepoint_unit,
        analysis_population=analysis_population,
        intervention_label=intervention_label,
        intervention_mean_change=intervention_mean,
        comparator_label=comparator_label,
        comparator_mean_change=comparator_mean,
        reported_effect=reported_effect,
        confidence_level=confidence_level,
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        confidence_interval_verification=interval_verification,
        formula=formula,
        tolerance=tolerance,
        source_span=SourceSpan(page_number, section, table_or_figure, locator_note),
        provenance_created_by=created_by,
        provenance_created_date=created_date,
        provenance_method=method,
        provenance_source_basis=source_basis,
        line_number=line_number,
    )


def _parse_confidence_interval_verification(
    payload: Mapping[str, Any],
    *,
    schema_version: int | None,
    confidence_level: Decimal | None,
    confidence_lower: Decimal | None,
    confidence_upper: Decimal | None,
    context: str,
    errors: list[str],
) -> ConfidenceIntervalVerificationInput | None:
    raw = payload.get("confidence_interval_verification")
    if raw is None:
        return None
    interval_context = f"{context}.confidence_interval_verification"
    if schema_version != 2:
        errors.append(
            f"{interval_context} is supported only by statistical input schema version 2."
        )
    if not isinstance(raw, dict):
        errors.append(f"{interval_context} must be an object.")
        return None

    method = _required_text(raw, "method", interval_context, errors)
    intervention_se = _decimal_field(raw, "intervention_standard_error", interval_context, errors)
    comparator_se = _decimal_field(raw, "comparator_standard_error", interval_context, errors)
    intervention_n = _positive_integer_field(
        raw, "intervention_sample_size", interval_context, errors
    )
    comparator_n = _positive_integer_field(raw, "comparator_sample_size", interval_context, errors)
    critical_value = _decimal_field(raw, "critical_value", interval_context, errors)
    endpoint_tolerance = _decimal_field(raw, "endpoint_tolerance", interval_context, errors)
    assumption_note = _required_text(raw, "assumption_note", interval_context, errors)

    if method and method != SUPPORTED_CONFIDENCE_INTERVAL_METHOD:
        errors.append(
            f"{interval_context}.method must be {SUPPORTED_CONFIDENCE_INTERVAL_METHOD!r}."
        )
    for field, value in (
        ("intervention_standard_error", intervention_se),
        ("comparator_standard_error", comparator_se),
    ):
        if value is not None and value <= 0:
            errors.append(f"{interval_context}.{field} must be positive.")
    if critical_value is not None and critical_value != SUPPORTED_CRITICAL_VALUE:
        errors.append(
            f"{interval_context}.critical_value must be {_decimal(SUPPORTED_CRITICAL_VALUE)}."
        )
    if endpoint_tolerance is not None and endpoint_tolerance <= 0:
        errors.append(f"{interval_context}.endpoint_tolerance must be positive.")
    if confidence_level != SUPPORTED_CONFIDENCE_LEVEL:
        errors.append(f"{interval_context} requires a reported 95% confidence interval.")
    if confidence_lower is None or confidence_upper is None:
        errors.append(
            f"{interval_context} requires complete reported confidence interval endpoints."
        )

    if any(
        value is None
        for value in (
            intervention_se,
            comparator_se,
            intervention_n,
            comparator_n,
            critical_value,
            endpoint_tolerance,
        )
    ):
        return None
    assert intervention_se is not None
    assert comparator_se is not None
    assert intervention_n is not None
    assert comparator_n is not None
    assert critical_value is not None
    assert endpoint_tolerance is not None
    return ConfidenceIntervalVerificationInput(
        method=method,
        intervention_standard_error=intervention_se,
        comparator_standard_error=comparator_se,
        intervention_sample_size=intervention_n,
        comparator_sample_size=comparator_n,
        critical_value=critical_value,
        endpoint_tolerance=endpoint_tolerance,
        assumption_note=assumption_note,
    )


def _approximate_confidence_interval(
    record: StatisticalInput,
) -> ConfidenceIntervalApproximation | None:
    interval_input = record.confidence_interval_verification
    if interval_input is None:
        return None
    assert record.confidence_lower is not None
    assert record.confidence_upper is not None
    with localcontext() as context:
        context.prec = 28
        variance = (
            interval_input.intervention_standard_error**2
            + interval_input.comparator_standard_error**2
        )
        difference_standard_error = variance.sqrt(context=context)
        margin = interval_input.critical_value * difference_standard_error
        lower = record.reported_effect - margin
        upper = record.reported_effect + margin
        lower_difference = abs(lower - record.confidence_lower)
        upper_difference = abs(upper - record.confidence_upper)
    status = (
        "compatible"
        if max(lower_difference, upper_difference) <= interval_input.endpoint_tolerance
        else "discrepant"
    )
    return ConfidenceIntervalApproximation(
        difference_standard_error=difference_standard_error,
        margin=margin,
        lower=lower,
        upper=upper,
        lower_difference=lower_difference,
        upper_difference=upper_difference,
        status=status,
    )


def _validate_evidence_reference(
    record: StatisticalInput,
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


def _positive_integer_field(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> int | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors.append(f"{context}.{field} must be a positive integer.")
        return None
    return value


def _decimal(value: Decimal | None) -> str:
    if value is None:
        return "Not recorded"
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


def _unit_label(value: str) -> str:
    return _md_text(value.replace("_", " "))
