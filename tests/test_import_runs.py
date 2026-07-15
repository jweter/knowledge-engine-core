from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Table, create_engine, text
from typer.testing import CliRunner

import knowledge_engine.cli as cli
import knowledge_engine.import_runs.service as import_run_service
from knowledge_engine.cli import app
from knowledge_engine.config import Settings
from knowledge_engine.database import CURRENT_SCHEMA_VERSION, Database, create_fts_tables
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.models import (
    Author,
    Base,
    Journal,
    Keyword,
    Paper,
    PaperAuthor,
    PaperKeyword,
    PaperText,
)
from tests.corpus_fixtures import (
    get_run,
    make_database,
    prepare_corpus_layout,
    write_corpus_manifest,
    write_sources,
)


def make_corpus(
    tmp_path: Path,
    *,
    corpus_id: str = "test_corpus",
    rows: list[dict[str, str]] | None = None,
    corpus_overrides: dict[str, object] | None = None,
    source_manifest: str = "sources.csv",
    create_source_manifest: bool = True,
    create_license: bool = True,
) -> Path:
    corpus_dir, _ = prepare_corpus_layout(
        tmp_path,
        corpus_id=corpus_id,
        create_license=create_license,
    )
    corpus = {
        "manifest_version": 1,
        "corpus_id": corpus_id,
        "name": "Test Corpus",
        "description": "A test corpus.",
        "scientific_domain": "test science",
        "research_question": {"question_id": "q_test", "text": "Does this persist?"},
        "created_at": "2026-07-11",
        "updated_at": "2026-07-11",
        "license_policy": "license_policy.md",
        "source_manifest": source_manifest,
        "default_local_papers_directory": f"papers/corpora/{corpus_id}",
    }
    if corpus_overrides:
        corpus.update(corpus_overrides)
    corpus_path = corpus_dir / "corpus.json"
    write_corpus_manifest(corpus_path, corpus)
    if create_source_manifest:
        write_sources(corpus_dir / source_manifest, rows or [source_row()])
    return corpus_path


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "source_id": "source-1",
        "title": "Persisted Paper",
        "publication_year": "2024",
        "doi": "10.1234/PERSIST",
        "usage_status": "approved_open_access",
        "inclusion_status": "included",
        "source_url": "https://example.test/persist",
        "access_date": "2026-07-11",
        "inclusion_reason": "Relevant.",
        "license_type": "CC-BY",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "local_path": "paper.pdf",
    }
    row.update(overrides)
    return row


def create_run(
    tmp_path: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    check_files: bool = False,
    corpus_overrides: dict[str, object] | None = None,
    create_source_manifest: bool = True,
    create_license: bool = True,
) -> tuple[Database, str]:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=rows,
        corpus_overrides=corpus_overrides,
        create_source_manifest=create_source_manifest,
        create_license=create_license,
    )
    if check_files:
        (tmp_path / "papers" / "corpora" / "test_corpus" / "paper.pdf").write_text(
            "placeholder", encoding="utf-8"
        )
    with database.session() as session:
        persisted = ImportRunService(session, project_root=tmp_path).create_run(
            corpus_path,
            check_files=check_files,
        )
        run_id = persisted.import_run_id
    return database, run_id


def test_fresh_database_creates_m8_schema(tmp_path: Path) -> None:
    database = make_database(tmp_path)

    with database.engine.connect() as connection:
        tables = set(
            connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars()
        )
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar()

    assert {"import_runs", "import_items", "import_issues", "manifest_snapshots"}.issubset(tables)
    assert version == CURRENT_SCHEMA_VERSION


