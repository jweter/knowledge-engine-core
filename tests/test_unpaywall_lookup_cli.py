from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.unpaywall_lookup import (
    UnpaywallBatchResult,
    UnpaywallLookupResult,
    UnpaywallRecord,
)


class FakeLookupService:
    def __init__(
        self,
        result: UnpaywallLookupResult | None = None,
        batch_result: UnpaywallBatchResult | None = None,
    ) -> None:
        self.result = result
        self.batch_result = batch_result
        self.lookup_calls: list[str] = []
        self.batch_calls: list[tuple[str, ...]] = []

    def lookup(self, doi: str) -> UnpaywallLookupResult:
        self.lookup_calls.append(doi)
        assert self.result is not None
        return self.result

    def lookup_many(self, dois: list[str]) -> UnpaywallBatchResult:
        self.batch_calls.append(tuple(dois))
        assert self.batch_result is not None
        return self.batch_result


def _found_result(doi: str = "10.1000/example") -> UnpaywallLookupResult:
    record = UnpaywallRecord(
        title="Example paper",
        is_oa=True,
        oa_status="gold",
        best_oa_location_url="https://example.org/preprint.pdf",
        best_oa_location_license="cc-by",
        license_rule_result="passed",
        oa_locations=(),
    )
    return UnpaywallLookupResult(doi=doi, found=True, record=record)


def test_unpaywall_doi_lookup_writes_evidence_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    service = FakeLookupService(result=_found_result())
    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-doi-lookup", "--doi", "10.1000/example", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert service.lookup_calls == ["10.1000/example"]
    assert "Network access:" in result.output
    assert "no PDFs were downloaded" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["found"] is True
    assert payload["record"]["license_rule_result"] == "passed"


def test_unpaywall_doi_lookup_reports_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    service = FakeLookupService(
        result=UnpaywallLookupResult(doi="10.9999/missing", found=False, record=None)
    )
    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-doi-lookup", "--doi", "10.9999/missing", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "not found in Unpaywall" in result.output


def test_unpaywall_doi_lookup_requires_email(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"

    def fail_if_called() -> FakeLookupService:
        raise ValueError("KE_UNPAYWALL_EMAIL is not set. Unpaywall requires a contact email.")

    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-doi-lookup", "--doi", "10.1000/example", "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "KE_UNPAYWALL_EMAIL" in result.output
    assert not output.exists()


def test_unpaywall_doi_lookup_rejects_existing_output_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    output.write_text("existing", encoding="utf-8")
    called = False

    def fail_if_called() -> FakeLookupService:
        nonlocal called
        called = True
        raise AssertionError("should not be called")

    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-doi-lookup", "--doi", "10.1000/example", "--output", str(output)],
    )

    assert result.exit_code != 0
    assert not called


def test_unpaywall_batch_lookup_writes_evidence_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dois_file = tmp_path / "dois.json"
    dois_file.write_text(json.dumps({"dois": ["10.1000/a", "10.1000/b"]}), encoding="utf-8")
    output = tmp_path / "evidence.json"
    batch_result = UnpaywallBatchResult(
        requested_count=2,
        results=(_found_result("10.1000/a"), _found_result("10.1000/b")),
    )
    service = FakeLookupService(batch_result=batch_result)
    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-batch-lookup", "--dois-file", str(dois_file), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert service.batch_calls == [("10.1000/a", "10.1000/b")]
    normalized_output = " ".join(result.output.split())
    assert "2 found, 0 not found" in normalized_output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["requested_count"] == 2


def test_unpaywall_batch_lookup_rejects_malformed_dois_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dois_file = tmp_path / "dois.json"
    dois_file.write_text("not json", encoding="utf-8")
    output = tmp_path / "evidence.json"
    called = False

    def fail_if_called() -> FakeLookupService:
        nonlocal called
        called = True
        raise AssertionError("should not be called")

    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        ["unpaywall-batch-lookup", "--dois-file", str(dois_file), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert not called
