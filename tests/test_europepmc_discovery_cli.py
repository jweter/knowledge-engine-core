from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.europepmc_discovery import EuropePmcCandidate, EuropePmcDiscoveryResult


class FakeDiscoveryService:
    def __init__(self, result: EuropePmcDiscoveryResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int, str]] = []

    def discover(
        self, query: str, *, limit: int, cursor_mark: str = "*"
    ) -> EuropePmcDiscoveryResult:
        self.calls.append((query, limit, cursor_mark))
        return self.result


def _candidate(**overrides: object) -> EuropePmcCandidate:
    base: dict[str, object] = {
        "europepmc_id": "PPR123",
        "source": "PPR",
        "pmid": "111",
        "pmcid": None,
        "doi": "10.1000/example",
        "title": "Example preprint",
        "abstract": None,
        "authors": (),
        "publication_year": None,
        "venue": None,
        "in_pmc": False,
        "open_access": True,
        "license": "cc by",
        "pdf_url": "https://europepmc.org/api/fulltextRepo?pprId=PPR123",
        "pdf_host": "europepmc.org",
    }
    base.update(overrides)
    return EuropePmcCandidate(**base)  # type: ignore[arg-type]


def test_europepmc_candidate_discover_writes_reviewable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    service = FakeDiscoveryService(
        EuropePmcDiscoveryResult(
            query="semaglutide obesity",
            cursor_mark="*",
            next_cursor_mark="AoIIQ==",
            limit=1,
            candidates=(_candidate(),),
        )
    )
    monkeypatch.setattr(entrypoint, "_europepmc_discovery_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--limit",
            "1",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [("semaglutide obesity", 1, "*")]
    assert "Network access:" in result.output
    assert "no PDFs were downloaded" in result.output
    assert "AoIIQ==" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["europepmc_id"] == "PPR123"
    assert payload["candidates"][0]["open_access"] is True


def test_europepmc_candidate_discover_passes_cursor_mark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    service = FakeDiscoveryService(
        EuropePmcDiscoveryResult(
            query="semaglutide obesity",
            cursor_mark="AoIIQ==",
            next_cursor_mark=None,
            limit=25,
            candidates=(),
        )
    )
    monkeypatch.setattr(entrypoint, "_europepmc_discovery_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--cursor-mark",
            "AoIIQ==",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [("semaglutide obesity", 25, "AoIIQ==")]
    assert "Next page:" not in result.output


def test_europepmc_candidate_discover_rejects_existing_output_before_network(
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

    monkeypatch.setattr(entrypoint, "_europepmc_discovery_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "europepmc-candidate-discover",
            "--query",
            "semaglutide",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert not called
