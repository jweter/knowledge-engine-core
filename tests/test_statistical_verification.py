import json
from decimal import Decimal
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from knowledge_engine.cli import app
from knowledge_engine.statistical_verification import (
    render_statistical_verification_report,
    validate_statistical_inputs,
    verify_statistical_inputs,
)


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "statistical_input_id": "stat-step5-001",
        "evidence_record_id": "ev-step5",
        "source_doi": "10.1038/s41591-022-02026-4",
        "review_status": "source_verified",
        "effect_measure": "difference_in_mean_change",
        "outcome": "body_weight_change_from_baseline",
        "unit": "percentage_points",
        "timepoint": {"value": 104, "unit": "weeks"},
        "analysis_population": "Treatment-policy estimand; all randomized participants.",
        "intervention": {"label": "Semaglutide", "mean_change": -15.2},
        "comparator": {"label": "Placebo", "mean_change": -2.6},
        "reported_effect": -12.6,
        "reported_confidence_interval": {"level": 95, "lower": -15.3, "upper": -9.8},
        "formula": "intervention_minus_comparator",
        "tolerance": 0.05,
        "source_span": {
            "page_number": 2,
            "section": "Results",
            "table_or_figure": "Table 2",
            "locator_note": "Co-primary endpoint.",
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


def test_exact_decimal_verification_and_report_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "inputs.jsonl"
    _write(path, _payload())

    validation = validate_statistical_inputs(path, evidence_records=_evidence())
    first = verify_statistical_inputs(validation.records)
    second = verify_statistical_inputs(validation.records)

    assert validation.valid
    assert first == second
    assert first[0].recomputed_effect == Decimal("-12.6")
    assert first[0].absolute_difference == Decimal("0.0")
    assert first[0].status == "consistent"
    report = render_statistical_verification_report(first)
    assert "`-15.2 - (-2.6) = -12.6` percentage points" in report
    assert "95% CI `-15.3` to `-9.8` (displayed only; not recomputed)" in report
    assert "Arithmetic consistency is not replication" in report
    assert report == render_statistical_verification_report(second)


def test_discrepancy_is_deterministic(tmp_path: Path) -> None:
    payload = _payload()
    payload["reported_effect"] = -12.4
    path = tmp_path / "inputs.jsonl"
    _write(path, payload)

    validation = validate_statistical_inputs(path, evidence_records=_evidence())
    result = verify_statistical_inputs(validation.records)[0]

    assert validation.valid
    assert result.recomputed_effect == Decimal("-12.6")
    assert result.absolute_difference == Decimal("0.2")
    assert result.status == "discrepant"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda value: value.update(schema_version=True), "schema_version must be integer 1"),
        (
            lambda value: value.update(statistical_input_id="Bad ID"),
            "statistical_input_id has an invalid format",
        ),
        (
            lambda value: value.update(effect_measure="risk_ratio"),
            "effect_measure must be 'difference_in_mean_change'",
        ),
        (
            lambda value: value.update(outcome="waist_circumference"),
            "outcome must be 'body_weight_change_from_baseline'",
        ),
        (
            lambda value: value["timepoint"].update(value=0),
            "timepoint.value must be positive",
        ),
        (
            lambda value: value["intervention"].update(mean_change=True),
            "intervention.mean_change must be a finite JSON number",
        ),
        (lambda value: value.update(tolerance=0), "tolerance must be positive"),
        (
            lambda value: value["reported_confidence_interval"].update(lower=-9, upper=-15),
            "lower must not exceed upper",
        ),
        (
            lambda value: value["source_span"].update(page_number=0),
            "source_span.page_number must be a positive integer",
        ),
        (
            lambda value: value["provenance"].update(created_date="August 4"),
            "provenance.created_date must be an ISO 8601 date",
        ),
    ],
)
def test_contract_rejects_invalid_fields(
    tmp_path: Path,
    mutate: object,
    expected: str,
) -> None:
    payload = _payload()
    assert callable(mutate)
    mutate(payload)
    path = tmp_path / "inputs.jsonl"
    _write(path, payload)

    result = validate_statistical_inputs(path, evidence_records=_evidence())

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
def test_reference_validation_rejects_mismatches(
    tmp_path: Path,
    evidence_mutation: object,
    expected: str,
) -> None:
    path = tmp_path / "inputs.jsonl"
    _write(path, _payload())
    evidence = _evidence()
    assert callable(evidence_mutation)
    evidence_mutation(evidence[0])

    result = validate_statistical_inputs(path, evidence_records=evidence)

    assert not result.valid
    assert any(expected in error for error in result.errors)


def test_typed_locator_can_differ_from_evidence_claim_locator(tmp_path: Path) -> None:
    payload = _payload()
    payload["source_span"] = {"page_number": 4, "section": "Results / Body weight"}
    path = tmp_path / "inputs.jsonl"
    _write(path, payload)

    result = validate_statistical_inputs(path, evidence_records=_evidence())

    assert result.valid
    assert result.records[0].source_span.page_number == 4
    assert result.records[0].source_span.section == "Results / Body weight"