def test_existing_pre_m8_database_upgrades_and_preserves_papers(tmp_path: Path) -> None:
    db_path = tmp_path / "knowledge.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    old_tables: list[Table] = [
        cast(Table, Journal.__table__),
        cast(Table, Author.__table__),
        cast(Table, Keyword.__table__),
        cast(Table, Paper.__table__),
        cast(Table, PaperText.__table__),
        cast(Table, PaperAuthor.__table__),
        cast(Table, PaperKeyword.__table__),
    ]
    Base.metadata.create_all(engine, tables=old_tables)
    create_fts_tables(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO papers(title, source_path, content_hash, page_count, word_count) "
                "VALUES ('Existing', 'paper.pdf', :hash, 1, 10)"
            ),
            {"hash": "a" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO paper_texts(paper_id, raw_text, extraction_method) "
                "VALUES (1, 'searchable text', 'pymupdf')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO paper_search(rowid, title, abstract, body_text, raw_text) "
                "VALUES (1, 'Existing', '', '', 'searchable text')"
            )
        )

    database = Database(
        Settings(
            project_root=tmp_path, data_dir=tmp_path / "data", database_url=f"sqlite:///{db_path}"
        )
    )
    database.initialize()

    with database.engine.connect() as connection:
        paper_count = connection.execute(text("SELECT count(*) FROM papers")).scalar()
        text_count = connection.execute(text("SELECT count(*) FROM paper_texts")).scalar()
        fts_match = connection.execute(
            text("SELECT count(*) FROM paper_search WHERE paper_search MATCH 'searchable'")
        ).scalar()
        run_table = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_runs'")
        ).scalar()
    assert paper_count == 1
    assert text_count == 1
    assert fts_match == 1
    assert run_table == 1


def test_repeated_initialization_is_idempotent(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    database.initialize()

    with database.engine.connect() as connection:
        versions = connection.execute(text("SELECT count(*) FROM schema_versions")).scalar()

    assert versions == 1


def test_unsupported_future_schema_version_fails_clearly(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    with database.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO schema_versions(version, applied_at) VALUES (999, 'now')")
        )

    with pytest.raises(RuntimeError, match="newer than this application"):
        database.initialize()


def test_current_schema_version_with_missing_tables_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "incomplete.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_versions(version INTEGER, applied_at TEXT)"))
        connection.execute(
            text("INSERT INTO schema_versions(version, applied_at) VALUES (:version, 'now')"),
            {"version": CURRENT_SCHEMA_VERSION},
        )

    database = Database(
        Settings(
            project_root=tmp_path, data_dir=tmp_path / "data", database_url=f"sqlite:///{db_path}"
        )
    )

    with pytest.raises(RuntimeError, match="incomplete"):
        database.initialize()


def test_duplicate_schema_version_rows_fail_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "ambiguous.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_versions(version INTEGER, applied_at TEXT)"))
        connection.execute(text("INSERT INTO schema_versions(version, applied_at) VALUES (1, 'a')"))
        connection.execute(text("INSERT INTO schema_versions(version, applied_at) VALUES (1, 'b')"))

    database = Database(
        Settings(
            project_root=tmp_path, data_dir=tmp_path / "data", database_url=f"sqlite:///{db_path}"
        )
    )

    with pytest.raises(RuntimeError, match="recorded more than once"):
        database.initialize()


def test_partial_migration_failure_does_not_record_schema_version_and_can_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'broken.sqlite3'}",
        )
    )

    def fail_create_all(bind: Any, *args: object, **kwargs: object) -> None:
        bind.execute(text("CREATE TABLE partial_migration_marker(id INTEGER)"))
        raise RuntimeError("boom")

    monkeypatch.setattr("knowledge_engine.database.Base.metadata.create_all", fail_create_all)
    with pytest.raises(RuntimeError, match="boom"):
        database.initialize()

    with database.engine.connect() as connection:
        table_exists = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_versions'")
        ).scalar()
    assert table_exists is None

    monkeypatch.undo()
    database.initialize()
    with database.engine.connect() as connection:
        version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar()
    assert version == CURRENT_SCHEMA_VERSION


def test_valid_manifest_without_file_checks_persists_validated_run(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path)

    run = get_run(database, run_id)

    assert run.run_status == "validated"
    assert run.validation_mode == "metadata_only"
    assert run.manifest_validity == "valid"
    assert run.import_readiness == "not evaluated"
    assert len(run.items) == 1
    assert run.items[0].item_status == "valid"
    assert len(run.issues) == 0


def test_ready_manifest_with_file_checks_persists_validated_run(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path, check_files=True)

    run = get_run(database, run_id)

    assert run.run_status == "validated"
    assert run.import_readiness == "ready"
    assert run.items[0].local_path == "paper.pdf"


