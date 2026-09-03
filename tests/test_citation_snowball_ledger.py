from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.citation_snowball import CitationSnowballPlan, CitationSnowballResult
from knowledge_engine.citation_snowball_ledger import CitationSnowballLedger
from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    FederatedCandidate,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)

_RUN_ID = UUID("00000000-0000-0000-0000-000000000707")


def _candidate(provider_id: str) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"openalex:{provider_id}",
        title=f"Paper {provider_id}",
        observations=(
            ProviderObservation(
                provider="openalex",
                provider_id=provider_id,
                title=f"Paper {provider_id}",
                openalex_id=provider_id,
            ),
        ),
    )


def _result() -> CitationSnowballResult:
    query = CitationTraversalQuery(
        seed_identifier="W1",
        direction=CitationDirection.REFERENCES,
        limit=2,
    )
    traversal = CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="openalex",
            outcome=ProviderOutcome.SUCCESS,
            attempted=True,
            result_count=1,
        ),
        candidates=(_candidate("W2"),),
        edges=(
            CitationEdge(
                provider="openalex",
                seed_identifier="W1",
                related_provider_id="W2",
                direction=CitationDirection.REFERENCES,
                retrieved_at="2026-08-16T18:00:00+00:00",
            ),
        ),
    )
    return CitationSnowballResult(
        provider="openalex",
        plan=CitationSnowballPlan(
            seed_identifiers=("W1",),
            directions=(CitationDirection.REFERENCES,),
            max_depth=2,
            limit_per_traversal=2,
            max_candidates=10,
        ),
        traversals=(traversal,),
        candidates=(_candidate("W2"),),
        edges=traversal.edges,
        truncated=False,
    )


def test_ledger_round_trip_preserves_replay_and_provenance_facts(tmp_path: Path) -> None:
    ledger = CitationSnowballLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 18, 30, tzinfo=UTC),
        id_factory=lambda: _RUN_ID,
    )

    recorded = ledger.record(_result())
    loaded = ledger.load(str(_RUN_ID))

    assert loaded == recorded
    assert loaded.seed_identifiers == ("W1",)
    assert loaded.directions == ("references",)
    assert loaded.max_depth == 2
    assert loaded.limit_per_traversal == 2
    assert loaded.max_candidates == 10
    assert loaded.completeness == "complete"
    assert loaded.candidate_ids == ("openalex:W2",)
    assert loaded.traversals[0].outcome == "success"
    assert loaded.edges[0].related_provider_id == "W2"


def _result_with_retry(
    *, retry_attempt_count: int, rate_limited_observed: bool
) -> CitationSnowballResult:
    query = CitationTraversalQuery(
        seed_identifier="W1",
        direction=CitationDirection.REFERENCES,
        limit=2,
    )
    traversal = CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="semantic_scholar",
            outcome=ProviderOutcome.SUCCESS,
            attempted=True,
            result_count=1,
            retry_attempt_count=retry_attempt_count,
            rate_limited_observed=rate_limited_observed,
        ),
        candidates=(_candidate("W2"),),
        edges=(
            CitationEdge(
                provider="semantic_scholar",
                seed_identifier="W1",
                related_provider_id="W2",
                direction=CitationDirection.REFERENCES,
                retrieved_at="2026-08-16T18:00:00+00:00",
            ),
        ),
    )
    return CitationSnowballResult(
        provider="semantic_scholar",
        plan=CitationSnowballPlan(
            seed_identifiers=("W1",),
            directions=(CitationDirection.REFERENCES,),
            max_depth=2,
            limit_per_traversal=2,
            max_candidates=10,
        ),
        traversals=(traversal,),
        candidates=(_candidate("W2"),),
        edges=traversal.edges,
        truncated=False,
    )


def test_record_preserves_retry_and_rate_limit_facts_from_provider_status(
    tmp_path: Path,
) -> None:
    """A citation-snowball run that retried past a 429 must remain
    distinguishable from a clean first-attempt success once persisted --
    `CitationTraversalRecord` must carry `retry_attempt_count`/
    `rate_limited_observed`, not silently discard them (issue #433 item 2,
    Codex review finding 2)."""

    ledger = CitationSnowballLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 18, 30, tzinfo=UTC),
        id_factory=lambda: _RUN_ID,
    )

    recorded = ledger.record(_result_with_retry(retry_attempt_count=2, rate_limited_observed=True))

    assert recorded.traversals[0].retry_attempt_count == 2
    assert recorded.traversals[0].rate_limited_observed is True

    loaded = ledger.load(str(_RUN_ID))
    assert loaded.traversals[0].retry_attempt_count == 2
    assert loaded.traversals[0].rate_limited_observed is True

    payload = json.loads((tmp_path / f"{_RUN_ID}.json").read_text(encoding="utf-8"))
    assert payload["traversals"][0]["retry_attempt_count"] == 2
    assert payload["traversals"][0]["rate_limited_observed"] is True


