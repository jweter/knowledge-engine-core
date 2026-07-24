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
                "offset": 0,
                "next_offset": None,
                "limit": 25,
                "total_hits": 1,
                "candidate_count": 1,
                "candidates": [
                    {
                        "core_id": "12345",
                        "doi": "10.1000/example",
                        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
                        "abstract": None,
                        "authors": [],
                        "publication_year": None,
                        "venue": None,
                        "document_type": None,
                        "pdf_url": "https://core.ac.uk/download/12345.pdf",
                        "pdf_host": "core.ac.uk",
                        "source_fulltext_urls": [],
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
            "core-candidate-review-prepare",
            "--candidates",
            str(candidates),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Prepared 1 pending candidate reviews" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["items"][0]["decision"] == "held"


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates)
    output = tmp_path / "review.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "core-candidate-review-prepare",
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
            "core-candidate-review-prepare",
            "--candidates",
            str(candidates),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "CORE candidate review preparation failed" in result.output
    assert not output.exists()
