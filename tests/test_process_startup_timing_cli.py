from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.entrypoint import app
from knowledge_engine.vector_search import LocalEmbeddingError


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _build_database(tmp_path: Path) -> Database:
    return Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )


class _FakeEmbeddingGenerator:
    """Minimal `EmbeddingGenerator` double -- no real model load or network call."""

    @property
    def model_id(self) -> str:
        return "fake:test-v1"

    @property
    def dimension(self) -> int:
        return 2

    def generate(self, text: str) -> tuple[float, ...]:
        return (1.0, 0.0)


class _FailingReadyEmbeddingGenerator:
    """Constructs fine, but raises when readiness (`.dimension`) is checked.

    Mirrors a real lazy-loading generator whose model load fails on first
    use rather than at construction time (e.g. `SentenceTransformerEmbeddingGenerator`).
    """

    model_id = "fake:test-v1"

    @property
    def dimension(self) -> int:
        raise LocalEmbeddingError("Failed to load local embedding model 'fake-model'.")

    def generate(self, text: str) -> tuple[float, ...]:
        raise LocalEmbeddingError("Failed to load local embedding model 'fake-model'.")


def test_cli_prints_both_timings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["process-startup-timing"])

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Import to command:" in unwrapped
    assert "Database open:" in unwrapped


def test_cli_output_writes_full_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "timing.json"

    result = CliRunner().invoke(
        app,
        ["process-startup-timing", "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["import_to_command_ms"] >= 0
    assert payload["database_open_ms"] >= 0


def test_cli_uses_the_injected_database_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def build_database() -> Database:
        nonlocal calls
        calls += 1
        return _build_database(tmp_path)

    monkeypatch.setattr(entrypoint, "_local_database", build_database)

    result = CliRunner().invoke(app, ["process-startup-timing"])

    assert result.exit_code == 0, result.output
    assert calls == 1


def test_cli_omits_embedding_generator_timing_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "timing.json"

    result = CliRunner().invoke(app, ["process-startup-timing", "--output", str(output_path)])

    assert result.exit_code == 0, result.output
    assert "Embedding generator ready" not in _unwrapped(result.output)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["embedding_generator_ready_ms"] is None
    assert payload["embedding_generator_model_id"] is None


def test_cli_measures_embedding_generator_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    calls: list[tuple[str, str | None]] = []

    def fake_build_embedding_generator(generator: str, model: str | None) -> object:
        calls.append((generator, model))
        return _FakeEmbeddingGenerator()

    monkeypatch.setattr(entrypoint, "_build_embedding_generator", fake_build_embedding_generator)
    output_path = tmp_path / "timing.json"

    result = CliRunner().invoke(
        app,
        [
            "process-startup-timing",
            "--generator",
            "local",
            "--model",
            "custom-model",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [("local", "custom-model")]
    unwrapped = _unwrapped(result.output)
    assert "Embedding generator ready:" in unwrapped
    assert "fake:test-v1" in unwrapped
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["embedding_generator_ready_ms"] >= 0
    assert payload["embedding_generator_model_id"] == "fake:test-v1"


def test_cli_reports_clean_error_when_generator_fails_to_become_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(
        entrypoint,
        "_build_embedding_generator",
        lambda generator, model: _FailingReadyEmbeddingGenerator(),
    )

    result = CliRunner().invoke(app, ["process-startup-timing", "--generator", "local"])

    assert result.exit_code == 1
    assert "Failed to prepare embedding generator" in _unwrapped(result.output)
    assert "Failed to load local embedding model" in _unwrapped(result.output)


def test_cli_rejects_model_without_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _build_database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["process-startup-timing", "--model", "custom-model"])

    assert result.exit_code == 1
    assert "--model is only used with --generator" in _unwrapped(result.output)
