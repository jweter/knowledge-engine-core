from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.manifest_curation_cli import app


def test_cli_exports_reconciled_curation_draft(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "curation.csv"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "title": "Trial title",
                        "doi": "10.1000/example",
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
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "pmcid": "PMC100",
                        "license": "CC BY",
                        "filename": "PMC100.pdf",
                        "byte_count": 123,
                        "sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "export",
            "--worksheet",
            str(worksheet),
            "--receipt",
            str(receipt),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "No sources.csv file was modified" in result.output
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["local_path"] == "PMC100.pdf"
    assert rows[0]["authors"] == ""
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    output = tmp_path / "curation.csv"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "export",
            "--worksheet",
            str(tmp_path / "missing-review.json"),
            "--receipt",
            str(tmp_path / "missing-receipt.json"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"