def test_load_defaults_retry_fields_to_no_retry_state_for_pre_existing_records(
    tmp_path: Path,
) -> None:
    ledger = CitationSnowballLedger(tmp_path)
    path = tmp_path / f"{_RUN_ID}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "snowball_run_id": str(_RUN_ID),
                "created_at": "2026-08-16T18:30:00+00:00",
                "provider": "openalex",
                "seed_identifiers": ["W1"],
                "directions": ["references"],
                "max_depth": 2,
                "limit_per_traversal": 2,
                "max_candidates": 10,
                "completeness": "complete",
                "truncated": False,
                "candidate_ids": ["openalex:W2"],
                "traversals": [
                    {
                        "seed_identifier": "W1",
                        "direction": "references",
                        "outcome": "success",
                        "attempted": True,
                        "result_count": 1,
                        "reason": None,
                        # deliberately no "retry_attempt_count"/
                        # "rate_limited_observed" keys -- pre-existing shape
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = ledger.load(str(_RUN_ID))

    assert loaded.traversals[0].retry_attempt_count == 0
    assert loaded.traversals[0].rate_limited_observed is False


def test_load_derives_rate_limited_observed_for_pre_existing_rate_limited_traversals(
    tmp_path: Path,
) -> None:
    """The backward-compatible-loading counterpart to the previous test: a
    pre-existing traversal whose own outcome is already "rate_limited" must
    not load as rate_limited_observed=False merely because that field
    postdates the record (issue #433 item 2, Codex review finding 4's
    citation-snowball-ledger counterpart)."""

    ledger = CitationSnowballLedger(tmp_path)
    path = tmp_path / f"{_RUN_ID}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "snowball_run_id": str(_RUN_ID),
                "created_at": "2026-08-16T18:30:00+00:00",
                "provider": "semantic_scholar",
                "seed_identifiers": ["W1"],
                "directions": ["references"],
                "max_depth": 2,
                "limit_per_traversal": 2,
                "max_candidates": 10,
                "completeness": "failed",
                "truncated": False,
                "candidate_ids": [],
                "traversals": [
                    {
                        "seed_identifier": "W1",
                        "direction": "references",
                        "outcome": "rate_limited",
                        "attempted": True,
                        "result_count": 0,
                        "reason": "rate_limited",
                        # deliberately no "rate_limited_observed" key
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = ledger.load(str(_RUN_ID))

    assert loaded.traversals[0].rate_limited_observed is True


def test_ledger_json_excludes_credentials_and_raw_provider_payloads(tmp_path: Path) -> None:
    ledger = CitationSnowballLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 18, 30, tzinfo=UTC),
        id_factory=lambda: _RUN_ID,
    )

    ledger.record(_result())
    payload = json.loads((tmp_path / f"{_RUN_ID}.json").read_text(encoding="utf-8"))

    assert "credentials" not in payload
    assert "headers" not in payload
    assert "raw_response" not in payload
    assert payload["provider"] == "openalex"


def test_ledger_refuses_to_overwrite_existing_run(tmp_path: Path) -> None:
    ledger = CitationSnowballLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 18, 30, tzinfo=UTC),
        id_factory=lambda: _RUN_ID,
    )
    ledger.record(_result())

    with pytest.raises(FileExistsError, match="already exists"):
        ledger.record(_result())


def test_ledger_rejects_naive_clock(tmp_path: Path) -> None:
    ledger = CitationSnowballLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 18, 30),
        id_factory=lambda: _RUN_ID,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.record(_result())


def test_ledger_rejects_tampered_run_identifier(tmp_path: Path) -> None:
    ledger = CitationSnowballLedger(tmp_path)
    path = tmp_path / f"{_RUN_ID}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "snowball_run_id": "00000000-0000-0000-0000-000000000999",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match its filename"):
        ledger.load(str(_RUN_ID))
