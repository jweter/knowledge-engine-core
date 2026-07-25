from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.core_discovery import CoreCandidate, CoreDiscoveryResult


class FakeDiscoveryService:
    def __init__(self, result: CoreDiscoveryResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int, int]] = []

    def discover(self, query: str, *, limit: int, offset: int = 0) -> CoreDiscoveryResult:
        self.calls.append((query, limit, offset))
        return self.result


def _candidate(**overrides: object) -> CoreCandidate:
    base: dict[str, object] = {
        "core_id": "12345",
        "doi": "10.1000/example",
        "title": "Example paper",
        "abstract": None,
        "authors": (),
        "publication_year": None,
        "venue": None,
        "document_type": None,
        "pdf_url": "https://core.ac.uk/download/12345.pdf",
        "pdf_host": "core.ac.uk",
        "source_fulltext_urls": (),
    }
    base.update(overrides)
    return CoreCandidate(**base)  # type: ignore[arg-type]


def test_core_candidate_discover_writes_reviewable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    service = FakeDiscoveryService(
        CoreDiscoveryResult(
            query="semaglutide obesity",
            offset=0,
            next_offset=25,
            limit=25,
            total_hits=100,
            candidates=(_candidate(),),
        )
    )
    monkeypatch.setattr(entrypoint, "_core_discovery_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "core-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--limit",
            "25",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [("semaglutide obesity", 25, 0)]
    assert "Network access:" in result.output
    assert "no PDFs were downloaded" in result.output
    assert "Next page: --offset 25" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["core_id"] == "12345"


def test_core_candidate_discover_passes_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    service = FakeDiscoveryService(
        CoreDiscoveryResult(
            query="semaglutide obesity",
            offset=25,
            next_offset=None,
            limit=25,
            total_hits=30,
            candidates=(),
        )
    )
    monkeypatch.setattr(entrypoint, "_core_discovery_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "core-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--offset",
            "25",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [("semaglutide obesity", 25, 25)]
    assert "Next page:" not in result.output


def test_core_candidate_discover_rejects_existing_output_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    output.write_text("existing", encoding="utf-8")
    called = False

    def fail_if_called() -> FakeDiscoveryService:
        nonlocal called
        called = True
        raise AssertionError("should not be called")

    monkeypatch.setattr(entrypoint, "_core_discovery_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "core-candidate-discover",
            "--query",
            "semaglutide",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert not called
