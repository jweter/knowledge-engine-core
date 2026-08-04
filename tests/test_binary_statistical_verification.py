import json
from decimal import Decimal
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from knowledge_engine.binary_statistical_verification import (
    render_binary_verification_sections,
    validate_binary_statistical_inputs,
    verify_binary_statistical_inputs,
)
from knowledge_engine.cli import app


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "binary_input_id": "binary-step5-001",
        "evidence_record_id": "ev-step5",
        "source_doi": "10.1038/s41591-022-02026-4",
        "review_status": "source_verified",
        "effect_measure": "crude_risk_ratio",
        "outcome": "achievement_of_at_least_5_percent_weight_loss",
        "timepoint": {"value": 104, "unit": "weeks"},
        "analysis_population": "Observed week-104 participants; not the adjusted estimand.",
        "intervention": {
            "label": "Semaglutide",
            "events": 111,
            "total": 144,
            "reported_percentage": 77.1,
        },
        "comparator": {
            "label": "Placebo",
            "events": 44,
            "total": 128,
            "reported_percentage": 34.4,
        },
        "calculation": {
            "method": "crude_risk_ratio_log_wald",
            "confidence_level": 95,
            "critical_value": 1.96,
            "continuity_correction": "none",
            "continuity_correction_value": 0,
            "reported_percentage_tolerance": 0.05,
            "assumption_note": "Crude observed-count calculation; not the source model.",
        },
        "source_reported_comparison": {
            "measure": "adjusted_odds_ratio",
            "estimate": 5.0,
            "confidence_interval": {"level": 95, "lower": 3.0, "upper": 8.4},
            "method_note": "Adjusted logistic regression with multiple imputation.",
            "comparison_policy": "display_only_not_compared",
        },
        "source_span": {
            "page_number": 5,
            "section": "Table 2",
            "table_or_figure": "Table 2",
            "locator_note": "Observed counts and percentages.",
        },
        "method_source_span": {
            "page_number": 6,
            "section": "Table 2 notes",
            "locator_note": "Adjusted method context.",
        },
        "provenance": {
            "created_by": "Reviewer",
            "created_date": "2026-08-04",
            "method": "Manual source transcription.",
            "source_basis": "Legally usable source PDF.",
        },
    }


def _evidence() -> list[dict[str, object]]:
    return [
        {
            "evidence_record_id": "ev-step5",
            "source_doi": "https://doi.org/10.1038/S41591-022-02026-4",
            "review_status": "reviewed",
            "outcome": "Percentage change in body weight from baseline.",
            "source_span": {"page_number": 2, "section": "Results"},
        }
    ]


def _write(path: Path, *payloads: object) -> None:
    path.write_text(
        "\n".join(json.dumps(payload, separators=(",", ":")) for payload in payloads) + "\n",
        encoding="utf-8",
    )


def test_binary_calculation_is_exact_deterministic_and_non_equivalent(tmp_path: Path) -> None:
    path = tmp_path / "binary.jsonl"
    _write(path, _payload())

    validation = validate_binary_statistical_inputs(path, evidence_records=_evidence())
    first = verify_binary_statistical_inputs(validation.records)[0]
    second = verify_binary_statistical_inputs(validation.records)[0]

    assert validation.valid
    assert first == second
    assert first.intervention_percentage == Decimal("77.08333333333333333333333333")
    assert first.comparator_percentage == Decimal("34.37500")
    assert first.intervention_percentage_difference == Decimal("0.01666666666666666666666667")
    assert first.comparator_percentage_difference == Decimal("0.02500")
    assert first.risk_ratio == Decimal("2.242424242424242424242424242")
    assert first.log_risk_ratio_standard_error == Decimal("0.1303047861432468329166826695")
    assert first.confidence_lower == Decimal("1.737001152739515274479743155")
    assert first.confidence_upper == Decimal("2.894912576817396082275094335")
    assert first.status == "consistent"
    assert not first.has_discrepancy
    report = "\n".join(render_binary_verification_sections((first,), start_index=3))
    assert "## 3. `binary-step5-001`" in report
    assert "**Calculated crude risk ratio:** `2.242424242424242424242424242`" in report
    assert "`adjusted_odds_ratio` `5` (95% CI `3` to `8.4`; display only)" in report
    assert "the two are not compared" in report


