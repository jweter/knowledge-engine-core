from __future__ import annotations

from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.process_startup_timing import (
    PROCESS_STARTUP_TIMING_SCHEMA_VERSION,
    ProcessStartupTiming,
    measure_process_startup_timing,
)


def _database(tmp_path: Path) -> Database:
    return Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )


def test_measures_both_costs_independently(tmp_path: Path) -> None:
    built: list[Database] = []

    def build_database() -> Database:
        database = _database(tmp_path)
        built.append(database)
        return database

    timing = measure_process_startup_timing(build_database)

    assert timing.schema_version == PROCESS_STARTUP_TIMING_SCHEMA_VERSION
    assert timing.import_to_command_ms >= 0
    assert timing.database_open_ms >= 0
    # build_database() was actually called, and its database was initialized
    # (schema/index readiness) rather than merely constructed.
    assert len(built) == 1
    with built[0].session() as session:
        assert session is not None


def test_only_calls_build_database_once(tmp_path: Path) -> None:
    calls = 0

    def build_database() -> Database:
        nonlocal calls
        calls += 1
        return _database(tmp_path)

    measure_process_startup_timing(build_database)

    assert calls == 1


def test_to_dict_and_to_json_round_trip() -> None:
    timing = ProcessStartupTiming(
        schema_version=PROCESS_STARTUP_TIMING_SCHEMA_VERSION,
        import_to_command_ms=12,
        database_open_ms=34,
    )

    payload = timing.to_dict()

    assert payload == {
        "schema_version": PROCESS_STARTUP_TIMING_SCHEMA_VERSION,
        "import_to_command_ms": 12,
        "database_open_ms": 34,
    }
    assert '"database_open_ms": 34' in timing.to_json()
