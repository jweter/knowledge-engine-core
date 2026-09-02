from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.entrypoint import app


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
