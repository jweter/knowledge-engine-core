"""Focused tests for the M10 schema version 2 migration."""

from pathlib import Path

from sqlalchemy import text

from knowledge_engine.config import Settings
from knowledge_engine.database import CURRENT_SCHEMA_VERSION, Database


def _database(tmp_path: Path) -> Database:
    return Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'schema.sqlite3'}",
        )
    )


def _column_names(database: Database, table_name: str) -> set[str]:
    with database.engine.connect() as connection:
        return {
            str(row[1])
            for row in connection.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
        }


def _index_names(database: Database) -> set[str]:
    with database.engine.connect() as connection:
        return set(
            connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL")
            ).scalars()
        )


def test_fresh_database_initializes_at_schema_version_2(tmp_path: Path) -> None:
    database = _database(tmp_path)

    database.initialize()

    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
        foreign_keys_enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert version == CURRENT_SCHEMA_VERSION == 2
    assert foreign_keys_enabled == 1
    assert "run_mode" in _column_names(database, "import_runs")
    assert {
        "duplicate_outcome",
        "matched_paper_id",
        "matched_import_item_id",
        "computed_content_hash",
        "duplicate_evidence_json",
        "retry_of_import_item_id",
    } <= _column_names(database, "import_items")
    assert {
        "ix_import_runs_parent_import_run_id",
        "ix_import_items_duplicate_outcome",
        "ix_import_items_matched_paper_id",
        "ix_import_items_matched_import_item_id",
        "ix_import_items_computed_content_hash",
        "ix_import_items_retry_of_import_item_id",
    } <= _index_names(database)


def test_schema_version_2_migration_is_retry_safe(tmp_path: Path) -> None:
    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("UPDATE schema_versions SET version = 1 WHERE version = 2"))

    database.initialize()
    database.initialize()

    with database.engine.connect() as connection:
        versions = list(
            connection.execute(text("SELECT version FROM schema_versions ORDER BY version")).scalars()
        )

    assert versions == [1, 2]
    assert "run_mode" in _column_names(database, "import_runs")
    assert "duplicate_evidence_json" in _column_names(database, "import_items")
