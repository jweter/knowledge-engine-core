from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.discovery_broker import FederatedDiscoveryBroker
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
    SearchCompleteness,
)
from knowledge_engine.federated_discovery_service import FederatedDiscoveryService
from knowledge_engine.federated_search_ledger import FederatedSearchLedger


@dataclass(frozen=True)
class FakeProvider:
    name: str
    outcome: ProviderOutcome
    candidate: FederatedCandidate | None = None
    error: Exception | None = None

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        if self.error is not None:
            raise self.error
        candidates = () if self.candidate is None else (self.candidate,)
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider=self.name,
                    outcome=self.outcome,
                    attempted=True,
                    result_count=len(candidates),
                ),
            ),
            candidates=candidates,
        )


def _candidate() -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id="openalex:W1",
        title="Reproducible discovery",
        observations=(
            ProviderObservation(
                provider="openalex",
                provider_id="W1",
                title="Reproducible discovery",
            ),
        ),
    )


def _ledger(root: Path) -> FederatedSearchLedger:
    return FederatedSearchLedger(
        root,
        clock=lambda: datetime(2026, 8, 16, 3, 0, tzinfo=UTC),
        id_factory=lambda: UUID("11111111-1111-4111-8111-111111111111"),
    )


def test_service_returns_result_only_after_persisting_coverage(tmp_path: Path) -> None:
    query = DiscoveryQuery(text="  reproducible discovery  ", year_from=2020, year_to=2026)
    service = FederatedDiscoveryService(
        FederatedDiscoveryBroker(
            (FakeProvider("openalex", ProviderOutcome.SUCCESS, candidate=_candidate()),)
        ),
        _ledger(tmp_path),
    )

    execution = service.search(
        query,
        initiated_by=" core-test ",
        project_id=" project-1 ",
        research_question_id=" rq-1 ",
    )

    assert execution.result.completeness is SearchCompleteness.COMPLETE
    assert execution.record.search_run_id == "11111111-1111-4111-8111-111111111111"
    assert execution.record.query_text == query.normalized_text
    assert execution.record.initiated_by == "core-test"
    assert execution.record.project_id == "project-1"
    assert execution.record.research_question_id == "rq-1"
    assert execution.coverage.providers_completed == ("openalex",)
    assert (tmp_path / f"{execution.record.search_run_id}.json").is_file()


def test_service_persists_degraded_provider_outcome(tmp_path: Path) -> None:
    query = DiscoveryQuery(text="partial coverage")
    service = FederatedDiscoveryService(
        FederatedDiscoveryBroker(
            (
                FakeProvider("openalex", ProviderOutcome.SUCCESS, candidate=_candidate()),
                FakeProvider("crossref", ProviderOutcome.FAILED, error=TimeoutError()),
            )
        ),
        _ledger(tmp_path),
    )

    execution = service.search(query)

    assert execution.result.completeness is SearchCompleteness.PARTIAL
    assert execution.record.completeness == "partial"
    assert execution.coverage.providers_completed == ("openalex",)
    assert execution.coverage.providers_failed == ("crossref",)


def test_service_does_not_hide_persistence_failure(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    query = DiscoveryQuery(text="write once")
    service = FederatedDiscoveryService(
        FederatedDiscoveryBroker((FakeProvider("openalex", ProviderOutcome.EMPTY),)),
        ledger,
    )

    first = service.search(query)
    assert first.record.search_run_id == "11111111-1111-4111-8111-111111111111"

    with pytest.raises(FileExistsError, match="already exists"):
        service.search(query)
