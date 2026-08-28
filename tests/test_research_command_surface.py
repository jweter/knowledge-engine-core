from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from knowledge_engine.research_command_surface import (
    RESEARCH_RUNTIME_CONTRACT_VERSION,
    RESEARCH_RUNTIME_REQUIRED_COMMANDS,
    app,
    research_runtime_capability_payload,
)

runner = CliRunner()


def test_capability_payload_is_explicit_and_fail_closed_until_complete() -> None:
    payload = research_runtime_capability_payload()

    required = set(cast(list[str], payload["required_commands"]))
    available = set(cast(list[str], payload["available_commands"]))
    missing = set(cast(list[str], payload["missing_commands"]))

    assert payload["schema_version"] == RESEARCH_RUNTIME_CONTRACT_VERSION == 1
    assert payload["surface"] == "ke-research"
    assert required == set(RESEARCH_RUNTIME_REQUIRED_COMMANDS)
    assert available.isdisjoint(missing)
    assert available | missing == required
    assert payload["complete"] is (not missing)
    # Stage 1 preserves Core retrieval; Stage 2 adds the first external
    # discovery/planning group without importing the heavyweight entrypoint.
    assert {
        "evidence-report",
        "federated-discover",
        "general-question-acquisition-plan",
    } <= available
    assert "citation-snowball" in missing
    assert payload["complete"] is False


def test_capability_command_emits_machine_readable_json() -> None:
    result = runner.invoke(app, ["research-runtime-capabilities"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == research_runtime_capability_payload()


def test_new_research_commands_are_cli_reachable_without_execution() -> None:
    for command in ("federated-discover", "general-question-acquisition-plan"):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0


def test_poetry_exposes_additive_ke_research_entrypoint() -> None:
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert 'ke = "knowledge_engine.command_surface:app"' in pyproject
    assert 'ke-research = "knowledge_engine.research_command_surface:app"' in pyproject
