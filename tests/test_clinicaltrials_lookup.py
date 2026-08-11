from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.clinicaltrials_lookup import (
    CLINICALTRIALS_CONTENT_LICENSE,
    ClinicalTrialsLookupError,
    ClinicalTrialsLookupService,
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
) -> ClinicalTrialsLookupService:
    recorded_delays = delays if delays is not None else []
    return ClinicalTrialsLookupService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _study_response(**overrides: object) -> FakeResponse:
    protocol_section: dict[str, object] = {
        "identificationModule": {
            "nctId": "NCT03652870",
            "briefTitle": "Antidepressants Trial in Parkinson's Disease",
            "officialTitle": (
                "A Randomised Placebo-Controlled Trial of Escitalopram and "
                "Nortriptyline With Standard Psychological Care for Depression "
                "in Parkinson's Disease"
            ),
        },
        "statusModule": {"overallStatus": "COMPLETED"},
        "designModule": {
            "studyType": "INTERVENTIONAL",
            "phases": ["PHASE3"],
            "enrollmentInfo": {"count": 52, "type": "ACTUAL"},
        },
        "conditionsModule": {"conditions": ["Depression", "Parkinson Disease"]},
        "armsInterventionsModule": {
            "interventions": [
                {"name": "Nortriptyline"},
                {"name": "Escitalopram"},
                {"name": "Placebo"},
            ]
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "University College, London", "class": "OTHER"}
        },
        "descriptionModule": {"briefSummary": "A randomised trial in an NHS setting."},
    }
    protocol_section.update(overrides)
    payload = {"protocolSection": protocol_section}
    return FakeResponse(status_code=200, body=json.dumps(payload).encode("utf-8"), headers={})


def test_lookup_returns_a_found_result_with_grounding_fields() -> None:
    transport = FakeTransport([_study_response()])
    service = _service(transport)

    result = service.lookup("NCT03652870")

    assert result.found is True
    assert result.nct_id == "NCT03652870"
    assert result.brief_title == "Antidepressants Trial in Parkinson's Disease"
    assert result.overall_status == "COMPLETED"
    assert result.phases == ("PHASE3",)
    assert result.study_type == "INTERVENTIONAL"
    assert result.conditions == ("Depression", "Parkinson Disease")
    assert result.interventions == ("Nortriptyline", "Escitalopram", "Placebo")
    assert result.enrollment_count == 52
    assert result.lead_sponsor == "University College, London"
    assert result.brief_summary == "A randomised trial in an NHS setting."
    assert result.source_url == "https://clinicaltrials.gov/study/NCT03652870"
    assert result.license == CLINICALTRIALS_CONTENT_LICENSE
    assert result.retrieved_at


def test_lookup_url_encodes_the_id() -> None:
    transport = FakeTransport([_study_response()])
    service = _service(transport)

    service.lookup("NCT03652870")

    assert transport.urls[0] == (
        "https://clinicaltrials.gov/api/v2/studies/NCT03652870?format=json"
    )


def test_lookup_returns_not_found_on_404_without_raising() -> None:
    """Real ClinicalTrials.gov behavior: a well-formed but unregistered ID returns 404."""

    transport = FakeTransport([FakeResponse(status_code=404, body=b"", headers={})])
    service = _service(transport)

    result = service.lookup("NCT99999999")

    assert result.found is False
    assert result.brief_title is None
    assert result.phases == ()
    assert result.interventions == ()
    assert result.source_url is None
    assert result.license is None
    assert result.retrieved_at


def test_lookup_returns_not_found_on_400_without_raising() -> None:
    """Real ClinicalTrials.gov behavior: a malformed ID returns 400
    ("Parameter `nctId` has incorrect format"), not 404 -- treated the same as
    not-found rather than a hard error, since neither implies more than "no
    matching registration for this input."""

    transport = FakeTransport(
        [
            FakeResponse(
                status_code=400,
                body=b"Parameter `nctId` has incorrect format",
                headers={},
            )
        ]
    )
    service = _service(transport)

    result = service.lookup("not-an-nct-id")

    assert result.found is False


def test_lookup_rejects_an_empty_id() -> None:
    transport = FakeTransport([])
    service = _service(transport)

    with pytest.raises(ValueError, match="NCT ID must not be empty"):
        service.lookup("   ")


def test_lookup_retries_a_retryable_status_and_succeeds() -> None:
    delays: list[float] = []
    transport = FakeTransport(
        [
            FakeResponse(status_code=503, body=b"", headers={}),
            _study_response(),
        ]
    )
    service = _service(transport, delays=delays)

    result = service.lookup("NCT03652870")

    assert result.found is True
    assert len(transport.urls) == 2
    assert delays == [2.0]


def test_lookup_raises_after_exhausting_retries_on_a_non_retryable_status() -> None:
    transport = FakeTransport([FakeResponse(status_code=403, body=b"", headers={})])
    service = _service(transport)

    with pytest.raises(ClinicalTrialsLookupError, match="non-success status"):
        service.lookup("NCT03652870")


def test_lookup_raises_after_exhausting_retries_on_a_transport_error() -> None:
    transport = FakeTransport([OSError("boom"), OSError("boom"), OSError("boom")])
    service = _service(transport, max_attempts=3)

    with pytest.raises(ClinicalTrialsLookupError, match="failed after 3 attempt"):
        service.lookup("NCT03652870")


def test_lookup_raises_on_incomplete_read_after_retries() -> None:
    transport = FakeTransport([IncompleteRead(b""), IncompleteRead(b"")])
    service = _service(transport, max_attempts=2)

    with pytest.raises(ClinicalTrialsLookupError):
        service.lookup("NCT03652870")


def test_lookup_raises_on_malformed_json() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"not json", headers={})])
    service = _service(transport)

    with pytest.raises(ClinicalTrialsLookupError, match="malformed JSON"):
        service.lookup("NCT03652870")


def test_lookup_raises_when_response_is_missing_a_protocol_section() -> None:
    transport = FakeTransport([FakeResponse(status_code=200, body=b"{}", headers={})])
    service = _service(transport)

    with pytest.raises(ClinicalTrialsLookupError, match="missing required evidence"):
        service.lookup("NCT03652870")


def test_lookup_tolerates_missing_optional_fields() -> None:
    payload = {"protocolSection": {"identificationModule": {"nctId": "NCT03652870"}}}
    transport = FakeTransport(
        [FakeResponse(status_code=200, body=json.dumps(payload).encode("utf-8"), headers={})]
    )
    service = _service(transport)

    result = service.lookup("NCT03652870")

    assert result.found is True
    assert result.nct_id == "NCT03652870"
    assert result.brief_title is None
    assert result.phases == ()
    assert result.interventions == ()
    assert result.enrollment_count is None


def test_lookup_ignores_interventions_missing_a_name() -> None:
    transport = FakeTransport(
        [_study_response(armsInterventionsModule={"interventions": [{"type": "DRUG"}]})]
    )
    service = _service(transport)

    result = service.lookup("NCT03652870")

    assert result.interventions == ()


def test_to_json_is_stable_and_complete() -> None:
    transport = FakeTransport([_study_response()])
    service = _service(transport)

    result = service.lookup("NCT03652870")
    payload = result.to_json()

    assert '"found": true' in payload
    assert '"nct_id": "NCT03652870"' in payload
    assert payload.endswith("\n")
