from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from knowledge_engine.research_runtime import (
    RESEARCH_RUNTIME_CONTRACT_VERSION,
    RESEARCH_RUNTIME_REQUIRED_COMMANDS,
    app,
    research_runtime_capability_payload,
)

runner = CliRunner()


def test_capability_payload_covers_the_complete_research_manifest() -> None:
    payload = research_runtime_capability_payload()

    required = set(cast(list[str], payload["required_commands"]))
    available = set(cast(list[str], payload["available_commands"]))
    missing = set(cast(list[str], payload["missing_commands"]))

    assert payload["schema_version"] == RESEARCH_RUNTIME_CONTRACT_VERSION == 1
    assert payload["surface"] == "ke-research"
    assert required == set(RESEARCH_RUNTIME_REQUIRED_COMMANDS)
    assert available == required
    assert missing == set()
    assert payload["complete"] is True


def test_capability_command_emits_machine_readable_json() -> None:
    result = runner.invoke(app, ["research-runtime-capabilities"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == research_runtime_capability_payload()


def test_every_required_research_command_is_cli_reachable_without_execution() -> None:
    for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"{command}: {result.stdout}"


def test_slim_runtime_import_does_not_require_phase3_vector_modules() -> None:
    """Guard the dependency seam before package slimming begins.

    Run in a fresh interpreter and poison the heavy Phase 3 module names. If
    the research runtime or one of its command modules starts importing them,
    this subprocess fails immediately even though the dev environment has the
    real packages installed.
    """

    blocked = (
        "faiss",
        "torch",
        "sentence_transformers",
        "qdrant_client",
        "knowledge_engine.vector_search",
    )
    script = "\n".join(
        [
            "import json, sys",
            f"blocked = {blocked!r}",
            "for name in blocked: sys.modules[name] = None",
            "import knowledge_engine.research_runtime",
            "for forbidden in ('knowledge_engine.entrypoint', 'knowledge_engine.command_surface'): ",
            "    assert forbidden not in sys.modules, forbidden",
            "print(json.dumps({'ok': True}))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_poetry_exposes_additive_ke_research_entrypoint() -> None:
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert 'ke = "knowledge_engine.command_surface:app"' in pyproject
    assert 'ke-research = "knowledge_engine.research_runtime:app"' in pyproject
