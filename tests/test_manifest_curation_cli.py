from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.manifest_curation_cli import app

RULES_VERSION = "m14-candidate-adjudication-v1"


def test_cli_exports_reconciled_curation_draft(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "curation.csv"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "rules_version": RULES_VERSION,
                "candidate_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
                        "authors": [],
                        "publication_year": None,
                        "venue": None,
                        "doi": "10.1000/example",
                        "pmcid": "PMC100",
                        "open_access": True,
                        "reported_license": "CC BY 4.0",
                        "pdf_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC100.1/PMC100.1.pdf",
                        "discovery_status": "oa_verified",
                        "decision": "accepted",
                        "reason_codes": ["ALL_REQUIRED_RULES_PASSED"],
                        "rules_version": RULES_VERSION,
                        "adjudicated_at": "2026-07-20T12:00:00+00:00",
                        "inclusion_rule_result": "passed",
                        "identity_rule_result": "passed",
                        "license_rule_result": "passed",
                        "full_text_rule_result": "passed",
                        "duplicate_rule_result": "passed_exact_identifier_uniqueness",
                        "evidence_provenance": ["pubmed_metadata", "pmc_cloud_service"],
                        "unresolved_ambiguities": [],
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
                        "license": "CC BY 4.0",
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
    assert rows[0]["inclusion_reason"] == "ALL_REQUIRED_RULES_PASSED"
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
