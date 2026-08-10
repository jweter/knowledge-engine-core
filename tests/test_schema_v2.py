"""Focused tests for the M10 schema version 3 migration."""

from pathlib import Path

import pytest
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


def _table_names(database: Database) -> set[str]:
    with database.engine.connect() as connection:
        return set(
            connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars()
        )


def test_fresh_database_initializes_at_current_schema_version(tmp_path: Path) -> None:
    database = _database(tmp_path)

    database.initialize()

    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
        foreign_keys_enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert version == CURRENT_SCHEMA_VERSION == 12
    assert "review_status" in _column_names(database, "import_runs")
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


def test_schema_version_4_migration_is_retry_safe(tmp_path: Path) -> None:
    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE schema_versions SET version = 2 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()
    database.initialize()

    with database.engine.connect() as connection:
        versions = list(
            connection.execute(
                text("SELECT version FROM schema_versions ORDER BY version")
            ).scalars()
        )

    assert versions == [2, CURRENT_SCHEMA_VERSION]
    assert "run_mode" in _column_names(database, "import_runs")
    assert "duplicate_evidence_json" in _column_names(database, "import_items")


def test_current_version_missing_table_is_not_silently_repaired(tmp_path: Path) -> None:
    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE import_items"))

    with pytest.raises(RuntimeError, match="incomplete"):
        database.initialize()

    assert "import_items" not in _table_names(database)
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION


def test_older_version_missing_table_is_not_silently_repaired(tmp_path: Path) -> None:
    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE schema_versions SET version = 2 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )
        connection.execute(text("DROP TABLE import_items"))

    with pytest.raises(RuntimeError, match="incomplete"):
        database.initialize()

    assert "import_items" not in _table_names(database)
    with database.engine.connect() as connection:
        versions = list(
            connection.execute(
                text("SELECT version FROM schema_versions ORDER BY version")
            ).scalars()
        )
    assert versions == [2]


def test_current_version_missing_index_is_not_silently_repaired(tmp_path: Path) -> None:
    database = _database(tmp_path)
    database.initialize()
    index_name = "ix_import_items_computed_content_hash"

    with database.engine.begin() as connection:
        connection.execute(text(f'DROP INDEX "{index_name}"'))

    with pytest.raises(RuntimeError, match="missing indexes"):
        database.initialize()

    assert index_name not in _index_names(database)


def test_upgrading_older_database_adds_new_table_without_error(tmp_path: Path) -> None:
    """A table introduced at a newer schema version is expected to be absent on an
    older database; create_all must add it silently rather than raise."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE paper_pages"))
        connection.execute(
            text(f"UPDATE schema_versions SET version = 3 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    assert "paper_pages" in _table_names(database)
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_dropping_paper_pages_at_current_version_is_not_silently_repaired(
    tmp_path: Path,
) -> None:
    """Once a database is already at the version that introduced paper_pages,
    dropping it is corruption, not an expected absence, and must not be
    silently recreated by create_all."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE paper_pages"))

    with pytest.raises(RuntimeError, match="incomplete"):
        database.initialize()

    assert "paper_pages" not in _table_names(database)


def test_upgrading_older_database_adds_extraction_runs_table_without_error(
    tmp_path: Path,
) -> None:
    """extraction_runs (introduced at version 5) must be silently added when
    upgrading an older database, exactly like paper_pages was at version 4."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE extraction_runs"))
        connection.execute(
            text(f"UPDATE schema_versions SET version = 4 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    assert "extraction_runs" in _table_names(database)
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_dropping_extraction_runs_at_current_version_is_not_silently_repaired(
    tmp_path: Path,
) -> None:
    """Once a database is already at the version that introduced
    extraction_runs, dropping it is corruption, not an expected absence,
    and must not be silently recreated by create_all."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE extraction_runs"))

    with pytest.raises(RuntimeError, match="incomplete"):
        database.initialize()

    assert "extraction_runs" not in _table_names(database)


