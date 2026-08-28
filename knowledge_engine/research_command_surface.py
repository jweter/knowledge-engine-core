"""Slim Core command surface for the hosted Research Copilot path.

This is deliberately built on :mod:`knowledge_engine.cli`, not the production
``knowledge_engine.command_surface`` / ``knowledge_engine.entrypoint`` registry.
The latter imports Phase 3 vector backends at module import time and therefore
pulls FAISS, sentence-transformers, PyTorch, and Qdrant into any process that
only wants the deterministic research commands.

Stage 1 does not pretend the slim surface is complete. It exposes every command
already registered by ``knowledge_engine.cli`` and adds a machine-readable
capability report against the explicit command set the current AI orchestration
can invoke. Later slices can add the missing federated-discovery/acquisition
commands here one bounded group at a time. Until ``complete`` becomes true, a
hosted Web deployment must continue to fail closed.
"""

from __future__ import annotations

import json

import click
import typer

import knowledge_engine.cli as cli

RESEARCH_RUNTIME_CONTRACT_VERSION = 1
RESEARCH_RUNTIME_REQUIRED_COMMANDS: tuple[str, ...] = (
    "evidence-report",
    "evidence-intelligence",
    "federated-discover",
    "citation-snowball",
    "general-question-acquisition-plan",
    "general-question-acquire-pmc",
    "general-question-acquire-europe-pmc",
    "general-question-acquire-core",
    "general-question-acquire-unpaywall",
    "extraction-review-batch-generate",
    "extraction-review-autoclassify",
    "extraction-review-promote",
    "evidence-review-automate",
    "evidence-record-review-promote",
)

app = cli.app


def research_runtime_capability_payload() -> dict[str, object]:
    """Return the exact Research Copilot command coverage of this slim surface."""

    registered = _registered_command_names()
    available = tuple(
        command for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS if command in registered
    )
    missing = tuple(
        command for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS if command not in registered
    )
    return {
        "schema_version": RESEARCH_RUNTIME_CONTRACT_VERSION,
        "surface": "ke-research",
        "complete": not missing,
        "required_commands": list(RESEARCH_RUNTIME_REQUIRED_COMMANDS),
        "available_commands": list(available),
        "missing_commands": list(missing),
    }


def _registered_command_names() -> frozenset[str]:
    command = typer.main.get_command(app)
    if not isinstance(command, click.Group):
        return frozenset()
    return frozenset(command.commands)


@app.command("research-runtime-capabilities")
def research_runtime_capabilities() -> None:
    """Print machine-readable hosted Research Copilot command coverage."""

    typer.echo(json.dumps(research_runtime_capability_payload(), sort_keys=True))
