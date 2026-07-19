from __future__ import annotations

from pathlib import Path

import pytest
import typer

from knowledge_engine import corpus_readiness_cli


def test_atomic_report_replaces_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "readiness.json"
    output.write_text("old", encoding="utf-8")

    corpus_readiness_cli._write_report_atomically(output, "new\n")

    assert output.read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / ".readiness.json.tmp").exists()


def test_stage_collision_preserves_existing_files(tmp_path: Path) -> None:
    output = tmp_path / "readiness.json"
    output.write_text("old", encoding="utf-8")
    stage = tmp_path / ".readiness.json.tmp"
    stage.write_text("other process", encoding="utf-8")

    with pytest.raises(typer.BadParameter, match="could not be written"):
        corpus_readiness_cli._write_report_atomically(output, "new\n")

    assert output.read_text(encoding="utf-8") == "old"
    assert stage.read_text(encoding="utf-8") == "other process"


def test_replace_failure_removes_owned_stage_and_preserves_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "readiness.json"
    output.write_text("old", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError

    monkeypatch.setattr(corpus_readiness_cli.os, "replace", fail_replace)

    with pytest.raises(typer.BadParameter, match="could not be written"):
        corpus_readiness_cli._write_report_atomically(output, "new\n")

    assert output.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / ".readiness.json.tmp").exists()
