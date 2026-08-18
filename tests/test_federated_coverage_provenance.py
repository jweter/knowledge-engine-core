from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedSearchResult,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger

_RUN_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_CREATED_AT = datetime(2026, 8, 18, 14, 30, tzinfo=UTC)


def test_coverage_report_carries_search_method_provenance(tmp_path: Path) -> None:
    ledger = FederatedSearchLedger(
        tmp_path,
        clock=lambda: _CREATED_AT,
        id_factory=lambda: _RUN_ID,
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(
            text="  obesity   treatment  ",
            year_from=2019,
            year_to=2026,
            limit_per_provider=17,
        ),
        provider_statuses=(
            ProviderStatus(
                provider="PubMed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=3,
            ),
        ),
    )

    record = ledger.record(result, initiated_by="automation")
    report = ledger.coverage_report(record.search_run_id)

    assert report.search_run_id == str(_RUN_ID)
    assert report.created_at == "2026-08-18T14:30:00+00:00"
    assert report.query_text == "obesity treatment"
    assert report.year_from == 2019
    assert report.year_to == 2026
    assert report.limit_per_provider == 17
    assert report.completeness == "complete"
    assert report.providers_requested == ("pubmed",)
    assert report.providers_completed == ("pubmed",)

    # Coverage is a public provenance view, not the full internal run context.
    assert not hasattr(report, "initiated_by")
    assert not hasattr(report, "project_id")
    assert not hasattr(report, "research_question_id")
