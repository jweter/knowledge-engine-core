from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from knowledge_engine.federated_discovery import DiscoveryQuery, ProviderOutcome
from knowledge_engine.pubmed_discovery import DiscoveryResult, NcbiDiscoveryError, PubmedCandidate
from knowledge_engine.pubmed_federated_adapter import PubmedFederatedAdapter


@dataclass
class FakePubmedService:
    result: DiscoveryResult | None = None
    error: NcbiDiscoveryError | None = None
    calls: list[tuple[str, int, int]] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        assert self.calls is not None
        self.calls.append((query, limit, retstart))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _candidate(*, title: str = "A PubMed paper") -> PubmedCandidate:
    return PubmedCandidate(
        pmid="12345",
        title=title,
        abstract="Abstract text",
        authors=("A. Author", "B. Author"),
        publication_year=2024,
        venue="Example Journal",
        doi="10.1000/example",
        pmcid="PMC12345",
        open_access=True,
        license="CC BY",
        pdf_url="https://example.invalid/paper.pdf",
        xml_url="https://example.invalid/paper.xml",
        status="oa_verified",
        metadata_source="pubmed_efetch",
        pmcid_source="pmc_id_converter",
        oa_source="pmc_cloud_service",
    )


def _result(
    query: str,
    *candidates: PubmedCandidate,
    limit: int = 20,
) -> DiscoveryResult:
    return DiscoveryResult(query=query, retstart=0, limit=limit, candidates=tuple(candidates))


def test_pubmed_adapter_preserves_existing_candidate_observations() -> None:
    provider_query = "(sleep apnea) AND 2020:2025[dp]"
    service = FakePubmedService(result=_result(provider_query, _candidate()))
    adapter = PubmedFederatedAdapter(
        service,
        clock=lambda: datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
    )
    query = DiscoveryQuery(text="  sleep   apnea  ", year_from=2020, year_to=2025)

    result = adapter.search(query)

    assert service.calls == [(provider_query, 20, 0)]
    assert result.provider_statuses[0].outcome is ProviderOutcome.SUCCESS
    assert result.provider_statuses[0].result_count == 1
    candidate = result.candidates[0]
    observation = candidate.observations[0]
    assert candidate.canonical_id == "pubmed:12345"
    assert candidate.doi == "10.1000/example"
    assert observation.provider_id == "12345"
    assert observation.pmid == "12345"
    assert observation.pmcid == "PMC12345"
    assert observation.abstract == "Abstract text"
    assert observation.authors == ("A. Author", "B. Author")
    assert observation.venue == "Example Journal"
    assert observation.full_text_url == "https://example.invalid/paper.pdf"
    assert observation.xml_url == "https://example.invalid/paper.xml"
    assert observation.license == "CC BY"
    assert observation.metadata_source == "pubmed_efetch"
    assert observation.pmcid_source == "pmc_id_converter"
    assert observation.open_access_source == "pmc_cloud_service"
    assert observation.open_access is True
    assert observation.retrieved_at == "2026-08-15T17:00:00+00:00"


def test_pubmed_adapter_supports_one_sided_year_bounds() -> None:
    from_query = "(aging) AND 2022:9999[dp]"
    to_query = "(aging) AND 1000:2022[dp]"
    from_service = FakePubmedService(result=_result(from_query))
    to_service = FakePubmedService(result=_result(to_query))

    PubmedFederatedAdapter(from_service).search(DiscoveryQuery(text="aging", year_from=2022))
    PubmedFederatedAdapter(to_service).search(DiscoveryQuery(text="aging", year_to=2022))

    assert from_service.calls == [(from_query, 20, 0)]
    assert to_service.calls == [(to_query, 20, 0)]


def test_pubmed_adapter_maps_empty_discovery() -> None:
    service = FakePubmedService(result=_result("aging"))

    result = PubmedFederatedAdapter(service).search(DiscoveryQuery(text="aging"))

    assert result.provider_statuses[0].outcome is ProviderOutcome.EMPTY
    assert result.candidates == ()


def test_pubmed_adapter_maps_rate_limit_without_leaking_error_text() -> None:
    service = FakePubmedService(
        error=NcbiDiscoveryError("PubMed search returned private detail (429) after 3 attempts.")
    )

    result = PubmedFederatedAdapter(service).search(DiscoveryQuery(text="aging"))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.RATE_LIMITED
    assert status.reason == "rate_limited"
    assert "private" not in result.to_json()


def test_pubmed_adapter_maps_transport_failure_to_unavailable() -> None:
    service = FakePubmedService(
        error=NcbiDiscoveryError("PubMed search request failed after 3 attempts.")
    )

    result = PubmedFederatedAdapter(service).search(DiscoveryQuery(text="aging"))

    assert result.provider_statuses[0].outcome is ProviderOutcome.UNAVAILABLE
    assert result.provider_statuses[0].reason == "transport_error"


def test_pubmed_adapter_rejects_unsupported_limit_without_network_call() -> None:
    service = FakePubmedService()

    result = PubmedFederatedAdapter(service).search(
        DiscoveryQuery(text="aging", limit_per_provider=101)
    )

    assert service.calls == []
    assert result.provider_statuses[0].outcome is ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "unsupported_limit"


def test_pubmed_adapter_rejects_result_limit_mismatch() -> None:
    service = FakePubmedService(result=_result("aging", limit=21))

    result = PubmedFederatedAdapter(service).search(DiscoveryQuery(text="aging"))

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome is ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "provider_result_mismatch"


def test_pubmed_adapter_rejects_result_page_over_requested_bound() -> None:
    candidates = tuple(_candidate() for _ in range(2))
    service = FakePubmedService(result=_result("aging", *candidates, limit=1))

    result = PubmedFederatedAdapter(service).search(
        DiscoveryQuery(text="aging", limit_per_provider=1)
    )

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome is ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "provider_result_mismatch"


def test_pubmed_adapter_fails_closed_on_malformed_candidate() -> None:
    service = FakePubmedService(result=_result("aging", _candidate(title="")))

    result = PubmedFederatedAdapter(service).search(DiscoveryQuery(text="aging"))

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome is ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "candidate_contract_mismatch"
