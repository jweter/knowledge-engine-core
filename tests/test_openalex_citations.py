from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from knowledge_engine.citation_discovery import CitationDirection
from knowledge_engine.federated_discovery import ProviderOutcome
from knowledge_engine.openalex_citations import OpenAlexCitationProvider
from knowledge_engine.openalex_provider import ResponseTooLargeError, TransportResponse


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
    api_key: str | None = "test-key",
) -> tuple[OpenAlexCitationProvider, FakeTransport]:
    transport = FakeTransport(response)
    provider = OpenAlexCitationProvider(
        transport=transport,
        api_key=api_key,
        clock=lambda: datetime(2026, 8, 15, 15, 0, tzinfo=UTC),
        timeout_seconds=3.0,
        max_response_bytes=10_000,
        user_agent="knowledge-engine-test/1",
    )
    return provider, transport


def test_references_returns_bounded_provenance_edges() -> None:
    provider, transport = _provider(
        _response(
            200,
            b'{"id":"https://openalex.org/W10","referenced_works":['
            b'"https://openalex.org/W20","W30","W20","bad"]}',
        )
    )

    result = provider.references("https://openalex.org/W10", limit=2)

    assert result.direction == CitationDirection.REFERENCES
    assert result.seed_id == "W10"
    assert result.discovered_ids == ("W20", "W30")
    assert result.provider_status.outcome == ProviderOutcome.SUCCESS
    assert result.provider_status.result_count == 2
    assert [(edge.source_id, edge.target_id) for edge in result.edges] == [
        ("W10", "W20"),
        ("W10", "W30"),
    ]
    assert all(edge.observed_at == "2026-08-15T15:00:00+00:00" for edge in result.edges)

    url, headers, timeout_seconds, max_response_bytes = transport.calls[0]
    assert url.startswith("https://api.openalex.org/works/W10?")
    assert "select=id%2Creferenced_works" in url
    assert "api_key=test-key" in url
    assert headers["User-Agent"] == "knowledge-engine-test/1"
    assert timeout_seconds == 3.0
    assert max_response_bytes == 10_000


def test_cited_by_uses_cites_filter_and_preserves_edge_direction() -> None:
    provider, transport = _provider(
        _response(
            200,
            b'{"results":[{"id":"https://openalex.org/W40"},{"id":"W50"}]}',
        )
    )

    result = provider.cited_by("W10", limit=2)

    assert result.direction == CitationDirection.CITED_BY
    assert result.discovered_ids == ("W40", "W50")
    assert [(edge.source_id, edge.target_id) for edge in result.edges] == [
        ("W40", "W10"),
        ("W50", "W10"),
    ]
    assert result.provider_status.outcome == ProviderOutcome.SUCCESS
    url = transport.calls[0][0]
    assert "filter=cites%3AW10" in url
    assert "select=id" in url
    assert "per_page=2" in url
    assert "api_key=test-key" in url


def test_missing_api_key_disables_without_network_call() -> None:
    provider, transport = _provider(_response(200), api_key=None)

    result = provider.references("W10")

    assert provider.configured is False
    assert result.provider_status.outcome == ProviderOutcome.DISABLED
    assert result.provider_status.attempted is False
    assert result.provider_status.reason == "missing_api_key"
    assert transport.calls == []


@pytest.mark.parametrize(
    ("status_code", "outcome", "reason"),
    [
        (404, ProviderOutcome.EMPTY, None),
        (401, ProviderOutcome.FAILED, "authentication_failed"),
        (403, ProviderOutcome.FAILED, "authentication_failed"),
        (429, ProviderOutcome.RATE_LIMITED, "rate_limited"),
        (500, ProviderOutcome.UNAVAILABLE, "provider_unavailable"),
        (503, ProviderOutcome.UNAVAILABLE, "provider_unavailable"),
    ],
)
def test_traversal_classifies_provider_statuses(
    status_code: int,
    outcome: ProviderOutcome,
    reason: str | None,
) -> None:
    provider, _ = _provider(_response(status_code))

    result = provider.cited_by("W10")

    assert result.provider_status.outcome == outcome
    assert result.provider_status.reason == reason


@pytest.mark.parametrize(
    ("error", "outcome", "reason"),
    [
        (TimeoutError(), ProviderOutcome.UNAVAILABLE, "timeout"),
        (OSError("secret transport detail"), ProviderOutcome.UNAVAILABLE, "transport_error"),
        (ResponseTooLargeError("secret body detail"), ProviderOutcome.FAILED, "oversized_response"),
    ],
)
def test_traversal_sanitizes_transport_errors(
    error: Exception,
    outcome: ProviderOutcome,
    reason: str,
) -> None:
    provider, _ = _provider(error)

    result = provider.references("W10")

    assert result.provider_status.outcome == outcome
    assert result.provider_status.reason == reason
    assert "secret" not in (result.provider_status.reason or "")


def test_empty_reference_list_is_explicit_empty() -> None:
    provider, _ = _provider(_response(200, b'{"referenced_works":[]}'))

    result = provider.references("W10")

    assert result.edges == ()
    assert result.provider_status.outcome == ProviderOutcome.EMPTY
    assert result.provider_status.attempted is True


def test_malformed_payload_is_failed_not_empty() -> None:
    provider, _ = _provider(_response(200, b'{"results":"wrong-shape"}'))

    result = provider.cited_by("W10")

    assert result.provider_status.outcome == ProviderOutcome.FAILED
    assert result.provider_status.reason == "malformed_response"


@pytest.mark.parametrize("seed", ["", "not-an-openalex-id", "A123"])
def test_traversal_rejects_non_work_seed_ids(seed: str) -> None:
    provider, _ = _provider(_response(200))

    with pytest.raises(ValueError, match="OpenAlex work ID"):
        provider.references(seed)


@pytest.mark.parametrize("limit", [0, 101])
def test_traversal_enforces_explicit_bounds(limit: int) -> None:
    provider, _ = _provider(_response(200))

    with pytest.raises(ValueError, match="between 1 and 100"):
        provider.cited_by("W10", limit=limit)
