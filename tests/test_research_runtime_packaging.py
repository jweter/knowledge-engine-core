from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_engine.research_runtime_packaging import (
    VECTOR_ONLY_DEPENDENCIES,
    _caret_upper_bound,
    dependency_names,
    render_research_runtime_requirements,
    research_runtime_requirements,
)


def _pyproject() -> Path:
    return Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_research_runtime_projection_excludes_only_vector_stack() -> None:
    requirements = research_runtime_requirements(_pyproject())
    names = dependency_names(requirements)

    assert names == frozenset(
        {
            "click",
            "cryptography",
            "h2",
            "pydantic",
            "pydantic-settings",
            "pymupdf",
            "rich",
            "sqlalchemy",
            "typer",
        }
    )
    assert names.isdisjoint(VECTOR_ONLY_DEPENDENCIES)


def test_research_runtime_projection_translates_current_poetry_constraints() -> None:
    requirements = research_runtime_requirements(_pyproject())

    assert "pydantic>=2.8.0,<3.0.0" in requirements
    assert "pymupdf>=1.24.7,<2.0.0" in requirements
    assert "rich>=13.7.1,<16.0.0" in requirements
    assert "click>=8.0,<8.6" in requirements
    assert "cryptography>=50.0.0,<51.0.0" in requirements


def test_rendered_requirements_are_deterministic_and_explain_exclusions() -> None:
    first = render_research_runtime_requirements(_pyproject())
    second = render_research_runtime_requirements(_pyproject())

    assert first == second
    assert "Phase-3/vector-only dependencies are intentionally excluded." in first
    assert "torch" not in first
    assert "sentence-transformers" not in first
    assert first.endswith("\n")


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2.8.0", "3.0.0"),
        ("0.8.1", "0.9.0"),
        ("0.0.7", "0.0.8"),
    ],
)
def test_caret_upper_bound_matches_poetry_compatibility_rules(version: str, expected: str) -> None:
    assert _caret_upper_bound(version) == expected