def test_import_blocked_manifest_persists_blocked_run(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path, rows=[source_row(usage_status="needs_legal_review")])

    run = get_run(database, run_id)

    assert run.run_status == "import_blocked"
    assert run.manifest_validity == "valid"
    assert run.import_readiness == "blocked"
    assert run.items[0].item_status == "import_blocked"
    assert run.import_blocker_count == 1


def test_run_status_invariants_match_validity_and_readiness(tmp_path: Path) -> None:
    valid_database, valid_run_id = create_run(tmp_path / "valid")
    blocked_database, blocked_run_id = create_run(
        tmp_path / "blocked",
        rows=[source_row(usage_status="needs_legal_review")],
    )
    invalid_database, invalid_run_id = create_run(
        tmp_path / "invalid",
        corpus_overrides={"corpus_id": "Bad ID"},
    )

    valid_run = get_run(valid_database, valid_run_id)
    blocked_run = get_run(blocked_database, blocked_run_id)
    invalid_run = get_run(invalid_database, invalid_run_id)

    assert (valid_run.run_status, valid_run.manifest_validity) == ("validated", "valid")
    assert (blocked_run.run_status, blocked_run.manifest_validity) == (
        "import_blocked",
        "valid",
    )
    assert blocked_run.import_readiness == "blocked"
    assert (invalid_run.run_status, invalid_run.manifest_validity) == (
        "validation_failed",
        "invalid",
    )


def test_structurally_invalid_manifest_is_persisted(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path, corpus_overrides={"corpus_id": "Bad ID"})

    run = get_run(database, run_id)

    assert run.run_status == "validation_failed"
    assert run.manifest_validity == "invalid"
    assert run.structural_error_count == 1
    assert run.issues[0].code == "invalid_corpus_id"


