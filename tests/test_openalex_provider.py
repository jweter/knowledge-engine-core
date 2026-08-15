from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from knowledge_engine.federated_discovery import DiscoveryQuery, ProviderOutcome
from knowledge_engine.openalex_provider import (
    OpenAlexProvider,
    ResponseTooLargeError,
    TransportResponse,
)


class FakeTransport:
    def __init__(self, response: TransportResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, str], float, int]] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.calls.append((url, headers, timeout_seconds, max_response_bytes))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _response(status_code: int, body: bytes = b"{}") -> TransportResponse:
    return TransportResponse(status_code=status_code, body=body, headers={})


def _provider(
    response: TransportResponse | Exception,
    *,
    api_key: str | None = None,
) -> tuple[OpenAlexProvider, FakeTransport]:
    transport = FakeTransport(response)
    provider = OpenAlexProvider(
        transport=transport,
        clock=lambda: datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        timeout_seconds=3.0,
        max_response_bytes=10_000,
        user_agent="knowledge-engine-test/1",
        api_key=api_key,
    )
    return provider, transport


def _single_work_payload() -> bytes:
    return b"""{
      "id": "https://openalex.org/W123456789",
      "doi": "https://doi.org/10.1000/Example",
      "title": "Example Paper",
      "publication_year": 2024,
      "authorships": [
        {"author": {"display_name": "Ada Scientist"}},
        {"author": {"display_name": "Ben Researcher"}}
      ],
      "primary_location": {
        "landing_page_url": "https://example.org/article",
        "pdf_url": "https://example.org/article.pdf",
        "source": {"display_name": "Example Journal"}
      },
      "abstract_inverted_index": {
        "OpenAlex": [0],
        "preserves": [1],
        "provenance": [2]
      },
      "cited_by_count": 42,
      "open_access": {"is_oa": true},
      "is_retracted": false
    }"""


def _work_payload() -> bytes:
    return b'{"results":[' + _single_work_payload() + b"]}"


def test_openalex_search_maps_provider_native_metadata_and_request_bounds() -> None:
    provider, transport = _provider(_response(200, _work_payload()))

    result = provider.search(
        DiscoveryQuery(
            text="  protein   folding  ",
            year_from=2020,
            year_to=2024,
            limit_per_provider=7,
        )
    )

    assert result.completeness.value == "complete"
    assert result.provider_statuses[0].outcome == ProviderOutcome.SUCCESS
    assert result.provider_statuses[0].result_count == 1
    candidate = result.candidates[0]
    assert candidate.canonical_id == "openalex:W123456789"
    assert candidate.doi == "10.1000/example"
    assert candidate.publication_year == 2024
    observation = candidate.observations[0]
    assert observation.provider == "openalex"
    assert observation.provider_id == "W123456789"
    assert observation.openalex_id == "W123456789"
    assert observation.authors == ("Ada Scientist", "Ben Researcher")
    assert observation.venue == "Example Journal"
    assert observation.abstract == "OpenAlex preserves provenance"
    assert observation.citation_count == 42
    assert observation.open_access is True
    assert observation.retracted is False
    assert observation.retrieved_at == "2026-08-15T12:00:00+00:00"

    url, headers, timeout_seconds, max_response_bytes = transport.calls[0]
    assert url.startswith("https://api.openalex.org/works?")
    assert "search=protein+folding" in url
    assert "per-page=7" in url
    assert "from_publication_date%3A2020-01-01" in url
    assert "to_publication_date%3A2024-12-31" in url
    assert headers == {
        "Accept": "application/json",
        "User-Agent": "knowledge-engine-test/1",
    }
    assert timeout_seconds == 3.0
    assert max_response_bytes == 10_000


def test_openalex_search_supports_optional_api_key_without_logging_it() -> None:
    provider, transport = _provider(_response(200, b'{"results":[]}'), api_key="secret-key")

    result = provider.search(DiscoveryQuery(text="example"))

    assert result.provider_statuses[0].outcome == ProviderOutcome.EMPTY
    assert "api_key=secret-key" in transport.calls[0][0]
    assert result.to_json().find("secret-key") == -1


def test_openalex_lookup_by_openalex_id_uses_single_work_endpoint() -> None:
    provider, transport = _provider(_response(200, _single_work_payload()))

    result = provider.lookup("https://openalex.org/W123456789")

    assert result.provider_statuses[0].outcome == ProviderOutcome.SUCCESS
    assert result.candidates[0].observations[0].openalex_id == "W123456789"
    assert transport.calls[0][0] == "https://api.openalex.org/works/W123456789"


