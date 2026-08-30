from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
import knowledge_engine.research_review_surface as research_review_surface
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.research_runtime import app as research_app

_RICH_TEXT = (
    "Abstract\n"
    "We enrolled 253 adults with obesity in this trial.\n"
    "Participants received semaglutide once weekly for 68 weeks.\n"
    "Weight loss was compared with placebo over the study period.\n"
    "The primary outcome was change in body weight from baseline.\n\n"
    "Methods\n"
    "This was a randomized, double-blind, placebo-controlled trial.\n\n"
    "Results\n"
    "Mean weight loss was 15.3% (95% CI, 12.1-18.5) versus 2.6% with placebo.\n\n"
    "Limitations\n"
    "This study was limited by a short follow-up period.\n\n"
    "Conclusion\n"
    "Semaglutide produced significantly greater weight loss than placebo.\n"
)


def _database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def _seed_paper(database: Database, tmp_path: Path) -> int:
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            ParsedPaper(
                source_path=tmp_path / "a.pdf",
                content_hash="a" * 64,
                title="Rich Paper",
                authors=["Ada Scientist"],
                abstract="An abstract about semaglutide and weight loss.",
                doi="10.1/abcdefgh",
                page_count=1,
                word_count=10,
                raw_text=_RICH_TEXT,
                body_text=_RICH_TEXT,
                pages=[ParsedPage(page_number=1, text=_RICH_TEXT)],
            )
        )
        return paper.id


def _receipt(tmp_path: Path, paper_id: int) -> Path:
    payload = {
        "schema_version": 1,
        "search_run_id": "run-1",
        "research_question_id": "rq-1",
        "acquisition_route": "pmc_oa",
        "import_run_id": "import-1",
        "parsed_count": 1,
        "persisted_count": 1,
        "reused_count": 0,
        "items": [
            {"candidate_id": "candidate-1", "paper_id": paper_id, "persistence_status": "persisted"}
        ],
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_production_cli_extracts_and_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    paper_id = _seed_paper(database, tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    receipt_path = _receipt(tmp_path, paper_id)
    evidence_path = tmp_path / "evidence.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "general-question-extract-and-promote",
            "--receipt",
            str(receipt_path),
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "papers=1" in result.output
    assert "rejected=0" in result.output
    assert evidence_path.exists()
    records = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
    assert records
    assert all(record["source_span"]["paper_id"] == paper_id for record in records)


def test_slim_research_cli_extracts_and_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    paper_id = _seed_paper(database, tmp_path)
    monkeypatch.setattr(research_review_surface, "_local_database", lambda: database)
    receipt_path = _receipt(tmp_path, paper_id)
    evidence_path = tmp_path / "evidence.jsonl"

    result = CliRunner().invoke(
        research_app,
        [
            "general-question-extract-and-promote",
            "--receipt",
            str(receipt_path),
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "papers=1" in result.output
    assert "rejected=0" in result.output
    assert evidence_path.exists()
