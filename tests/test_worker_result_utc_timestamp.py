"""WorkerResult.completed_at_utc must be an ISO-8601 UTC timestamp (Codex finding, PR #495)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from knowledge_engine.unattended_verification_contract import WorkerResult


def _result(completed_at_utc: str) -> WorkerResult:
    return WorkerResult(
        request_id="request-1",
        repository="jweter/knowledge-engine-core",
        exact_sha="a" * 40,
        environment_id="windows-worker-1",
        status="PASS",
        completed_at_utc=completed_at_utc,
        summary="ok",
    )


@pytest.mark.parametrize(
    "value", ["2026-09-13T12:03:00Z", "2026-09-16T12:00:00+00:00", "2026-09-16T12:00:00.5+00:00"]
)
def test_utc_timestamps_are_accepted_unchanged(value: str) -> None:
    assert _result(value).completed_at_utc == value


@pytest.mark.parametrize(
    "value",
    ["not-a-date", "2026-09-13T12:03:00", "2026-09-13T14:03:00+02:00", "2026-02-30T12:00:00Z", " "],
)
def test_malformed_naive_or_non_utc_timestamps_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        _result(value)
