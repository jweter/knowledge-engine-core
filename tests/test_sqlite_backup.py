from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge_engine.sqlite_backup import (
    SQLiteBackupError,
    create_sqlite_backup,
    verify_restored_snapshot,
)


def build_database(path: Path) -> None:
    with sqlite3.connect(path) as database:
        database.execute("PRAGMA user_version = 14")
        database.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        database.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY)")
        database.execute("CREATE TABLE import_runs (id INTEGER PRIMARY KEY)")
        database.executemany("INSERT INTO papers(title) VALUES (?)", [("one",), ("two",)])
        database.execute("INSERT INTO sources DEFAULT VALUES")
        database.execute("INSERT INTO import_runs DEFAULT VALUES")
        database.commit()


def test_create_backup_and_verify_restore(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite"
    snapshot = tmp_path / "backup" / "snapshot.sqlite"
    build_database(source)
    created_at = datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc)

    manifest = create_sqlite_backup(
        source_path=source,
        snapshot_path=snapshot,
        production_commit="abc123",
        created_at=created_at,
    )

    assert manifest.schema_version == 14
    assert manifest.created_at == "2026-07-19T20:00:00Z"
    assert manifest.integrity_check == "ok"
    assert manifest.table_counts == {"papers": 2, "sources": 1, "import_runs": 1}
    assert manifest.byte_count == snapshot.stat().st_size
    assert manifest.filename == "snapshot.sqlite"
    assert manifest.to_json_bytes().endswith(b"\n")
    verify_restored_snapshot(snapshot_path=snapshot, manifest=manifest)


def test_snapshot_is_independent_from_later_source_writes(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    build_database(source)
    manifest = create_sqlite_backup(
        source_path=source,
        snapshot_path=snapshot,
        production_commit="abc123",
    )
    with sqlite3.connect(source) as database:
        database.execute("INSERT INTO papers(title) VALUES ('later')")
        database.commit()

    assert manifest.table_counts["papers"] == 2
    verify_restored_snapshot(snapshot_path=snapshot, manifest=manifest)


def test_modified_snapshot_fails_manifest_reconciliation(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    build_database(source)
    manifest = create_sqlite_backup(
        source_path=source,
        snapshot_path=snapshot,
        production_commit="abc123",
    )
    with snapshot.open("ab") as output:
        output.write(b"unexpected")

    with pytest.raises(SQLiteBackupError, match="does not match"):
        verify_restored_snapshot(snapshot_path=snapshot, manifest=manifest)


def test_existing_destination_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    build_database(source)
    snapshot.write_bytes(b"occupied")

    with pytest.raises(SQLiteBackupError, match="new and distinct"):
        create_sqlite_backup(
            source_path=source,
            snapshot_path=snapshot,
            production_commit="abc123",
        )


def test_naive_timestamp_is_rejected_and_partial_snapshot_removed(tmp_path: Path) -> None:
    source = tmp_path / "live.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    build_database(source)

    with pytest.raises(SQLiteBackupError, match="timezone-aware"):
        create_sqlite_backup(
            source_path=source,
            snapshot_path=snapshot,
            production_commit="abc123",
            created_at=datetime(2026, 7, 19),
        )
    assert not snapshot.exists()
