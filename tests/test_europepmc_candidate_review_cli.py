from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint


def _write_candidates(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "query": "semaglutide obesity",
                "cursor_mark": "*",
                "next_cursor_mark": None,
                "limit": 25,
                "candidate_count": 1,
                "candidates": [
                    {
                        "europepmc_id": "PPR123",
                        "source": "PPR",
                        "pmid": "111",
                        "pmcid": None,
                        "doi": "10.1000/example",
                        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
                        "abstract": None,
                        "authors": [],
                        "publication_year": None,
                        "venue": None,
                        "in_pmc": False,
                        "open_access": True,
                        "license": "CC BY 4.0",
                        "pdf_url": "https://europepmc.org/api/fulltextRepo?pprId=PPR123",
                        "pdf_host": "europepmc.org",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_cli_prepares_pending_only_review_worksheet(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates)
    output = tmp_path / "review.json"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-review-prepare",
            "--candidates",
            str(candidates),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Prepared 1 pending candidate reviews" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["items"][0]["decision"] == "accepted"


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates)
    output = tmp_path / "review.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-review-prepare",
            "--candidates",
            str(candidates),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert output.read_text(encoding="utf-8") == "existing"


def test_cli_reports_a_clean_error_on_malformed_input(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text("not json", encoding="utf-8")
    output = tmp_path / "review.json"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-review-prepare",
            "--candidates",
            str(candidates),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "Europe PMC candidate review preparation failed" in result.output
    assert not output.exists()
