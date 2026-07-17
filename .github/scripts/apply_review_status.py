"""Apply the guarded M10 execution/review status separation."""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path}:\n{old}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "knowledge_engine/models.py",
    '    run_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)\n',
    '    run_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)\n'
    '    review_status: Mapped[str] = mapped_column(\n'
    '        String(32), nullable=False, default="clear", index=True\n'
    '    )\n',
)

replace_once(
    "knowledge_engine/database.py",
    "CURRENT_SCHEMA_VERSION = 2\n",
    "CURRENT_SCHEMA_VERSION = 3\n",
)
replace_once(
    "knowledge_engine/database.py",
    "_SCHEMA_V2_INDEXES: dict[str, tuple[str, str]] = {\n",
    "_SCHEMA_V3_COLUMNS: dict[str, dict[str, str]] = {\n"
    "    \"import_runs\": {\n"
    "        \"review_status\": \"VARCHAR(32) NOT NULL DEFAULT 'clear'\",\n"
    "    },\n"
    "}\n\n"
    "_SCHEMA_V2_INDEXES: dict[str, tuple[str, str]] = {\n",
)
replace_once(
    "knowledge_engine/database.py",
    "        if existing_version < 2:\n            _migrate_schema_v2(connection)\n\n        _verify_schema_complete(connection)\n",
    "        if existing_version < 2:\n            _migrate_schema_v2(connection)\n        if existing_version < 3:\n            _migrate_schema_v3(connection)\n\n        _verify_schema_complete(connection)\n",
)
replace_once(
    "knowledge_engine/database.py",
    "\ndef _current_schema_version(connection: Connection) -> int:\n",
    "\ndef _migrate_schema_v3(connection: Connection) -> None:\n"
    "    \"\"\"Separate operational execution status from human-review disposition.\"\"\"\n\n"
    "    existing_columns = _table_columns(connection, \"import_runs\")\n"
    "    for column_name, definition in _SCHEMA_V3_COLUMNS[\"import_runs\"].items():\n"
    "        if column_name not in existing_columns:\n"
    "            connection.execute(\n"
    "                text(\n"
    "                    f'ALTER TABLE \"import_runs\" ADD COLUMN \"{column_name}\" {definition}'\n"
    "                )\n"
    "            )\n"
    "    connection.execute(\n"
    "        text(\n"
    "            \"UPDATE import_runs SET review_status = 'needs_review', \"\n"
    "            \"run_status = 'succeeded' WHERE run_status = 'needs_review'\"\n"
    "        )\n"
    "    )\n\n\n"
    "def _current_schema_version(connection: Connection) -> int:\n",
)
replace_once(
    "knowledge_engine/database.py",
    "    if missing_columns:\n",
    "    for table_name, columns in _SCHEMA_V3_COLUMNS.items():\n"
    "        existing_columns = _table_columns(connection, table_name)\n"
    "        for column_name in columns:\n"
    "            if column_name not in existing_columns:\n"
    "                missing_columns.append(f\"{table_name}.{column_name}\")\n"
    "    if missing_columns:\n",
)

replace_once(
    "knowledge_engine/import_runs/ingestion.py",
    "from knowledge_engine.import_runs.service import ImportRunService\n",
    "from knowledge_engine.import_runs.service import ImportRunService\n"
    "from knowledge_engine.import_runs.statuses import derive_review_status, derive_run_status\n",
)
replace_once(
    "knowledge_engine/import_runs/ingestion.py",
    "    needs_review_count: int = 0\n",
    "    needs_review_count: int = 0\n    review_status: str = \"clear\"\n",
)
replace_once(
    "knowledge_engine/import_runs/ingestion.py",
    "        run.run_status = _final_run_status(imported_count, failed_count, needs_review_count)\n",
    "        run.run_status = _final_run_status(imported_count, failed_count)\n"
    "        run.review_status = _final_review_status(needs_review_count)\n",
)
replace_once(
    "knowledge_engine/import_runs/ingestion.py",
    "            needs_review_count=needs_review_count,\n        )\n",
    "            needs_review_count=needs_review_count,\n"
    "            review_status=run.review_status,\n"
    "        )\n",
)
replace_once(
    "knowledge_engine/import_runs/ingestion.py",
    "def _final_run_status(imported_count: int, failed_count: int, needs_review_count: int = 0) -> str:\n"
    "    if failed_count and imported_count:\n"
    "        return \"partially_succeeded\"\n"
    "    if failed_count:\n"
    "        return \"failed\"\n"
    "    if needs_review_count:\n"
    "        return \"needs_review\"\n"
    "    return \"succeeded\"\n",
    "def _final_run_status(imported_count: int, failed_count: int, needs_review_count: int = 0) -> str:\n"
    "    del needs_review_count\n"
    "    return derive_run_status(imported=imported_count, failed=failed_count).value\n\n\n"
    "def _final_review_status(needs_review_count: int) -> str:\n"
    "    return derive_review_status(needs_review=needs_review_count).value\n",
)

replace_once(
    "knowledge_engine/import_runs/linked_ingestion.py",
    "    _final_run_status,\n",
    "    _final_review_status,\n    _final_run_status,\n",
)
replace_once(
    "knowledge_engine/import_runs/linked_ingestion.py",
    "        run.run_status = _final_run_status(\n"
    "            imported_count,\n"
    "            failed_count,\n"
    "            needs_review_count,\n"
    "        )\n",
    "        run.run_status = _final_run_status(imported_count, failed_count)\n"
    "        run.review_status = _final_review_status(needs_review_count)\n",
)
replace_once(
    "knowledge_engine/import_runs/linked_ingestion.py",
    "            needs_review_count=needs_review_count,\n        )\n",
    "            needs_review_count=needs_review_count,\n"
    "            review_status=run.review_status,\n"
    "        )\n",
)

