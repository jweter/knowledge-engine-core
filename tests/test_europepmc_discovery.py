from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.europepmc_discovery import (
    EuropePmcDiscoveryError,
    EuropePmcDiscoveryService,
)


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> FakeResponse:
        del headers, timeout_seconds, max_response_bytes
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _service(
    transport: FakeTransport,
    *,
    max_attempts: int = 3,
    delays: list[float] | None = None,
) -> EuropePmcDiscoveryService:
    recorded_delays = delays if delays is not None else []
    return EuropePmcDiscoveryService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _search_response(
    *results: dict[str, object], next_cursor_mark: str | None = None
) -> FakeResponse:
    payload: dict[str, object] = {"resultList": {"result": list(results)}}
    if next_cursor_mark is not None:
        payload["nextCursorMark"] = next_cursor_mark
    return FakeResponse(200, json.dumps(payload).encode(), {})


def _full_candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "PPR123",
        "source": "PPR",
        "pmid": "111",
        "pmcid": None,
        "doi": "10.1000/example",
        "title": "Semaglutide in adults with obesity",
        "abstractText": "A randomized trial of semaglutide therapy.",
        "authorList": {
            "author": [
                {"fullName": "Ada Lovelace"},
                {"fullName": "Grace Hopper"},
            ]
        },
        "journalInfo": {"journal": {"title": "Journal of Verified Results"}},
        "pubYear": "2024",
        "isOpenAccess": "Y",
        "inPMC": "N",
        "license": "cc by",
        "fullTextUrlList": {
            "fullTextUrl": [
                {
                    "availabilityCode": "OA",
                    "documentStyle": "pdf",
                    "site": "Unpaywall",
                    "url": "https://example.org/preprint.pdf",
                },
                {
                    "availabilityCode": "OA",
                    "documentStyle": "pdf",
                    "site": "Europe_PMC",
                    "url": "https://europepmc.org/api/fulltextRepo?pprId=PPR123",
                },
            ]
        },
    }
    base.update(overrides)
    return base


def test_discover_parses_a_full_candidate_preferring_europepmc_host() -> None:
    transport = FakeTransport([_search_response(_full_candidate())])
    result = _service(transport).discover("semaglutide", limit=10)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.europepmc_id == "PPR123"
    assert candidate.source == "PPR"
    assert candidate.pmid == "111"
    assert candidate.pmcid is None
    assert candidate.doi == "10.1000/example"
    assert candidate.title == "Semaglutide in adults with obesity"
    assert candidate.abstract == "A randomized trial of semaglutide therapy."
    assert candidate.authors == ("Ada Lovelace", "Grace Hopper")
    assert candidate.publication_year == 2024
    assert candidate.venue == "Journal of Verified Results"
    assert candidate.in_pmc is False
    assert candidate.open_access is True
    assert candidate.license == "cc by"
    assert candidate.pdf_url == "https://europepmc.org/api/fulltextRepo?pprId=PPR123"
    assert candidate.pdf_host == "europepmc.org"


def test_discover_falls_back_to_third_party_pdf_when_no_europepmc_host() -> None:
    candidate = _full_candidate(
        fullTextUrlList={
            "fullTextUrl": [
                {
                    "availabilityCode": "OA",
                    "documentStyle": "pdf",
                    "site": "Unpaywall",
                    "url": "https://example.org/preprint.pdf",
                }
            ]
        }
    )
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    assert result.candidates[0].pdf_url == "https://example.org/preprint.pdf"
    assert result.candidates[0].pdf_host == "example.org"


def test_discover_returns_none_pdf_when_no_oa_pdf_entry() -> None:
    candidate = _full_candidate(
        fullTextUrlList={
            "fullTextUrl": [
                {
                    "availabilityCode": "S",
                    "documentStyle": "doi",
                    "site": "DOI",
                    "url": "https://doi.org/10.1000/example",
                }
            ]
        }
    )
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    assert result.candidates[0].pdf_url is None
    assert result.candidates[0].pdf_host is None


def test_discover_handles_missing_optional_fields() -> None:
    candidate = _full_candidate(pmid=None, doi=None)
    for key in (
        "abstractText",
        "authorList",
        "journalInfo",
        "pubYear",
        "license",
        "fullTextUrlList",
    ):
        del candidate[key]
    transport = FakeTransport([_search_response(candidate)])
    result = _service(transport).discover("semaglutide", limit=10)

    parsed = result.candidates[0]
    assert parsed.pmid is None
    assert parsed.doi is None
    assert parsed.abstract is None
    assert parsed.authors == ()
    assert parsed.venue is None
    assert parsed.publication_year is None
    assert parsed.license is None
    assert parsed.pdf_url is None


def test_discover_next_cursor_mark_is_none_when_exhausted() -> None:
    transport = FakeTransport([_search_response(_full_candidate(), next_cursor_mark="*")])
    result = _service(transport).discover("semaglutide", limit=10, cursor_mark="*")

    assert result.next_cursor_mark is None


def test_discover_returns_next_cursor_mark_when_more_pages_remain() -> None:
    transport = FakeTransport([_search_response(_full_candidate(), next_cursor_mark="AoIIQ==")])
    result = _service(transport).discover("semaglutide", limit=10, cursor_mark="*")

    assert result.next_cursor_mark == "AoIIQ=="


def test_discover_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _service(FakeTransport([])).discover("   ", limit=10)


def test_discover_rejects_out_of_range_limit() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        _service(FakeTransport([])).discover("semaglutide", limit=0)


def test_discover_rejects_empty_cursor_mark() -> None:
    with pytest.raises(ValueError, match="cursor_mark"):
        _service(FakeTransport([])).discover("semaglutide", limit=10, cursor_mark="")


def test_discover_retries_on_a_retryable_status() -> None:
    transport = FakeTransport(
        [
            FakeResponse(503, b"", {}),
            _search_response(_full_candidate()),
        ]
    )
    delays: list[float] = []
    result = _service(transport, delays=delays).discover("semaglutide", limit=10)

    assert len(result.candidates) == 1
    assert delays == [2.0]


def test_discover_raises_after_exhausting_retries_on_transport_error() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b""), IncompleteRead(b"")])
    with pytest.raises(EuropePmcDiscoveryError, match="failed after 3 attempt"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(200, b"not json", {})])
    with pytest.raises(EuropePmcDiscoveryError, match="malformed JSON"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_missing_result_list() -> None:
    transport = FakeTransport([FakeResponse(200, json.dumps({}).encode(), {})])
    with pytest.raises(EuropePmcDiscoveryError, match="malformed"):
        _service(transport).discover("semaglutide", limit=10)


def test_discover_raises_on_result_missing_required_field() -> None:
    candidate = _full_candidate()
    del candidate["title"]
    transport = FakeTransport([_search_response(candidate)])
    with pytest.raises(EuropePmcDiscoveryError, match="missing required evidence"):
        _service(transport).discover("semaglutide", limit=10)
