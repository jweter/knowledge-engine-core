"""Typed, deterministic verification of explicitly curated statistical inputs.

Version 1 supports one arithmetic identity: the difference between intervention
and comparator mean changes. Values are never extracted from prose, and a
consistent result is not a judgment about scientific validity.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from knowledge_engine.utils import normalize_doi

STATISTICAL_INPUT_SCHEMA_VERSION = 1
SUPPORTED_EFFECT_MEASURE = "difference_in_mean_change"
SUPPORTED_FORMULA = "intervention_minus_comparator"
SUPPORTED_OUTCOME = "body_weight_change_from_baseline"
SUPPORTED_UNIT = "percentage_points"
SUPPORTED_TIME_UNIT = "weeks"
SUPPORTED_REVIEW_STATUS = "source_verified"
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
class StatisticalInput:
    """One source-linked reported effect with explicit formula inputs."""

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
        results.append(
            StatisticalVerification(
                record=record,
                recomputed_effect=recomputed,
                absolute_difference=absolute_difference,
                status=status,
            )
        )
    return tuple(results)


def render_statistical_verification_report(
    results: Sequence[StatisticalVerification],
) -> str:
    """Render deterministic Markdown for already-validated results."""

    consistent_count = sum(result.status == "consistent" for result in results)
    discrepant_count = len(results) - consistent_count
    lines = [
        "# Statistical Verification Report",
        "",
        "## Summary",
        "",
        f"- **Contract version:** {STATISTICAL_INPUT_SCHEMA_VERSION}",
        f"- **Typed inputs:** {len(results)}",
        f"- **Consistent arithmetic checks:** {consistent_count}",
        f"- **Discrepancies:** {discrepant_count}",
        "",
        "These checks use only explicitly curated formula inputs. No numerical value "
        "was extracted from Evidence Record prose.",
        "",
    ]
    for index, result in enumerate(results, start=1):
        record = result.record
        lines.extend(
            [
                f"## {index}. `{_md_code(record.statistical_input_id)}`",
                "",
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
        if record.confidence_level is not None:
            lines.append(
                f"- **Reported confidence interval:** "
                f"{_decimal(record.confidence_level)}% CI "
                f"`{_decimal(record.confidence_lower)}` to "
                f"`{_decimal(record.confidence_upper)}` (displayed only; not recomputed)"
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

    lines.extend(
        [
            "## Trust Boundary",
            "",
            "- No value was parsed from prose or inferred from a missing field.",
            "- No confidence interval was recomputed.",
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
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != STATISTICAL_INPUT_SCHEMA_VERSION:
        errors.append(f"{context}: schema_version must be integer 1.")

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
    return StatisticalInput(
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
        formula=formula,
        tolerance=tolerance,
        source_span=SourceSpan(page_number, section, table_or_figure, locator_note),
        provenance_created_by=created_by,
        provenance_created_date=created_date,
        provenance_method=method,
        provenance_source_basis=source_basis,
        line_number=line_number,
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
