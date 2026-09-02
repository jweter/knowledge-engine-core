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


class _FakeEmbeddingGenerator:
    """Minimal `EmbeddingGenerator` double -- no real model load or network call."""

    def __init__(self) -> None:
        self.dimension_reads = 0

    @property
    def model_id(self) -> str:
        return "fake:test-v1"

    @property
    def dimension(self) -> int:
        self.dimension_reads += 1
        return 2

    def generate(self, text: str) -> tuple[float, ...]:
        return (1.0, 0.0)


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


def test_embedding_generator_timing_is_none_when_not_requested(tmp_path: Path) -> None:
    timing = measure_process_startup_timing(lambda: _database(tmp_path))

    assert timing.embedding_generator_ready_ms is None
    assert timing.embedding_generator_model_id is None


def test_embedding_generator_timing_is_measured_when_requested(tmp_path: Path) -> None:
    fake = _FakeEmbeddingGenerator()

    timing = measure_process_startup_timing(
        lambda: _database(tmp_path), build_embedding_generator=lambda: fake
    )

    assert timing.embedding_generator_ready_ms is not None
    assert timing.embedding_generator_ready_ms >= 0
    assert timing.embedding_generator_model_id == "fake:test-v1"
    # `dimension` was actually read, forcing a lazy-loading generator to load.
    assert fake.dimension_reads == 1


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
        "embedding_generator_ready_ms": None,
        "embedding_generator_model_id": None,
    }
    assert '"database_open_ms": 34' in timing.to_json()
