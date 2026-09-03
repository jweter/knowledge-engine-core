from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from knowledge_engine.arxiv_provider import ArxivProvider, TransportResponse
from knowledge_engine.federated_discovery import DiscoveryQuery, ProviderOutcome

_NOW = datetime(2026, 8, 16, 4, 0, tzinfo=UTC)


def _feed(*entries: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom">' + "".join(entries) + "</feed>"
    ).encode()


def _entry(
    identifier: str = "2408.12345v2",
    *,
    title: str = "  Explicit   Preprint   Semantics ",
    doi: str | None = "10.1000/JOURNAL.1",
    journal_ref: str | None = "Journal of Examples 12 (2026)",
) -> str:
    doi_xml = f"<arxiv:doi>{doi}</arxiv:doi>" if doi is not None else ""
    journal_xml = (
        f"<arxiv:journal_ref>{journal_ref}</arxiv:journal_ref>" if journal_ref is not None else ""
    )
    pdf_link = (
        f'<link href="https://arxiv.org/pdf/{identifier}" '
        'rel="related" type="application/pdf" title="pdf" />'
    )
    return f"""
    <entry>
      <id>https://arxiv.org/abs/{identifier}</id>
      <updated>2026-08-15T12:00:00Z</updated>
      <published>2026-08-14T12:00:00Z</published>
      <title>{title}</title>
      <summary>  A   preprint   abstract. </summary>
      <author><name>Ada Example</name></author>
      <author><name>Lin Researcher</name></author>
      <link href="https://arxiv.org/abs/{identifier}" rel="alternate" type="text/html" />
      {pdf_link}
      {doi_xml}
      {journal_xml}
      <arxiv:license>https://creativecommons.org/licenses/by/4.0/</arxiv:license>
    </entry>
    """


@dataclass
class FakeTransport:
    response: TransportResponse
    calls: list[dict[str, object]] = field(default_factory=list)

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        return self.response


def _provider(
    body: bytes,
    status_code: int = 200,
    *,
    max_attempts: int = 1,
) -> tuple[ArxivProvider, FakeTransport]:
    # max_attempts defaults to 1 (no retries) so status-code/transport-failure
    # tests that reuse a single fixed FakeTransport response test outcome
    # mapping, not the retry loop -- see the dedicated retry tests below, which
    # pass max_attempts explicitly with a SequenceTransport and a captured
    # sleep function.
    transport = FakeTransport(TransportResponse(status_code=status_code, body=body, headers={}))
    provider = ArxivProvider(
        transport=transport,
        clock=lambda: _NOW,
        max_attempts=max_attempts,
        sleep=lambda _seconds: None,
    )
    return provider, transport


def test_search_preserves_preprint_identity_and_explicit_journal_version_link() -> None:
    provider, _ = _provider(_feed(_entry()))

    result = provider.search(DiscoveryQuery(text="preprint semantics", limit_per_provider=3))

    assert result.provider_statuses[0].outcome is ProviderOutcome.SUCCESS
    assert result.provider_statuses[0].result_count == 1
    candidate = result.candidates[0]
    observation = candidate.observations[0]
    assert candidate.canonical_id == "arxiv:2408.12345v2"
    assert candidate.doi is None
    assert observation.doi is None
    assert observation.provider_id == "2408.12345v2"
    assert observation.arxiv_id == "2408.12345"
    assert observation.preprint is True
    assert observation.preprint_version == 2
    assert observation.related_journal_doi == "10.1000/journal.1"
    assert observation.related_journal_reference == "Journal of Examples 12 (2026)"
    assert observation.title == "Explicit Preprint Semantics"
    assert observation.abstract == "A preprint abstract."
    assert observation.authors == ("Ada Example", "Lin Researcher")
    assert observation.publication_year == 2026
    assert observation.open_access is True
    assert observation.open_access_source == "arxiv"
    assert observation.full_text_url == "https://arxiv.org/pdf/2408.12345v2"


def test_legacy_identifier_is_normalized_without_erasing_version() -> None:
    provider, _ = _provider(_feed(_entry("hep-th/9901001v3", doi=None, journal_ref=None)))

    result = provider.search(DiscoveryQuery(text="legacy identifier", limit_per_provider=1))

    observation = result.candidates[0].observations[0]
    assert result.candidates[0].canonical_id == "arxiv:hep-th/9901001v3"
    assert observation.arxiv_id == "hep-th/9901001"
    assert observation.preprint_version == 3
    assert observation.related_journal_doi is None


def test_year_bounds_are_encoded_in_provider_query_instead_of_ignored() -> None:
    provider, transport = _provider(_feed())

    provider.search(
        DiscoveryQuery(
            text="quantum sensors",
            year_from=2022,
            year_to=2025,
            limit_per_provider=7,
        )
    )

    url = str(transport.calls[0]["url"])
    params = parse_qs(urlparse(url).query)
    assert params["max_results"] == ["7"]
    assert params["search_query"] == [
        "all:quantum sensors AND submittedDate:[202201010000 TO 202512312359]"
    ]


def test_transport_uses_only_public_headers_and_bounded_request_controls() -> None:
    provider, transport = _provider(_feed())

    provider.search(DiscoveryQuery(text="bounded request"))

    call = transport.calls[0]
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert set(headers) == {"Accept", "User-Agent"}
    assert call["timeout_seconds"] == 10.0
    assert call["max_response_bytes"] == 2_000_000


