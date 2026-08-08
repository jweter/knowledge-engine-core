import json
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from knowledge_engine.binary_statistical_verification import (
    validate_binary_statistical_inputs,
    verify_binary_statistical_inputs,
)
from knowledge_engine.cli import app
from knowledge_engine.statistical_readiness import (
    NOT_READY_VERDICT,
    READY_VERDICT,
    StatisticalReadinessError,
    StatisticalReadinessResult,
    load_statistical_readiness_map,
    render_statistical_readiness_report,
    validate_statistical_readiness,
)
from knowledge_engine.statistical_verification import (
    validate_statistical_inputs,
    verify_statistical_inputs,
)


def _evidence(evidence_record_id: str, *, review_status: str = "reviewed") -> dict[str, object]:
    return {"evidence_record_id": evidence_record_id, "review_status": review_status}


def _record(
    evidence_record_id: str,
    *,
    readiness_category: str = "not_selected_for_verification",
    continuous_input_ids: list[str] | None = None,
    binary_input_ids: list[str] | None = None,
    compatibility_group: str | None = None,
    incompatibility_reasons: list[str] | None = None,
    review_note: str = "Reviewed context; no typed input promoted.",
) -> dict[str, object]:
    return {
        "evidence_record_id": evidence_record_id,
        "readiness_category": readiness_category,
        "continuous_input_ids": continuous_input_ids or [],
        "binary_input_ids": binary_input_ids or [],
        "compatibility_group": compatibility_group,
        "incompatibility_reasons": incompatibility_reasons or [],
        "review_note": review_note,
    }


def _map_payload(
    *records: dict[str, object],
    continuous_inputs: list[str] | None = None,
    binary_inputs: list[str] | None = None,
    schema_version: object = 1,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "research_question": "Do GLP-1 receptor agonists reduce body weight?",
        "golden_evidence_map": "test-map-v1",
        "continuous_inputs": continuous_inputs or [],
        "binary_inputs": binary_inputs or [],
        "records": list(records),
    }


def _validate(
    payload: dict[str, object],
    *,
    golden_map_evidence_record_ids: set[str],
    evidence_records_by_id: dict[str, dict[str, object]],
    continuous_input_ids: set[str] | None = None,
    binary_input_ids: set[str] | None = None,
) -> StatisticalReadinessResult:
    return validate_statistical_readiness(
        payload,
        golden_map_evidence_record_ids=golden_map_evidence_record_ids,
        evidence_records_by_id=evidence_records_by_id,
        continuous_input_ids=continuous_input_ids or set(),
        binary_input_ids=binary_input_ids or set(),
    )


def test_valid_minimal_map_is_accepted() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified"),
        _record("ev-b"),
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    assert result.valid
    assert len(result.records) == 2
    assert result.category_counts == {"exactly_verified": 1, "not_selected_for_verification": 1}


@pytest.mark.parametrize("schema_version", [True, 2, "1", 0])
def test_unsupported_schema_version_is_rejected(schema_version: object) -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"), schema_version=schema_version)

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert "schema_version must be integer 1." in result.errors


@pytest.mark.parametrize("field", ["evidence_record_id", "readiness_category", "review_note"])
def test_missing_required_field_is_rejected(field: str) -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    record = _record("ev-a")
    del record[field]
    payload = _map_payload(record)

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any(f"{field} must be a nonblank string" in error for error in result.errors)


def test_unknown_readiness_category_is_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a", readiness_category="bogus_category"))

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any("is not a supported category" in error for error in result.errors)


def test_duplicate_evidence_record_id_is_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"), _record("ev-a"))

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any("duplicate evidence_record_id" in error for error in result.errors)


def test_evidence_record_id_not_selected_by_golden_map_is_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-outside": _evidence("ev-outside")}
    payload = _map_payload(_record("ev-a"), _record("ev-outside"))

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any(
        "is not selected by the reviewed golden evidence map" in error for error in result.errors
    )


def test_missing_golden_map_coverage_is_reported_per_record() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"))

    result = _validate(
        payload,
        golden_map_evidence_record_ids={"ev-a", "ev-b"},
        evidence_records_by_id=evidence,
    )

    assert not result.valid
    assert any("'ev-b' has no readiness classification" in error for error in result.errors)