def test_reported_percentage_discrepancy_is_separate_from_derived_ratio(tmp_path: Path) -> None:
    payload = _payload()
    intervention = payload["intervention"]
    assert isinstance(intervention, dict)
    intervention["reported_percentage"] = 76.9
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    validation = validate_binary_statistical_inputs(path, evidence_records=_evidence())
    result = verify_binary_statistical_inputs(validation.records)[0]

    assert validation.valid
    assert result.risk_ratio == Decimal("2.242424242424242424242424242")
    assert result.status == "discrepant"
    assert result.has_discrepancy


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda value: value.update(schema_version=True), "schema_version must be integer 1"),
        (lambda value: value.update(schema_version=2), "schema_version must be integer 1"),
        (lambda value: value.update(binary_input_id="Bad ID"), "invalid format"),
        (lambda value: value.update(review_status="draft"), "review_status must be"),
        (lambda value: value.update(effect_measure="odds_ratio"), "effect_measure must be"),
        (lambda value: value.update(outcome="any_weight_loss"), "outcome must be"),
        (lambda value: value["timepoint"].update(value=0), "timepoint.value must be positive"),
        (lambda value: value["timepoint"].update(unit="days"), "timepoint.unit must be"),
        (lambda value: value.update(extra="field"), "unsupported field 'extra'"),
        (
            lambda value: value["provenance"].update(created_date="August 4"),
            "created_date must be an ISO 8601 date",
        ),
    ],
)
def test_binary_contract_rejects_invalid_common_fields(
    tmp_path: Path, mutate: object, expected: str
) -> None:
    payload = _payload()
    assert callable(mutate)
    mutate(payload)
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any(expected in error for error in result.errors)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("events", True, "events must be a JSON integer"),
        ("events", 0, "events must be positive"),
        ("events", -1, "events must be positive"),
        ("events", 145, "events must not exceed total"),
        ("total", True, "total must be a positive integer"),
        ("total", 0, "total must be a positive integer"),
        ("reported_percentage", -1, "must be between 0 and 100"),
        ("reported_percentage", 101, "must be between 0 and 100"),
    ],
)
def test_binary_contract_rejects_invalid_arm_values(
    tmp_path: Path, field: str, value: object, expected: str
) -> None:
    payload = _payload()
    arm = payload["intervention"]
    assert isinstance(arm, dict)
    arm[field] = value
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any(expected in error for error in result.errors)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("method", "fisher_exact", "method must be 'crude_risk_ratio_log_wald'"),
        ("confidence_level", 90, "confidence_level must be 95"),
        ("critical_value", 1.645, "critical_value must be 1.96"),
        ("continuity_correction", "haldane_anscombe", "continuity_correction must be 'none'"),
        ("continuity_correction_value", 0.5, "continuity_correction_value must be 0"),
        ("reported_percentage_tolerance", 0, "reported_percentage_tolerance must be positive"),
        ("assumption_note", "  ", "assumption_note must be non-empty text"),
    ],
)
def test_binary_contract_rejects_unsupported_calculation_policy(
    tmp_path: Path, field: str, value: object, expected: str
) -> None:
    payload = _payload()
    calculation = payload["calculation"]
    assert isinstance(calculation, dict)
    calculation[field] = value
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any(expected in error for error in result.errors)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda value: value.update(measure="risk_ratio"),
            "measure must be 'adjusted_odds_ratio'",
        ),
        (lambda value: value.update(estimate=0), "estimate must be positive"),
        (
            lambda value: value.update(comparison_policy="compare"),
            "comparison_policy must be 'display_only_not_compared'",
        ),
        (
            lambda value: value["confidence_interval"].update(level=90),
            "confidence_interval.level must be 95",
        ),
        (
            lambda value: value["confidence_interval"].update(lower=9, upper=3),
            "lower must not exceed upper",
        ),
        (
            lambda value: value.update(estimate=9),
            "estimate must fall within the reported confidence interval",
        ),
    ],
)
def test_source_adjusted_comparison_is_strictly_display_only(
    tmp_path: Path, mutate: object, expected: str
) -> None:
    payload = _payload()
    comparison = payload["source_reported_comparison"]
    assert isinstance(comparison, dict)
    assert callable(mutate)
    mutate(comparison)
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any(expected in error for error in result.errors)


@pytest.mark.parametrize(
    ("evidence_mutation", "expected"),
    [
        (lambda record: record.update(review_status="draft"), "must be reviewed"),
        (lambda record: record.update(source_doi="10.1000/wrong"), "source_doi does not match"),
        (lambda record: record.update(outcome="Blood pressure"), "body-weight outcome"),
        (
            lambda record: record.update(source_span={"page_number": 0, "section": ""}),
            "must have a valid source span",
        ),
    ],
)
def test_binary_reference_validation_rejects_mismatches(
    tmp_path: Path, evidence_mutation: object, expected: str
) -> None:
    path = tmp_path / "binary.jsonl"
    _write(path, _payload())
    evidence = _evidence()
    assert callable(evidence_mutation)
    evidence_mutation(evidence[0])

    result = validate_binary_statistical_inputs(path, evidence_records=evidence)

    assert not result.valid
    assert any(expected in error for error in result.errors)