def test_empty_feed_is_explicit_empty_provider_outcome() -> None:
    provider, _ = _provider(_feed())

    result = provider.search(DiscoveryQuery(text="no matches"))

    assert result.provider_statuses[0].outcome is ProviderOutcome.EMPTY
    assert result.candidates == ()


def test_rate_limit_is_visible_in_provider_status() -> None:
    provider, _ = _provider(b"rate limited", status_code=429)

    result = provider.search(DiscoveryQuery(text="rate limited"))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.RATE_LIMITED
    assert status.reason == "rate_limited"
    assert status.retry_attempt_count == 0


def test_malformed_entry_fails_closed_instead_of_silently_dropping_it() -> None:
    provider, _ = _provider(_feed("<entry><title>Missing identifier</title></entry>"))

    result = provider.search(DiscoveryQuery(text="malformed"))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.FAILED
    assert status.reason == "malformed_response"
    assert result.candidates == ()


def test_provider_rejects_limits_above_bounded_cap_without_transport_call() -> None:
    provider, transport = _provider(_feed())

    result = provider.search(DiscoveryQuery(text="too broad", limit_per_provider=101))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.FAILED
    assert status.reason == "unsupported_limit"
    assert transport.calls == []


def test_provider_rejects_result_page_larger_than_requested_limit() -> None:
    provider, _ = _provider(_feed(_entry("2408.00001v1"), _entry("2408.00002v1")))

    result = provider.search(DiscoveryQuery(text="oversized page", limit_per_provider=1))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.FAILED
    assert status.reason == "oversized_result_page"
    assert result.candidates == ()


def test_rejects_non_positive_max_attempts() -> None:
    with pytest.raises(ValueError, match="max_attempts must be at least 1"):
        ArxivProvider(
            transport=FakeTransport(TransportResponse(200, _feed(), {})),
            max_attempts=0,
        )


def test_rejects_negative_retry_backoff() -> None:
    with pytest.raises(ValueError, match="retry backoff must not be negative"):
        ArxivProvider(
            transport=FakeTransport(TransportResponse(200, _feed(), {})),
            retry_backoff_seconds=-1.0,
        )


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


def test_rate_limit_is_retried_and_eventually_succeeds() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(200, _feed(_entry()), {}),
        ]
    )
    sleeps: list[float] = []
    provider = ArxivProvider(transport=transport, clock=lambda: _NOW, sleep=sleeps.append)

    result = provider.search(DiscoveryQuery(text="preprint semantics"))

    assert len(transport.calls) == 2
    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.SUCCESS
    assert status.retry_attempt_count == 1
    assert status.rate_limited_observed is True
    assert result.candidates[0].canonical_id == "arxiv:2408.12345v2"
    assert len(sleeps) == 1
    assert sleeps[0] > 0


def test_provider_unavailable_is_retried_up_to_the_configured_bound_then_reported() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(503, b"unavailable", {}),
            TransportResponse(503, b"unavailable", {}),
            TransportResponse(503, b"unavailable", {}),
        ]
    )
    sleeps: list[float] = []
    provider = ArxivProvider(
        transport=transport,
        clock=lambda: _NOW,
        max_attempts=3,
        sleep=sleeps.append,
    )

    result = provider.search(DiscoveryQuery(text="preprint semantics"))

    # 3 total attempts (1 initial + 2 retries), then the final failure is
    # reported honestly rather than silently swallowed.
    assert len(transport.calls) == 3
    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.UNAVAILABLE
    assert status.reason == "provider_unavailable"
    assert status.retry_attempt_count == 2
    assert status.rate_limited_observed is False
    assert len(sleeps) == 2


def test_non_transient_client_error_is_never_retried() -> None:
    transport = SequenceTransport(responses=[TransportResponse(400, b"bad request", {})])
    sleeps: list[float] = []
    provider = ArxivProvider(transport=transport, clock=lambda: _NOW, sleep=sleeps.append)

    result = provider.search(DiscoveryQuery(text="preprint semantics"))

    assert len(transport.calls) == 1
    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.FAILED
    assert status.reason == "unsupported_http_status"
    assert status.retry_attempt_count == 0
    assert sleeps == []


def test_successful_first_attempt_reports_zero_retries() -> None:
    transport = SequenceTransport(responses=[TransportResponse(200, _feed(_entry()), {})])
    provider = ArxivProvider(transport=transport, clock=lambda: _NOW)

    result = provider.search(DiscoveryQuery(text="preprint semantics"))

    assert len(transport.calls) == 1
    status = result.provider_statuses[0]
    assert status.retry_attempt_count == 0
    assert status.rate_limited_observed is False


def test_retry_backoff_is_exponential() -> None:
    transport = SequenceTransport(
        responses=[
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(429, b"rate limited", {}),
            TransportResponse(200, _feed(_entry()), {}),
        ]
    )
    sleeps: list[float] = []

    ArxivProvider(
        transport=transport,
        clock=lambda: _NOW,
        max_attempts=3,
        retry_backoff_seconds=0.5,
        sleep=sleeps.append,
    ).search(DiscoveryQuery(text="preprint semantics"))

    assert sleeps == [0.5, 1.0]


def test_unsupported_limit_is_rejected_without_a_transport_attempt() -> None:
    provider, transport = _provider(_feed())

    result = provider.search(DiscoveryQuery(text="too broad", limit_per_provider=101))

    status = result.provider_statuses[0]
    assert status.outcome is ProviderOutcome.FAILED
    assert status.reason == "unsupported_limit"
    assert status.retry_attempt_count == 0
    assert status.rate_limited_observed is False
    assert transport.calls == []
