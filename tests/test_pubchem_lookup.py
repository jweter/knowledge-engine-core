from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.pubchem_lookup import (
    PUBCHEM_CONTENT_LICENSE,
    PubchemLookupError,
    PubchemLookupService,
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
) -> PubchemLookupService:
    recorded_delays = delays if delays is not None else []
    return PubchemLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _property_response(**overrides: object) -> FakeResponse:
    base: dict[str, object] = {
        "CID": 4091,
        "Title": "Metformin",
        "IUPACName": "3-(diaminomethylidene)-1,1-dimethylguanidine",
        "MolecularFormula": "C4H11N5",
        "MolecularWeight": "129.16",
        "ConnectivitySMILES": "CN(C)C(=N)N=C(N)N",
    }
    base.update(overrides)
    payload = {"PropertyTable": {"Properties": [base]}}
    return FakeResponse(status_code=200, body=json.dumps(payload).encode("utf-8"), headers={})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport([_property_response()])
    service = _service(transport)

    result = service.lookup("metformin")

    assert result.found is True
    assert result.term == "metformin"
    assert result.cid == "4091"
    assert result.title == "Metformin"
    assert result.iupac_name == "3-(diaminomethylidene)-1,1-dimethylguanidine"
    assert result.molecular_formula == "C4H11N5"
    assert result.molecular_weight == "129.16"
    assert result.smiles == "CN(C)C(=N)N=C(N)N"
    assert result.source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/4091"
    assert result.license == PUBCHEM_CONTENT_LICENSE
    assert result.retrieved_at


def test_lookup_url_encodes_the_term() -> None:
    transport = FakeTransport([_property_response(CID=11949646, Title="Empagliflozin")])
    service = _service(transport)

    service.lookup("SGLT2 inhibitor")

    assert transport.urls[0] == (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/SGLT2%20inhibitor"
        "/property/Title,IUPACName,MolecularFormula,MolecularWeight,ConnectivitySMILES/JSON"
    )


def test_lookup_declines_to_resolve_when_multiple_compounds_match() -> None:
    """Real PubChem behavior: "estrogen" resolves to two distinct CIDs (21628493,
    12115739) sharing the same synonym. Picking the first would misidentify the
    compound, so the service must decline rather than guess."""

    body = {
        "PropertyTable": {
            "Properties": [
                {"CID": 21628493, "Title": "Estrogen"},
                {"CID": 12115739, "Title": "13-methyl-..."},
            ]
        }
    }
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(body).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    result = service.lookup("estrogen")

    assert result.found is False
    assert result.cid is None


def test_lookup_returns_not_found_on_404_without_raising() -> None:
    transport = FakeTransport([FakeResponse(status_code=404, body=b"", headers={})])
    service = _service(transport)

    result = service.lookup("xyzzynonexistentcompound")

    assert result.found is False
    assert result.cid is None
    assert result.title is None
    assert result.smiles is None
    assert result.source_url is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_handles_a_numeric_molecular_weight() -> None:
    """Real PubChem behavior: MolecularWeight is sometimes a JSON number, not a string."""

    transport = FakeTransport([_property_response(MolecularWeight=129.16)])
    service = _service(transport)

    result = service.lookup("metformin")

    assert result.molecular_weight == "129.16"


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
            _property_response(),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("metformin")

    assert result.found is True
    assert len(transport.urls) == 2
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=400, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(PubchemLookupError, match="non-success status"):
        service.lookup("metformin")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(PubchemLookupError, match="failed after 3 attempt"):
        service.lookup("metformin")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(PubchemLookupError):
        service.lookup("metformin")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(PubchemLookupError, match="malformed JSON"):
        service.lookup("metformin")


def test_lookup_raises_when_response_is_missing_a_property_table() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"{}", headers={})])
    service = _service(transport)

    with pytest.raises(PubchemLookupError, match="missing required evidence"):
        service.lookup("metformin")


def test_lookup_raises_when_response_is_missing_a_cid() -> None:
    body = {"PropertyTable": {"Properties": [{"Title": "Metformin"}]}}
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(body).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    with pytest.raises(PubchemLookupError, match="missing required evidence"):
        service.lookup("metformin")


def test_lookup_tolerates_a_missing_optional_property() -> None:
    body = {"PropertyTable": {"Properties": [{"CID": 4091}]}}
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(body).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    result = service.lookup("metformin")

    assert result.found is True
    assert result.cid == "4091"
    assert result.title is None
    assert result.smiles is None


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport([_property_response()])
    service = _service(transport)

    result = service.lookup("metformin")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"cid": "4091"' in payload
    assert payload.endswith("\n")
