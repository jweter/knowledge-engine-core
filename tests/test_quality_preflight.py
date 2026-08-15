from __future__ import annotations

from types import SimpleNamespace

from scripts.quality_preflight import QualityGate, quality_gates, run_preflight


def test_quality_gates_match_ci_order() -> None:
    gates = quality_gates("python-test")

    assert [gate.name for gate in gates] == ["format", "lint", "typing", "tests"]
    assert gates[0].args == ("python-test", "-m", "ruff", "format", "--check", ".")
    assert gates[1].args == ("python-test", "-m", "ruff", "check", ".")
    assert gates[2].args == ("python-test", "-m", "mypy", "knowledge_engine", "tests")
    assert gates[3].args == ("python-test", "-m", "pytest")


def test_preflight_stops_at_first_failure(monkeypatch) -> None:
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


def test_preflight_runs_all_gates_when_clean(monkeypatch) -> None:
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
