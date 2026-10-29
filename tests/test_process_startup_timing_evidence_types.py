import json
from pathlib import Path

import pytest

from knowledge_engine import unattended_worker as worker


def _run_with_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: dict[str, object]
) -> tuple[str, str, str | None]:
    def fake_run_logged(
        args: list[str], *, cwd: Path, log_path: Path, timeout_seconds: float
    ) -> tuple[int, float, bool]:
        evidence_path = Path(args[-1])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        return 0, 0.5, False

    monkeypatch.setattr(worker, "run_logged", fake_run_logged)
    return worker.run_process_startup_timing(tmp_path, tmp_path / "state", 30)


@pytest.mark.parametrize("value", [True, 1.9, "12", -1, None])
@pytest.mark.parametrize("field", ["import_to_command_ms", "database_open_ms"])
def test_coercible_or_negative_timing_values_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    evidence: dict[str, object] = {"import_to_command_ms": 12, "database_open_ms": 3}
    evidence[field] = value
    status, _summary, failure_class = _run_with_evidence(tmp_path, monkeypatch, evidence)
    assert status == "ENVIRONMENT_FAILURE"
    assert failure_class == "ENVIRONMENT_FAILURE"


def test_zero_millisecond_timings_are_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence: dict[str, object] = {"import_to_command_ms": 0, "database_open_ms": 0}
    status, summary, failure_class = _run_with_evidence(tmp_path, monkeypatch, evidence)
    assert status == "PASS" and failure_class is None
    assert "import_to_command_ms=0" in summary and "database_open_ms=0" in summary
