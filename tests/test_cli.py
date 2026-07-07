from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPaper


def build_cli_database(tmp_path: Path, *, doi: str = "10.1234/answer") -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    parsed = ParsedPaper(
        source_path=tmp_path / "glp1.pdf",
        content_hash=f"{abs(hash(doi)):064d}"[-64:],
        title="GLP-1 Therapy Reduces Body Weight",
        authors=["Ada Scientist"],
        abstract="GLP-1 receptor agonists reduce body weight in adults with obesity.",
        doi=doi,
        page_count=5,
        word_count=30,
        raw_text="GLP-1 receptor agonists reduce body weight compared with placebo.",
        body_text="Weight reduction was observed with GLP-1 receptor agonist therapy.",
    )
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        paper.publication_year = 2023
    return database


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Offline scientific paper ingestion and search" in result.output


def test_safe_text_normalizes_pdf_ligatures() -> None:
    assert cli._safe_text("Efﬁcacy") == "Efficacy"


def test_answer_command_returns_retrieval_only_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        ["answer", "Do GLP-1 receptor agonists reduce body weight?"],
    )

    assert result.exit_code == 0
    assert "GLP-1 Therapy Reduces Body Weight" in result.output
    assert "2023" in result.output
    assert "10.1234/answer" in result.output
    assert "This is retrieval only." in result.output
    assert "No scientific synthesis has been performed." in result.output


def test_answer_command_applies_sources_overlay_by_doi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.3389/fphar.2022.935823")
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "source_id,title,authors,year,venue,doi,source_url,license_type\n"
        "source-1,Curated GLP-1 Review,"
        "Gao; Hua; Wang,2022,Frontiers in Pharmacology,"
        "10.3389/fphar.2022.935823,https://example.test/article,CC-BY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code == 0
    assert "Curated GLP-1 Review" in result.output
    assert "Metadata source: corpus sources.csv" in result.output
    assert "Gao; Hua; Wang" in result.output
    assert "Frontiers in Pharmacology" in result.output
    assert "CC-BY" in result.output
    assert "GLP-1 Therapy Reduces Body Weight" not in result.output


def test_answer_command_falls_back_when_sources_overlay_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1234/answer")
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "source_id,title,authors,year,venue,doi,source_url,license_type\n"
        "source-1,Curated Nonmatch,Curator,2022,Journal,10.9999/nope,"
        "https://example.test/article,CC-BY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code == 0
    assert "GLP-1 Therapy Reduces Body Weight" in result.output
    assert "Metadata source: corpus sources.csv" not in result.output
    assert "Curated Nonmatch" not in result.output


def test_answer_command_rejects_invalid_sources_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text("title\nCurated GLP-1 Review\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code != 0
    assert "sources CSV is missing required column" in result.output
