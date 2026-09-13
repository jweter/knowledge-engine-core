from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from knowledge_engine import unattended_worker as worker
from knowledge_engine.unattended_verification_contract import WorkerRequest


def request(**overrides: object) -> WorkerRequest:
    payload: dict[str, object] = {
        "request_id": "req-1",
        "repository": worker.REPOSITORY,
        "branch": "main",
        "exact_sha": "a" * 40,
        "requested_checks": ("preflight",),
        "environment_id": "jeremy-laptop",
        "created_at_utc": "2026-09-13T23:30:00Z",
    }
    payload.update(overrides)
    return WorkerRequest.model_validate(payload)


def test_runtime_consumes_authoritative_worker_request_contract(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    expected = request(requested_checks=("preflight", "ollama_health"))
    path.write_text(expected.model_dump_json(), encoding="utf-8")

    loaded = worker.load_request(path)

    assert isinstance(loaded, WorkerRequest)
    assert loaded == expected
    assert not hasattr(worker, "VerificationRequest")
    assert not hasattr(worker, "VerificationResult")


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


def test_acquire_lock_reclaims_stale_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_validate_checkout_fails_closed_on_wrong_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    values = iter(["https://github.com/jweter/knowledge-engine-core.git", "b" * 40])
    monkeypatch.setattr(worker, "git_output", lambda *args, **kwargs: next(values))

    with pytest.raises(RuntimeError, match="Checkout identity mismatch"):
        worker.validate_checkout(tmp_path, request(), environment_id="jeremy-laptop")


def test_validate_checkout_fails_closed_on_wrong_environment(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="worker environment mismatch"):
        worker.validate_checkout(tmp_path, request(), environment_id="different-laptop")


def test_unsupported_check_returns_review_required_without_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "validate_checkout", lambda *args, **kwargs: None)

    result = worker.execute_request(
        request(requested_checks=("shell",)),
        repo_root=tmp_path,
        state_dir=tmp_path / "state",
        environment_id="jeremy-laptop",
        timeout_seconds=30,
    )

    assert result.status == "REVIEW_REQUIRED"
    assert result.failure_class == "POLICY_FAILURE"
    assert result.matches_request(request(requested_checks=("shell",)))


def test_ollama_health_unavailable_is_environment_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise OSError("offline")

    monkeypatch.setattr(worker.urllib.request, "urlopen", fail)
    status, summary, failure_class = worker.run_ollama_health(1)
    assert status == "ENVIRONMENT_FAILURE"
    assert failure_class == "ENVIRONMENT_FAILURE"
    assert "unavailable" in summary


def test_write_result_uses_authoritative_result_schema(tmp_path: Path) -> None:
    result = worker.execute_request
    evidence = {
        "request_id": "req-1",
        "repository": worker.REPOSITORY,
        "exact_sha": "a" * 40,
        "environment_id": "jeremy-laptop",
        "status": "PASS",
        "completed_at_utc": "2026-09-13T23:31:00Z",
        "summary": "preflight: passed",
    }
    from knowledge_engine.unattended_verification_contract import WorkerResult

    path = tmp_path / "result.json"
    worker.write_result(path, WorkerResult.model_validate(evidence))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["exact_sha"] == "a" * 40
    assert "commit_sha" not in payload
    assert callable(result)
