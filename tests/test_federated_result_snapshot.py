from __future__ import annotations

from dataclasses import replace

import pytest

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_result_snapshot import build_public_federated_result_payload
from knowledge_engine.federated_search_ledger import SearchCoverageReport


def _result() -> FederatedSearchResult:
    observation = ProviderObservation(
        provider="PubMed",
        provider_id="12345",
        title="A protein folding study",
        pmid="12345",
    )
    return FederatedSearchResult(
        query=DiscoveryQuery(
            text="  protein   folding  ",
            year_from=2020,
            year_to=2026,
            limit_per_provider=25,
        ),
        provider_statuses=(
            ProviderStatus(
                provider="PubMed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
        candidates=(
            FederatedCandidate(
                canonical_id="pubmed:12345",
                title=observation.title,
                observations=(observation,),
            ),
        ),
    )


def _result_with_title_disagreement() -> FederatedSearchResult:
    result = _result()
    candidate = result.candidates[0]
    second_observation = ProviderObservation(
        provider="OpenAlex",
        provider_id="W123",
        title="A different protein folding study",
    )
    return replace(
        result,
        candidates=(
            replace(
                candidate,
                observations=candidate.observations + (second_observation,),
            ),
        ),
    )


def _coverage() -> SearchCoverageReport:
    return SearchCoverageReport(
        search_run_id="11111111-2222-3333-4444-555555555555",
        created_at="2026-08-18T16:00:00+00:00",
        query_text="protein folding",
        year_from=2020,
        year_to=2026,
        limit_per_provider=25,
        completeness="complete",
        raw_observation_count=1,
        total_retry_attempts=0,
        candidate_count=1,
        providers_requested=("pubmed",),
        providers_attempted=("pubmed",),
        providers_completed=("pubmed",),
        providers_failed=(),
        providers_rate_limited=(),
    )


def _mismatched_coverage(field: str) -> SearchCoverageReport:
    coverage = _coverage()
    if field == "query_text":
        return replace(coverage, query_text="different query")
    if field == "year_from":
        return replace(coverage, year_from=2019)
    if field == "year_to":
        return replace(coverage, year_to=2025)
    if field == "limit_per_provider":
        return replace(coverage, limit_per_provider=10)
    if field == "completeness":
        return replace(coverage, completeness="partial")
    if field == "candidate_count":
        return replace(coverage, candidate_count=0)
    if field == "raw_observation_count":
        return replace(coverage, raw_observation_count=0)
    if field == "total_retry_attempts":
        return replace(coverage, total_retry_attempts=5)
    raise AssertionError(f"Unhandled mismatch field: {field}")


def test_public_snapshot_includes_safe_coverage_and_result_contract() -> None:
    payload = build_public_federated_result_payload(_result(), _coverage())

    assert payload["search_run_id"] == "11111111-2222-3333-4444-555555555555"
    assert payload["query"]["text"] == "protein folding"
    assert payload["completeness"] == "complete"
    assert payload["candidates"][0]["title"] == "A protein folding study"
    assert payload["coverage"] == {
        "search_run_id": "11111111-2222-3333-4444-555555555555",
        "created_at": "2026-08-18T16:00:00+00:00",
        "query_text": "protein folding",
        "year_from": 2020,
        "year_to": 2026,
        "limit_per_provider": 25,
        "completeness": "complete",
        "raw_observation_count": 1,
        "total_retry_attempts": 0,
        "candidate_count": 1,
        "providers_requested": ["pubmed"],
        "providers_attempted": ["pubmed"],
        "providers_completed": ["pubmed"],
        "providers_failed": [],
        "providers_rate_limited": [],
    }
    assert payload["provider_disagreements"] == {
        "candidates": (),
        "disagreement_count": 0,
    }
    assert "initiated_by" not in payload["coverage"]
    assert "project_id" not in payload["coverage"]
    assert "research_question_id" not in payload["coverage"]


def test_public_snapshot_exposes_provider_disagreement_without_picking_a_winner() -> None:
    payload = build_public_federated_result_payload(_result_with_title_disagreement(), _coverage())

    assert payload["provider_disagreements"] == {
        "candidates": (
            {
                "canonical_id": "pubmed:12345",
                "disagreements": (
                    {
                        "field": "title",
                        "assertions": (
                            {
                                "provider": "pubmed",
                                "provider_id": "12345",
                                "value": "A protein folding study",
                            },
                            {
                                "provider": "openalex",
                                "provider_id": "W123",
                                "value": "A different protein folding study",
                            },
                        ),
                    },
                ),
            },
        ),
        "disagreement_count": 1,
    }


@pytest.mark.parametrize(
    "field",
    [
        "query_text",
        "year_from",
        "year_to",
        "limit_per_provider",
        "completeness",
        "raw_observation_count",
        "total_retry_attempts",
        "candidate_count",
    ],
)
def test_public_snapshot_rejects_mismatched_provenance(field: str) -> None:
    coverage = _mismatched_coverage(field)

    with pytest.raises(ValueError, match=field):
        build_public_federated_result_payload(_result(), coverage)
