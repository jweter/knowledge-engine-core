"""Run Knowledge Engine's deterministic local quality gates in CI order.

Use ``--fix`` before pushing Python changes so deterministic Ruff formatting and
safe lint fixes are applied before the check-only CI-equivalent gates run.
GitHub Actions remains the authoritative merge gate.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityGate:
    """One deterministic repository quality gate."""

    name: str
    args: tuple[str, ...]


def fix_gates(python_executable: str = sys.executable) -> tuple[QualityGate, ...]:
    """Return deterministic, safe autofix gates run before CI-equivalent checks."""
    return (
        QualityGate(
            "format_fix",
            (python_executable, "-m", "ruff", "format", "."),
        ),
        QualityGate(
            "lint_fix",
            (python_executable, "-m", "ruff", "check", "--fix", "."),
        ),
        # Ruff lint fixes can change line layout. Normalize formatting one final time
        # before the check-only phase so CI sees the exact repository style.
        QualityGate(
            "format_after_lint_fix",
            (python_executable, "-m", "ruff", "format", "."),
        ),
    )


def quality_gates(python_executable: str = sys.executable) -> tuple[QualityGate, ...]:
    """Return the canonical check-only gate sequence used before PR submission."""
    return (
        QualityGate(
            "format",
            (python_executable, "-m", "ruff", "format", "--check", "."),
        ),
        QualityGate(
            "lint",
            (python_executable, "-m", "ruff", "check", "."),
        ),
        QualityGate(
            "typing",
            (python_executable, "-m", "mypy", "knowledge_engine", "tests"),
        ),
        QualityGate(
            "tests",
            (python_executable, "-m", "pytest"),
        ),
        QualityGate(
            "diff_hygiene",
            ("git", "diff", "--check"),
        ),
    )


def _run_gates(gates: Sequence[QualityGate], *, phase: str) -> int:
    """Run gates in order, stopping at the first non-zero return code."""
    for gate in gates:
        print(f"\n=== quality preflight [{phase}]: {gate.name} ===", flush=True)
        completed = subprocess.run(gate.args, check=False)  # noqa: S603
        if completed.returncode != 0:
            print(
                f"Quality preflight stopped: {gate.name} failed "
                f"with exit code {completed.returncode}.",
                file=sys.stderr,
            )
            return completed.returncode
    return 0


def run_preflight(
    gates: Sequence[QualityGate] | None = None,
    *,
    apply_fixes: bool = False,
    fixes: Sequence[QualityGate] | None = None,
) -> int:
    """Optionally apply safe Ruff fixes, then run the check-only quality gates."""
    if apply_fixes:
        selected_fixes = tuple(fixes) if fixes is not None else fix_gates()
        fix_result = _run_gates(selected_fixes, phase="fix")
        if fix_result != 0:
            return fix_result

    selected = tuple(gates) if gates is not None else quality_gates()
    check_result = _run_gates(selected, phase="check")
    if check_result != 0:
        return check_result

    print("\nQuality preflight passed.")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Knowledge Engine's local CI-equivalent quality preflight."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply Ruff formatting and safe lint fixes before running all checks.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entrypoint."""
    args = _parse_args(argv)
    raise SystemExit(run_preflight(apply_fixes=args.fix))


if __name__ == "__main__":
    main()