def test_unknown_evidence_record_id_not_found_among_validated_records_is_rejected() -> None:
    payload = _map_payload(_record("ev-a"))

    result = _validate(payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id={})

    assert not result.valid
    assert any("was not found among validated Evidence Records" in error for error in result.errors)


def test_unreviewed_evidence_record_is_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a", review_status="draft")}
    payload = _map_payload(_record("ev-a"))

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any("is not a reviewed Evidence Record" in error for error in result.errors)


def test_unknown_continuous_and_binary_input_ids_are_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(
        _record(
            "ev-a",
            readiness_category="exactly_verified",
            continuous_input_ids=["stat-unknown"],
            binary_input_ids=["binary-unknown"],
        )
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any(
        "continuous_input_ids references unknown input id 'stat-unknown'" in error
        for error in result.errors
    )
    assert any(
        "binary_input_ids references unknown input id 'binary-unknown'" in error
        for error in result.errors
    )


def test_declared_top_level_inputs_referencing_unknown_ids_are_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"), continuous_inputs=["stat-unknown"])

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any(
        "continuous_inputs references unknown or unvalidated input id 'stat-unknown'" in error
        for error in result.errors
    )


def test_duplicate_input_assignment_across_records_is_rejected() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record(
            "ev-a", readiness_category="exactly_verified", continuous_input_ids=["stat-shared"]
        ),
        _record(
            "ev-b", readiness_category="exactly_verified", continuous_input_ids=["stat-shared"]
        ),
    )

    result = _validate(
        payload,
        golden_map_evidence_record_ids={"ev-a", "ev-b"},
        evidence_records_by_id=evidence,
        continuous_input_ids={"stat-shared"},
    )

    assert not result.valid
    assert any(
        "continuous input id 'stat-shared' is already assigned to 'ev-a'" in error
        for error in result.errors
    )


def test_records_must_be_a_nonempty_list() -> None:
    payload = _map_payload()
    payload["records"] = []

    result = _validate(payload, golden_map_evidence_record_ids=set(), evidence_records_by_id={})

    assert not result.valid
    assert "records must be a nonempty list." in result.errors


def test_non_object_record_is_rejected() -> None:
    payload = _map_payload()
    payload["records"] = ["not-an-object"]

    result = _validate(payload, golden_map_evidence_record_ids=set(), evidence_records_by_id={})

    assert not result.valid
    assert any("must be a JSON object" in error for error in result.errors)


@pytest.mark.parametrize("value", ["", 5, ["x"]])
def test_blank_or_invalid_compatibility_group_is_rejected(value: object) -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"))
    payload["records"][0]["compatibility_group"] = value  # type: ignore[index]

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert not result.valid
    assert any("compatibility_group must" in error for error in result.errors)


def test_two_compatible_members_yield_candidate_group_and_ready_verdict() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified", compatibility_group="group-x"),
        _record("ev-b", readiness_category="exactly_verified", compatibility_group="group-x"),
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    assert result.valid
    assert len(result.compatibility_groups) == 1
    group = result.compatibility_groups[0]
    assert group.label == "group-x"
    assert group.status == "candidate"
    assert group.reasons == ()
    assert result.readiness_verdict == READY_VERDICT
    assert result.blockers == ()


def test_member_with_incompatibility_reason_forces_group_status_no() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record(
            "ev-a",
            readiness_category="exactly_verified",
            compatibility_group="group-x",
            incompatibility_reasons=["different timepoints"],
        ),
        _record("ev-b", readiness_category="exactly_verified", compatibility_group="group-x"),
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    assert result.valid
    group = result.compatibility_groups[0]
    assert group.status == "no"
    assert group.reasons == ("different timepoints",)
    assert result.readiness_verdict == NOT_READY_VERDICT
    assert any("different timepoints" in blocker for blocker in result.blockers)


def test_single_member_group_is_undetermined_not_no() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified", compatibility_group="group-x"),
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    assert result.valid
    group = result.compatibility_groups[0]
    assert group.status == "undetermined"
    assert result.readiness_verdict == NOT_READY_VERDICT
    assert any("too few candidate studies" in blocker for blocker in result.blockers)