def test_malformed_json_is_persisted_without_items(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = tmp_path / "bad.json"
    corpus_path.write_text("{not-json}", encoding="utf-8")

    with database.session() as session:
        persisted = ImportRunService(session, project_root=tmp_path).create_run(corpus_path)
        run_id = persisted.import_run_id

    run = get_run(database, run_id)
    assert run.run_status == "validation_failed"
    assert run.manifest_validity == "invalid"
    assert run.manifest_snapshot.source_csv_text is None
    assert len(run.items) == 0
    assert run.issues[0].code == "malformed_json"


def test_missing_source_csv_and_license_policy_are_persisted(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path, create_source_manifest=False, create_license=False)

    run = get_run(database, run_id)
    codes = [issue.code for issue in run.issues]
    assert run.run_status == "validation_failed"
    assert "source_manifest_missing" in codes
    assert "license_policy_missing" in codes


def test_duplicate_source_id_and_doi_warning_are_persisted_in_order(tmp_path: Path) -> None:
    rows = [
        source_row(source_id="source-1", doi="https://doi.org/10.1234/DUP"),
        source_row(source_id="source-1", doi="doi:10.1234/dup", title="Second"),
    ]
    database, run_id = create_run(tmp_path, rows=rows)

    run = get_run(database, run_id)
    assert [issue.sequence for issue in run.issues] == [1, 2]
    assert [issue.code for issue in run.issues] == [
        "duplicate_normalized_doi",
        "duplicate_source_id",
    ]
    assert run.items[1].item_status == "invalid"


def test_legacy_year_warning_is_persisted(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    sources = corpus_path.parent / "sources.csv"
    sources.write_text(
        "source_id,title,year,doi,usage_status,inclusion_status,source_url,access_date,"
        "inclusion_reason,license_type,license_url,local_path\n"
        "source-1,Legacy,2024,10.1234/legacy,approved_open_access,included,"
        "https://example.test,2026-07-11,Relevant,CC-BY,"
        "https://creativecommons.org/licenses/by/4.0/,paper.pdf\n",
        encoding="utf-8",
    )
    with database.session() as session:
        persisted = ImportRunService(session, project_root=tmp_path).create_run(corpus_path)
        run_id = persisted.import_run_id

    run = get_run(database, run_id)
    assert run.issues[0].code == "deprecated_year_column"
    assert run.warning_count == 1


def test_snapshot_hashes_and_bytes_round_trip(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path)

    run = get_run(database, run_id)

    corpus_bytes = run.manifest_snapshot.corpus_json_bytes
    source_bytes = run.manifest_snapshot.source_csv_bytes
    assert source_bytes is not None
    combined = sha256()
    for label, value in [
        (b"manifest_version", b"1"),
        (b"corpus_json", corpus_bytes),
        (b"source_csv:present", source_bytes),
    ]:
        combined.update(label)
        combined.update(len(value).to_bytes(8, byteorder="big"))
        combined.update(value)

    assert "manifest_version" in run.manifest_snapshot.corpus_json_text
    assert "source_id" in (run.manifest_snapshot.source_csv_text or "")
    assert run.manifest_snapshot.corpus_json_sha256 == sha256(corpus_bytes).hexdigest()
    assert run.manifest_snapshot.source_csv_sha256 == sha256(source_bytes).hexdigest()
    assert run.manifest_snapshot.combined_sha256 == combined.hexdigest()


def test_snapshot_preserves_bom_hash_identity(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    original = corpus_path.read_bytes()
    corpus_path.write_bytes(b"\xef\xbb\xbf" + original)

    with database.session() as session:
        run_id = (
            ImportRunService(session, project_root=tmp_path).create_run(corpus_path).import_run_id
        )

    run = get_run(database, run_id)
    assert run.manifest_snapshot.corpus_json_bytes.startswith(b"\xef\xbb\xbf")
    assert not run.manifest_snapshot.corpus_json_text.startswith("\ufeff")
    assert (
        run.manifest_snapshot.corpus_json_sha256
        == sha256(run.manifest_snapshot.corpus_json_bytes).hexdigest()
    )


def test_snapshot_does_not_capture_non_csv_source_manifest(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path, source_manifest="paper.pdf", create_source_manifest=False)
    (corpus_path.parent / "paper.pdf").write_bytes(b"%PDF-not-a-source-csv")

    with database.session() as session:
        run_id = (
            ImportRunService(session, project_root=tmp_path).create_run(corpus_path).import_run_id
        )

    run = get_run(database, run_id)
    assert run.run_status == "validation_failed"
    assert run.manifest_snapshot.source_csv_bytes is None
    assert run.manifest_snapshot.source_csv_text is None


def test_oversized_manifest_input_fails_before_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    monkeypatch.setattr(import_run_service, "MAX_MANIFEST_INPUT_BYTES", 10)

    with pytest.raises(ValueError, match="too large"), database.session() as session:
        ImportRunService(session, project_root=tmp_path).create_run(corpus_path)

    with database.engine.connect() as connection:
        run_count = connection.execute(text("SELECT count(*) FROM import_runs")).scalar()
    assert run_count == 0


def test_item_and_issue_counts_match_persisted_records(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path, rows=[source_row(source_id="")])

    run = get_run(database, run_id)

    assert run.total_source_rows == len(run.items)
    assert run.warning_count == sum(1 for issue in run.issues if issue.severity == "warning")
    assert run.structural_error_count == sum(1 for issue in run.issues if issue.blocks_manifest)
    assert run.import_blocker_count == sum(1 for issue in run.issues if issue.blocks_import)
    assert run.issues[0].import_item_id == run.items[0].import_item_id
    item = run.items[0]
    assert item.warning_count == sum(1 for issue in item.issues if issue.severity == "warning")
    assert item.structural_error_count == sum(1 for issue in item.issues if issue.blocks_manifest)
    assert item.import_blocker_count == sum(1 for issue in item.issues if issue.blocks_import)


def test_uuid_identifiers_are_unique_and_printable(tmp_path: Path) -> None:
    database, run_id = create_run(
        tmp_path,
        rows=[source_row(source_id="source-1"), source_row(source_id="source-2")],
    )

    run = get_run(database, run_id)
    item_ids = [item.import_item_id for item in run.items]
    assert len(item_ids) == len(set(item_ids))
    assert len(run.import_run_id) == 36
    assert all(len(item_id) == 36 for item_id in item_ids)


def test_timestamps_use_utc_iso_policy(tmp_path: Path) -> None:
    database, run_id = create_run(tmp_path)
    run = get_run(database, run_id)

    assert run.created_at.endswith("+00:00")
    assert run.completed_at.endswith("+00:00")
    assert run.manifest_snapshot.captured_at.endswith("+00:00")


def test_cli_corpus_run_create_and_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus_path = make_corpus(tmp_path)
    database = make_database(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    create_result = CliRunner().invoke(app, ["corpus-run-create", str(corpus_path)])

    assert create_result.exit_code == 0
    assert "Import run recorded" in create_result.output
    assert "Validation run metadata was written to the database." in create_result.output
    assert "No PDFs were parsed or hashed." in create_result.output
    assert "No papers were imported." in create_result.output
    run_id = _run_id_from_output(create_result.output)

    show_result = CliRunner().invoke(app, ["corpus-run-show", run_id])

    assert show_result.exit_code == 0
    assert "Persisted import run" in show_result.output
    assert "source_id=source-1" in show_result.output
    assert "No database writes to paper or FTS records were performed." in show_result.output


def test_cli_corpus_run_create_import_blocked_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = make_corpus(tmp_path, rows=[source_row(usage_status="needs_legal_review")])
    database = make_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(app, ["corpus-run-create", str(corpus_path)])

    assert result.exit_code == 0
    assert "Run status: import_blocked" in result.output
    assert "Import readiness: blocked" in result.output


def test_cli_corpus_run_create_invalid_manifest_exits_nonzero_but_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = make_corpus(tmp_path, corpus_overrides={"corpus_id": "Bad ID"})
    database = make_database(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    create_result = CliRunner().invoke(app, ["corpus-run-create", str(corpus_path)])

    assert create_result.exit_code == 1
    run_id = _run_id_from_output(create_result.output)
    show_result = CliRunner().invoke(app, ["corpus-run-show", run_id])
    assert show_result.exit_code == 0
    assert "validation_failed" in show_result.output
    assert "invalid_corpus_id" in show_result.output


def test_cli_corpus_run_show_unknown_id_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(app, ["corpus-run-show", "missing"])

    assert result.exit_code == 1
    assert "Unknown import run" in result.output


def test_cli_corpus_run_show_malformed_uuid_exits_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(app, ["corpus-run-show", "not-a-uuid"])

    assert result.exit_code == 1
    assert "Unknown import run" in result.output
    assert "Traceback" not in result.output


def test_cli_corpus_run_create_does_not_create_papers_or_fts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = make_corpus(tmp_path)
    database = make_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(app, ["corpus-run-create", str(corpus_path)])

    assert result.exit_code == 0
    with database.engine.connect() as connection:
        paper_count = connection.execute(text("SELECT count(*) FROM papers")).scalar()
        fts_count = connection.execute(text("SELECT count(*) FROM paper_search")).scalar()
    assert paper_count == 0
    assert fts_count == 0


def test_corpus_validate_remains_non_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = make_corpus(tmp_path)
    database = make_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path)])

    assert result.exit_code == 0
    with database.engine.connect() as connection:
        run_count = connection.execute(text("SELECT count(*) FROM import_runs")).scalar()
    assert run_count == 0


def test_persistence_failure_rolls_back_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = make_corpus(tmp_path)
    database = make_database(tmp_path)

    def fail_add_issues(*args: object, **kwargs: object) -> None:
        raise RuntimeError("issue persistence failed")

    monkeypatch.setattr(
        "knowledge_engine.import_runs.repository.ImportRunRepository.add_issues",
        fail_add_issues,
    )

    with (
        pytest.raises(RuntimeError, match="issue persistence failed"),
        database.session() as session,
    ):
        ImportRunService(session, project_root=tmp_path).create_run(corpus_path)

    with database.engine.connect() as connection:
        run_count = connection.execute(text("SELECT count(*) FROM import_runs")).scalar()
        item_count = connection.execute(text("SELECT count(*) FROM import_items")).scalar()
        snapshot_count = connection.execute(
            text("SELECT count(*) FROM manifest_snapshots")
        ).scalar()
    assert run_count == 0
    assert item_count == 0
    assert snapshot_count == 0


def test_cli_help_includes_import_run_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "corpus-run-create" in result.output
    assert "corpus-run-show" in result.output


def _run_id_from_output(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Import run ID:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("Import run ID not found in output")
