from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead
from pathlib import Path

import pytest

from knowledge_engine.unpaywall_lookup import (
    UnpaywallLookupError,
    UnpaywallLookupService,
    parse_dois_file,
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
    email: str = "test@example.org",
    max_attempts: int = 3,
    delays: list[float] | None = None,
) -> UnpaywallLookupService:
    recorded_delays = delays if delays is not None else []
    return UnpaywallLookupService(
        transport,
        email=email,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _record_response(**overrides: object) -> FakeResponse:
    base: dict[str, object] = {
        "doi": "10.1000/example",
        "title": "Semaglutide in adults with obesity",
        "is_oa": True,
        "oa_status": "gold",
        "best_oa_location": {
            "url": "https://example.org/preprint.pdf",
            "license": "cc-by",
        },
        "oa_locations": [
            {
                "url": "https://example.org/preprint.pdf",
                "host_type": "publisher",
                "license": "cc-by",
                "is_best": True,
            },
            {
                "url": "https://repository.example.edu/paper.pdf",
                "host_type": "repository",
                "license": None,
                "is_best": False,
            },
        ],
    }
    base.update(overrides)
    return FakeResponse(200, json.dumps(base).encode(), {})


def test_lookup_parses_a_full_record() -> None:
    transport = FakeTransport([_record_response()])
    result = _service(transport).lookup("10.1000/example")

    assert result.doi == "10.1000/example"
    assert result.found is True
    assert result.record is not None
    assert result.record.title == "Semaglutide in adults with obesity"
    assert result.record.is_oa is True
    assert result.record.oa_status == "gold"
    assert result.record.best_oa_location_url == "https://example.org/preprint.pdf"
    assert result.record.best_oa_location_license == "cc-by"
    assert result.record.license_rule_result == "passed"
    assert len(result.record.oa_locations) == 2
    assert result.record.oa_locations[0].is_best is True
    assert result.record.oa_locations[1].license is None


def test_lookup_normalizes_doi_casing_and_url_prefix() -> None:
    transport = FakeTransport([_record_response()])
    result = _service(transport).lookup("https://doi.org/10.1000/EXAMPLE")

    assert result.doi == "10.1000/example"


def test_lookup_maps_cc_license_tokens_before_evaluating() -> None:
    transport = FakeTransport(
        [
            _record_response(
                best_oa_location={"url": "https://x.org/p.pdf", "license": "cc-by-nc-nd"}
            )
        ]
    )
    result = _service(transport).lookup("10.1000/example")

    assert result.record is not None
    assert result.record.license_rule_result == "unsupported_license_basis"


def test_lookup_handles_null_license() -> None:
    transport = FakeTransport(
        [_record_response(best_oa_location={"url": "https://x.org/p.pdf", "license": None})]
    )
    result = _service(transport).lookup("10.1000/example")

    assert result.record is not None
    assert result.record.license_rule_result == "incomplete_missing_license"


def test_lookup_handles_null_best_oa_location_when_not_oa() -> None:
    transport = FakeTransport(
        [_record_response(is_oa=False, best_oa_location=None, oa_locations=[])]
    )
    result = _service(transport).lookup("10.1000/example")

    assert result.record is not None
    assert result.record.is_oa is False
    assert result.record.best_oa_location_url is None
    assert result.record.license_rule_result == "incomplete_missing_license"
    assert result.record.oa_locations == ()


def test_lookup_skips_malformed_location_entries() -> None:
    transport = FakeTransport(
        [
            _record_response(
                oa_locations=[
                    {"url": "https://x.org/p.pdf", "host_type": "publisher", "is_best": True},
                    "not a dict",
                    {"host_type": "repository"},
                ]
            )
        ]
    )
    result = _service(transport).lookup("10.1000/example")

    assert result.record is not None
    assert len(result.record.oa_locations) == 1


def test_lookup_returns_not_found_on_404() -> None:
    transport = FakeTransport([FakeResponse(404, b"<html>not found</html>", {})])
    result = _service(transport).lookup("10.9999/does-not-exist")

    assert result.found is False
    assert result.record is None


def test_lookup_rejects_empty_doi() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _service(FakeTransport([])).lookup("   ")


def test_lookup_rejects_empty_email() -> None:
    with pytest.raises(ValueError, match="email must not be empty"):
        _service(FakeTransport([]), email="  ")


def test_lookup_retries_on_a_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(503, b"", {}), _record_response()])
    delays: list[float] = []
    result = _service(transport, delays=delays).lookup("10.1000/example")

    assert result.found is True
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_transport_error() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b""), IncompleteRead(b"")])
    with pytest.raises(UnpaywallLookupError, match="failed after 3 attempt"):
        _service(transport).lookup("10.1000/example")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(200, b"not json", {})])
    with pytest.raises(UnpaywallLookupError, match="malformed JSON"):
        _service(transport).lookup("10.1000/example")


def test_lookup_raises_on_missing_is_oa() -> None:
    transport = FakeTransport([FakeResponse(200, json.dumps({}).encode(), {})])
    with pytest.raises(UnpaywallLookupError, match="missing required evidence"):
        _service(transport).lookup("10.1000/example")


def test_lookup_many_queries_each_doi() -> None:
    transport = FakeTransport(
        [
            _record_response(doi="10.1000/a"),
            FakeResponse(404, b"", {}),
            _record_response(doi="10.1000/c"),
        ]
    )
    result = _service(transport).lookup_many(["10.1000/a", "10.9999/b", "10.1000/c"])

    assert result.requested_count == 3
    assert [item.found for item in result.results] == [True, False, True]


def test_lookup_many_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="At least one DOI"):
        _service(FakeTransport([])).lookup_many([])


def test_lookup_many_rejects_oversized_batch() -> None:
    with pytest.raises(ValueError, match="limited to 100"):
        _service(FakeTransport([])).lookup_many([f"10.1000/{i}" for i in range(101)])


def test_parse_dois_file_reads_a_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "dois.json"
    path.write_text(json.dumps({"dois": ["10.1000/a", "10.1000/b"]}), encoding="utf-8")

    assert parse_dois_file(path) == ("10.1000/a", "10.1000/b")


def test_parse_dois_file_rejects_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "dois.json"
    path.write_text(json.dumps({"dois": []}), encoding="utf-8")

    with pytest.raises(UnpaywallLookupError, match="non-empty"):
        parse_dois_file(path)


def test_parse_dois_file_rejects_malformed_entry(tmp_path: Path) -> None:
    path = tmp_path / "dois.json"
    path.write_text(json.dumps({"dois": ["10.1000/a", ""]}), encoding="utf-8")

    with pytest.raises(UnpaywallLookupError, match="malformed"):
        parse_dois_file(path)


def test_parse_dois_file_rejects_a_symlinked_input(tmp_path: Path) -> None:
    real_path = tmp_path / "real.json"
    real_path.write_text(json.dumps({"dois": ["10.1000/a"]}), encoding="utf-8")
    symlink_path = tmp_path / "link.json"
    symlink_path.symlink_to(real_path)

    with pytest.raises(UnpaywallLookupError, match="symbolic link"):
        parse_dois_file(symlink_path)


def test_lookup_result_to_json_round_trips() -> None:
    transport = FakeTransport([_record_response()])
    result = _service(transport).lookup("10.1000/example")
    payload = json.loads(result.to_json())

    assert payload["found"] is True
    assert payload["record"]["license_rule_result"] == "passed"
