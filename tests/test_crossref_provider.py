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
    # max_attempts defaults to 1 (no retries) so status-code/transport-failure
    # tests below keep testing outcome mapping rather than sleeping through
    # real backoffs; retry-loop behavior itself is covered separately below
    # with a SequenceTransport and a captured sleep function.
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        timeout_seconds=3.0,
        max_response_bytes=100,
        user_agent="knowledge-engine-test/1",
        max_attempts=1,
        sleep=lambda _seconds: None,
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
    assert result.publication_status is not None
    assert result.publication_status.provider == "crossref"
    assert result.publication_status.retracted is None
    url, headers, timeout_seconds, max_response_bytes = transport.calls[0]
    assert url == "https://api.crossref.org/works/10.1000%2Fexample"
    assert headers == {
        "Accept": "application/json",
        "User-Agent": "knowledge-engine-test/1",
    }
    assert timeout_seconds == 3.0
    assert max_response_bytes == 100


def test_crossref_provider_populates_publication_status_from_update_to() -> None:
    body = (
        b'{"message":{"DOI":"10.1000/example","title":["Example Paper"],'
        b'"update-to":[{"type":"retraction"}]}}'
    )
    transport = FakeTransport(_response(200, body))
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        timeout_seconds=3.0,
        max_response_bytes=len(body) + 1,
        user_agent="knowledge-engine-test/1",
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.publication_status is not None
    assert result.publication_status.retracted is True
    assert result.publication_status.corrected is None


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


def test_crossref_provider_rejects_non_positive_max_attempts() -> None:
    with pytest.raises(ValueError, match="max_attempts must be at least 1"):
        CrossrefProvider(transport=FakeTransport(_response(200)), max_attempts=0)


def test_crossref_provider_rejects_negative_retry_backoff() -> None:
    with pytest.raises(ValueError, match="retry backoff must not be negative"):
        CrossrefProvider(transport=FakeTransport(_response(200)), retry_backoff_seconds=-1.0)


def test_crossref_provider_first_attempt_success_reports_zero_retries() -> None:
    provider, _ = _provider(
        _response(200, b'{"message":{"DOI":"10.1000/example","title":["Example Paper"]}}')
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.retry_attempt_count == 0
    assert result.rate_limited_observed is False


@pytest.mark.parametrize(
    ("status_code", "code", "retryable"),
    [
        (404, "no_match", False),
        (403, "provider_unavailable", False),
    ],
)
def test_crossref_provider_never_retries_a_real_result(
    status_code: int, code: str, retryable: bool
) -> None:
    provider, _ = _provider(_response(status_code))

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert result.diagnostics[0].code == code
    assert result.diagnostics[0].retryable is retryable
    assert result.retry_attempt_count == 0
    assert result.rate_limited_observed is False


class SequenceTransport:
    """Fake transport returning a different response for each successive call."""

    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.calls.append(url)
        return self.responses[len(self.calls) - 1]


def test_crossref_provider_retries_rate_limit_then_succeeds() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}),
        ]
    )
    sleeps: list[float] = []
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        sleep=sleeps.append,
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert len(transport.calls) == 2
    assert result.diagnostics == ()
    assert result.retry_attempt_count == 1
    assert result.rate_limited_observed is True
    assert len(sleeps) == 1
    assert sleeps[0] > 0


def test_crossref_provider_retries_provider_unavailable_up_to_the_bound_then_reports() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(503, b"unavailable", {}),
            TransportResponse(503, b"unavailable", {}),
            TransportResponse(503, b"unavailable", {}),
        ]
    )
    sleeps: list[float] = []
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        max_attempts=3,
        sleep=sleeps.append,
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert len(transport.calls) == 3
    assert result.diagnostics[0].code == "provider_unavailable"
    assert result.retry_attempt_count == 2
    assert result.rate_limited_observed is False
    assert len(sleeps) == 2


def test_crossref_provider_retries_timeout_then_succeeds() -> None:
    class FlakyTransport:
        def __init__(self) -> None:
            self.calls = 0

        def get(
            self,
            *,
            url: str,
            headers: Mapping[str, str],
            timeout_seconds: float,
            max_response_bytes: int,
        ) -> TransportResponse:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError()
            return TransportResponse(
                200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}
            )

    transport = FlakyTransport()
    sleeps: list[float] = []
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        sleep=sleeps.append,
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert transport.calls == 2
    assert result.diagnostics == ()
    assert result.retry_attempt_count == 1
    assert len(sleeps) == 1


def test_crossref_provider_retry_backoff_is_exponential() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}),
        ]
    )
    sleeps: list[float] = []

    CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        max_attempts=3,
        retry_backoff_seconds=0.5,
        sleep=sleeps.append,
    ).lookup(MetadataQuery(doi="10.1000/example"))

    assert sleeps == [0.5, 1.0]


def test_crossref_provider_retry_after_header_is_honored_when_longer() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {"Retry-After": "10"}),
            TransportResponse(200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}),
        ]
    )
    sleeps: list[float] = []

    CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        retry_backoff_seconds=1.0,
        sleep=sleeps.append,
    ).lookup(MetadataQuery(doi="10.1000/example"))

    assert sleeps == [10.0]


def test_crossref_provider_caps_an_abnormally_large_but_finite_retry_after_header() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {"Retry-After": "99999"}),
            TransportResponse(200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}),
        ]
    )
    sleeps: list[float] = []

    result = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        retry_backoff_seconds=1.0,
        sleep=sleeps.append,
    ).lookup(MetadataQuery(doi="10.1000/example"))

    # A huge but finite Retry-After must be capped at MAX_RETRY_AFTER_SECONDS
    # rather than handed straight to `sleep`, which would otherwise block a
    # "bounded" retry loop for an effectively unbounded duration.
    assert sleeps == [120.0]
    assert result.diagnostics == ()
    assert result.retry_attempt_count == 1


@pytest.mark.parametrize("retry_after_header", ["1e309", "nan", "-1e309"])
def test_crossref_provider_ignores_a_non_finite_or_invalid_retry_after_header(
    retry_after_header: str,
) -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {"Retry-After": retry_after_header}),
            TransportResponse(200, b'{"message":{"DOI":"10.1000/example","title":["Paper"]}}', {}),
        ]
    )
    sleeps: list[float] = []

    # "1e309"/"-1e309" overflow a bare `float()` call to +/-inf rather than
    # raising, and `inf` must never reach `sleep` (which raises OverflowError
    # on a non-finite duration): the header is rejected as invalid and the
    # loop falls back to its own computed backoff instead of fabricating or
    # crashing on a wait time.
    CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        retry_backoff_seconds=3.0,
        sleep=sleeps.append,
    ).lookup(MetadataQuery(doi="10.1000/example"))

    assert sleeps == [3.0]


def test_crossref_provider_oversized_response_is_never_retried() -> None:
    transport = SequenceTransport(responses=[TransportResponse(200, b"x" * 200, {})])
    sleeps: list[float] = []
    provider = CrossrefProvider(
        transport=transport,
        clock=lambda: datetime(2026, 7, 18, tzinfo=UTC),
        max_response_bytes=100,
        sleep=sleeps.append,
    )

    result = provider.lookup(MetadataQuery(doi="10.1000/example"))

    assert len(transport.calls) == 1
    assert result.diagnostics[0].code == "oversized_response"
    assert result.retry_attempt_count == 0
    assert sleeps == []
