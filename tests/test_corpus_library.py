from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select, text

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import (
    export_corpus_library,
    export_corpus_library_compressed,
    import_corpus_library,
    import_corpus_library_compressed,
)
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.models import Author, Keyword, Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper


def _evidence_line(record_id: str, *, source_doi: str = "10.1/x") -> str:
    return json.dumps(
        {
            "evidence_record_id": record_id,
            "schema_version": 1,
            "source_doi": source_doi,
            "claim_text": "Weight loss was significantly greater with treatment.",
            "review_status": "draft",
        }
    )


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


def test_import_corpus_library_clears_embedding_identity(tmp_path: Path) -> None:
    """A source paper's embedding_id (its own database-local primary key)

    must never survive into a target database, where the imported paper
    gets a different primary key -- copying it verbatim would let the
    imported paper silently claim another (unrelated) paper's vector-index
    identity, or a stale one nothing indexes. Found by a Codex review on
    PR #154.
    """

    source = _database(tmp_path, "source")
    with source.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64)
        )
        PaperRepository(session).set_embedding(
            paper.id, embedding_model="external:test-v1", embedding_id=str(paper.id)
        )
    snapshot_path = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot_path)

    target = _database(tmp_path, "target")
    with target.session() as session:
        import_corpus_library(session, snapshot_path)

    with target.session() as session:
        imported = session.scalars(select(Paper)).one()
        assert imported.embedding_model is None
        assert imported.embedding_id is None


def test_import_corpus_library_indexes_imported_papers_for_search(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64, title="Findable")
        )
    snapshot_path = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot_path)

    target = _database(tmp_path, "target")
    with target.session() as session:
        import_corpus_library(session, snapshot_path)

    with target.session() as session:
        rows = list(session.execute(text("SELECT title FROM paper_search")))
        assert [row[0] for row in rows] == ["Findable"]


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


def test_export_import_compressed_round_trips(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    with source.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(source_path=tmp_path / "a.pdf", content_hash="a" * 64, doi="10.1/a"),
            keywords=["obesity"],
        )

    output = tmp_path / "snapshot.sqlite3.gz"
    summary = export_corpus_library_compressed(source.engine, output)

    assert summary.paper_count == 1
    assert output.exists()
    # A real gzip stream starts with the two-byte magic number.
    assert output.read_bytes()[:2] == b"\x1f\x8b"

    target = _database(tmp_path, "target")
    with target.session() as session:
        import_summary = import_corpus_library_compressed(session, output)

    assert import_summary.imported_paper_count == 1
    with target.session() as session:
        papers = list(session.scalars(select(Paper)))
        assert len(papers) == 1
        assert papers[0].doi == "10.1/a"
        assert len(papers[0].pages) == 1


def test_export_corpus_library_compressed_raises_if_output_already_exists(
    tmp_path: Path,
) -> None:
    source = _database(tmp_path, "source")
    output = tmp_path / "snapshot.sqlite3.gz"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_corpus_library_compressed(source.engine, output)


def test_import_corpus_library_compressed_raises_if_input_missing(tmp_path: Path) -> None:
    target = _database(tmp_path, "target")
    with target.session() as session, pytest.raises(FileNotFoundError):
        import_corpus_library_compressed(session, tmp_path / "missing.sqlite3.gz")


def test_export_corpus_library_omits_evidence_when_not_given(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    output = tmp_path / "snapshot.sqlite3"
    summary = export_corpus_library(source.engine, output)

    assert summary.evidence_record_count == 0


def test_export_corpus_library_counts_evidence_records_when_given(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(
        _evidence_line("auto-1") + "\n" + _evidence_line("auto-2") + "\n", encoding="utf-8"
    )

    output = tmp_path / "snapshot.sqlite3"
    summary = export_corpus_library(source.engine, output, evidence_path)

    assert summary.evidence_record_count == 2


def test_export_corpus_library_skips_malformed_evidence_lines(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                _evidence_line("auto-1"),
                "not json",
                json.dumps(["not", "an", "object"]),
                json.dumps({"claim_text": "no id here"}),
                "",
            ]
        ),
        encoding="utf-8",
    )

    output = tmp_path / "snapshot.sqlite3"
    summary = export_corpus_library(source.engine, output, evidence_path)

    assert summary.evidence_record_count == 1


