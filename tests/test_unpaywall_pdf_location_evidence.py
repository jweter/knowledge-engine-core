from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from knowledge_engine.unpaywall_http import TransportResponse
from knowledge_engine.unpaywall_lookup import UnpaywallLookupService


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, max_response_bytes
        return self.response


def test_lookup_preserves_direct_pdf_separately_from_landing_location() -> None:
    payload = {
        "title": "A paper",
        "is_oa": True,
        "oa_status": "green",
        "best_oa_location": {
            "url": "https://core.ac.uk/works/123",
            "url_for_pdf": "https://core.ac.uk/download/123.pdf",
            "license": "cc-by",
        },
        "oa_locations": [
            {
                "url": "https://core.ac.uk/works/123",
                "url_for_pdf": "https://core.ac.uk/download/123.pdf",
                "host_type": "repository",
                "license": "cc-by",
                "is_best": True,
            }
        ],
    }
    service = UnpaywallLookupService(
        FakeTransport(FakeResponse(200, json.dumps(payload).encode("utf-8"), {})),
        email="test@example.org",
        request_interval_seconds=0.0,
    )

    result = service.lookup("10.1000/example")

    assert result.record is not None
    assert result.record.best_oa_location_url == "https://core.ac.uk/works/123"
    assert result.record.best_oa_location_pdf_url == "https://core.ac.uk/download/123.pdf"
    assert result.record.oa_locations[0].pdf_url == "https://core.ac.uk/download/123.pdf"


def test_lookup_keeps_missing_direct_pdf_explicitly_none() -> None:
    payload = {
        "title": "A paper",
        "is_oa": True,
        "oa_status": "green",
        "best_oa_location": {
            "url": "https://publisher.example/article",
            "license": "cc-by",
        },
        "oa_locations": [],
    }
    service = UnpaywallLookupService(
        FakeTransport(FakeResponse(200, json.dumps(payload).encode("utf-8"), {})),
        email="test@example.org",
        request_interval_seconds=0.0,
    )

    result = service.lookup("10.1000/example")

    assert result.record is not None
    assert result.record.best_oa_location_pdf_url is None
