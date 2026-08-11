from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.uniprot_lookup import (
    UNIPROT_CONTENT_LICENSE,
    UniProtLookupError,
    UniProtLookupService,
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
) -> UniProtLookupService:
    recorded_delays = delays if delays is not None else []
    return UniProtLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "primaryAccession": "P43220",
        "uniProtkbId": "GLP1R_HUMAN",
        "organism": {"scientificName": "Homo sapiens"},
        "proteinDescription": {
            "recommendedName": {"fullName": {"value": "Glucagon-like peptide 1 receptor"}}
        },
        "genes": [{"geneName": {"value": "GLP1R"}}],
        "comments": [
            {
                "commentType": "FUNCTION",
                "texts": [{"value": "G protein-coupled receptor for GLP-1."}],
            }
        ],
        "sequence": {"length": 463},
    }
    entry.update(overrides)
    return entry


def _search_response(*entries: dict[str, object]) -> FakeResponse:
    payload = {"results": list(entries)}
    return FakeResponse(status_code=200, body=json.dumps(payload).encode("utf-8"), headers={})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport([_search_response(_entry())])
    service = _service(transport)

    result = service.lookup("GLP-1 receptor")

    assert result.found is True
    assert result.term == "GLP-1 receptor"
    assert result.accession == "P43220"
    assert result.entry_name == "GLP1R_HUMAN"
    assert result.protein_name == "Glucagon-like peptide 1 receptor"
    assert result.gene_name == "GLP1R"
    assert result.organism == "Homo sapiens"
    assert result.function == "G protein-coupled receptor for GLP-1."
    assert result.sequence_length == 463
    assert result.source_url == "https://www.uniprot.org/uniprotkb/P43220/entry"
    assert result.license == UNIPROT_CONTENT_LICENSE
    assert result.retrieved_at


def test_lookup_builds_a_quoted_human_reviewed_query() -> None:
    transport = FakeTransport([_search_response(_entry())])
    service = _service(transport)

    service.lookup("GLP-1 receptor")

    assert "query=%22GLP-1+receptor%22" in transport.urls[0]
    assert "organism_id%3A9606" in transport.urls[0]
    assert "reviewed%3Atrue" in transport.urls[0]


def test_lookup_escapes_embedded_quotes_in_the_term() -> None:
    transport = FakeTransport([_search_response(_entry())])
    service = _service(transport)

    service.lookup('weird "term"')

    assert "weird+%5C%22term%5C%22" in transport.urls[0]


def test_lookup_returns_not_found_on_empty_results_without_raising() -> None:
    """Real UniProt behavior: an unmatched term returns 200 with an empty results array."""

    transport = FakeTransport([_search_response()])
    service = _service(transport)

    result = service.lookup("zzznonexistentproteinxyz")

    assert result.found is False
    assert result.accession is None
    assert result.function is None
    assert result.source_url is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_rejects_an_empty_term() -> None:
    transport = FakeTransport([])
    service = _service(transport)

    with pytest.raises(ValueError, match="term must not be empty"):
        service.lookup("   ")


def test_lookup_retries_a_retryable_status_and_succeeds() -> None:
    delays: list[float] = []
    transport = FakeTransport(
        [
            FakeResponse(status_code=503, body=b"", headers={}),
            _search_response(_entry()),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("GLP-1 receptor")

    assert result.found is True
    assert len(transport.urls) == 2
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=400, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(UniProtLookupError, match="non-success status"):
        service.lookup("GLP-1 receptor")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(UniProtLookupError, match="failed after 3 attempt"):
        service.lookup("GLP-1 receptor")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(UniProtLookupError):
        service.lookup("GLP-1 receptor")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(UniProtLookupError, match="malformed JSON"):
        service.lookup("GLP-1 receptor")


def test_lookup_raises_when_response_is_missing_a_results_field() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"{}", headers={})])
    service = _service(transport)

    with pytest.raises(UniProtLookupError, match="missing required evidence"):
        service.lookup("GLP-1 receptor")


def test_lookup_tolerates_missing_optional_fields() -> None:
    payload = {"results": [{"primaryAccession": "P43220"}]}
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(payload).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    result = service.lookup("GLP-1 receptor")

    assert result.found is True
    assert result.accession == "P43220"
    assert result.protein_name is None
    assert result.gene_name is None
    assert result.function is None
    assert result.sequence_length is None


def test_lookup_ignores_a_function_comment_missing_text() -> None:
    transport = FakeTransport(
        [_search_response(_entry(comments=[{"commentType": "FUNCTION", "texts": []}]))]
    )
    service = _service(transport)

    result = service.lookup("GLP-1 receptor")

    assert result.function is None


def test_lookup_skips_non_function_comments() -> None:
    transport = FakeTransport(
        [
            _search_response(
                _entry(
                    comments=[
                        {"commentType": "SUBUNIT", "texts": [{"value": "Homodimer."}]},
                        {"commentType": "FUNCTION", "texts": [{"value": "Real function."}]},
                    ]
                )
            )
        ]
    )
    service = _service(transport)

    result = service.lookup("GLP-1 receptor")

    assert result.function == "Real function."


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport([_search_response(_entry())])
    service = _service(transport)

    result = service.lookup("GLP-1 receptor")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"accession": "P43220"' in payload
    assert payload.endswith("\n")
