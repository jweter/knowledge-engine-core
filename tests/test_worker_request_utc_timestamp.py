"""WorkerRequest.created_at_utc must be an ISO-8601 UTC timestamp (Codex finding, PR #495)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from knowledge_engine.unattended_verification_contract import WorkerRequest


def _request(created_at_utc: str) -> WorkerRequest:
    return WorkerRequest(
        repository="jweter/knowledge-engine-core",
        branch="main",
        exact_sha="a" * 40,
        request_id="request-1",
        requested_checks=("core-preflight",),
        environment_id="windows-worker-1",
        created_at_utc=created_at_utc,
    )


@pytest.mark.parametrize(
    "value",
    ["2026-09-13T12:00:00Z", "2026-09-13T12:00:00+00:00", "2026-09-13T12:00:00.123456+00:00"],
)
def test_utc_timestamps_are_accepted_unchanged(value: str) -> None:
    assert _request(value).created_at_utc == value


@pytest.mark.parametrize(
    "value",
    ["not-a-date", "2026-09-13T12:00:00", "2026-09-13T07:00:00-05:00", "2026-13-40T12:00:00Z", " "],
)
def test_malformed_naive_or_non_utc_timestamps_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _request(value)
