from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.quality_preflight import QualityGate, fix_gates, quality_gates, run_preflight


def test_fix_gates_apply_safe_ruff_changes_in_stable_order() -> None:
    gates = fix_gates("python-test")

    assert [gate.name for gate in gates] == [
        "format_fix",
        "lint_fix",
        "format_after_lint_fix",
    ]
    assert gates[0].args == ("python-test", "-m", "ruff", "format", ".")
    assert gates[1].args == ("python-test", "-m", "ruff", "check", "--fix", ".")
    assert gates[2].args == ("python-test", "-m", "ruff", "format", ".")


def test_quality_gates_match_ci_order() -> None:
    gates = quality_gates("python-test")

    assert [gate.name for gate in gates] == [
        "format",
        "lint",
        "typing",
        "tests",
        "diff_hygiene",
    ]
    assert gates[0].args == ("python-test", "-m", "ruff", "format", "--check", ".")
    assert gates[1].args == ("python-test", "-m", "ruff", "check", ".")
    assert gates[2].args == ("python-test", "-m", "mypy", "knowledge_engine", "tests")
    assert gates[3].args == ("python-test", "-m", "pytest")
    assert gates[4].args == ("git", "diff", "--check")


def test_preflight_stops_at_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    gates = (
        QualityGate("format", ("format-command",)),
        QualityGate("lint", ("lint-command",)),
        QualityGate("typing", ("typing-command",)),
    )

    def fake_run(args: tuple[str, ...], *, check: bool) -> SimpleNamespace:
        assert check is False
        calls.append(args)
        return SimpleNamespace(returncode=7 if args == ("lint-command",) else 0)

    monkeypatch.setattr("scripts.quality_preflight.subprocess.run", fake_run)

    assert run_preflight(gates) == 7
    assert calls == [("format-command",), ("lint-command",)]


def test_preflight_runs_all_gates_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    gates = (
        QualityGate("format", ("format-command",)),
        QualityGate("lint", ("lint-command",)),
    )

    def fake_run(args: tuple[str, ...], *, check: bool) -> SimpleNamespace:
        assert check is False
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("scripts.quality_preflight.subprocess.run", fake_run)

    assert run_preflight(gates) == 0
    assert calls == [("format-command",), ("lint-command",)]


def test_fix_mode_runs_fixes_before_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    fixes = (
        QualityGate("format_fix", ("format-fix",)),
        QualityGate("lint_fix", ("lint-fix",)),
    )
    gates = (
        QualityGate("format", ("format-check",)),
        QualityGate("lint", ("lint-check",)),
    )

    def fake_run(args: tuple[str, ...], *, check: bool) -> SimpleNamespace:
        assert check is False
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("scripts.quality_preflight.subprocess.run", fake_run)

    assert run_preflight(gates, apply_fixes=True, fixes=fixes) == 0
    assert calls == [
        ("format-fix",),
        ("lint-fix",),
        ("format-check",),
        ("lint-check",),
    ]


def test_fix_failure_prevents_check_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    fixes = (
        QualityGate("format_fix", ("format-fix",)),
        QualityGate("lint_fix", ("lint-fix",)),
    )
    gates = (QualityGate("format", ("format-check",)),)

    def fake_run(args: tuple[str, ...], *, check: bool) -> SimpleNamespace:
        assert check is False
        calls.append(args)
        return SimpleNamespace(returncode=3 if args == ("lint-fix",) else 0)

    monkeypatch.setattr("scripts.quality_preflight.subprocess.run", fake_run)

    assert run_preflight(gates, apply_fixes=True, fixes=fixes) == 3
    assert calls == [("format-fix",), ("lint-fix",)]
