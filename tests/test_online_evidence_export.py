from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.online_evidence_export import (
    SCHEMA_FILE_NAME,
    OnlineEvidenceExportError,
    export_online_evidence_contract,
)
from knowledge_engine.online_evidence_schema import validate
from knowledge_engine.online_golden import GOLDEN_BUNDLE_NAME, GOLDEN_CONTENTS_DIR

FIXTURE = Path(__file__).parent / "fixtures" / "online_evidence"
SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "schemas" / "online_evidence_v1.schema.json"


def _committed_files() -> list[Path]:
    return sorted(p.relative_to(FIXTURE) for p in FIXTURE.rglob("*") if p.is_file())


def test_export_writes_byte_identical_fixture_and_schema(tmp_path: Path) -> None:
    export_online_evidence_contract(tmp_path)

    for relative in _committed_files():
        assert (tmp_path / relative).read_bytes() == (FIXTURE / relative).read_bytes()
    assert (tmp_path / SCHEMA_FILE_NAME).read_bytes() == SCHEMA_PATH.read_bytes()


def test_export_creates_a_missing_directory(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "export"
    export_online_evidence_contract(destination)

    assert (destination / GOLDEN_BUNDLE_NAME).is_file()
    assert (destination / GOLDEN_CONTENTS_DIR).is_dir()
    assert (destination / SCHEMA_FILE_NAME).is_file()


def test_export_refuses_a_non_empty_directory_without_force(tmp_path: Path) -> None:
    (tmp_path / "unrelated.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(OnlineEvidenceExportError, match="not empty"):
        export_online_evidence_contract(tmp_path)

    # The refusal is fail-closed: nothing from the contract was written alongside it.
    assert not (tmp_path / GOLDEN_BUNDLE_NAME).exists()
    assert (tmp_path / "unrelated.txt").read_text(encoding="utf-8") == "keep me"


def test_export_with_force_overwrites_a_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "unrelated.txt").write_text("keep me", encoding="utf-8")

    export_online_evidence_contract(tmp_path, force=True)

    assert (tmp_path / GOLDEN_BUNDLE_NAME).is_file()
    assert (tmp_path / "unrelated.txt").read_text(encoding="utf-8") == "keep me"


def test_export_refuses_a_symlinked_directory(tmp_path: Path) -> None:
    real_target = tmp_path / "real"
    real_target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_target, target_is_directory=True)

    with pytest.raises(OnlineEvidenceExportError, match="symbolic link"):
        export_online_evidence_contract(link)


def test_exported_bundle_validates_against_the_json_schema(tmp_path: Path) -> None:
    export_online_evidence_contract(tmp_path)

    schema: dict[str, Any] = json.loads((tmp_path / SCHEMA_FILE_NAME).read_text("utf-8"))
    bundle: dict[str, Any] = json.loads((tmp_path / GOLDEN_BUNDLE_NAME).read_text("utf-8"))
    assert validate(bundle, schema) == []


def test_exported_bundle_passes_online_evidence_validate(tmp_path: Path) -> None:
    export_online_evidence_contract(tmp_path)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "online-evidence-validate",
            str(tmp_path / GOLDEN_BUNDLE_NAME),
            "--contents-dir",
            str(tmp_path / GOLDEN_CONTENTS_DIR),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "verified against retrieved content" in " ".join(result.output.split())


def test_cli_exports_and_refuses_overwrite_without_force(tmp_path: Path) -> None:
    destination = tmp_path / "export"
    runner = CliRunner()

    ok = runner.invoke(entrypoint.app, ["online-evidence-export-contract", str(destination)])
    assert ok.exit_code == 0, ok.output
    for relative in _committed_files():
        assert (destination / relative).read_bytes() == (FIXTURE / relative).read_bytes()

    refused = runner.invoke(entrypoint.app, ["online-evidence-export-contract", str(destination)])
    assert refused.exit_code != 0
    assert "already exists and is not empty" in refused.output

    forced = runner.invoke(
        entrypoint.app, ["online-evidence-export-contract", str(destination), "--force"]
    )
    assert forced.exit_code == 0, forced.output
