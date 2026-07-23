from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import export_corpus_library, import_corpus_library
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.models import Author, Keyword, Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper


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


def _parsed_paper(
    *,
    source_path: Path,
    content_hash: str,
    title: str = "A Trial",
    doi: str | None = None,
    authors: list[str] | None = None,
) -> ParsedPaper:
    text = "Results\n\nBody weight decreased by 10%."
    return ParsedPaper(
        source_path=source_path,
        content_hash=content_hash,
        title=title,
        authors=authors or ["Ada Scientist"],
        abstract="An abstract.",
        doi=doi,
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def test_export_corpus_library_copies_papers_pages_and_text(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64, doi="10.1/a"),
            keywords=["obesity"],
        )

    output = tmp_path / "library" / "snapshot.sqlite3"
    summary = export_corpus_library(source.engine, output)

    assert summary.paper_count == 1
    assert summary.author_count == 1
    assert summary.keyword_count == 1
    assert output.exists()

    snapshot = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "readback",
            database_url=f"sqlite:///{output}",
        )
    )
    with snapshot.session() as session:
        papers = list(session.scalars(select(Paper)))
        assert len(papers) == 1
        assert papers[0].doi == "10.1/a"
        assert papers[0].text is not None
        assert papers[0].text.raw_text.startswith("Results")
        assert len(papers[0].pages) == 1
        assert papers[0].pages[0].text == "Results\n\nBody weight decreased by 10%."


def test_export_corpus_library_dedupes_shared_author_and_keyword(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        repo = PaperRepository(session)
        repo.add_parsed_paper(
            _parsed_paper(
                source_path=tmp_path / "a.pdf",
                content_hash="a" * 64,
                authors=["Shared Author"],
            ),
            keywords=["shared-keyword"],
        )
        repo.add_parsed_paper(
            _parsed_paper(
                source_path=tmp_path / "b.pdf",
                content_hash="b" * 64,
                authors=["Shared Author"],
            ),
            keywords=["shared-keyword"],
        )

    output = tmp_path / "snapshot.sqlite3"
    summary = export_corpus_library(source.engine, output)

    assert summary.paper_count == 2
    assert summary.author_count == 1
    assert summary.keyword_count == 1


def test_export_corpus_library_raises_if_output_already_exists(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    output = tmp_path / "snapshot.sqlite3"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_corpus_library(source.engine, output)


def test_import_corpus_library_hydrates_empty_database(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64),
            keywords=["obesity"],
        )
    snapshot_path = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot_path)

    target = _database(tmp_path, "target")
    with target.session() as session:
        summary = import_corpus_library(session, snapshot_path)

    assert summary.imported_paper_count == 1
    assert summary.skipped_existing_paper_count == 0

    with target.session() as session:
        papers = list(session.scalars(select(Paper)))
        assert len(papers) == 1
        assert papers[0].content_hash == "a" * 64
        assert len(papers[0].pages) == 1
        assert len(list(session.scalars(select(Author)))) == 1
        assert len(list(session.scalars(select(Keyword)))) == 1


def test_import_corpus_library_skips_papers_already_present_by_content_hash(
    tmp_path: Path,
) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64)
        )
    snapshot_path = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot_path)

    target = _database(tmp_path, "target")
    with target.session() as session:
        import_corpus_library(session, snapshot_path)
    with target.session() as session:
        summary = import_corpus_library(session, snapshot_path)

    assert summary.imported_paper_count == 0
    assert summary.skipped_existing_paper_count == 1
    with target.session() as session:
        assert len(list(session.scalars(select(Paper)))) == 1


def test_import_corpus_library_reuses_existing_author_by_name(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(
                source_path=tmp_path / "a.pdf", content_hash="a" * 64, authors=["Ada Scientist"]
            )
        )
    snapshot_path = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot_path)

    target = _database(tmp_path, "target")
    with target.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(
                source_path=tmp_path / "existing.pdf",
                content_hash="c" * 64,
                authors=["Ada Scientist"],
            )
        )
    with target.session() as session:
        import_corpus_library(session, snapshot_path)

    with target.session() as session:
        authors = list(session.scalars(select(Author)))
        assert len(authors) == 1
        assert len(list(session.scalars(select(Paper)))) == 2


def test_import_corpus_library_raises_if_input_missing(tmp_path: Path) -> None:
    target = _database(tmp_path, "target")
    with target.session() as session, pytest.raises(FileNotFoundError):
        import_corpus_library(session, tmp_path / "missing.sqlite3")
