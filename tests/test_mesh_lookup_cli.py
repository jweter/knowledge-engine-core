from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.mesh_lookup import MeshLookupError, MeshLookupResult


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self, result: MeshLookupResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, term: str) -> MeshLookupResult:
        self.lookup_calls.append(term)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(term: str = "obesity") -> MeshLookupResult:
    return MeshLookupResult(
        term=term,
        found=True,
        mesh_id="D009765",
        heading="Obesity",
        scope_note="A status with body weight grossly above recommended standards.",
        synonyms=(),
        source_url="https://id.nlm.nih.gov/mesh/D009765",
        license="Free, non-proprietary content, National Library of Medicine (MeSH)",
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def _not_found_result(term: str = "xyzzy") -> MeshLookupResult:
    return MeshLookupResult(
        term=term,
        found=False,
        mesh_id=None,
        heading=None,
        scope_note=None,
        synonyms=(),
        source_url=None,
        license=None,
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def test_mesh_lookup_prints_grounding_for_a_found_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "obesity"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["obesity"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Obesity" in unwrapped
    assert "body weight grossly above" in unwrapped
    assert "D009765" in unwrapped
    assert "https://id.nlm.nih.gov/mesh/D009765" in unwrapped
    assert "National Library of Medicine" in unwrapped
    assert "not evidence" in unwrapped


def test_mesh_lookup_reports_no_descriptor_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "xyzzy"])

    assert result.exit_code == 0, result.output
    assert "No exact MeSH descriptor found for: xyzzy" in _unwrapped(result.output)


def test_mesh_lookup_surfaces_synonyms(monkeypatch: pytest.MonkeyPatch) -> None:
    result_with_synonyms = MeshLookupResult(
        **{
            **_found_result(term="type 2 diabetes").__dict__,
            "mesh_id": "D003924",
            "heading": "Diabetes Mellitus, Type 2",
            "synonyms": ("Type 2 Diabetes", "NIDDM"),
        }
    )
    service = FakeLookupService(result=result_with_synonyms)
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "type 2 diabetes"])

    assert result.exit_code == 0, result.output
    assert "Synonyms: Type 2 Diabetes, NIDDM" in _unwrapped(result.output)


def test_mesh_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "obesity", "--output", str(output)])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["mesh_id"] == "D009765"


def test_mesh_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=MeshLookupError("boom"))
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "obesity"])

    assert result.exit_code != 0
    assert "MeSH lookup failed" in result.output


def test_mesh_lookup_rejects_an_empty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(error=ValueError("Term must not be empty."))
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["mesh-lookup", "   "])

    assert result.exit_code != 0