def test_upgrading_older_database_adds_study_design_rules_version_column(
    tmp_path: Path,
) -> None:
    """M26 adds `extraction_runs.study_design_rules_version` (version 6) to a
    table that already existed at version 5; the ALTER TABLE migration must
    backfill a placeholder for any pre-existing rows rather than fail."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(
            text('ALTER TABLE extraction_runs DROP COLUMN "study_design_rules_version"')
        )
        connection.execute(
            text(f"UPDATE schema_versions SET version = 5 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    assert "study_design_rules_version" in _column_names(database, "extraction_runs")
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_upgrading_older_database_adds_pico_extraction_rules_version_column(
    tmp_path: Path,
) -> None:
    """M28 adds `extraction_runs.pico_extraction_rules_version` (version 7) to a
    table that already existed at version 6; the ALTER TABLE migration must
    backfill a placeholder for any pre-existing rows rather than fail."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(
            text('ALTER TABLE extraction_runs DROP COLUMN "pico_extraction_rules_version"')
        )
        connection.execute(
            text(f"UPDATE schema_versions SET version = 6 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    assert "pico_extraction_rules_version" in _column_names(database, "extraction_runs")
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_upgrading_older_database_adds_paper_pages_table_text_column(
    tmp_path: Path,
) -> None:
    """Adds `paper_pages.table_text` (version 11) to a table that already
    existed at version 10; the ALTER TABLE migration must succeed against a
    `paper_pages` table already carrying rows (unlike the `extraction_runs`
    columns above, this column is nullable with no DEFAULT, since a page
    backfilled before v11 has no re-derivable table-detection signal until
    a separate PDF re-parse)."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text('ALTER TABLE paper_pages DROP COLUMN "table_text"'))
        connection.execute(
            text(
                f"UPDATE schema_versions SET version = 10 WHERE version = {CURRENT_SCHEMA_VERSION}"
            )
        )

    database.initialize()

    assert "table_text" in _column_names(database, "paper_pages")
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_upgrading_older_database_adds_graph_citations_table_without_error(
    tmp_path: Path,
) -> None:
    """graph_citations (introduced at version 9, M47) must be silently added
    when upgrading an older database, exactly like paper_pages/extraction_runs
    were at their own introduction versions."""

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE graph_citations"))
        connection.execute(
            text(f"UPDATE schema_versions SET version = 8 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    assert "graph_citations" in _table_names(database)
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12


def test_upgrading_older_database_widens_relationship_type_constraint(
    tmp_path: Path,
) -> None:
    """M50 adds `supersedes` as a fifth relationship_type (version 10).

    SQLite CHECK constraints cannot be altered in place, so the version 10
    migration rebuilds `graph_claim_relationships` entirely -- simulate a
    pre-M50 database (the original four-value constraint, with an existing
    row) and confirm the rebuild preserves that row, keeps every index, and
    accepts `supersedes` afterward.
    """

    database = _database(tmp_path)
    database.initialize()

    with database.engine.begin() as connection:
        connection.execute(text("DROP TABLE graph_claim_relationships"))
        connection.execute(
            text(
                "CREATE TABLE graph_claim_relationships ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "relationship_id VARCHAR(128) NOT NULL UNIQUE, "
                "source_claim_id INTEGER NOT NULL REFERENCES graph_claims(id), "
                "target_claim_id INTEGER NOT NULL REFERENCES graph_claims(id), "
                "relationship_type VARCHAR(16) NOT NULL, "
                "rationale TEXT NOT NULL, "
                "created_at VARCHAR(32) NOT NULL, "
                "CHECK (relationship_type IN "
                "('supports','contradicts','qualifies','contextualizes'))"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX ix_graph_claim_relationships_relationship_id "
                "ON graph_claim_relationships (relationship_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX ix_graph_claim_relationships_source_claim_id "
                "ON graph_claim_relationships (source_claim_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX ix_graph_claim_relationships_target_claim_id "
                "ON graph_claim_relationships (target_claim_id)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO graph_claims (id, evidence_record_id, created_at) VALUES "
                "(1, 'ev-1', '2026-01-01T00:00:00Z'), (2, 'ev-2', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO graph_claim_relationships "
                "(id, relationship_id, source_claim_id, target_claim_id, "
                "relationship_type, rationale, created_at) VALUES "
                "(1, 'rel-1', 1, 2, 'supports', 'Pre-existing row.', '2026-01-01T00:00:00Z')"
            )
        )
        connection.execute(
            text(f"UPDATE schema_versions SET version = 9 WHERE version = {CURRENT_SCHEMA_VERSION}")
        )

    database.initialize()

    with database.engine.begin() as connection:
        rows = connection.execute(
            text("SELECT relationship_id, relationship_type FROM graph_claim_relationships")
        ).all()
        assert [tuple(row) for row in rows] == [("rel-1", "supports")]

        connection.execute(
            text(
                "INSERT INTO graph_claim_relationships "
                "(id, relationship_id, source_claim_id, target_claim_id, "
                "relationship_type, rationale, created_at) VALUES "
                "(2, 'rel-2', 2, 1, 'supersedes', 'A later trial revises the earlier one.', "
                "'2026-01-01T00:00:00Z')"
            )
        )

    assert {
        "ix_graph_claim_relationships_relationship_id",
        "ix_graph_claim_relationships_source_claim_id",
        "ix_graph_claim_relationships_target_claim_id",
    } <= _index_names(database)
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar_one()
    assert version == CURRENT_SCHEMA_VERSION == 12
