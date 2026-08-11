from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": "ev-1",
        "extraction_method": "m52-evidence-classification-v1",
        "review_status": "draft",
        "review_checklist": {},
    }
    record.update(overrides)
    return record


def _write_jsonl(path: Path, *records: dict[str, object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def test_promotes_an_llm_grounded_record_with_a_populated_checklist(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(
            extraction_method="m69-llm-grounded-pico-v1",
            review_checklist={"llm_grounded": True, "human_reviewed": False},
        ),
    )

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-record-review-promote", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Promoted 1 record(s)" in _unwrapped(result.output)

    updated = json.loads(evidence_path.read_text(encoding="utf-8").strip())
    assert updated["review_status"] == "reviewed"
    assert "M72 promotion" in updated["review_notes"]


def test_promotes_a_manually_authored_record(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(extraction_method="manual_human_review"),
    )

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-record-review-promote", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    updated = json.loads(evidence_path.read_text(encoding="utf-8").strip())
    assert updated["review_status"] == "reviewed"


def test_leaves_a_raw_m52_record_untouched(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(extraction_method="m52-evidence-classification-v1", review_checklist={}),
    )
    original_content = evidence_path.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-record-review-promote", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Records eligible for promotion: 0" in _unwrapped(result.output)
    assert evidence_path.read_text(encoding="utf-8") == original_content


def test_skips_a_record_already_reviewed(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(
            extraction_method="m69-llm-grounded-pico-v1",
            review_checklist={"llm_grounded": True},
            review_status="reviewed",
        ),
    )

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-record-review-promote", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Records eligible for promotion: 0" in _unwrapped(result.output)


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(
            extraction_method="m69-llm-grounded-pico-v1",
            review_checklist={"llm_grounded": True},
        ),
    )
    original_content = evidence_path.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["evidence-record-review-promote", "--evidence", str(evidence_path), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "Dry run" in _unwrapped(result.output)
    assert evidence_path.read_text(encoding="utf-8") == original_content


def test_preserves_existing_review_notes(tmp_path: Path) -> None:
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _record(
            extraction_method="m69-llm-grounded-pico-v1",
            review_checklist={"llm_grounded": True},
            review_notes="Original M69 note.",
        ),
    )

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-record-review-promote", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    updated = json.loads(evidence_path.read_text(encoding="utf-8").strip())
    assert "Original M69 note." in updated["review_notes"]
    assert "M72 promotion" in updated["review_notes"]
