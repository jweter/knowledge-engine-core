from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.clinicaltrials_lookup import (
    CLINICALTRIALS_CONTENT_LICENSE,
    ClinicalTrialsLookupError,
    ClinicalTrialsLookupResult,
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self,
        result: ClinicalTrialsLookupResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, nct_id: str) -> ClinicalTrialsLookupResult:
        self.lookup_calls.append(nct_id)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(nct_id: str = "NCT03652870") -> ClinicalTrialsLookupResult:
    return ClinicalTrialsLookupResult(
        nct_id=nct_id,
        found=True,
        brief_title="Antidepressants Trial in Parkinson's Disease",
        official_title=(
            "A Randomised Placebo-Controlled Trial of Escitalopram and Nortriptyline "
            "With Standard Psychological Care for Depression in Parkinson's Disease"
        ),
        overall_status="COMPLETED",
        phases=("PHASE3",),
        study_type="INTERVENTIONAL",
        conditions=("Depression", "Parkinson Disease"),
        interventions=("Nortriptyline", "Escitalopram", "Placebo"),
        enrollment_count=52,
        lead_sponsor="University College, London",
        brief_summary="A randomised trial in an NHS setting.",
        source_url="https://clinicaltrials.gov/study/NCT03652870",
        license=CLINICALTRIALS_CONTENT_LICENSE,
        retrieved_at="2026-08-10T00:00:00+00:00",
    )


def _not_found_result(nct_id: str = "NCT99999999") -> ClinicalTrialsLookupResult:
    return ClinicalTrialsLookupResult(
        nct_id=nct_id,
        found=False,
        brief_title=None,
        official_title=None,
        overall_status=None,
        phases=(),
        study_type=None,
        conditions=(),
        interventions=(),
        enrollment_count=None,
        lead_sponsor=None,
        brief_summary=None,
        source_url=None,
        license=None,
        retrieved_at="2026-08-10T00:00:00+00:00",
    )


def test_clinicaltrials_lookup_prints_grounding_for_a_found_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "ClinicalTrialsLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["clinicaltrials-lookup", "NCT03652870"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["NCT03652870"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Antidepressants Trial in Parkinson's Disease" in unwrapped
    assert "COMPLETED" in unwrapped
    assert "PHASE3" in unwrapped
    assert "Depression, Parkinson Disease" in unwrapped
    assert "Nortriptyline, Escitalopram, Placebo" in unwrapped
    assert "52" in unwrapped
    assert "University College, London" in unwrapped
    assert "https://clinicaltrials.gov/study/NCT03652870" in unwrapped
    assert "not evidence" in unwrapped


def test_clinicaltrials_lookup_reports_no_study_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "ClinicalTrialsLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["clinicaltrials-lookup", "NCT99999999"])

    assert result.exit_code == 0, result.output
    assert "No ClinicalTrials.gov study found for: NCT99999999" in _unwrapped(result.output)


def test_clinicaltrials_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "ClinicalTrialsLookupService", lambda transport: service)

    result = CliRunner().invoke(
        entrypoint.app,
        ["clinicaltrials-lookup", "NCT03652870", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["nct_id"] == "NCT03652870"


def test_clinicaltrials_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=ClinicalTrialsLookupError("boom"))
    monkeypatch.setattr(entrypoint, "ClinicalTrialsLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["clinicaltrials-lookup", "NCT03652870"])

    assert result.exit_code != 0
    assert "ClinicalTrials.gov lookup failed" in result.output


def test_clinicaltrials_lookup_rejects_an_empty_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=ValueError("NCT ID must not be empty."))
    monkeypatch.setattr(entrypoint, "ClinicalTrialsLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["clinicaltrials-lookup", "   "])

    assert result.exit_code != 0
