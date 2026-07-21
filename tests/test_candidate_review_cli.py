from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.candidate_review_cli import app


def test_cli_prepares_pending_only_review_worksheet(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            {
                "query": "GLP-1 obesity",
                "retstart": 0,
                "limit": 25,
                "candidate_count": 1,
                "candidates": [
                    {
                        "pmid": "100",
                        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
                        "doi": "10.1000/example",
                        "pmcid": "PMC100",
                        "open_access": True,
                        "license": "CC BY",
                        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
                        "xml_url": None,
                        "status": "oa_verified",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "review.json"

    result = CliRunner().invoke(
        app,
        ["prepare", "--candidates", str(candidates), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "Prepared 1 pending candidate reviews" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["items"][0]["decision"] == "accepted"
    assert "approvals" not in payload
    assert str(tmp_path) not in output.read_text(encoding="utf-8")


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    output = tmp_path / "review.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "prepare",
            "--candidates",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"
