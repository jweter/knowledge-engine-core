from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.europepmc_reviewed_approval_cli import app

RULES_VERSION = "m34-europepmc-candidate-adjudication-v1"


def _accepted(index: int) -> dict[str, object]:
    return {
        "europepmc_id": f"EPMC{index}",
        "doi": f"10.1000/example-{index}",
        "open_access": True,
        "in_pmc": False,
        "reported_license": "CC BY 4.0",
        "pdf_url": f"https://europepmc.org/articles/EPMC{index}?pdf=render",
        "decision": "accepted",
        "reason_codes": ["ALL_REQUIRED_RULES_PASSED"],
        "rules_version": RULES_VERSION,
        "adjudicated_at": "2026-07-20T12:00:00+00:00",
        "inclusion_rule_result": "passed",
        "identity_rule_result": "passed",
        "license_rule_result": "passed",
        "full_text_rule_result": "passed",
        "pmc_overlap_rule_result": "passed",
        "duplicate_rule_result": "passed_exact_identifier_uniqueness",
        "evidence_provenance": ["europepmc_search"],
        "unresolved_ambiguities": [],
    }


def _write_worksheet(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rules_version": RULES_VERSION,
                "candidate_count": len(items),
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def test_cli_exports_exact_limit_atomically(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted(300), _accepted(100), _accepted(200)])
    output = tmp_path / "approvals.json"

    result = CliRunner().invoke(
        app,
        [
            "export",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
            "--limit",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "Selected 2 of 3 validated accepted" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["selection_rule"] == "accepted_in_worksheet_order"
    assert payload["source_accepted_count"] == 3
    assert payload["selected_count"] == 2
    assert [item["europepmc_id"] for item in payload["approvals"]] == ["EPMC300", "EPMC100"]
    assert payload["approvals"][0]["filename"] == "europepmc-EPMC300.pdf"
    assert "reviewer" not in payload["approvals"][0]
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_module_invocation_preserves_export_subcommand(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted(300), _accepted(100)])
    output = tmp_path / "approvals.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "knowledge_engine.europepmc_reviewed_approval_cli",
            "export",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
            "--limit",
            "2",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Selected 2 of 2 validated accepted" in result.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["selected_count"] == 2


def test_cli_fails_when_limit_exceeds_accepted_count(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted(100)])
    output = tmp_path / "approvals.json"

    result = CliRunner().invoke(
        app,
        [
            "export",
            "--worksheet",
            str(worksheet),
            "--output",
            str(output),
            "--limit",
            "2",
        ],
    )

    assert result.exit_code == 1
    assert "fewer accepted approvals" in result.output
    assert not output.exists()


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    output = tmp_path / "approvals.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "export",
            "--worksheet",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"