def test_binary_contract_rejects_unknown_reference_malformed_json_and_duplicate_ids(
    tmp_path: Path,
) -> None:
    unknown = _payload()
    unknown["evidence_record_id"] = "ev-unknown"
    path = tmp_path / "binary.jsonl"
    path.write_text(
        json.dumps(unknown) + "\n{" + "\n" + json.dumps(_payload()) + "\n" + json.dumps(_payload()),
        encoding="utf-8",
    )

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any("line 1: unknown evidence_record_id" in error for error in result.errors)
    assert any("line 2: invalid JSON object" in error for error in result.errors)
    assert any("line 4: duplicate binary_input_id" in error for error in result.errors)


def test_binary_contract_rejects_duplicate_json_fields(tmp_path: Path) -> None:
    path = tmp_path / "binary.jsonl"
    raw = json.dumps(_payload(), separators=(",", ":"))
    raw = raw.replace('"schema_version":1', '"schema_version":1,"schema_version":1')
    path.write_text(raw + "\n", encoding="utf-8")

    result = validate_binary_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert result.errors == ("line 1: duplicate JSON field 'schema_version'.",)


def test_binary_report_escapes_source_controlled_markdown(tmp_path: Path) -> None:
    payload = _payload()
    payload["analysis_population"] = "Adults [reviewed]\n# Injected"
    intervention = payload["intervention"]
    assert isinstance(intervention, dict)
    intervention["label"] = "Drug **[A]**"
    path = tmp_path / "binary.jsonl"
    _write(path, payload)

    validation = validate_binary_statistical_inputs(path, evidence_records=_evidence())
    result = verify_binary_statistical_inputs(validation.records)
    report = "\n".join(render_binary_verification_sections(result, start_index=1))

    assert validation.valid
    assert "Adults \\[reviewed\\] \\# Injected" in report
    assert "Drug \\*\\*\\[A\\]\\*\\*" in report
    assert "\n# Injected" not in report


def test_committed_binary_input_verifies_with_continuous_report_and_no_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    output = tmp_path / "verification.md"
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(corpus / "statistical_inputs.jsonl"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--binary-inputs",
            str(corpus / "binary_statistical_inputs.jsonl"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Typed inputs: 2" in result.output
    assert "Binary count checks: 1" in result.output
    assert "Consistent binary percentage checks: 1" in result.output
    assert "Binary percentage discrepancies: 0" in result.output
    assert "Overall requested-check discrepancies: 0" in result.output
    report = output.read_text(encoding="utf-8")
    assert "binary-glp1-step5-week104-five-percent-response-001" in report
    assert "`111/144`" in report
    assert "`44/128`" in report
    assert "**Calculated crude risk ratio:** `2.242424242424242424242424242`" in report
    assert "adjusted odds ratio and the two are not compared" in report
    assert "No scientific synthesis was performed" in report
    assert not (tmp_path / "data" / "knowledge_engine.sqlite3").exists()


def test_binary_discrepancy_exits_one_after_rendering(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    payload = _payload()
    intervention = payload["intervention"]
    assert isinstance(intervention, dict)
    intervention["reported_percentage"] = 70
    payload["evidence_record_id"] = "ev-glp1-step5-body-weight-week104-001"
    binary_inputs = tmp_path / "binary.jsonl"
    output = tmp_path / "report.md"
    _write(binary_inputs, payload)

    result = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(corpus / "statistical_inputs.jsonl"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--binary-inputs",
            str(binary_inputs),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "Binary percentage discrepancies: 1" in result.output
    assert "Overall requested-check discrepancies: 1" in result.output
    assert "**Binary status:** **discrepant**" in output.read_text(encoding="utf-8")


def test_binary_input_is_protected_from_output_overwrite(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    binary_inputs = tmp_path / "binary.jsonl"
    _write(binary_inputs, _payload())

    result = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(corpus / "statistical_inputs.jsonl"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--binary-inputs",
            str(binary_inputs),
            "--output",
            str(binary_inputs),
            "--force",
        ],
    )

    assert result.exit_code == 2
    assert "must not overwrite an input file" in unstyle(result.output)


def test_statistical_verify_help_documents_optional_binary_contract() -> None:
    result = CliRunner().invoke(app, ["statistical-verify", "--help"])

    assert result.exit_code == 0
    assert "--binary-inputs" in unstyle(result.output)
