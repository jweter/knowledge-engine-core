from __future__ import annotations

import json

import pytest

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
    SearchCompleteness,
)


def _observation(provider: str = "PubMed", provider_id: str = "123") -> ProviderObservation:
    return ProviderObservation(
        provider=provider,
        provider_id=provider_id,
        title="A real paper",
        doi="10.1000/example",
        publication_year=2026,
        citation_count=4,
        retrieved_at="2026-08-15T12:00:00Z",
    )


def test_discovery_query_normalizes_whitespace_without_mutating_input() -> None:
    query = DiscoveryQuery("  semaglutide   body weight  ", year_from=2020, year_to=2026)

    assert query.text == "  semaglutide   body weight  "
    assert query.normalized_text == "semaglutide body weight"


def test_discovery_query_rejects_invalid_year_range() -> None:
    with pytest.raises(ValueError, match="year_from must not be after year_to"):
        DiscoveryQuery("x", year_from=2026, year_to=2020)


def test_provider_observation_preserves_provider_native_identity() -> None:
    observation = ProviderObservation(
        provider="Semantic Scholar",
        provider_id="S2-abc",
        title="Paper",
        semantic_scholar_id="S2-abc",
        doi="10.1000/abc",
    )

    assert observation.provider_id == "S2-abc"
    assert observation.semantic_scholar_id == "S2-abc"
    assert observation.normalized_provider == "semantic_scholar"


def test_preprint_version_requires_explicit_preprint_status() -> None:
    with pytest.raises(ValueError, match="requires preprint=true"):
        ProviderObservation(
            provider="arxiv",
            provider_id="2408.12345v2",
            title="Paper",
            arxiv_id="2408.12345",
            preprint_version=2,
        )


def test_preprint_version_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ProviderObservation(
            provider="arxiv",
            provider_id="2408.12345",
            title="Paper",
            arxiv_id="2408.12345",
            preprint=True,
            preprint_version=0,
        )


def test_related_journal_version_metadata_requires_explicit_preprint_status() -> None:
    with pytest.raises(ValueError, match="requires preprint=true"):
        ProviderObservation(
            provider="arxiv",
            provider_id="2408.12345v1",
            title="Paper",
            arxiv_id="2408.12345",
            related_journal_doi="10.1000/journal",
        )


def test_provider_observation_publication_status_flags_default_unreported() -> None:
    observation = _observation()

    assert observation.retracted is None
    assert observation.corrected is None
    assert observation.expression_of_concern is None
    assert observation.withdrawn is None


def test_provider_observation_publication_status_flags_are_independent() -> None:
    observation = ProviderObservation(
        provider="crossref",
        provider_id="10.1000/example",
        title="Paper",
        doi="10.1000/example",
        corrected=True,
        expression_of_concern=True,
        withdrawn=False,
        retracted=False,
    )

    assert observation.corrected is True
    assert observation.expression_of_concern is True
    assert observation.withdrawn is False
    assert observation.retracted is False


def test_federated_candidate_preserves_multiple_provider_observations() -> None:
    candidate = FederatedCandidate(
        canonical_id="candidate-1",
        title="A real paper",
        doi="10.1000/example",
        observations=(
            _observation("PubMed", "pmid-1"),
            _observation("OpenAlex", "W123"),
        ),
    )

    assert candidate.providers == ("pubmed", "openalex")
    assert [observation.provider_id for observation in candidate.observations] == [
        "pmid-1",
        "W123",
    ]


def test_provider_status_rejects_ambiguous_skipped_attempt() -> None:
    with pytest.raises(ValueError, match="must not be marked attempted"):
        ProviderStatus(
            provider="arxiv",
            outcome=ProviderOutcome.SKIPPED,
            attempted=True,
            reason="not relevant",
        )


def test_provider_status_rejects_retry_count_on_unattempted_provider() -> None:
    with pytest.raises(ValueError, match="must not report retries or rate-limit"):
        ProviderStatus(
            provider="arxiv",
            outcome=ProviderOutcome.SKIPPED,
            attempted=False,
            reason="not relevant",
            retry_attempt_count=1,
        )


def test_provider_status_rejects_rate_limit_flag_on_unattempted_provider() -> None:
    with pytest.raises(ValueError, match="must not report retries or rate-limit"):
        ProviderStatus(
            provider="arxiv",
            outcome=ProviderOutcome.SKIPPED,
            attempted=False,
            reason="not relevant",
            rate_limited_observed=True,
        )


