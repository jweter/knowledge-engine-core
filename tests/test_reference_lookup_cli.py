from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.reference_lookup import ReferenceLookupError, ReferenceLookupResult


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeLookupService:
    def __init__(
        self, result: ReferenceLookupResult | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.lookup_calls: list[str] = []

    def lookup(self, term: str) -> ReferenceLookupResult:
        self.lookup_calls.append(term)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _found_result(term: str = "semaglutide") -> ReferenceLookupResult:
    return ReferenceLookupResult(
        term=term,
        found=True,
        title="Semaglutide",
        description="Anti-diabetic and anti-obesity medication",
        extract="Semaglutide is an anti-diabetic medication used for the treatment of "
        "type 2 diabetes.",
        page_type="standard",
        source_url="https://en.wikipedia.org/wiki/Semaglutide",
        revision="1366562225",
        permanent_url="https://en.wikipedia.org/wiki/Semaglutide?oldid=1366562225",
        license="CC BY-SA",
        page_last_modified="2026-07-28T19:10:18Z",
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def _not_found_result(term: str = "xyzzy") -> ReferenceLookupResult:
    return ReferenceLookupResult(
        term=term,
        found=False,
        title=None,
        description=None,
        extract=None,
        page_type=None,
        source_url=None,
        revision=None,
        permanent_url=None,
        license=None,
        page_last_modified=None,
        retrieved_at="2026-07-29T00:00:00+00:00",
    )


def test_reference_lookup_prints_grounding_for_a_found_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["reference-lookup", "semaglutide"])

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["semaglutide"]
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Semaglutide" in unwrapped
    assert "Anti-diabetic and anti-obesity medication" in unwrapped
    assert "type 2 diabetes" in unwrapped
    assert "https://en.wikipedia.org/wiki/Semaglutide" in unwrapped
    assert "CC BY-SA" in unwrapped
    assert "not evidence" in unwrapped
    assert "Permanent link" in unwrapped
    assert "https://en.wikipedia.org/wiki/Semaglutide?oldid=1366562225" in unwrapped


def test_reference_lookup_reports_no_article_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(result=_not_found_result())
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["reference-lookup", "xyzzy"])

    assert result.exit_code == 0, result.output
    assert "No Wikipedia article found for: xyzzy" in _unwrapped(result.output)


def test_reference_lookup_surfaces_a_non_standard_page_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disambiguation = _found_result(term="mercury")
    disambiguation = ReferenceLookupResult(
        **{**disambiguation.__dict__, "page_type": "disambiguation", "title": "Mercury"}
    )
    service = FakeLookupService(result=disambiguation)
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["reference-lookup", "mercury"])

    assert result.exit_code == 0, result.output
    assert "Page type: disambiguation" in _unwrapped(result.output)


def test_reference_lookup_writes_output_json_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "lookup.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(
        entrypoint.app, ["reference-lookup", "semaglutide", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["title"] == "Semaglutide"


def test_reference_lookup_exits_nonzero_on_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeLookupService(error=ReferenceLookupError("boom"))
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["reference-lookup", "semaglutide"])

    assert result.exit_code != 0
    assert "Reference lookup failed" in result.output


def test_reference_lookup_rejects_an_empty_term(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeLookupService(error=ValueError("Term must not be empty."))
    monkeypatch.setattr(entrypoint, "ReferenceLookupService", lambda transport: service)

    result = CliRunner().invoke(entrypoint.app, ["reference-lookup", "   "])

    assert result.exit_code != 0