def test_not_ready_verdict_reports_binary_input_shortfall_blocker() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified", binary_input_ids=["binary-a"]),
        binary_inputs=["binary-a"],
    )

    result = _validate(
        payload,
        golden_map_evidence_record_ids={"ev-a"},
        evidence_records_by_id=evidence,
        binary_input_ids={"binary-a"},
    )

    assert result.valid
    assert result.readiness_verdict == NOT_READY_VERDICT
    assert any(
        "Only 1 production binary statistical input(s) exist" in blocker
        for blocker in result.blockers
    )


def test_ready_verdict_has_no_blockers() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified", compatibility_group="group-x"),
        _record("ev-b", readiness_category="exactly_verified", compatibility_group="group-x"),
    )

    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    assert result.readiness_verdict == READY_VERDICT
    assert result.blockers == ()


def test_report_rendering_is_deterministic_and_lists_category_counts() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified"),
        _record("ev-b", readiness_category="display_only"),
    )
    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    first = render_statistical_readiness_report(result)
    second = render_statistical_readiness_report(result)

    assert first == second
    assert "- exactly_verified: 1" in first
    assert "- display_only: 1" in first
    assert "- not_applicable: 0" in first
    assert f"Verdict: `{NOT_READY_VERDICT}`" in first
    assert "No studies were pooled." in first
    assert "No scientific synthesis was performed." in first


def test_report_escapes_markdown_in_curated_free_text() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(
        _record(
            "ev-a",
            readiness_category="not_selected_for_verification",
            incompatibility_reasons=["Injected [reviewer]\n# Heading"],
            review_note="Note with *markdown* and `code`",
        )
    )
    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    report = render_statistical_readiness_report(result)

    assert "Injected \\[reviewer\\] \\# Heading" in report
    assert "\n# Heading" not in report
    assert "Note with \\*markdown\\* and `code`" in report


def test_report_shows_no_compatibility_groups_message_when_none_declared() -> None:
    evidence = {"ev-a": _evidence("ev-a")}
    payload = _map_payload(_record("ev-a"))
    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a"}, evidence_records_by_id=evidence
    )

    report = render_statistical_readiness_report(result)

    assert "No compatibility groups are declared in the current readiness map." in report


def test_report_shows_none_recorded_for_blockers_when_verdict_is_ready() -> None:
    evidence = {"ev-a": _evidence("ev-a"), "ev-b": _evidence("ev-b")}
    payload = _map_payload(
        _record("ev-a", readiness_category="exactly_verified", compatibility_group="group-x"),
        _record("ev-b", readiness_category="exactly_verified", compatibility_group="group-x"),
    )
    result = _validate(
        payload, golden_map_evidence_record_ids={"ev-a", "ev-b"}, evidence_records_by_id=evidence
    )

    report = render_statistical_readiness_report(result)

    assert result.readiness_verdict == READY_VERDICT
    assert "None recorded." in report


# -- Verification facet rendering (STEP5-style: 3 facets; SELECT-style: 1 facet) --


def _continuous_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
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
        "confidence_interval_verification": {
            "method": "independent_arm_standard_errors_normal",
            "intervention_standard_error": 0.9,
            "comparator_standard_error": 1.1,
            "intervention_sample_size": 152,
            "comparator_sample_size": 152,
            "critical_value": 1.96,
            "endpoint_tolerance": 0.1,
            "assumption_note": "Independent-arm normal approximation; not the source model.",
        },
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


