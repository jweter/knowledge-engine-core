from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import (
    LEDGER_SCHEMA_VERSION,
    FederatedSearchLedger,
)

_RUN_ID = UUID("11111111-2222-3333-4444-555555555555")
_CREATED_AT = datetime(2026, 8, 16, 2, 45, tzinfo=UTC)


def _result() -> FederatedSearchResult:
    query = DiscoveryQuery(
        text="  protein   folding  ",
        year_from=2020,
        year_to=2026,
        limit_per_provider=25,
    )
    observation = ProviderObservation(
        provider="PubMed",
        provider_id="12345",
        title="A protein folding study",
        pmid="12345",
        retrieved_at="2026-08-16T02:44:00+00:00",
    )
    candidate = FederatedCandidate(
        canonical_id="pubmed:12345",
        title=observation.title,
        observations=(observation,),
    )
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="PubMed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=120,
            ),
            ProviderStatus(
                provider="OpenAlex",
                outcome=ProviderOutcome.RATE_LIMITED,
                attempted=True,
                latency_ms=80,
                reason="rate_limited",
            ),
            ProviderStatus(
                provider="Crossref",
                outcome=ProviderOutcome.SKIPPED,
                attempted=False,
                reason="unsupported_query",
            ),
        ),
        candidates=(candidate,),
    )


def _ledger(root: Path) -> FederatedSearchLedger:
    return FederatedSearchLedger(
        root,
        clock=lambda: _CREATED_AT,
        id_factory=lambda: _RUN_ID,
    )


def test_record_persists_reproducible_run_and_provider_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "search-runs")

    record = ledger.record(
        _result(),
        initiated_by=" core-test ",
        project_id=" project-7 ",
        research_question_id=" rq-2 ",
    )

    assert record.schema_version == LEDGER_SCHEMA_VERSION
    assert record.search_run_id == str(_RUN_ID)
    assert record.created_at == "2026-08-16T02:45:00+00:00"
    assert record.query_text == "protein folding"
    assert record.year_from == 2020
    assert record.year_to == 2026
    assert record.limit_per_provider == 25
    assert record.completeness == "partial"
    assert record.candidate_count == 1
    assert record.initiated_by == "core-test"
    assert record.project_id == "project-7"
    assert record.research_question_id == "rq-2"
    assert record.providers_requested == ("pubmed", "openalex", "crossref")
    assert record.providers_attempted == ("pubmed", "openalex")
    assert record.providers_completed == ("pubmed",)
    assert record.providers_failed == ("openalex",)

    persisted = json.loads(
        (tmp_path / "search-runs" / f"{_RUN_ID}.json").read_text(encoding="utf-8")
    )
    assert persisted["query_text"] == "protein folding"
    assert persisted["providers"][1] == {
        "attempted": True,
        "latency_ms": 80,
        "outcome": "rate_limited",
        "provider": "openalex",
        "reason": "rate_limited",
        "result_count": 0,
    }
    assert "api_key" not in persisted
    assert "headers" not in persisted


def test_load_round_trips_typed_record(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    recorded = ledger.record(_result())

    loaded = ledger.load(recorded.search_run_id)

    assert loaded == recorded


def test_coverage_report_is_deterministic_and_does_not_guess(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    recorded = ledger.record(_result())

    report = ledger.coverage_report(recorded.search_run_id)

    assert report.search_run_id == str(_RUN_ID)
    assert report.completeness == "partial"
    assert report.candidate_count == 1
    assert report.providers_requested == ("pubmed", "openalex", "crossref")
    assert report.providers_attempted == ("pubmed", "openalex")
    assert report.providers_completed == ("pubmed",)
    assert report.providers_failed == ("openalex",)


def test_record_is_immutable_and_refuses_overwrite(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record(_result())

    with pytest.raises(FileExistsError, match="already exists"):
        ledger.record(_result())


def test_record_rejects_naive_clock(tmp_path: Path) -> None:
    ledger = FederatedSearchLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 2, 45),
        id_factory=lambda: _RUN_ID,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.record(_result())


def test_record_rejects_blank_optional_context(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="must not be blank"):
        ledger.record(_result(), project_id="   ")


def test_load_rejects_path_traversal_as_invalid_uuid(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError):
        ledger.load("../outside")


def test_load_rejects_malformed_or_wrong_schema_record(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    path = root / f"{_RUN_ID}.json"
    path.write_text("not-json", encoding="utf-8")
    ledger = _ledger(root)

    with pytest.raises(ValueError, match="malformed"):
        ledger.load(str(_RUN_ID))

    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "search_run_id": str(_RUN_ID),
                "providers": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema version"):
        ledger.load(str(_RUN_ID))
