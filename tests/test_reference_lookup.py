from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.reference_lookup import (
    WIKIPEDIA_CONTENT_LICENSE,
    ReferenceLookupError,
    ReferenceLookupService,
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
) -> ReferenceLookupService:
    recorded_delays = delays if delays is not None else []
    return ReferenceLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _summary_response(**overrides: object) -> FakeResponse:
    base: dict[str, object] = {
        "type": "standard",
        "title": "Semaglutide",
        "description": "Anti-diabetic and anti-obesity medication",
        "extract": "Semaglutide is an anti-diabetic medication used for the treatment of "
        "type 2 diabetes.",
        "timestamp": "2026-07-28T19:10:18Z",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Semaglutide"}},
    }
    base.update(overrides)
    return FakeResponse(status_code=200, body=json.dumps(base).encode("utf-8"), headers={})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport([_summary_response()])
    service = _service(transport)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert result.term == "semaglutide"
    assert result.title == "Semaglutide"
    assert result.description == "Anti-diabetic and anti-obesity medication"
    assert result.extract is not None
    assert result.extract.startswith("Semaglutide is an anti-diabetic medication")
    assert result.page_type == "standard"
    assert result.source_url == "https://en.wikipedia.org/wiki/Semaglutide"
    assert result.license == WIKIPEDIA_CONTENT_LICENSE
    assert result.page_last_modified == "2026-07-28T19:10:18Z"
    assert result.retrieved_at


def test_lookup_url_encodes_the_term() -> None:
    transport = FakeTransport([_summary_response(title="SGLT2 inhibitor")])
    service = _service(transport)

    service.lookup("SGLT2 inhibitor")

    assert transport.urls == ["https://en.wikipedia.org/api/rest_v1/page/summary/SGLT2%20inhibitor"]


def test_lookup_returns_not_found_on_404_without_raising() -> None:
    transport = FakeTransport([FakeResponse(status_code=404, body=b'{"status":404}', headers={})])
    service = _service(transport)

    result = service.lookup("Xyzzynonexistentterm")

    assert result.found is False
    assert result.title is None
    assert result.extract is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_surfaces_a_disambiguation_page_type() -> None:
    transport = FakeTransport([_summary_response(type="disambiguation", title="Mercury")])
    service = _service(transport)

    result = service.lookup("Mercury")

    assert result.found is True
    assert result.page_type == "disambiguation"


def test_lookup_rejects_an_empty_term() -> None:
    transport = FakeTransport([])
    service = _service(transport)

    with pytest.raises(ValueError, match="Term must not be empty"):
        service.lookup("   ")


def test_lookup_retries_a_retryable_status_and_succeeds() -> None:
    delays: list[float] = []
    transport = FakeTransport(
        [
            FakeResponse(status_code=503, body=b"", headers={}),
            _summary_response(),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert len(transport.urls) == 2
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=400, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(ReferenceLookupError, match="non-success status"):
        service.lookup("semaglutide")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(ReferenceLookupError, match="failed after 3 attempt"):
        service.lookup("semaglutide")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(ReferenceLookupError):
        service.lookup("semaglutide")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(ReferenceLookupError, match="malformed JSON"):
        service.lookup("semaglutide")


def test_lookup_raises_when_response_is_missing_a_title() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"{}", headers={})])
    service = _service(transport)

    with pytest.raises(ReferenceLookupError, match="missing required evidence"):
        service.lookup("semaglutide")


def test_lookup_tolerates_a_missing_content_urls_block() -> None:
    body = {"type": "standard", "title": "Semaglutide"}
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(body).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert result.source_url is None
    assert result.description is None
    assert result.extract is None


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport([_summary_response()])
    service = _service(transport)

    result = service.lookup("semaglutide")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"title": "Semaglutide"' in payload
    assert payload.endswith("\n")
