from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from knowledge_engine.federated_discovery import DiscoveryQuery, ProviderOutcome
from knowledge_engine.semantic_scholar_provider import (
    ResponseTooLargeError,
    SemanticScholarProvider,
    TransportResponse,
)


@dataclass
class FakeTransport:
    response: TransportResponse | None = None
    error: Exception | None = None
    calls: list[tuple[str, dict[str, str], float, int]] = field(default_factory=list)

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.calls.append((url, dict(headers), timeout_seconds, max_response_bytes))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _response(payload: object, status_code: int = 200) -> TransportResponse:
    return TransportResponse(
        status_code=status_code,
        body=json.dumps(payload).encode(),
        headers={},
    )


def _paper() -> dict[str, object]:
    return {
        "paperId": "abc123",
        "title": "Provider-neutral discovery",
        "authors": [{"authorId": "a1", "name": "Ada Example"}],
        "year": 2025,
        "venue": "Journal of Tests",
        "abstract": "Source-paper abstract.",
        "externalIds": {
            "DOI": "https://doi.org/10.1000/Example",
            "PubMed": "12345678",
            "ArXiv": "2501.01234",
        },
        "url": "https://www.semanticscholar.org/paper/abc123",
        "openAccessPdf": {"url": "https://example.org/paper.pdf"},
        "citationCount": 17,
        "tldr": {"text": "Provider-generated summary must not enter evidence."},
    }


def test_search_works_without_api_key_and_preserves_provider_provenance() -> None:
    transport = FakeTransport(_response({"total": 1, "data": [_paper()]}))
    provider = SemanticScholarProvider(
        transport=transport,
        clock=lambda: datetime(2026, 8, 16, 3, 0, tzinfo=UTC),
    )

    result = provider.search(
        DiscoveryQuery(
            text="  provider neutral discovery  ",
            year_from=2020,
            year_to=2026,
            limit_per_provider=5,
        )
    )

    assert provider.authenticated is False
    assert result.provider_statuses[0].outcome is ProviderOutcome.SUCCESS
    assert result.provider_statuses[0].result_count == 1
    candidate = result.candidates[0]
    observation = candidate.observations[0]
    assert candidate.canonical_id == "semantic_scholar:abc123"
    assert candidate.doi == "10.1000/example"
    assert observation.semantic_scholar_id == "abc123"
    assert observation.pmid == "12345678"
    assert observation.arxiv_id == "2501.01234"
    assert observation.abstract == "Source-paper abstract."
    assert observation.full_text_url == "https://example.org/paper.pdf"
    assert observation.open_access is True
    assert observation.open_access_source == "semantic_scholar"
    assert observation.citation_count == 17
    assert observation.retrieved_at == "2026-08-16T03:00:00+00:00"

    url, headers, timeout_seconds, max_response_bytes = transport.calls[0]
    params = parse_qs(urlparse(url).query)
    assert params["query"] == ["provider neutral discovery"]
    assert params["limit"] == ["5"]
    assert params["year"] == ["2020-2026"]
    assert "tldr" not in params["fields"][0].lower()
    assert "x-api-key" not in headers
    assert timeout_seconds > 0
    assert max_response_bytes > 0


def test_optional_api_key_is_header_only() -> None:
    transport = FakeTransport(_response({"total": 0, "data": []}))
    provider = SemanticScholarProvider(transport=transport, api_key=" secret-key ")

    result = provider.search(DiscoveryQuery(text="test"))

    assert provider.authenticated is True
    assert result.provider_statuses[0].outcome is ProviderOutcome.EMPTY
    url, headers, _, _ = transport.calls[0]
    assert headers["x-api-key"] == "secret-key"
    assert "secret-key" not in url


def test_missing_open_access_pdf_stays_unknown_not_false() -> None:
    paper = _paper()
    paper["openAccessPdf"] = None
    transport = FakeTransport(_response({"data": [paper]}))

    result = SemanticScholarProvider(transport=transport).search(
        DiscoveryQuery(text="test")
    )

    observation = result.candidates[0].observations[0]
    assert observation.full_text_url is None
    assert observation.open_access is None
    assert observation.open_access_source is None


def test_search_rejects_provider_page_larger_than_requested_bound() -> None:
    transport = FakeTransport(_response({"data": [_paper(), _paper()]}))

    result = SemanticScholarProvider(transport=transport).search(
        DiscoveryQuery(text="bounded", limit_per_provider=1)
    )

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome is ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "oversized_result_page"


@pytest.mark.parametrize(
    ("status_code", "outcome", "reason"),
    [
        (429, ProviderOutcome.RATE_LIMITED, "rate_limited"),
        (503, ProviderOutcome.UNAVAILABLE, "provider_unavailable"),
        (401, ProviderOutcome.FAILED, "authentication_failed"),
    ],
)
def test_http_failures_map_to_explicit_provider_status(
    status_code: int,
    outcome: ProviderOutcome,
    reason: str,
) -> None:
    transport = FakeTransport(TransportResponse(status_code, b"{}", {}))

    result = SemanticScholarProvider(transport=transport).search(
        DiscoveryQuery(text="test")
    )

    assert result.provider_statuses[0].outcome is outcome
    assert result.provider_statuses[0].reason == reason


@pytest.mark.parametrize(
    ("error", "outcome", "reason"),
    [
        (TimeoutError(), ProviderOutcome.UNAVAILABLE, "timeout"),
        (OSError(), ProviderOutcome.UNAVAILABLE, "transport_error"),
        (ResponseTooLargeError(), ProviderOutcome.FAILED, "oversized_response"),
    ],
)
def test_transport_failures_are_contained(
    error: Exception,
    outcome: ProviderOutcome,
    reason: str,
) -> None:
    result = SemanticScholarProvider(transport=FakeTransport(error=error)).search(
        DiscoveryQuery(text="test")
    )

    assert result.provider_statuses[0].outcome is outcome
    assert result.provider_statuses[0].reason == reason


def test_malformed_search_item_fails_closed() -> None:
    transport = FakeTransport(_response({"data": [{"paperId": "missing-title"}]}))

    result = SemanticScholarProvider(transport=transport).search(
        DiscoveryQuery(text="test")
    )

    assert result.candidates == ()
    assert result.provider_statuses[0].reason == "malformed_response"


def test_lookup_normalizes_doi_to_semantic_scholar_identifier() -> None:
    transport = FakeTransport(_response(_paper()))

    result = SemanticScholarProvider(transport=transport).lookup(
        "https://doi.org/10.1000/Example"
    )

    assert result.provider_statuses[0].outcome is ProviderOutcome.SUCCESS
    path = urlparse(transport.calls[0][0]).path
    assert path.endswith("/paper/DOI:10.1000%2Fexample")


def test_blank_optional_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="API key must not be blank"):
        SemanticScholarProvider(transport=FakeTransport(), api_key="   ")