def _binary_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "binary_input_id": "binary-step5-001",
        "evidence_record_id": "ev-step5",
        "source_doi": "10.1038/s41591-022-02026-4",
        "review_status": "source_verified",
        "effect_measure": "crude_risk_ratio",
        "outcome": "achievement_of_at_least_5_percent_weight_loss",
        "timepoint": {"value": 104, "unit": "weeks"},
        "analysis_population": "Observed in-trial participants with a week-104 measurement.",
        "intervention": {
            "label": "Semaglutide 2.4 mg once weekly",
            "events": 111,
            "total": 144,
            "reported_percentage": 77.1,
        },
        "comparator": {
            "label": "Placebo once weekly",
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
            "assumption_note": "Crude observed-count risk ratio; not the source-adjusted model.",
        },
        "source_reported_comparison": {
            "measure": "adjusted_odds_ratio",
            "estimate": 5.0,
            "confidence_interval": {"level": 95, "lower": 3.0, "upper": 8.4},
            "method_note": "Source reports an adjusted odds ratio from logistic regression.",
            "comparison_policy": "display_only_not_compared",
        },
        "source_span": {
            "page_number": 5,
            "section": "Table 2 / Co-primary endpoints",
            "table_or_figure": "Table 2",
            "locator_note": "Reports 111/144 versus 44/128.",
        },
        "method_source_span": {
            "page_number": 6,
            "section": "Table 2 notes / statistical methods",
            "table_or_figure": "Table 2 notes",
            "locator_note": "States the logistic-regression method.",
        },
        "provenance": {
            "created_by": "Reviewer",
            "created_date": "2026-08-04",
            "method": "Manual transcription of observed event counts.",
            "source_basis": "Legally usable source PDF.",
        },
    }


def _write_jsonl(path: Path, *payloads: object) -> None:
    path.write_text(
        "\n".join(json.dumps(payload, separators=(",", ":")) for payload in payloads) + "\n",
        encoding="utf-8",
    )


def test_report_shows_three_facets_for_a_record_with_continuous_and_binary_inputs(
    tmp_path: Path,
) -> None:
    evidence_records = [
        {
            "evidence_record_id": "ev-step5",
            "source_doi": "https://doi.org/10.1038/S41591-022-02026-4",
            "review_status": "reviewed",
            "outcome": "Percentage change in body weight from baseline.",
            "source_span": {"page_number": 2, "section": "Results"},
        }
    ]
    continuous_path = tmp_path / "continuous.jsonl"
    binary_path = tmp_path / "binary.jsonl"
    _write_jsonl(continuous_path, _continuous_payload())
    _write_jsonl(binary_path, _binary_payload())

    continuous_validation = validate_statistical_inputs(
        continuous_path, evidence_records=evidence_records
    )
    binary_validation = validate_binary_statistical_inputs(
        binary_path, evidence_records=evidence_records
    )
    assert continuous_validation.valid
    assert binary_validation.valid
    continuous_verifications = verify_statistical_inputs(continuous_validation.records)
    binary_verifications = verify_binary_statistical_inputs(binary_validation.records)

    evidence = {"ev-step5": _evidence("ev-step5")}
    payload = _map_payload(
        _record(
            "ev-step5",
            readiness_category="exactly_verified",
            continuous_input_ids=["stat-step5-001"],
            binary_input_ids=["binary-step5-001"],
        )
    )
    result = _validate(
        payload,
        golden_map_evidence_record_ids={"ev-step5"},
        evidence_records_by_id=evidence,
        continuous_input_ids={"stat-step5-001"},
        binary_input_ids={"binary-step5-001"},
    )
    assert result.valid

    report = render_statistical_readiness_report(
        result,
        continuous_verifications=continuous_verifications,
        binary_verifications=binary_verifications,
    )

    assert "Exact continuous arithmetic reproduction" in report
    assert "Bounded confidence-interval approximation" in report
    assert "Derived crude binary risk ratio" in report
    assert report.count("stat-step5-001") >= 1
    assert report.count("binary-step5-001") >= 1


