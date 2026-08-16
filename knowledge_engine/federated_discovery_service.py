"""Execute federated discovery and durably record coverage in one Core boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from knowledge_engine.discovery_broker import FederatedDiscoveryBroker
from knowledge_engine.federated_discovery import DiscoveryQuery, FederatedSearchResult
from knowledge_engine.federated_search_ledger import SearchCoverageReport, SearchRunRecord


class FederatedSearchRecorder(Protocol):
    """Persistence capability required by recorded federated discovery execution."""

    def record(
        self,
        result: FederatedSearchResult,
        *,
        initiated_by: str | None = None,
        project_id: str | None = None,
        research_question_id: str | None = None,
    ) -> SearchRunRecord:
        """Persist one federated search result and return its immutable run record."""

    def coverage_report(self, search_run_id: str) -> SearchCoverageReport:
        """Return deterministic coverage facts for a persisted run."""


@dataclass(frozen=True)
class FederatedSearchExecution:
    """One broker result paired with its durable run and coverage state."""

    result: FederatedSearchResult
    record: SearchRunRecord
    coverage: SearchCoverageReport


class FederatedDiscoveryService:
    """Guarantee that a runtime federated search is persisted before it is returned."""

    def __init__(
        self,
        broker: FederatedDiscoveryBroker,
        recorder: FederatedSearchRecorder,
    ) -> None:
        self._broker = broker
        self._recorder = recorder

    def search(
        self,
        query: DiscoveryQuery,
        *,
        initiated_by: str | None = None,
        project_id: str | None = None,
        research_question_id: str | None = None,
    ) -> FederatedSearchExecution:
        """Execute, persist, reload coverage, and only then expose the run to callers.

        Persistence failures intentionally propagate. Returning an unrecorded search
        result would violate FRD-6 reproducibility and allow downstream AI/Web layers
        to present coverage that cannot be audited later.
        """

        result = self._broker.search(query)
        record = self._recorder.record(
            result,
            initiated_by=initiated_by,
            project_id=project_id,
            research_question_id=research_question_id,
        )
        coverage = self._recorder.coverage_report(record.search_run_id)
        return FederatedSearchExecution(result=result, record=record, coverage=coverage)
