from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database


def _database(tmp_path: Path) -> tuple[Database, Path]:
    database_path = tmp_path / "knowledge-engine.sqlite3"
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{database_path}",
    )
    return Database(settings), database_path


def test_sqlite_connections_use_bounded_busy_timeout(tmp_path: Path) -> None:
    database, _ = _database(tmp_path)
    with database.engine.connect() as connection:
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert busy_timeout == 30_000


def test_initialize_waits_for_transient_parallel_writer(tmp_path: Path) -> None:
    first, database_path = _database(tmp_path)
    first.initialize()
    second, _ = _database(tmp_path)

    blocker = sqlite3.connect(database_path, isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second.initialize)
            time.sleep(0.2)
            assert not future.done()
            blocker.execute("COMMIT")
            future.result(timeout=5)
    finally:
        if blocker.in_transaction:
            blocker.execute("ROLLBACK")
        blocker.close()
