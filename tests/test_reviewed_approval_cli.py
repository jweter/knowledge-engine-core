from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.reviewed_approval_cli import app

RULES_VERSION = "m14-candidate-adjudication-v1"


def test_cli_exports_accepted_adjudications_atomically(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "rules_version": RULES_VERSION,
                "candidate_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "pmcid": "PMC100",
                        "open_access": True,
                        "reported_license": "CC BY 4.0",
                        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
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
                        "evidence_provenance": ["pubmed_metadata", "pmc_oa_service"],
                        "unresolved_ambiguities": [],
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
    assert "Exported 1 automated acquisition approvals" in result.output
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