def test_openalex_lookup_by_doi_uses_documented_shorthand_endpoint() -> None:
    provider, transport = _provider(_response(200, _single_work_payload()))

    result = provider.lookup("https://doi.org/10.1000/Example")

    assert result.provider_statuses[0].outcome == ProviderOutcome.SUCCESS
    assert transport.calls[0][0] == "https://api.openalex.org/works/doi:10.1000/example"


@pytest.mark.parametrize(
    ("status_code", "outcome", "reason"),
    [
        (404, ProviderOutcome.EMPTY, None),
        (429, ProviderOutcome.RATE_LIMITED, "rate_limited"),
        (500, ProviderOutcome.UNAVAILABLE, "provider_unavailable"),
        (503, ProviderOutcome.UNAVAILABLE, "provider_unavailable"),
        (403, ProviderOutcome.FAILED, "unsupported_http_status"),
    ],
)
def test_openalex_classifies_http_statuses(
    status_code: int,
    outcome: ProviderOutcome,
    reason: str | None,
) -> None:
    provider, _ = _provider(_response(status_code))

    result = provider.search(DiscoveryQuery(text="example"))

    status = result.provider_statuses[0]
    assert status.outcome == outcome
    assert status.reason == reason


@pytest.mark.parametrize(
    ("error", "outcome", "reason"),
    [
        (TimeoutError(), ProviderOutcome.UNAVAILABLE, "timeout"),
        (
            OSError("secret transport detail"),
            ProviderOutcome.UNAVAILABLE,
            "transport_error",
        ),
        (
            ResponseTooLargeError("raw response detail"),
            ProviderOutcome.FAILED,
            "oversized_response",
        ),
    ],
)
def test_openalex_sanitizes_transport_failures(
    error: Exception,
    outcome: ProviderOutcome,
    reason: str,
) -> None:
    provider, _ = _provider(error)

    result = provider.search(DiscoveryQuery(text="example"))

    status = result.provider_statuses[0]
    assert status.outcome == outcome
    assert status.reason == reason
    assert "secret transport detail" not in (status.reason or "")
    assert "raw response detail" not in (status.reason or "")


def test_openalex_empty_results_are_explicit_not_failures() -> None:
    provider, _ = _provider(_response(200, b'{"results":[]}'))

    result = provider.search(DiscoveryQuery(text="no matches"))

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome == ProviderOutcome.EMPTY
    assert result.provider_statuses[0].attempted is True
    assert result.completeness.value == "complete"


def test_openalex_rejects_malformed_payload() -> None:
    provider, _ = _provider(_response(200, b"not-json"))

    result = provider.search(DiscoveryQuery(text="example"))

    assert result.provider_statuses[0].outcome == ProviderOutcome.FAILED
    assert result.provider_statuses[0].reason == "malformed_response"


def test_openalex_skips_malformed_rows_without_fabricating_fields() -> None:
    provider, _ = _provider(
        _response(
            200,
            b'{"results":[{"id":"https://openalex.org/W1"},{"title":"Missing ID"}]}',
        )
    )

    result = provider.search(DiscoveryQuery(text="example"))

    assert result.candidates == ()
    assert result.provider_statuses[0].outcome == ProviderOutcome.EMPTY


@pytest.mark.parametrize(
    ("identifier", "message"),
    [
        ("", "must not be blank"),
        ("not-an-id", "OpenAlex work ID or DOI"),
    ],
)
def test_openalex_lookup_rejects_invalid_identifiers(identifier: str, message: str) -> None:
    provider, _ = _provider(_response(200, b"{}"))

    with pytest.raises(ValueError, match=message):
        provider.lookup(identifier)


@pytest.mark.parametrize(
    ("timeout_seconds", "max_response_bytes", "user_agent", "api_key", "message"),
    [
        (0.0, 100, "agent", None, "timeout"),
        (1.0, 0, "agent", None, "response limit"),
        (1.0, 100, " ", None, "User-Agent"),
        (1.0, 100, "agent", " ", "API key"),
    ],
)
def test_openalex_rejects_invalid_configuration(
    timeout_seconds: float,
    max_response_bytes: int,
    user_agent: str,
    api_key: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        OpenAlexProvider(
            transport=FakeTransport(_response(200)),
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
            user_agent=user_agent,
            api_key=api_key,
        )
