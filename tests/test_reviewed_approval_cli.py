from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.reviewed_approval_cli import app


def test_cli_exports_completed_reviews_atomically(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "pmcid": "PMC100",
                        "open_access": True,
                        "reported_license": "CC BY",
                        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
                        "discovery_status": "oa_verified",
                        "decision": "accepted",
                        "inclusion_review": "Meets criteria",
                        "license_review": "Reusable",
                        "identity_review": "Identifiers match",
                        "reviewer": "reviewer-1",
                        "reviewed_at": "2026-07-19T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "approvals.json"

    result = CliRunner().invoke(
        app,
        ["export", "--worksheet", str(worksheet), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "Exported 1 reviewed acquisition approvals" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["approvals"][0]["filename"] == "PMC100.pdf"
    assert "reviewer" not in payload["approvals"][0]
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


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