def test_provider_status_rejects_negative_retry_attempt_count() -> None:
    with pytest.raises(ValueError, match="retry_attempt_count must not be negative"):
        ProviderStatus(
            provider="pubmed",
            outcome=ProviderOutcome.SUCCESS,
            attempted=True,
            result_count=1,
            retry_attempt_count=-1,
        )


def test_provider_status_defaults_retry_fields_to_no_retry_state() -> None:
    status = ProviderStatus(
        provider="pubmed", outcome=ProviderOutcome.SUCCESS, attempted=True, result_count=1
    )

    assert status.retry_attempt_count == 0
    assert status.rate_limited_observed is False


def test_complete_search_allows_success_and_empty_providers() -> None:
    result = FederatedSearchResult(
        query=DiscoveryQuery("query"),
        provider_statuses=(
            ProviderStatus("pubmed", ProviderOutcome.SUCCESS, True, result_count=2),
            ProviderStatus("crossref", ProviderOutcome.EMPTY, True),
        ),
    )

    assert result.completeness is SearchCompleteness.COMPLETE
    assert result.failed_providers == ()


def test_partial_search_is_a_normal_result_not_an_exception() -> None:
    result = FederatedSearchResult(
        query=DiscoveryQuery("query"),
        provider_statuses=(
            ProviderStatus("pubmed", ProviderOutcome.SUCCESS, True, result_count=2),
            ProviderStatus(
                "semantic_scholar",
                ProviderOutcome.RATE_LIMITED,
                True,
                reason="shared pool exhausted",
            ),
        ),
        candidates=(
            FederatedCandidate(
                canonical_id="candidate-1",
                title="A real paper",
                observations=(_observation(),),
            ),
        ),
    )

    assert result.completeness is SearchCompleteness.PARTIAL
    assert result.failed_providers == ("semantic_scholar",)


def test_failed_search_requires_no_successful_attempt() -> None:
    result = FederatedSearchResult(
        query=DiscoveryQuery("query"),
        provider_statuses=(
            ProviderStatus(
                "pubmed",
                ProviderOutcome.UNAVAILABLE,
                True,
                reason="timeout",
            ),
            ProviderStatus(
                "crossref",
                ProviderOutcome.FAILED,
                True,
                reason="malformed response",
            ),
        ),
    )

    assert result.completeness is SearchCompleteness.FAILED


def test_disabled_only_search_is_failed_without_pretending_it_was_attempted() -> None:
    result = FederatedSearchResult(
        query=DiscoveryQuery("query"),
        provider_statuses=(
            ProviderStatus(
                "semantic_scholar",
                ProviderOutcome.DISABLED,
                False,
                reason="operator disabled",
            ),
        ),
    )

    assert result.completeness is SearchCompleteness.FAILED
    assert result.failed_providers == ()


def test_duplicate_provider_status_is_rejected() -> None:
    with pytest.raises(ValueError, match="each provider at most once"):
        FederatedSearchResult(
            query=DiscoveryQuery("query"),
            provider_statuses=(
                ProviderStatus("PubMed", ProviderOutcome.EMPTY, True),
                ProviderStatus("pubmed", ProviderOutcome.EMPTY, True),
            ),
        )


def test_json_exposes_completeness_and_failure_without_erasing_candidates() -> None:
    result = FederatedSearchResult(
        query=DiscoveryQuery("  cancer   immunotherapy  "),
        provider_statuses=(
            ProviderStatus("pubmed", ProviderOutcome.SUCCESS, True, result_count=1),
            ProviderStatus(
                "openalex",
                ProviderOutcome.UNAVAILABLE,
                True,
                reason="provider unavailable",
            ),
        ),
        candidates=(
            FederatedCandidate(
                canonical_id="candidate-1",
                title="A real paper",
                observations=(_observation(),),
            ),
        ),
    )

    payload = json.loads(result.to_json())

    assert payload["query"]["text"] == "cancer immunotherapy"
    assert payload["completeness"] == "partial"
    assert payload["failed_providers"] == ["openalex"]
    assert payload["candidates"][0]["observations"][0]["provider_id"] == "123"
