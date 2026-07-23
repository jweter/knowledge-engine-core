from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from knowledge_engine.cli import app


def _completed_draft_item(**overrides: Any) -> dict[str, Any]:
    """A draft item shaped like M20's output, with a reviewer having filled
    in the fields M19/M20 leave None."""

    record: dict[str, Any] = {
        "schema_version": None,
        "evidence_record_id": None,
        "extraction_method": "m19-draft-evidence-item-v1",
        "extraction_status": "draft_review_required",
        "source_doi": "10.1234/example",
        "source_title": "Example Trial of a GLP-1 Agonist",
        "source_type": "paper",
        "study_type": "randomized_controlled_trial",
        "research_question": "Do GLP-1 receptor agonists reduce body weight?",
        "claim_text": "Body weight decreased by 12.4% relative to baseline.",
        "evidence_direction": "supports",
        "population": "Adults with obesity.",
        "intervention": "Semaglutide 2.4 mg.",
        "comparator": "Placebo.",
        "outcome": "Percent body weight change.",
        "result_summary": "Body weight decreased by 12.4% relative to baseline.",
        "source_span": {"paper_id": 1, "page_number": 3, "section": "results"},
        "limitations": ["Single trial only."],
        "uncertainty_notes": "One paper only.",
        "confidence_note": "Reviewer-verified.",
        "provenance": {"created_by": "reviewer"},
        "created_for_milestone": "M19",
        "extraction_context": {
            "matched_signal": "percentage",
            "section_type": "results",
            "framing": "unclassified",
            "matched_cue": None,
            "candidate_rules_version": "m17-claim-candidate-v1",
            "framing_rules_version": "m18-claim-framing-v1",
        },
    }
    record.update(overrides)
    return record


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_promote_fully_completed_record_succeeds(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(input_path, [_completed_draft_item()])

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Promoted 1 record(s):" in result.output

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["schema_version"] == "0.1"
    assert record["evidence_record_id"].startswith("auto-")
    assert record["review_status"] == "draft"
    assert record["review_checklist"] == {}
    assert record["review_notes"] == ""
    assert record["claim_text"] == "Body weight decreased by 12.4% relative to baseline."


def test_promoted_record_passes_evidence_validate(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(input_path, [_completed_draft_item()])

    CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    result = CliRunner().invoke(app, ["evidence-validate", str(output_path)])

    assert result.exit_code == 0, result.output
    assert "Evidence validation passed." in result.output


def test_promote_rejects_still_incomplete_record(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(
        input_path, [_completed_draft_item(research_question=None, evidence_direction=None)]
    )

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Rejected 1 incomplete record(s):" in result.output
    assert "research_question is required" in result.output
    assert "evidence_direction is required" in result.output
    assert not output_path.exists()


def test_promote_is_idempotent(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(input_path, [_completed_draft_item()])
    runner = CliRunner()

    first = runner.invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )
    second = runner.invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "Skipped 1 already-promoted record(s)." in second.output

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_promote_preserves_reviewer_supplied_review_status(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(input_path, [_completed_draft_item(review_status="reviewed")])

    CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    record = json.loads(output_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["review_status"] == "reviewed"


def test_promote_mixed_input_promotes_valid_and_reports_invalid(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(
        input_path,
        [
            _completed_draft_item(claim_text="Valid claim one."),
            _completed_draft_item(claim_text="Invalid claim.", evidence_direction=None),
        ],
    )

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Promoted 1 record(s):" in result.output
    assert "Rejected 1 incomplete record(s):" in result.output
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["claim_text"] == "Valid claim one."


def test_promote_appends_to_existing_output_file(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    existing = _completed_draft_item(claim_text="Pre-existing claim.")
    existing["schema_version"] = "0.1"
    existing["evidence_record_id"] = "ev-existing-1"
    existing["review_status"] = "draft"
    existing["review_checklist"] = {}
    existing["review_notes"] = ""
    _write_jsonl(output_path, [existing])
    _write_jsonl(input_path, [_completed_draft_item(claim_text="New claim.")])

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    claim_texts = {json.loads(line)["claim_text"] for line in lines}
    assert claim_texts == {"Pre-existing claim.", "New claim."}


def test_promote_rejects_missing_input_file(tmp_path: Path) -> None:
    input_path = tmp_path / "missing.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Input file does not exist" in result.output


def test_promote_empty_input_reports_no_records(tmp_path: Path) -> None:
    input_path = tmp_path / "review.jsonl"
    input_path.write_text("", encoding="utf-8")
    output_path = tmp_path / "evidence_records.jsonl"

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert "No records found in input file." in result.output


def test_promote_rejects_identical_input_and_output_paths(tmp_path: Path) -> None:
    """Promoting in place would leave the original draft rows mixed in with
    promoted records, corrupting the declared evidence file."""

    path = tmp_path / "review.jsonl"
    _write_jsonl(path, [_completed_draft_item()])

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(path), "--output", str(path)],
    )

    assert result.exit_code == 1
    assert "--input and --output must not be the same file" in result.output
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_promote_reports_non_string_evidence_record_id_instead_of_crashing(
    tmp_path: Path,
) -> None:
    """A malformed evidence_record_id (e.g. a JSON array) must be reported
    by the validator, not crash the command on an unhashable-type set
    lookup before later records get a chance to be processed."""

    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "evidence_records.jsonl"
    _write_jsonl(
        input_path,
        [
            _completed_draft_item(evidence_record_id=["not", "a", "string"]),
            _completed_draft_item(claim_text="A second, well-formed record."),
        ],
    )

    result = CliRunner().invoke(
        app,
        ["extraction-review-promote", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 1, result.output
    assert "evidence_record_id is required" in result.output
    assert "Promoted 1 record(s):" in result.output
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["claim_text"] == "A second, well-formed record."
