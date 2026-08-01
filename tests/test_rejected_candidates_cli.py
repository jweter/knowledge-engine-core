from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _write_rejections(tmp_path: Path, *records: dict[str, object]) -> Path:
    path = tmp_path / "rejections.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def test_rejected_candidates_add_writes_the_ledger(tmp_path: Path) -> None:
    input_path = _write_rejections(
        tmp_path,
        {
            "pmid": "12345678",
            "title": "A busulfan pharmacokinetics study",
            "reason_category": "off_target_primary_disease",
            "batch_label": "retstart=3000",
        },
    )
    ledger_path = tmp_path / "ledger.csv"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "rejected-candidates-add",
            "--input",
            str(input_path),
            "--ledger",
            str(ledger_path),
        ],
    )

    assert result.exit_code == 0, result.output
    rows = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    assert "12345678" in rows[1]
    unwrapped = _unwrapped(result.output)
    assert "Appended 1 rejection record" in unwrapped


def test_rejected_candidates_add_skips_a_duplicate_pmid(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    first_input = _write_rejections(
        tmp_path,
        {
            "pmid": "12345678",
            "title": "First decision",
            "reason_category": "off_target_primary_disease",
            "batch_label": "retstart=3000",
        },
    )
    CliRunner().invoke(
        entrypoint.app,
        ["rejected-candidates-add", "--input", str(first_input), "--ledger", str(ledger_path)],
    )

    second_input = tmp_path / "second.jsonl"
    second_input.write_text(
        json.dumps(
            {
                "pmid": "12345678",
                "title": "A different later decision",
                "reason_category": "diagnostic_or_measurement_only",
                "batch_label": "retstart=3250",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["rejected-candidates-add", "--input", str(second_input), "--ledger", str(ledger_path)],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Appended 0 rejection record" in unwrapped
    assert "Skipped 1 pmid" in unwrapped
    assert "12345678" in unwrapped


def test_rejected_candidates_add_rejects_an_unknown_reason_category(tmp_path: Path) -> None:
    input_path = _write_rejections(
        tmp_path,
        {
            "pmid": "12345678",
            "title": "Example",
            "reason_category": "not_a_real_category",
            "batch_label": "retstart=3000",
        },
    )
    ledger_path = tmp_path / "ledger.csv"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "rejected-candidates-add",
            "--input",
            str(input_path),
            "--ledger",
            str(ledger_path),
        ],
    )

    assert result.exit_code == 1
    assert not ledger_path.exists()


def test_rejected_candidates_check_reports_already_rejected_pmids(tmp_path: Path) -> None:
    input_path = _write_rejections(
        tmp_path,
        {
            "pmid": "12345678",
            "title": "A busulfan pharmacokinetics study",
            "reason_category": "off_target_primary_disease",
            "batch_label": "retstart=3000",
        },
    )
    ledger_path = tmp_path / "ledger.csv"
    CliRunner().invoke(
        entrypoint.app,
        ["rejected-candidates-add", "--input", str(input_path), "--ledger", str(ledger_path)],
    )

    candidates_path = tmp_path / "discovery.json"
    candidates_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {"pmid": "12345678", "title": "A busulfan pharmacokinetics study"},
                    {"pmid": "99999999", "title": "A genuinely new candidate"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "rejected-candidates-check",
            "--candidates",
            str(candidates_path),
            "--ledger",
            str(ledger_path),
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Net-new: 1" in unwrapped
    assert "Already rejected: 1" in unwrapped
    assert "12345678" in unwrapped


def test_rejected_candidates_check_reads_worksheet_items_shape(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    candidates_path = tmp_path / "worksheet.json"
    candidates_path.write_text(
        json.dumps({"items": [{"pmid": "1"}, {"pmid": "2"}]}), encoding="utf-8"
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "rejected-candidates-check",
            "--candidates",
            str(candidates_path),
            "--ledger",
            str(ledger_path),
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Net-new: 2" in unwrapped
    assert "Already rejected: 0" in unwrapped


def test_rejected_candidates_check_writes_a_markdown_report(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    candidates_path = tmp_path / "discovery.json"
    candidates_path.write_text(
        json.dumps({"candidates": [{"pmid": "1", "title": "Example"}]}), encoding="utf-8"
    )
    output_path = tmp_path / "report.md"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "rejected-candidates-check",
            "--candidates",
            str(candidates_path),
            "--ledger",
            str(ledger_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert "Rejected-Candidates Check" in output_path.read_text(encoding="utf-8")
