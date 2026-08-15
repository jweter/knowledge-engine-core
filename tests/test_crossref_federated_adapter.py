from __future__ import annotations

from datetime import UTC, datetime

from knowledge_engine.crossref_federated_adapter import CrossrefFederatedAdapter
from knowledge_engine.federated_discovery import DiscoveryQuery, ProviderOutcome
from knowledge_engine.metadata_enrichment import (
    MetadataCandidate,
    MetadataProviderResult,
    MetadataQuery,
    ProviderDiagnostic,
    normalize_candidate_value,
)

_RETRIEVED_AT = datetime(2026, 8, 15, 23, 0, tzinfo=UTC)


class FakeCrossrefProvider:
    def __init__(self, result: MetadataProviderResult) -> None:
        self.result = result
        self.queries: list[MetadataQuery] = []

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        self.queries.append(query)
        return self.result


def _candidate(
    field: str,
    value: str,
    *,
    queried_identifier: str = "10.1000/example",
    provider: str = "crossref",
    provider_record_id: str | None = "10.1000/example",
    retrieved_at: datetime = _RETRIEVED_AT,
) -> MetadataCandidate:
    return MetadataCandidate(
        provider=provider,
        provider_record_id=provider_record_id,
        queried_identifier=queried_identifier,
        field=field,  # type: ignore[arg-type]
        value=value,
        normalized_value=normalize_candidate_value(field, value),  # type: ignore[arg-type]
        retrieved_at=retrieved_at,
    )


def test_crossref_adapter_maps_exact_doi_metadata_without_losing_provenance() -> None:
    provider = FakeCrossrefProvider(
        MetadataProviderResult(
            candidates=(
                _candidate("doi", "10.1000/example"),
                _candidate("title", "Example Paper"),
                _candidate("journal", "Example Journal"),
                _candidate("publication_year", "2025"),
                _candidate("author", "Ada Example"),
                _candidate("author", "Grace Example"),
                _candidate("issn", "1234-5678"),
            )
        )
    )

    result = CrossrefFederatedAdapter(provider).search(
        DiscoveryQuery(text="https://doi.org/10.1000/example")
    )

    assert provider.queries == [MetadataQuery(doi="10.1000/example")]
    assert result.completeness.value == "complete"
    assert result.provider_statuses[0].outcome == ProviderOutcome.SUCCESS
    assert result.provider_statuses[0].result_count == 1
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.canonical_id == "crossref:10.1000/example"
    assert candidate.title == "Example Paper"
    assert candidate.doi == "10.1000/example"
    assert candidate.publication_year == 2025
    observation = candidate.observations[0]
    assert observation.provider == "crossref"
    assert observation.provider_id == "10.1000/example"
    assert observation.authors == ("Ada Example", "Grace Example")
    assert observation.venue == "Example Journal"
    assert observation.metadata_source == "crossref"
    assert observation.retrieved_at == _RETRIEVED_AT.isoformat()


def test_crossref_adapter_rejects_free_text_without_calling_doi_provider() -> None:
    provider = FakeCrossrefProvider(MetadataProviderResult())

    result = CrossrefFederatedAdapter(provider).search(
        DiscoveryQuery(text="semaglutide body weight")
    )

    assert provider.queries == []
    assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "unsupported_query"


def test_crossref_adapter_rejects_year_filter_instead_of_silently_ignoring_it() -> None:
    provider = FakeCrossrefProvider(MetadataProviderResult())

    result = CrossrefFederatedAdapter(provider).search(
        DiscoveryQuery(text="10.1000/example", year_from=2020)
    )

    assert provider.queries == []
    assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "unsupported_filter"


def test_crossref_adapter_maps_no_match_to_empty() -> None:
    provider = FakeCrossrefProvider(
        MetadataProviderResult(
            diagnostics=(
                ProviderDiagnostic(
                    provider="crossref",
                    code="no_match",
                    message="Crossref did not return a record for this DOI.",
                ),
            )
        )
    )

    result = CrossrefFederatedAdapter(provider).search(DiscoveryQuery(text="10.1000/example"))

    assert result.provider_statuses[0].outcome == ProviderOutcome.EMPTY
    assert result.provider_statuses[0].reason is None
    assert result.candidates == ()


def test_crossref_adapter_maps_retryable_provider_diagnostics() -> None:
    for code, expected_outcome in (
        ("rate_limited", ProviderOutcome.RATE_LIMITED),
        ("provider_unavailable", ProviderOutcome.UNAVAILABLE),
        ("timeout", ProviderOutcome.UNAVAILABLE),
        ("transport_error", ProviderOutcome.UNAVAILABLE),
    ):
        provider = FakeCrossrefProvider(
            MetadataProviderResult(
                diagnostics=(
                    ProviderDiagnostic(
                        provider="crossref",
                        code=code,  # type: ignore[arg-type]
                        message="sanitized provider message",
                        retryable=True,
                    ),
                )
            )
        )

        result = CrossrefFederatedAdapter(provider).search(DiscoveryQuery(text="10.1000/example"))

        assert result.provider_statuses[0].outcome == expected_outcome
        assert result.provider_statuses[0].reason == code


def test_crossref_adapter_maps_bad_provider_payloads_to_failed() -> None:
    for code in ("malformed_response", "oversized_response"):
        provider = FakeCrossrefProvider(
            MetadataProviderResult(
                diagnostics=(
                    ProviderDiagnostic(
                        provider="crossref",
                        code=code,
                        message="raw response details must not escape",
                    ),
                )
            )
        )

        result = CrossrefFederatedAdapter(provider).search(DiscoveryQuery(text="10.1000/example"))

        assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
        assert result.provider_statuses[0].reason == code
        assert "raw response details" not in result.to_json()


def test_crossref_adapter_fails_closed_on_mismatched_candidate_identity() -> None:
    provider = FakeCrossrefProvider(
        MetadataProviderResult(
            candidates=(
                _candidate("doi", "10.9999/other", provider_record_id="10.9999/other"),
                _candidate("title", "Wrong Paper", provider_record_id="10.9999/other"),
            )
        )
    )

    result = CrossrefFederatedAdapter(provider).search(DiscoveryQuery(text="10.1000/example"))

    assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "candidate_contract_mismatch"
    assert result.candidates == ()


def test_crossref_adapter_requires_title_for_federated_candidate() -> None:
    provider = FakeCrossrefProvider(
        MetadataProviderResult(candidates=(_candidate("doi", "10.1000/example"),))
    )

    result = CrossrefFederatedAdapter(provider).search(DiscoveryQuery(text="10.1000/example"))

    assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "candidate_contract_mismatch"
