"""Lean dependency projection for the hosted ``ke-research`` command surface.

The normal Knowledge Engine installation intentionally keeps the complete vector
stack. Hosted Research Copilot does not need that stack at command-surface import
or execution time, so deployment tooling can install the project with ``--no-deps``
and install only the requirements rendered by this module.

The requirements are derived from ``pyproject.toml`` rather than copied into a
second hand-maintained requirements file. Unsupported Poetry dependency shapes
fail closed instead of being silently omitted.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

VECTOR_ONLY_DEPENDENCIES = frozenset(
    {
        "faiss-cpu",
        "qdrant-client",
        "sentence-transformers",
        "torch",
    }
)


def research_runtime_requirements(pyproject_path: Path) -> tuple[str, ...]:
    """Return PEP 508-ish pip requirements for the slim Research runtime.

    Only the four Phase-3/vector dependencies are excluded. Every other declared
    main dependency must have a string constraint that this module can translate;
    a new unsupported dependency shape raises ``ValueError`` so packaging cannot
    accidentally produce an incomplete hosted runtime.
    """

    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = payload["tool"]["poetry"]["dependencies"]
    if not isinstance(dependencies, dict):
        raise ValueError("tool.poetry.dependencies must be a table")

    requirements: list[str] = []
    for name in sorted(dependencies):
        if name == "python" or name in VECTOR_ONLY_DEPENDENCIES:
            continue
        constraint = dependencies[name]
        if not isinstance(constraint, str):
            raise ValueError(
                f"Unsupported dependency declaration for {name!r}: "
                f"expected a string constraint, got {type(constraint).__name__}."
            )
        requirements.append(f"{name}{_constraint_to_pip(constraint)}")
    return tuple(requirements)


def render_research_runtime_requirements(pyproject_path: Path) -> str:
    """Render the slim requirement projection as a deterministic requirements file."""

    lines = (
        "# Generated from pyproject.toml by knowledge_engine.research_runtime_packaging.",
        "# Phase-3/vector-only dependencies are intentionally excluded.",
        *research_runtime_requirements(pyproject_path),
    )
    return "\n".join(lines) + "\n"


def _constraint_to_pip(constraint: str) -> str:
    normalized = constraint.strip()
    if not normalized or normalized == "*":
        return ""
    if normalized.startswith("^"):
        version = normalized[1:]
        return f">={version},<{_caret_upper_bound(version)}"
    if normalized.startswith((">", "<", "=", "!", "~")):
        return normalized
    # A plain Poetry version means an exact version for this narrow deployment
    # projector. Current Core dependencies use caret/comparator constraints, but
    # supporting an exact version costs nothing and avoids surprising output.
    return f"=={normalized}"


def _caret_upper_bound(version: str) -> str:
    parts = version.split(".")
    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"Unsupported caret version: {version!r}") from exc
    if not numbers:
        raise ValueError(f"Unsupported caret version: {version!r}")

    while len(numbers) < 3:
        numbers.append(0)

    major, minor, patch = numbers[:3]
    if major > 0:
        return f"{major + 1}.0.0"
    if minor > 0:
        return f"0.{minor + 1}.0"
    return f"0.0.{patch + 1}"


def dependency_names(requirements: tuple[str, ...]) -> frozenset[str]:
    """Return normalized package names from this module's rendered requirement shape."""

    names: set[str] = set()
    for requirement in requirements:
        boundary = len(requirement)
        for token in (">", "<", "=", "!", "~"):
            position = requirement.find(token)
            if position >= 0:
                boundary = min(boundary, position)
        names.add(requirement[:boundary].strip().lower().replace("_", "-"))
    return frozenset(names)


__all__ = [
    "VECTOR_ONLY_DEPENDENCIES",
    "dependency_names",
    "render_research_runtime_requirements",
    "research_runtime_requirements",
]