def test_unknown_reference_malformed_json_and_duplicate_ids_are_rejected(
    tmp_path: Path,
) -> None:
    unknown = _payload()
    unknown["evidence_record_id"] = "ev-unknown"
    path = tmp_path / "inputs.jsonl"
    path.write_text(
        json.dumps(unknown) + "\n{" + "\n" + json.dumps(_payload()) + "\n" + json.dumps(_payload()),
        encoding="utf-8",
    )

    result = validate_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert any("line 1: unknown evidence_record_id" in error for error in result.errors)
    assert any("line 2: invalid JSON object" in error for error in result.errors)
    assert any("line 4: duplicate statistical_input_id" in error for error in result.errors)


def test_duplicate_json_fields_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "inputs.jsonl"
    raw = json.dumps(_payload(), separators=(",", ":"))
    raw = raw.replace('"schema_version":1', '"schema_version":1,"schema_version":1')
    path.write_text(raw + "\n", encoding="utf-8")

    result = validate_statistical_inputs(path, evidence_records=_evidence())

    assert not result.valid
    assert result.errors == ("line 1: duplicate JSON field 'schema_version'.",)


def test_report_escapes_source_controlled_markdown(tmp_path: Path) -> None:
    payload = _payload()
    payload["analysis_population"] = "Adults [reviewed]\n# Injected"
    payload["intervention"] = {"label": "Drug **[A]**", "mean_change": -15.2}
    path = tmp_path / "inputs.jsonl"
    _write(path, payload)

    validation = validate_statistical_inputs(path, evidence_records=_evidence())
    report = render_statistical_verification_report(verify_statistical_inputs(validation.records))

    assert validation.valid
    assert "Adults \\[reviewed\\] \\# Injected" in report
    assert "Drug \\*\\*\\[A\\]\\*\\*" in report
    assert "\n# Injected" not in report


def test_committed_step5_and_select_inputs_verify_without_database(
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
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Typed inputs: 2" in result.output
    assert "Consistent arithmetic checks: 2" in result.output
    assert "Discrepancies: 0" in result.output
    report = output.read_text(encoding="utf-8")
    assert "stat-glp1-step5-week104-treatment-difference-001" in report
    assert "stat-glp1-select-week208-treatment-difference-001" in report
    assert "`-15.2 - (-2.6) = -12.6`" in report
    assert "`-10.2 - (-1.5) = -8.7`" in report
    assert "95% CI `-9.42` to `-7.88` (displayed only; not recomputed)" in report
    assert "In-trial intention-to-treat analysis" in report
    assert "**Source span:** page 4, Results / Change in body weight" in report
    assert report.index("stat-glp1-step5") < report.index("stat-glp1-select")
    assert report.count("**Status:** **consistent**") == 2
    assert "No scientific synthesis was performed" in report
    assert not (tmp_path / "data" / "knowledge_engine.sqlite3").exists()


def test_cli_discrepancy_exits_one_after_rendering(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    first_line = (corpus / "statistical_inputs.jsonl").read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)
    payload["reported_effect"] = -12.4
    inputs = tmp_path / "discrepant.jsonl"
    output = tmp_path / "report.md"
    _write(inputs, payload)

    result = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(inputs),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "Discrepancies: 1" in result.output
    assert "**Status:** **discrepant**" in output.read_text(encoding="utf-8")


def test_cli_terminal_and_forced_file_output_match(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    inputs = corpus / "statistical_inputs.jsonl"
    evidence = corpus / "evidence_records.jsonl"
    output = tmp_path / "report.md"
    output.write_text("replace me", encoding="utf-8")

    terminal = CliRunner().invoke(
        app,
        ["statistical-verify", str(inputs), "--evidence", str(evidence)],
    )
    written = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(inputs),
            "--evidence",
            str(evidence),
            "--output",
            str(output),
            "--force",
        ],
    )

    assert terminal.exit_code == 0, terminal.output
    assert written.exit_code == 0, written.output
    assert terminal.output == output.read_text(encoding="utf-8")


def test_cli_rejects_invalid_input_and_protects_outputs(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    evidence = corpus / "evidence_records.jsonl"
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("{\n", encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("keep", encoding="utf-8")

    invalid_result = CliRunner().invoke(
        app, ["statistical-verify", str(invalid), "--evidence", str(evidence)]
    )
    existing_result = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(corpus / "statistical_inputs.jsonl"),
            "--evidence",
            str(evidence),
            "--output",
            str(output),
        ],
    )
    overwrite_input = CliRunner().invoke(
        app,
        [
            "statistical-verify",
            str(corpus / "statistical_inputs.jsonl"),
            "--evidence",
            str(evidence),
            "--output",
            str(evidence),
            "--force",
        ],
    )

    assert invalid_result.exit_code == 1
    assert "line 1: invalid JSON object" in invalid_result.output
    assert existing_result.exit_code == 2
    assert "Use --force to overwrite" in unstyle(existing_result.output)
    assert overwrite_input.exit_code == 2
    assert "must not overwrite an input file" in overwrite_input.output
    assert output.read_text(encoding="utf-8") == "keep"