replace_once(
    "knowledge_engine/cli.py",
    '    console.print(f"Run status: {_display_cli_text(run.run_status)}")\n',
    '    console.print(f"Run status: {_display_cli_text(run.run_status)}")\n'
    '    console.print(f"Review status: {_display_cli_text(run.review_status)}")\n'
    '    console.print(f"Run mode: {_display_cli_text(run.run_mode)}")\n'
    '    console.print(\n'
    '        f"Parent import run ID: {_display_cli_text(run.parent_import_run_id or \'None\')}"\n'
    '    )\n',
)
replace_once(
    "knowledge_engine/cli.py",
    '    completed_m9_statuses = {"succeeded", "partially_succeeded", "failed"}\n',
    '    completed_m9_statuses = {"succeeded", "partially_succeeded", "failed"}\n',
)
replace_once(
    "knowledge_engine/cli.py",
    '        console.print(f"Skipped items: {completed_ingestion_summary[\'skipped\']}")\n',
    '        console.print(f"Skipped items: {completed_ingestion_summary[\'skipped\']}")\n'
    '        console.print(f"Needs review items: {completed_ingestion_summary[\'needs_review\']}")\n',
)
replace_once(
    "knowledge_engine/cli.py",
    '        console.print(f"Skipped items: {import_result.skipped_count}")\n',
    '        console.print(f"Skipped items: {import_result.skipped_count}")\n'
    '        console.print(f"Needs review items: {import_result.needs_review_count}")\n',
)
replace_once(
    "knowledge_engine/cli.py",
    '            f"status={_display_cli_text(item.item_status)} "\n'
    '            f"warnings={item.warning_count} "\n',
    '            f"status={_display_cli_text(item.item_status)} "\n'
    '            f"duplicate_outcome={_display_cli_text(item.duplicate_outcome or \'None\')} "\n'
    '            f"matched_paper_id={item.matched_paper_id or \'None\'} "\n'
    '            "matched_import_item_id="\n'
    '            f"{_display_cli_text(item.matched_import_item_id or \'None\')} "\n'
    '            "retry_of_import_item_id="\n'
    '            f"{_display_cli_text(item.retry_of_import_item_id or \'None\')} "\n'
    '            f"warnings={item.warning_count} "\n',
)
replace_once(
    "knowledge_engine/cli.py",
    '        "skipped": sum(1 for item in run.items if item.item_status == "skipped"),\n'
    '    }\n',
    '        "skipped": sum(1 for item in run.items if item.item_status == "skipped"),\n'
    '        "needs_review": sum(\n'
    '            1 for item in run.items if item.item_status == "needs_review"\n'
    '        ),\n'
    '    }\n',
)

replace_once(
    "tests/test_import_run_status_truth_table.py",
    '        pytest.param(0, 0, 1, "needs_review", id="review-only"),\n'
    '        pytest.param(1, 0, 1, "needs_review", id="imported-and-review"),\n',
    '        pytest.param(0, 0, 1, "succeeded", id="review-only"),\n'
    '        pytest.param(1, 0, 1, "succeeded", id="imported-and-review"),\n',
)
replace_once(
    "tests/test_import_run_status_truth_table.py",
    '        pytest.param(5, 0, 3, "needs_review", id="counts-do-not-change-review-precedence"),\n',
    '        pytest.param(5, 0, 3, "succeeded", id="review-does-not-change-execution"),\n',
)

replace_once(
    "tests/test_schema_v2.py",
    '"""Focused tests for the M10 schema version 2 migration."""\n',
    '"""Focused tests for the M10 schema version 3 migration."""\n',
)
replace_once(
    "tests/test_schema_v2.py",
    "def test_fresh_database_initializes_at_schema_version_2(tmp_path: Path) -> None:\n",
    "def test_fresh_database_initializes_at_schema_version_3(tmp_path: Path) -> None:\n",
)
replace_once(
    "tests/test_schema_v2.py",
    "    assert version == CURRENT_SCHEMA_VERSION == 2\n",
    "    assert version == CURRENT_SCHEMA_VERSION == 3\n"
    "    assert \"review_status\" in _column_names(database, \"import_runs\")\n",
)
replace_once(
    "tests/test_schema_v2.py",
    "def test_schema_version_2_migration_is_retry_safe(tmp_path: Path) -> None:\n",
    "def test_schema_version_3_migration_is_retry_safe(tmp_path: Path) -> None:\n",
)
replace_once(
    "tests/test_schema_v2.py",
    '        connection.execute(text("UPDATE schema_versions SET version = 1 WHERE version = 2"))\n',
    '        connection.execute(text("UPDATE schema_versions SET version = 2 WHERE version = 3"))\n',
)
replace_once(
    "tests/test_schema_v2.py",
    "    assert versions == [1, 2]\n",
    "    assert versions == [2, 3]\n",
)
replace_once(
    "tests/test_schema_v2.py",
    '        connection.execute(text("UPDATE schema_versions SET version = 1 WHERE version = 2"))\n',
    '        connection.execute(text("UPDATE schema_versions SET version = 2 WHERE version = 3"))\n',
)
replace_once(
    "tests/test_schema_v2.py",
    "    assert versions == [1]\n",
    "    assert versions == [2]\n",
)
