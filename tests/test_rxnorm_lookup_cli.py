from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.rxnorm_lookup import RxNormLookupError, RxNormLookupResult


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self, result: RxNormLookupResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, term: str) -> RxNormLookupResult:
        self.lookup_calls.append(term)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(term: str = "semaglutide") -> RxNormLookupResult:
    return RxNormLookupResult(
        term=term,
        found=True,
        rxcui="1991302",
        name="semaglutide",
        term_type="IN",
        synonym=None,
        source_url="https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm=1991302",
        license="Non-proprietary content, National Library of Medicine (RxNorm API)",
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def _not_found_result(term: str = "xyzzy") -> RxNormLookupResult:
    return RxNormLookupResult(
        term=term,
        found=False,
        rxcui=None,
        name=None,
        term_type=None,
        synonym=None,
        source_url=None,
        license=None,
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def test_rxnorm_lookup_prints_grounding_for_a_found_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["rxnorm-lookup", "semaglutide"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["semaglutide"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "semaglutide" in unwrapped
    assert "Term type: IN" in unwrapped
    assert "1991302" in unwrapped
    assert "https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm=1991302" in unwrapped
    assert "National Library of Medicine" in unwrapped
    assert "not evidence" in unwrapped


def test_rxnorm_lookup_reports_no_concept_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["rxnorm-lookup", "xyzzy"])

    assert result.exit_code == 0, result.output
    assert "No RxNorm concept found for: xyzzy" in _unwrapped(result.output)


def test_rxnorm_lookup_surfaces_a_brand_name_synonym(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand = _found_result(term="Ozempic")
    brand = RxNormLookupResult(
        **{
            **brand.__dict__,
            "rxcui": "1991307",
            "name": "Ozempic",
            "term_type": "BN",
            "synonym": "Ozempic Pen",
        }
    )
    service = FakeLookupService(result=brand)
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["rxnorm-lookup", "Ozempic"])

    assert result.exit_code == 0, result.output
    assert "Synonym: Ozempic Pen" in _unwrapped(result.output)


def test_rxnorm_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(
        entrypoint.app, ["rxnorm-lookup", "semaglutide", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["rxcui"] == "1991302"


def test_rxnorm_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=RxNormLookupError("boom"))
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["rxnorm-lookup", "semaglutide"])

    assert result.exit_code != 0
    assert "RxNorm lookup failed" in result.output


def test_rxnorm_lookup_rejects_an_empty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(error=ValueError("Term must not be empty."))
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["rxnorm-lookup", "   "])

    assert result.exit_code != 0