def test_load_statistical_readiness_map_reports_missing_and_invalid_files(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(StatisticalReadinessError, match="Could not read"):
        load_statistical_readiness_map(missing)

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")
    with pytest.raises(StatisticalReadinessError, match="not valid JSON"):
        load_statistical_readiness_map(invalid)

    non_object = tmp_path / "non_object.json"
    non_object.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(StatisticalReadinessError, match="root must be a JSON object"):
        load_statistical_readiness_map(non_object)


# -- CLI-level tests against the real committed GLP-1 corpus --


def _corpus_dir() -> Path:
    return Path(__file__).parents[1] / "data" / "corpora" / "glp1_weight_loss"


def test_cli_against_committed_data_reproduces_documented_verdict(tmp_path: Path) -> None:
    corpus = _corpus_dir()
    output = tmp_path / "readiness.md"

    result = CliRunner().invoke(
        app,
        [
            "statistical-readiness-report",
            str(corpus / "statistical_readiness_map.json"),
            "--evidence-map",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--inputs",
            str(corpus / "statistical_inputs.jsonl"),
            "--binary-inputs",
            str(corpus / "binary_statistical_inputs.jsonl"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Golden-map records classified: 14" in result.output
    assert "Readiness verdict: not_ready_for_pooling_design" in result.output
    report = output.read_text(encoding="utf-8")
    assert "- exactly_verified: 2" in report
    assert "- display_only: 3" in report
    assert "- not_selected_for_verification: 7" in report
    assert "- not_applicable: 2" in report
    assert "Verdict: `not_ready_for_pooling_design`" in report
    assert "ev-glp1-step5-body-weight-week104-001" in report
    assert "Exact continuous arithmetic reproduction" in report
    assert "Bounded confidence-interval approximation" in report
    assert "Derived crude binary risk ratio" in report


def test_cli_terminal_and_file_output_match(tmp_path: Path) -> None:
    corpus = _corpus_dir()
    output = tmp_path / "readiness.md"
    output.write_text("replace me", encoding="utf-8")

    common_args = [
        "statistical-readiness-report",
        str(corpus / "statistical_readiness_map.json"),
        "--evidence-map",
        str(corpus / "golden_evidence_map.json"),
        "--evidence",
        str(corpus / "evidence_records.jsonl"),
        "--inputs",
        str(corpus / "statistical_inputs.jsonl"),
        "--binary-inputs",
        str(corpus / "binary_statistical_inputs.jsonl"),
    ]

    terminal = CliRunner().invoke(app, common_args)
    written = CliRunner().invoke(app, [*common_args, "--output", str(output), "--force"])

    assert terminal.exit_code == 0, terminal.output
    assert written.exit_code == 0, written.output
    assert terminal.output == output.read_text(encoding="utf-8")


def test_cli_missing_readiness_map_file_fails(tmp_path: Path) -> None:
    corpus = _corpus_dir()

    result = CliRunner().invoke(
        app,
        [
            "statistical-readiness-report",
            str(tmp_path / "does-not-exist.json"),
            "--evidence-map",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--inputs",
            str(corpus / "statistical_inputs.jsonl"),
        ],
    )

    assert result.exit_code != 0


def test_cli_stale_readiness_map_missing_coverage_fails(tmp_path: Path) -> None:
    corpus = _corpus_dir()
    stale_map = json.loads((corpus / "statistical_readiness_map.json").read_text(encoding="utf-8"))
    stale_map["records"] = stale_map["records"][:1]
    stale_path = tmp_path / "stale_readiness_map.json"
    stale_path.write_text(json.dumps(stale_map), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "statistical-readiness-report",
            str(stale_path),
            "--evidence-map",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--inputs",
            str(corpus / "statistical_inputs.jsonl"),
            "--binary-inputs",
            str(corpus / "binary_statistical_inputs.jsonl"),
        ],
    )

    assert result.exit_code == 1
    assert "has no readiness classification" in result.output


def test_cli_rejects_output_overwriting_an_input_file(tmp_path: Path) -> None:
    corpus = _corpus_dir()

    result = CliRunner().invoke(
        app,
        [
            "statistical-readiness-report",
            str(corpus / "statistical_readiness_map.json"),
            "--evidence-map",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--inputs",
            str(corpus / "statistical_inputs.jsonl"),
            "--output",
            str(corpus / "evidence_records.jsonl"),
            "--force",
        ],
    )

    assert result.exit_code == 2
    assert "must not overwrite an input file" in result.output


def test_cli_refuses_to_overwrite_existing_output_without_force(tmp_path: Path) -> None:
    corpus = _corpus_dir()
    output = tmp_path / "readiness.md"
    output.write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "statistical-readiness-report",
            str(corpus / "statistical_readiness_map.json"),
            "--evidence-map",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--inputs",
            str(corpus / "statistical_inputs.jsonl"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 2
    assert "Use --force to overwrite" in unstyle(result.output)
    assert output.read_text(encoding="utf-8") == "keep"


def test_cli_help_documents_the_command() -> None:
    result = CliRunner().invoke(app, ["statistical-readiness-report", "--help"])

    assert result.exit_code == 0
    assert "readiness" in result.output.lower()
