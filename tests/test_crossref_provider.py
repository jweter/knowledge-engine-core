from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from knowledge_engine.crossref_provider import (
    CrossrefProvider,
    ResponseTooLargeError,
    TransportResponse,
)
from knowledge_engine.metadata_enrichment import MetadataQuery


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


def _provider(response: TransportResponse | Exception) -> tuple[CrossrefProvider, FakeTransport]:
    transport = FakeTransport(response)
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        timeout_seconds=3.0,
        max_response_bytes=100,
        user_agent="knowledge-engine-test/1",
    )
    return provider, transport


def test_crossref_provider_returns_candidates_and_bounded_request() -> None:
    provider, transport = _provider(
        _response(
            200,
            b'{"message":{"DOI":"10.1000/example","title":["Example Paper"]}}',
        )
    )

    result = provider.lookup(MetadataQuery(doi="https://doi.org/10.1000/example"))

    assert result.diagnostics == ()
    assert [(candidate.field, candidate.normalized_value) for candidate in result.candidates] == [
        ("doi", "10.1000/example"),
        ("title", "example paper"),
    ]
    url, headers, timeout_seconds, max_response_bytes = transport.calls[0]
    assert url == "https://api.crossref.org/works/10.1000%2Fexample"
    assert headers == {
        "Accept": "application/json",
        "User-Agent": "knowledge-engine-test/1",
    }
    assert timeout_seconds == 3.0
    assert max_response_bytes == 100


@pytest.mark.parametrize(
    ("status_code", "code", "retryable"),
    [
        (404, "no_match", False),
        (429, "rate_limited", True),
        (500, "provider_unavailable", True),
        (503, "provider_unavailable", True),
        (403, "provider_unavailable", False),
    ],
)
def test_crossref_provider_classifies_http_statuses(
    status_code: int,
    code: str,
    retryable: bool,
) -> None:
    provider, _ = _provider(_response(status_code))

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.candidates == ()
    assert result.diagnostics[0].code == code
    assert result.diagnostics[0].retryable is retryable


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError(), "timeout"),
        (OSError("secret transport details"), "transport_error"),
    ],
)
def test_crossref_provider_sanitizes_transport_failures(error: Exception, code: str) -> None:
    provider, _ = _provider(error)

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.candidates == ()
    assert result.diagnostics[0].code == code
    assert "secret transport details" not in result.diagnostics[0].message
    assert result.diagnostics[0].retryable is True


def test_crossref_provider_classifies_transport_oversize() -> None:
    provider, _ = _provider(ResponseTooLargeError("raw response details"))

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.candidates == ()
    assert result.diagnostics[0].code == "oversized_response"
    assert "raw response details" not in result.diagnostics[0].message
    assert result.diagnostics[0].retryable is False


def test_crossref_provider_rejects_oversized_response() -> None:
    provider, _ = _provider(_response(200, b"x" * 101))

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.diagnostics[0].code == "oversized_response"


def test_crossref_provider_reports_malformed_json() -> None:
    provider, _ = _provider(_response(200, b"not-json"))

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.diagnostics[0].code == "malformed_response"
    assert result.diagnostics[0].message == "Crossref returned malformed JSON."


@pytest.mark.parametrize(
    ("timeout_seconds", "max_response_bytes", "user_agent", "message"),
    [
        (0.0, 100, "agent", "timeout"),
        (1.0, 0, "agent", "response limit"),
        (1.0, 100, " ", "User-Agent"),
    ],
)
def test_crossref_provider_rejects_invalid_configuration(
    timeout_seconds: float,
    max_response_bytes: int,
    user_agent: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CrossrefProvider(
            transport=FakeTransport(_response(200)),
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
            user_agent=user_agent,
        )
