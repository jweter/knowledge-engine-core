from __future__ import annotations

from pydantic import ValidationError
import pytest

from knowledge_engine.unattended_verification_contract import WorkerRequest, WorkerResult


SHA = "a" * 40


def test_worker_request_binds_exact_identity_and_normalizes_sha() -> None:
    request = WorkerRequest(
        repository="jweter/knowledge-engine-core",
        branch="main",
        exact_sha=SHA.upper(),
        request_id="request-1",
        requested_checks=("core-preflight", "ollama-health"),
        environment_id="windows-worker-1",
        created_at_utc="2026-09-13T12:00:00Z",
    )

    assert request.exact_sha == SHA
    assert request.requested_checks == ("core-preflight", "ollama-health")


def test_worker_request_rejects_partial_sha_and_duplicate_checks() -> None:
    with pytest.raises(ValidationError):
        WorkerRequest(
            repository="jweter/knowledge-engine-core",
            branch="main",
            exact_sha="abc123",
            request_id="request-1",
            requested_checks=("core-preflight",),
            environment_id="windows-worker-1",
            created_at_utc="2026-09-13T12:00:00Z",
        )

    with pytest.raises(ValidationError):
        WorkerRequest(
            repository="jweter/knowledge-engine-core",
            branch="main",
            exact_sha=SHA,
            request_id="request-1",
            requested_checks=("core-preflight", "core-preflight"),
            environment_id="windows-worker-1",
            created_at_utc="2026-09-13T12:00:00Z",
        )


def test_worker_result_matches_only_exact_request_identity() -> None:
    request = WorkerRequest(
        repository="jweter/knowledge-engine-core",
        branch="main",
        exact_sha=SHA,
        request_id="request-1",
        requested_checks=("core-preflight",),
        environment_id="windows-worker-1",
        created_at_utc="2026-09-13T12:00:00Z",
    )
    result = WorkerResult(
        request_id="request-1",
        repository="jweter/knowledge-engine-core",
        exact_sha=SHA,
        environment_id="windows-worker-1",
        status="PASS",
        completed_at_utc="2026-09-13T12:03:00Z",
        summary="Core preflight passed on the requested exact head.",
    )

    assert result.matches_request(request)
    assert not result.model_copy(update={"exact_sha": "b" * 40}).matches_request(request)


def test_worker_result_is_fail_closed_to_declared_statuses() -> None:
    with pytest.raises(ValidationError):
        WorkerResult(
            request_id="request-1",
            repository="jweter/knowledge-engine-core",
            exact_sha=SHA,
            environment_id="windows-worker-1",
            status="UNKNOWN",  # type: ignore[arg-type]
            completed_at_utc="2026-09-13T12:03:00Z",
            summary="Unclassified result.",
        )
