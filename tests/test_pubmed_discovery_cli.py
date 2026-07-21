from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.pubmed_discovery import DiscoveryResult, PubmedCandidate


class FakeDiscoveryService:
    def __init__(self, result: DiscoveryResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int, int]] = []

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        self.calls.append((query, limit, retstart))
        return self.result


def test_pubmed_candidate_discover_writes_reviewable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    service = FakeDiscoveryService(
        DiscoveryResult(
            query="semaglutide obesity",
            retstart=25,
            limit=1,
            candidates=(
                PubmedCandidate(
                    pmid="123",
                    title="Example trial",
                    abstract=None,
                    authors=(),
                    publication_year=None,
                    venue=None,
                    doi="10.1000/example",
                    pmcid="PMC123",
                    open_access=True,
                    license="CC BY",
                    pdf_url="https://pmc-oa-opendata.s3.amazonaws.com/PMC123.1/PMC123.1.pdf",
                    xml_url="https://pmc-oa-opendata.s3.amazonaws.com/PMC123.1/PMC123.1.xml",
                    status="oa_verified",
                    metadata_source="pubmed_efetch",
                    pmcid_source="pmc_id_converter",
                    oa_source="pmc_cloud_service",
                ),
            ),
        )
    )
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: service)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "pubmed-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--limit",
            "1",
            "--retstart",
            "25",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert service.calls == [("semaglutide obesity", 1, 25)]
    assert "Network access:" in result.output
    assert "no PDFs were downloaded" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["pmid"] == "123"
    assert payload["candidates"][0]["open_access"] is True


def test_pubmed_candidate_discover_rejects_existing_output_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "candidates.json"
    output.write_text("existing", encoding="utf-8")
    called = False

    def fail_if_called() -> FakeDiscoveryService:
        nonlocal called
        called = True
        raise AssertionError("discovery service must not be built")

    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "pubmed-candidate-discover",
            "--query",
            "semaglutide obesity",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert "Network access:" not in result.output
    assert called is False
