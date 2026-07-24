from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.core_discovery import CoreDiscoveryError, CoreDiscoveryService


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.urls: list[str] = []
        self.headers: list[Mapping[str, str]] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> FakeResponse:
        del timeout_seconds, max_response_bytes
        self.urls.append(url)
        self.headers.append(headers)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _service(
    transport: FakeTransport,
    *,
    api_key: str | None = None,
    max_attempts: int = 3,
    delays: list[float] | None = None,
) -> CoreDiscoveryService:
    recorded_delays = delays if delays is not None else []
    return CoreDiscoveryService(
        transport,
        api_key=api_key,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _search_response(*results: dict[str, object], total_hits: int | None = None) -> FakeResponse:
    payload: dict[str, object] = {
        "totalHits": total_hits if total_hits is not None else len(results),
        "limit": 25,
        "offset": 0,
        "results": list(results),
    }
    return FakeResponse(200, json.dumps(payload).encode(), {})


def _full_candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 12345,
        "doi": "10.1000/example",
        "title": "Semaglutide in adults with obesity",
        "abstract": "A randomized trial of semaglutide therapy.",
        "authors": [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}],
        "yearPublished": 2024,
        "publisher": "Journal of Verified Results",
        "documentType": "research",
        "downloadUrl": "https://core.ac.uk/download/12345.pdf",
        "sourceFulltextUrls": ["https://example.org/preprint.pdf"],
    }
    base.update(overrides)
    return base


def test_discover_parses_a_full_candidate_preferring_core_host() -> None:
    transport = FakeTransport([_search_response(_full_candidate())])
    result = _service(transport).discover("semaglutide", limit=10)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.core_id == "12345"
    assert candidate.doi == "10.1000/example"
    assert candidate.title == "Semaglutide in adults with obesity"
    assert candidate.abstract == "A randomized trial of semaglutide therapy."
    assert candidate.authors == ("Ada Lovelace", "Grace Hopper")
    assert candidate.publication_year == 2024
    assert candidate.venue == "Journal of Verified Results"
    assert candidate.document_type == "research"
    assert candidate.pdf_url == "https://core.ac.uk/download/12345.pdf"
    assert candidate.pdf_host == "core.ac.uk"
    assert candidate.source_fulltext_urls == ("https://example.org/preprint.pdf",)


def test_discover_falls_back_to_source_fulltext_url_when_no_download_url() -> None:
    candidate = _full_candidate(downloadUrl=None)
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    assert result.candidates[0].pdf_url == "https://example.org/preprint.pdf"
    assert result.candidates[0].pdf_host == "example.org"


def test_discover_returns_none_pdf_when_no_urls_present() -> None:
    candidate = _full_candidate(downloadUrl=None, sourceFulltextUrls=[])
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    assert result.candidates[0].pdf_url is None
    assert result.candidates[0].pdf_host is None


def test_discover_handles_missing_optional_fields() -> None:
    candidate = _full_candidate(doi=None)
    for key in (
        "abstract",
        "authors",
        "yearPublished",
        "publisher",
        "documentType",
        "sourceFulltextUrls",
    ):
        del candidate[key]
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    parsed = result.candidates[0]
    assert parsed.doi is None
    assert parsed.abstract is None
    assert parsed.authors == ()
    assert parsed.publication_year is None
    assert parsed.venue is None
    assert parsed.document_type is None
    assert parsed.source_fulltext_urls == ()


def test_discover_skips_malformed_author_entries() -> None:
    candidate = _full_candidate(authors=[{"name": "Ada Lovelace"}, "not a dict", {}])
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    assert result.candidates[0].authors == ("Ada Lovelace",)


def test_discover_computes_next_offset_when_more_results_remain() -> None:
    transport = FakeTransport([_search_response(_full_candidate(), total_hits=50)])
    result = _service(transport).discover("semaglutide", limit=1, offset=0)

    assert result.total_hits == 50
    assert result.next_offset == 1


def test_discover_next_offset_is_none_when_exhausted() -> None:
    transport = FakeTransport([_search_response(_full_candidate(), total_hits=1)])
    result = _service(transport).discover("semaglutide", limit=25, offset=0)

    assert result.next_offset is None


def test_discover_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _service(FakeTransport([])).discover("   ", limit=10)


def test_discover_rejects_out_of_range_limit() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        _service(FakeTransport([])).discover("semaglutide", limit=0)


def test_discover_rejects_negative_offset() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _service(FakeTransport([])).discover("semaglutide", limit=10, offset=-1)


def test_discover_sends_bearer_token_when_api_key_configured() -> None:
    transport = FakeTransport([_search_response(_full_candidate())])
    _service(transport, api_key="secret-token").discover("semaglutide", limit=10)

    assert transport.headers[0]["Authorization"] == "Bearer secret-token"


def test_discover_omits_authorization_header_without_api_key() -> None:
    transport = FakeTransport([_search_response(_full_candidate())])
    _service(transport).discover("semaglutide", limit=10)

    assert "Authorization" not in transport.headers[0]


def test_discover_retries_on_a_retryable_status() -> None:
    transport = FakeTransport(
        [
            FakeResponse(429, b"", {}),
            _search_response(_full_candidate()),
        ]
    )
    delays: list[float] = []
    result = _service(transport, delays=delays).discover("semaglutide", limit=10)

    assert len(result.candidates) == 1
    assert delays == [2.0]


def test_discover_raises_after_exhausting_retries_on_transport_error() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b""), IncompleteRead(b"")])
    with pytest.raises(CoreDiscoveryError, match="failed after 3 attempt"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(200, b"not json", {})])
    with pytest.raises(CoreDiscoveryError, match="malformed JSON"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_missing_total_hits() -> None:
    transport = FakeTransport([FakeResponse(200, json.dumps({"results": []}).encode(), {})])
    with pytest.raises(CoreDiscoveryError, match="malformed"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_result_missing_required_field() -> None:
    candidate = _full_candidate()
    del candidate["title"]
    transport = FakeTransport([_search_response(candidate)])
    with pytest.raises(CoreDiscoveryError, match="missing required evidence"):
        _service(transport).discover("semaglutide", limit=10)
