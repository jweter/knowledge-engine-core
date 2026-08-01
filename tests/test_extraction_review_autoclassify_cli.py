from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _draft_item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": None,
        "evidence_record_id": None,
        "extraction_method": "m19-draft-evidence-item-v1",
        "extraction_status": "draft_review_required",
        "source_doi": "10.1000/example",
        "source_title": "An example paper",
        "source_type": "paper",
        "study_type": "randomized_controlled_trial",
        "research_question": None,
        "claim_text": "Semaglutide reduced body weight by 12.4% versus placebo (p<0.001).",
        "evidence_direction": None,
        "population": "Adults with obesity.",
        "intervention": "Semaglutide 2.4 mg weekly.",
        "comparator": "Placebo.",
        "outcome": "Percentage change in body weight.",
        "result_summary": "Body weight decreased by 12.4% with semaglutide versus placebo.",
        "source_span": {"paper_id": 1, "page_number": 2},
        "limitations": None,
        "uncertainty_notes": None,
        "confidence_note": None,
        "provenance": None,
        "created_for_milestone": "M19",
    }
    base.update(overrides)
    return base


def _write_input(tmp_path: Path, *items: dict[str, Any]) -> Path:
    path = tmp_path / "draft_items.jsonl"
    path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")
    return path


def test_autoclassify_fills_research_question_and_direction(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _draft_item())
    output_path = tmp_path / "autoclassified.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-autoclassify",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    written = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(written) == 1
    record = written[0]
    assert record["research_question"] is not None
    assert record["evidence_direction"] == "supports"
    assert record["extraction_method"] == "m52-evidence-classification-v1"
    assert record["review_status"] == "draft"
    assert "no human read or confirmed" in record["review_notes"]
    unwrapped = _unwrapped(result.output)
    assert "Automatically classified 1 / 1 draft item" in unwrapped
    assert "no human review" in unwrapped


def test_autoclassify_skips_ineligible_items_without_failing(tmp_path: Path) -> None:
    eligible = _draft_item()
    ineligible = _draft_item(comparator=None)
    input_path = _write_input(tmp_path, eligible, ineligible)
    output_path = tmp_path / "autoclassified.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-autoclassify",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    written = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(written) == 1
    unwrapped = _unwrapped(result.output)
    assert "Automatically classified 1 / 2 draft item" in unwrapped
    assert "Skipped 1 item" in unwrapped


def test_autoclassify_output_is_promotable(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _draft_item())
    autoclassified_path = tmp_path / "autoclassified.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"

    autoclassify_result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-autoclassify",
            "--input",
            str(input_path),
            "--output",
            str(autoclassified_path),
        ],
    )
    assert autoclassify_result.exit_code == 0, autoclassify_result.output

    promote_result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-promote",
            "--input",
            str(autoclassified_path),
            "--output",
            str(evidence_path),
        ],
    )
    assert promote_result.exit_code == 0, promote_result.output

    validate_result = CliRunner().invoke(entrypoint.app, ["evidence-validate", str(evidence_path)])
    assert validate_result.exit_code == 0, validate_result.output
    assert "Evidence validation passed." in validate_result.output


def test_autoclassify_rejects_a_missing_input_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-autoclassify",
            "--input",
            str(tmp_path / "missing.jsonl"),
            "--output",
            str(tmp_path / "autoclassified.jsonl"),
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_autoclassify_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, _draft_item())
    output_path = tmp_path / "autoclassified.jsonl"
    output_path.write_text("existing content\n", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-autoclassify",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert output_path.read_text(encoding="utf-8") == "existing content\n"
