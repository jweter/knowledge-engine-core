from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from knowledge_engine import unattended_worker as worker


def request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "request_id": "req-1",
        "repository": "jweter/knowledge-engine-core",
        "branch": "main",
        "commit_sha": "a" * 40,
        "probe": "preflight",
        "timeout_seconds": 30,
    }
    payload.update(overrides)
    return payload


def test_request_rejects_unknown_fields() -> None:
    payload = request_payload(command=["rm", "-rf", "/"])
    with pytest.raises(ValueError, match="Unknown request fields"):
        worker.VerificationRequest.from_mapping(payload)


def test_request_rejects_arbitrary_probe() -> None:
    with pytest.raises(ValueError, match="probe is not authorized"):
        worker.VerificationRequest.from_mapping(request_payload(probe="shell"))


def test_request_requires_exact_commit_sha() -> None:
    with pytest.raises(ValueError, match="exact 40-character Git SHA"):
        worker.VerificationRequest.from_mapping(request_payload(commit_sha="main"))


def test_normalize_origin_accepts_https_and_ssh() -> None:
    assert worker.origin_is_expected("https://github.com/jweter/knowledge-engine-core.git")
    assert worker.origin_is_expected("git@github.com:jweter/knowledge-engine-core.git")
    assert not worker.origin_is_expected("https://github.com/example/other.git")


def test_sanitize_text_removes_paths_and_secret_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.Path, "home", classmethod(lambda cls: Path("/home/example")))
    text = f"{tmp_path}/file token=secret password:abc /home/example/data"
    sanitized = worker.sanitize_text(text, repo_root=tmp_path)
    assert str(tmp_path) not in sanitized
    assert "secret" not in sanitized
    assert "password:abc" not in sanitized
    assert "/home/example" not in sanitized
    assert "<REPO_ROOT>" in sanitized
    assert "<REDACTED>" in sanitized


def test_acquire_lock_reclaims_stale_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / worker.LOCK_NAME
    lock.write_text("99999999", encoding="ascii")
    monkeypatch.setattr(worker, "pid_is_alive", lambda pid: False)
    fd, acquired = worker.acquire_lock(tmp_path)
    assert acquired is True
    assert fd is not None
    try:
        assert int(lock.read_text(encoding="ascii")) == os.getpid()
    finally:
        worker.release_lock(tmp_path, fd)
    assert not lock.exists()


def test_acquire_lock_defers_when_owner_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / worker.LOCK_NAME
    lock.write_text("1234", encoding="ascii")
    monkeypatch.setattr(worker, "pid_is_alive", lambda pid: True)
    fd, acquired = worker.acquire_lock(tmp_path)
    assert acquired is False
    assert fd is None
    assert lock.read_text(encoding="ascii") == "1234"


def test_write_result_is_machine_readable(tmp_path: Path) -> None:
    result = worker.VerificationResult(
        request_id="r",
        repository=worker.REPOSITORY,
        branch="main",
        commit_sha="a" * 40,
        probe="preflight",
        status="PASS",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        duration_seconds=1.0,
        environment={"python": "3.12"},
        verification={"exit_code": 0},
    )
    path = tmp_path / "result.json"
    worker.write_result(path, result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["commit_sha"] == "a" * 40
    assert payload["verification"]["exit_code"] == 0


def test_validate_checkout_fails_closed_on_wrong_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    values = iter(
        [
            "https://github.com/jweter/knowledge-engine-core.git",
            "b" * 40,
        ]
    )
    monkeypatch.setattr(worker, "git_output", lambda *args, **kwargs: next(values))
    request = worker.VerificationRequest.from_mapping(request_payload())
    with pytest.raises(RuntimeError, match="Checkout identity mismatch"):
        worker.validate_checkout(tmp_path, request)


def test_ollama_health_unavailable_is_environment_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise OSError("offline")

    monkeypatch.setattr(worker.urllib.request, "urlopen", fail)
    status, verification, reason = worker.run_ollama_health(1)
    assert status == "ENVIRONMENT_FAILURE"
    assert verification["duration_seconds"] >= 0
    assert "unavailable" in reason
