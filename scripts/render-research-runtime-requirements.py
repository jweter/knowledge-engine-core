#!/usr/bin/env python3
"""Print the lean hosted Research runtime requirements to stdout."""

from __future__ import annotations

import argparse
from pathlib import Path

from knowledge_engine.research_runtime_packaging import render_research_runtime_requirements


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render non-vector Knowledge Engine dependencies for a lean ke-research deployment."
        )
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to Core's pyproject.toml (default: ./pyproject.toml).",
    )
    args = parser.parse_args()
    print(render_research_runtime_requirements(args.pyproject), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