def test_import_corpus_library_merges_evidence_records(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "source_evidence.jsonl"
    evidence_path.write_text(
        _evidence_line("auto-1") + "\n" + _evidence_line("auto-2") + "\n", encoding="utf-8"
    )

    snapshot = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot, evidence_path)

    target = _database(tmp_path, "target")
    target_evidence_path = tmp_path / "target_evidence.jsonl"
    with target.session() as session:
        summary = import_corpus_library(session, snapshot, target_evidence_path)

    assert summary.imported_evidence_record_count == 2
    assert summary.skipped_existing_evidence_record_count == 0
    lines = target_evidence_path.read_text(encoding="utf-8").strip().splitlines()
    ids = {json.loads(line)["evidence_record_id"] for line in lines}
    assert ids == {"auto-1", "auto-2"}


def test_import_corpus_library_deduplicates_evidence_already_present(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "source_evidence.jsonl"
    evidence_path.write_text(
        _evidence_line("auto-1") + "\n" + _evidence_line("auto-2") + "\n", encoding="utf-8"
    )

    snapshot = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot, evidence_path)

    target = _database(tmp_path, "target")
    target_evidence_path = tmp_path / "target_evidence.jsonl"
    target_evidence_path.write_text(_evidence_line("auto-1") + "\n", encoding="utf-8")

    with target.session() as session:
        summary = import_corpus_library(session, snapshot, target_evidence_path)

    assert summary.imported_evidence_record_count == 1
    assert summary.skipped_existing_evidence_record_count == 1
    lines = target_evidence_path.read_text(encoding="utf-8").strip().splitlines()
    ids = [json.loads(line)["evidence_record_id"] for line in lines]
    assert ids == ["auto-1", "auto-2"]

    # Re-importing the same snapshot again is idempotent: nothing new to add.
    with target.session() as session:
        second = import_corpus_library(session, snapshot, target_evidence_path)
    assert second.imported_evidence_record_count == 0
    assert second.skipped_existing_evidence_record_count == 2
    assert target_evidence_path.read_text(encoding="utf-8").strip().splitlines() == lines


def test_import_corpus_library_evidence_merge_does_not_corrupt_a_missing_trailing_newline(
    tmp_path: Path,
) -> None:
    """Regression test: a target evidence file whose last line lacks a trailing
    newline (e.g. hand-edited, or written by some other tool) must not have the
    first merged record concatenated directly onto it -- that would corrupt both
    as JSON and silently drop them from every evidence reader."""

    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "source_evidence.jsonl"
    evidence_path.write_text(_evidence_line("auto-2") + "\n", encoding="utf-8")

    snapshot = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot, evidence_path)

    target = _database(tmp_path, "target")
    target_evidence_path = tmp_path / "target_evidence.jsonl"
    target_evidence_path.write_text(_evidence_line("auto-1"), encoding="utf-8")  # no trailing "\n"

    with target.session() as session:
        summary = import_corpus_library(session, snapshot, target_evidence_path)

    assert summary.imported_evidence_record_count == 1
    lines = target_evidence_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    ids = [json.loads(line)["evidence_record_id"] for line in lines]
    assert ids == ["auto-1", "auto-2"]


def test_import_corpus_library_snapshot_without_evidence_table_is_a_noop(
    tmp_path: Path,
) -> None:
    source = _database(tmp_path, "source")
    snapshot = tmp_path / "snapshot.sqlite3"
    export_corpus_library(source.engine, snapshot)

    target = _database(tmp_path, "target")
    target_evidence_path = tmp_path / "target_evidence.jsonl"
    with target.session() as session:
        summary = import_corpus_library(session, snapshot, target_evidence_path)

    assert summary.imported_evidence_record_count == 0
    assert summary.skipped_existing_evidence_record_count == 0
    assert not target_evidence_path.exists()


def test_export_import_compressed_round_trip_carries_evidence(tmp_path: Path) -> None:
    source = _database(tmp_path, "source")
    evidence_path = tmp_path / "source_evidence.jsonl"
    evidence_path.write_text(_evidence_line("auto-1") + "\n", encoding="utf-8")

    output = tmp_path / "snapshot.sqlite3.gz"
    summary = export_corpus_library_compressed(source.engine, output, evidence_path)
    assert summary.evidence_record_count == 1

    target = _database(tmp_path, "target")
    target_evidence_path = tmp_path / "target_evidence.jsonl"
    with target.session() as session:
        import_summary = import_corpus_library_compressed(session, output, target_evidence_path)

    assert import_summary.imported_evidence_record_count == 1
    assert (
        json.loads(target_evidence_path.read_text(encoding="utf-8").strip())["evidence_record_id"]
        == "auto-1"
    )
