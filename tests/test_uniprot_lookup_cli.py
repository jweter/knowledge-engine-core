from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.uniprot_lookup import (
    UNIPROT_CONTENT_LICENSE,
    UniProtLookupError,
    UniProtLookupResult,
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self,
        result: UniProtLookupResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, term: str) -> UniProtLookupResult:
        self.lookup_calls.append(term)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(term: str = "GLP-1 receptor") -> UniProtLookupResult:
    return UniProtLookupResult(
        term=term,
        found=True,
        accession="P43220",
        entry_name="GLP1R_HUMAN",
        protein_name="Glucagon-like peptide 1 receptor",
        gene_name="GLP1R",
        organism="Homo sapiens",
        function="G protein-coupled receptor for GLP-1.",
        sequence_length=463,
        source_url="https://www.uniprot.org/uniprotkb/P43220/entry",
        license=UNIPROT_CONTENT_LICENSE,
        retrieved_at="2026-08-11T00:00:00+00:00",
    )


def _not_found_result(term: str = "not a real protein") -> UniProtLookupResult:
    return UniProtLookupResult(
        term=term,
        found=False,
        accession=None,
        entry_name=None,
        protein_name=None,
        gene_name=None,
        organism=None,
        function=None,
        sequence_length=None,
        source_url=None,
        license=None,
        retrieved_at="2026-08-11T00:00:00+00:00",
    )


def test_uniprot_lookup_prints_grounding_for_a_found_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "UniProtLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["uniprot-lookup", "GLP-1 receptor"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["GLP-1 receptor"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Glucagon-like peptide 1 receptor" in unwrapped
    assert "GLP1R" in unwrapped
    assert "Homo sapiens" in unwrapped
    assert "G protein-coupled receptor for GLP-1." in unwrapped
    assert "https://www.uniprot.org/uniprotkb/P43220/entry" in unwrapped
    assert "not evidence" in unwrapped


def test_uniprot_lookup_reports_no_entry_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "UniProtLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["uniprot-lookup", "not a real protein"])

    assert result.exit_code == 0, result.output
    assert "No UniProt entry found for: not a real protein" in _unwrapped(result.output)


def test_uniprot_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "UniProtLookupService", lambda transport: service)

    result = CliRunner().invoke(
        entrypoint.app,
        ["uniprot-lookup", "GLP-1 receptor", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["accession"] == "P43220"


def test_uniprot_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=UniProtLookupError("boom"))
    monkeypatch.setattr(entrypoint, "UniProtLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["uniprot-lookup", "GLP-1 receptor"])

    assert result.exit_code != 0
    assert "UniProt lookup failed" in result.output


def test_uniprot_lookup_rejects_an_empty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(error=ValueError("UniProt lookup term must not be empty."))
    monkeypatch.setattr(entrypoint, "UniProtLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["uniprot-lookup", "   "])

    assert result.exit_code != 0
