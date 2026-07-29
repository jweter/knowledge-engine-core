from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.pubchem_lookup import PubchemLookupError, PubchemLookupResult


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self, result: PubchemLookupResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, term: str) -> PubchemLookupResult:
        self.lookup_calls.append(term)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(term: str = "metformin") -> PubchemLookupResult:
    return PubchemLookupResult(
        term=term,
        found=True,
        cid="4091",
        title="Metformin",
        iupac_name="3-(diaminomethylidene)-1,1-dimethylguanidine",
        molecular_formula="C4H11N5",
        molecular_weight="129.16",
        smiles="CN(C)C(=N)N=C(N)N",
        source_url="https://pubchem.ncbi.nlm.nih.gov/compound/4091",
        license="Public domain, U.S. government work (National Library of Medicine, PubChem)",
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def _not_found_result(term: str = "xyzzy") -> PubchemLookupResult:
    return PubchemLookupResult(
        term=term,
        found=False,
        cid=None,
        title=None,
        iupac_name=None,
        molecular_formula=None,
        molecular_weight=None,
        smiles=None,
        source_url=None,
        license=None,
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def test_pubchem_lookup_prints_grounding_for_a_found_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "PubchemLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["pubchem-lookup", "metformin"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["metformin"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Metformin" in unwrapped
    assert "C4H11N5" in unwrapped
    assert "129.16" in unwrapped
    assert "CN(C)C(=N)N=C(N)N" in unwrapped
    assert "4091" in unwrapped
    assert "https://pubchem.ncbi.nlm.nih.gov/compound/4091" in unwrapped
    assert "National Library of Medicine" in unwrapped
    assert "not evidence" in unwrapped


def test_pubchem_lookup_reports_no_compound_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "PubchemLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["pubchem-lookup", "xyzzy"])

    assert result.exit_code == 0, result.output
    assert "No PubChem compound found for: xyzzy" in _unwrapped(result.output)


def test_pubchem_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "PubchemLookupService", lambda transport: service)

    result = CliRunner().invoke(
        entrypoint.app, ["pubchem-lookup", "metformin", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["cid"] == "4091"


def test_pubchem_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=PubchemLookupError("boom"))
    monkeypatch.setattr(entrypoint, "PubchemLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["pubchem-lookup", "metformin"])

    assert result.exit_code != 0
    assert "PubChem lookup failed" in result.output


def test_pubchem_lookup_rejects_an_empty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(error=ValueError("Term must not be empty."))
    monkeypatch.setattr(entrypoint, "PubchemLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["pubchem-lookup", "   "])

    assert result.exit_code != 0
