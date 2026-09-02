from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import export_corpus_library_compressed
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.research_workspace import bootstrap_research_workspace


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


def _parsed_paper(*, source_path: Path, content_hash: str) -> ParsedPaper:
    text = "Results\n\nBody weight decreased by 10%."
    return ParsedPaper(
        source_path=source_path,
        content_hash=content_hash,
        title="Seed Trial",
        authors=["Ada Scientist"],
        abstract="An abstract.",
        doi="10.1/seed",
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def _seed_snapshot(tmp_path: Path) -> Path:
    source = _database(tmp_path, "source")
    try:
        with source.session() as session:
            PaperRepository(session).add_parsed_paper(
                _parsed_paper(source_path=tmp_path / "seed.pdf", content_hash="a" * 64)
            )

        evidence = tmp_path / "seed-evidence.jsonl"
        evidence.write_text(
            json.dumps(
                {
                    "evidence_record_id": "evidence-seed-1",
                    "schema_version": 1,
                    "claim_text": "Body weight decreased by 10%.",
                    "review_status": "draft",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        snapshot = tmp_path / "seed.sqlite3.gz"
        export_corpus_library_compressed(source.engine, snapshot, evidence)
        return snapshot
    finally:
        source.engine.dispose()


def _make_snapshot_missing_current_paper_columns(snapshot: Path) -> None:
    """Simulate a committed snapshot that predates the current Paper mapping."""

    with tempfile.TemporaryDirectory() as raw_dir:
        raw_path = Path(raw_dir) / "snapshot.sqlite3"
        with gzip.open(snapshot, "rb") as compressed_file, raw_path.open("wb") as raw_file:
            shutil.copyfileobj(compressed_file, raw_file)

        connection = sqlite3.connect(raw_path)
        try:
            connection.execute("ALTER TABLE papers RENAME COLUMN pmid TO legacy_pmid")
            connection.execute("ALTER TABLE papers RENAME COLUMN arxiv_id TO legacy_arxiv_id")
            connection.commit()
        finally:
            connection.close()

        snapshot.unlink()
        with raw_path.open("rb") as raw_file, gzip.GzipFile(snapshot, "wb", mtime=0) as compressed_file:
            shutil.copyfileobj(raw_file, compressed_file)


def test_bootstrap_research_workspace_seeds_database_and_evidence(tmp_path: Path) -> None:
    snapshot = _seed_snapshot(tmp_path)
    workspace = tmp_path / "persistent"

    summary = bootstrap_research_workspace(workspace_dir=workspace, snapshot_path=snapshot)

    assert summary.imported_paper_count == 1
    assert summary.skipped_existing_paper_count == 0
    assert summary.imported_evidence_record_count == 1
    assert summary.skipped_existing_evidence_record_count == 0
    assert summary.total_paper_count == 1
    assert summary.database_path.exists()
    assert summary.evidence_path.read_text(encoding="utf-8").count("evidence-seed-1") == 1

    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=workspace,
            database_url=f"sqlite:///{summary.database_path}",
        )
    )
    try:
        with database.session() as session:
            paper = session.scalars(select(Paper)).one()
            assert paper.title == "Seed Trial"
            assert len(paper.pages) == 1
    finally:
        database.engine.dispose()


def test_bootstrap_research_workspace_migrates_stale_snapshot_copy(tmp_path: Path) -> None:
    snapshot = _seed_snapshot(tmp_path)
    _make_snapshot_missing_current_paper_columns(snapshot)

    summary = bootstrap_research_workspace(
        workspace_dir=tmp_path / "persistent-stale",
        snapshot_path=snapshot,
    )

    assert summary.imported_paper_count == 1
    assert summary.total_paper_count == 1


def test_bootstrap_research_workspace_is_idempotent(tmp_path: Path) -> None:
    snapshot = _seed_snapshot(tmp_path)
    workspace = tmp_path / "persistent"

    first = bootstrap_research_workspace(workspace_dir=workspace, snapshot_path=snapshot)
    second = bootstrap_research_workspace(workspace_dir=workspace, snapshot_path=snapshot)

    assert first.imported_paper_count == 1
    assert second.imported_paper_count == 0
    assert second.skipped_existing_paper_count == 1
    assert second.imported_evidence_record_count == 0
    assert second.skipped_existing_evidence_record_count == 1
    assert second.total_paper_count == 1
    assert second.evidence_path.read_text(encoding="utf-8").count("evidence-seed-1") == 1


def test_bootstrap_research_workspace_fails_before_creating_workspace_for_missing_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "persistent"

    try:
        bootstrap_research_workspace(
            workspace_dir=workspace,
            snapshot_path=tmp_path / "missing.sqlite3.gz",
        )
    except FileNotFoundError as exc:
        assert "missing.sqlite3.gz" in str(exc)
    else:
        raise AssertionError("missing snapshot must fail closed")

    assert not workspace.exists()
