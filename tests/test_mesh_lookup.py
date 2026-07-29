from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.mesh_lookup import (
    MESH_CONTENT_LICENSE,
    MeshLookupError,
    MeshLookupService,
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
) -> MeshLookupService:
    recorded_delays = delays if delays is not None else []
    return MeshLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _json_response(payload: object, status_code: int = 200) -> FakeResponse:
    return FakeResponse(
        status_code=status_code, body=json.dumps(payload).encode("utf-8"), headers={}
    )


def _esearch_response(*uids: str, count: int | None = None) -> FakeResponse:
    reported_count = len(uids) if count is None else count
    return _json_response({"esearchresult": {"count": str(reported_count), "idlist": list(uids)}})


def _record(record_type: str, meshterms: list[str], **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ds_recordtype": record_type,
        "ds_meshterms": meshterms,
        "ds_meshui": "D009765",
        "ds_scopenote": "",
    }
    base.update(overrides)
    return base


def _esummary_response(records: dict[str, dict[str, object]]) -> FakeResponse:
    result: dict[str, object] = {"uids": list(records.keys())}
    result.update(records)
    return _json_response({"result": result})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport(
        [
            _esearch_response("68009765"),
            _esummary_response(
                {
                    "68009765": _record(
                        "descriptor",
                        ["Obesity"],
                        ds_meshui="D009765",
                        ds_scopenote=(
                            "A status with body weight grossly above recommended standards."
                        ),
                    )
                }
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("obesity")

    assert result.found is True
    assert result.term == "obesity"
    assert result.mesh_id == "D009765"
    assert result.heading == "Obesity"
    assert result.scope_note == "A status with body weight grossly above recommended standards."
    assert result.synonyms == ()
    assert result.source_url == "https://id.nlm.nih.gov/mesh/D009765"
    assert result.license == MESH_CONTENT_LICENSE
    assert result.retrieved_at


def test_lookup_skips_non_descriptor_candidates_sharing_the_same_meshterms() -> None:
    """Real MeSH behavior: a 'pharmacological-action' record can share entry terms
    with the true descriptor -- only the descriptor record should match."""

    transport = FakeTransport(
        [
            _esearch_response("2028264", "2027927"),
            _esummary_response(
                {
                    "2028264": _record(
                        "pharmacological-action",
                        ["Sodium-Glucose Transporter 2 Inhibitors", "SGLT2 Inhibitor"],
                        ds_meshui="D000077317",
                    ),
                    "2027927": _record(
                        "descriptor",
                        ["Sodium-Glucose Transporter 2 Inhibitors", "SGLT2 Inhibitor"],
                        ds_meshui="D000068906",
                    ),
                }
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("SGLT2 inhibitor")

    assert result.found is True
    assert result.mesh_id == "D000068906"


def test_lookup_returns_not_found_when_search_has_no_candidates() -> None:
    transport = FakeTransport([_esearch_response()])
    service = _service(transport)

    result = service.lookup("xyzzynonexistentterm")

    assert result.found is False
    assert result.mesh_id is None
    assert result.heading is None
    assert result.synonyms == ()
    assert result.source_url is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_declines_to_resolve_when_more_candidates_exist_than_fetched() -> None:
    """Real MeSH behavior: "obesity" reports far more candidates than this module
    fetches (e.g. 37, or "cancer"'s 409); if the true descriptor could be outside
    the fetched window, this must decline rather than risk a false not-found."""

    transport = FakeTransport(
        [_esearch_response("2028264", "2027927", count=409)],
    )
    service = _service(transport)

    result = service.lookup("cancer")

    assert result.found is False


def test_lookup_declines_to_resolve_when_more_than_one_exact_match_exists() -> None:
    """Never guess among multiple candidates that all claim the same entry term."""

    transport = FakeTransport(
        [
            _esearch_response("11111111", "22222222"),
            _esummary_response(
                {
                    "11111111": _record("descriptor", ["Ambiguous Term"], ds_meshui="D000001"),
                    "22222222": _record("descriptor", ["Ambiguous Term"], ds_meshui="D000002"),
                }
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("Ambiguous Term")

    assert result.found is False
    assert result.mesh_id is None


def test_lookup_returns_not_found_when_no_candidate_is_an_exact_descriptor_match() -> None:
    """Real MeSH behavior: 'GLP-1 receptor agonist' (singular) has no exact entry
    term -- only the plural 'Agonists' form exists -- so this must not guess."""

    transport = FakeTransport(
        [
            _esearch_response("2106687", "2106625"),
            _esummary_response(
                {
                    "2106687": _record(
                        "pharmacological-action", ["Glucagon-Like Peptide-1 Receptor Agonists"]
                    ),
                    "2106625": _record(
                        "descriptor",
                        ["Glucagon-Like Peptide-1 Receptor Agonists", "GLP-1 Receptor Agonists"],
                    ),
                }
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("GLP-1 receptor agonist")

    assert result.found is False


def test_lookup_matches_case_insensitively() -> None:
    transport = FakeTransport(
        [
            _esearch_response("68009765"),
            _esummary_response({"68009765": _record("descriptor", ["Obesity"])}),
        ]
    )
    service = _service(transport)

    result = service.lookup("OBESITY")

    assert result.found is True
    assert result.heading == "Obesity"


def test_lookup_returns_remaining_meshterms_as_synonyms() -> None:
    transport = FakeTransport(
        [
            _esearch_response("68003924"),
            _esummary_response(
                {
                    "68003924": _record(
                        "descriptor",
                        ["Diabetes Mellitus, Type 2", "Type 2 Diabetes", "NIDDM"],
                        ds_meshui="D003924",
                    )
                }
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("type 2 diabetes")

    assert result.found is True
    assert result.heading == "Diabetes Mellitus, Type 2"
    assert result.synonyms == ("Type 2 Diabetes", "NIDDM")


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
            _esearch_response("68009765"),
            _esummary_response({"68009765": _record("descriptor", ["Obesity"])}),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("obesity")

    assert result.found is True
    assert len(transport.urls) == 3
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=400, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(MeshLookupError, match="non-success status"):
        service.lookup("obesity")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(MeshLookupError, match="failed after 3 attempt"):
        service.lookup("obesity")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(MeshLookupError):
        service.lookup("obesity")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(MeshLookupError, match="malformed JSON"):
        service.lookup("obesity")


def test_lookup_raises_when_esearch_response_is_missing_idlist() -> None:
    transport = FakeTransport([_json_response({"esearchresult": {}})])
    service = _service(transport)

    with pytest.raises(MeshLookupError, match="malformed evidence"):
        service.lookup("obesity")


def test_lookup_raises_when_esummary_response_is_malformed() -> None:
    transport = FakeTransport([_esearch_response("68009765"), _json_response({})])
    service = _service(transport)

    with pytest.raises(MeshLookupError, match="missing required evidence"):
        service.lookup("obesity")


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport(
        [
            _esearch_response("68009765"),
            _esummary_response({"68009765": _record("descriptor", ["Obesity"])}),
        ]
    )
    service = _service(transport)

    result = service.lookup("obesity")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"mesh_id": "D009765"' in payload
    assert payload.endswith("\n")
