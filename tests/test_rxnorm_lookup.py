from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.rxnorm_lookup import (
    RXNORM_CONTENT_LICENSE,
    RxNormIngredient,
    RxNormLookupError,
    RxNormLookupService,
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
) -> RxNormLookupService:
    recorded_delays = delays if delays is not None else []
    return RxNormLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _json_response(payload: object, status_code: int = 200) -> FakeResponse:
    return FakeResponse(
        status_code=status_code, body=json.dumps(payload).encode("utf-8"), headers={}
    )


def _rxcui_response(*ids: str) -> FakeResponse:
    return _json_response({"idGroup": {"rxnormId": list(ids)} if ids else {}})


def _properties_response(**overrides: object) -> FakeResponse:
    base: dict[str, object] = {
        "rxcui": "1991302",
        "name": "semaglutide",
        "synonym": "",
        "tty": "IN",
        "language": "ENG",
        "suppress": "N",
        "umlscui": "",
    }
    base.update(overrides)
    return _json_response({"properties": base})


def _related_response(*ingredients: tuple[str, str]) -> FakeResponse:
    """A `related.json?tty=IN` response naming zero or more ingredient concepts."""

    group: dict[str, object] = {"tty": "IN"}
    if ingredients:
        group["conceptProperties"] = [
            {"rxcui": rxcui, "name": name, "tty": "IN"} for rxcui, name in ingredients
        ]
    return _json_response({"relatedGroup": {"rxcui": None, "conceptGroup": [group]}})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1991302"),
            _properties_response(),
            _related_response(("1991302", "semaglutide")),
        ]
    )
    service = _service(transport)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert result.term == "semaglutide"
    assert result.rxcui == "1991302"
    assert result.name == "semaglutide"
    assert result.term_type == "IN"
    assert result.synonym is None
    assert result.ingredients == (RxNormIngredient(rxcui="1991302", name="semaglutide"),)
    assert result.source_url == (
        "https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm=1991302"
    )
    assert result.license == RXNORM_CONTENT_LICENSE
    assert result.retrieved_at


def test_lookup_url_encodes_the_term() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1545653"),
            _properties_response(rxcui="1545653", name="empagliflozin"),
            _related_response(("1545653", "empagliflozin")),
        ]
    )
    service = _service(transport)

    service.lookup("SGLT2 inhibitor")

    assert transport.urls[0] == "https://rxnav.nlm.nih.gov/REST/rxcui.json?name=SGLT2%20inhibitor"


def test_lookup_returns_not_found_when_rxnorm_has_no_match() -> None:
    transport = FakeTransport([_rxcui_response()])
    service = _service(transport)

    result = service.lookup("mitochondria")

    assert result.found is False
    assert result.rxcui is None
    assert result.name is None
    assert result.ingredients == ()
    assert result.source_url is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_normalizes_a_brand_name_to_the_same_ingredient_as_its_generic() -> None:
    """A brand name and its generic have different rxcuis but must share `ingredients`."""

    generic_transport = FakeTransport(
        [
            _rxcui_response("1991302"),
            _properties_response(),
            _related_response(("1991302", "semaglutide")),
        ]
    )
    brand_transport = FakeTransport(
        [
            _rxcui_response("1991307"),
            _properties_response(rxcui="1991307", name="Ozempic", tty="BN"),
            _related_response(("1991302", "semaglutide")),
        ]
    )

    generic_result = _service(generic_transport).lookup("semaglutide")
    brand_result = _service(brand_transport).lookup("Ozempic")

    assert generic_result.rxcui != brand_result.rxcui
    assert generic_result.ingredients == brand_result.ingredients
    assert brand_result.ingredients == (RxNormIngredient(rxcui="1991302", name="semaglutide"),)


def test_lookup_resolves_multiple_ingredients_for_a_combination_drug() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1602110"),
            _properties_response(rxcui="1602110", name="Glyxambi", tty="BN"),
            _related_response(
                ("1100699", "linagliptin"),
                ("1545653", "empagliflozin"),
            ),
        ]
    )
    service = _service(transport)

    result = service.lookup("Glyxambi")

    assert result.ingredients == (
        RxNormIngredient(rxcui="1100699", name="linagliptin"),
        RxNormIngredient(rxcui="1545653", name="empagliflozin"),
    )


def test_lookup_tolerates_a_concept_with_no_related_ingredients() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1649570"),
            _properties_response(rxcui="1649570", name="Auto-Injector", tty="DF"),
            _related_response(),
        ]
    )
    service = _service(transport)

    result = service.lookup("Auto-Injector")

    assert result.found is True
    assert result.ingredients == ()


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
            _rxcui_response("1991302"),
            _properties_response(),
            _related_response(("1991302", "semaglutide")),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert len(transport.urls) == 4
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=400, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(RxNormLookupError, match="non-success status"):
        service.lookup("semaglutide")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(RxNormLookupError, match="failed after 3 attempt"):
        service.lookup("semaglutide")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(RxNormLookupError):
        service.lookup("semaglutide")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(RxNormLookupError, match="malformed JSON"):
        service.lookup("semaglutide")


def test_lookup_raises_when_rxcui_response_is_missing_id_group() -> None:
    transport = FakeTransport([_json_response({})])
    service = _service(transport)

    with pytest.raises(RxNormLookupError, match="missing required evidence"):
        service.lookup("semaglutide")


def test_lookup_raises_when_properties_response_is_malformed() -> None:
    transport = FakeTransport([_rxcui_response("1991302"), _json_response({})])
    service = _service(transport)

    with pytest.raises(RxNormLookupError, match="missing required evidence"):
        service.lookup("semaglutide")


def test_lookup_raises_when_related_response_is_malformed() -> None:
    transport = FakeTransport(
        [_rxcui_response("1991302"), _properties_response(), _json_response({})]
    )
    service = _service(transport)

    with pytest.raises(RxNormLookupError, match="missing required evidence"):
        service.lookup("semaglutide")


def test_lookup_uses_the_first_rxcui_when_more_than_one_matches() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1991302", "9999999"),
            _properties_response(),
            _related_response(("1991302", "semaglutide")),
        ]
    )
    service = _service(transport)

    result = service.lookup("semaglutide")

    assert result.found is True
    assert result.rxcui == "1991302"


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport(
        [
            _rxcui_response("1991302"),
            _properties_response(),
            _related_response(("1991302", "semaglutide")),
        ]
    )
    service = _service(transport)

    result = service.lookup("semaglutide")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"rxcui": "1991302"' in payload
    assert '"ingredients"' in payload
    assert payload.endswith("\n")
