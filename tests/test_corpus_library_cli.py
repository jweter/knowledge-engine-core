from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it.

    `CliRunner` output is not a real terminal, so Rich wraps at a default
    80-column width; a long `tmp_path`-derived path in the same `console.
    print` call can push a short trailing phrase like "1 paper(s)" onto a
    line break between the two words.
    """

    return " ".join(output.split())


def _database(tmp_path: Path, name: str) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / name,
            database_url=f"sqlite:///{tmp_path / name}.sqlite3",
        )
    )
    database.initialize()
    return database


def _parsed_paper(tmp_path: Path, content_hash: str) -> ParsedPaper:
    text = "Results\n\nBody weight decreased by 10%."
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title="A Trial",
        authors=["Ada Scientist"],
        abstract="An abstract.",
        doi=f"10.1/{content_hash[:8]}",
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def test_corpus_library_export_cli_writes_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output = tmp_path / "snapshot.sqlite3"
    result = CliRunner().invoke(entrypoint.app, ["corpus-library-export", "--output", str(output)])

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Exported corpus library" in unwrapped
    assert "1 paper(s)" in unwrapped
    assert output.exists()


def test_corpus_library_export_cli_rejects_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output = tmp_path / "snapshot.sqlite3"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(entrypoint.app, ["corpus-library-export", "--output", str(output)])

    assert result.exit_code != 0
    assert "already exists" in _unwrapped(result.output)


def test_corpus_library_import_cli_hydrates_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(_parsed_paper(tmp_path, "b" * 64))
    snapshot_output = tmp_path / "snapshot.sqlite3"
    monkeypatch.setattr(entrypoint, "_local_database", lambda: source)
    CliRunner().invoke(entrypoint.app, ["corpus-library-export", "--output", str(snapshot_output)])

    target = _database(tmp_path, "target")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: target)
    result = CliRunner().invoke(
        entrypoint.app, ["corpus-library-import", "--input", str(snapshot_output)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "1 paper(s) imported" in unwrapped
    assert "0 already present" in unwrapped

    with target.session() as session:
        papers = list(session.scalars(select(Paper)))
        assert len(papers) == 1
        assert papers[0].content_hash == "b" * 64


def test_corpus_library_import_cli_reports_missing_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "target")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        entrypoint.app, ["corpus-library-import", "--input", str(tmp_path / "missing.sqlite3")]
    )

    assert result.exit_code != 0
    assert "does not exist" in _unwrapped(result.output)
