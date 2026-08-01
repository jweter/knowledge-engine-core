from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.pubmed_discovery import DiscoveryResult, PubmedCandidate


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeDiscoveryService:
    def __init__(self, results: list[DiscoveryResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, int, int]] = []

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        self.calls.append((query, limit, retstart))
        return self._results.pop(0)


def _accepted_candidate(pmid: str) -> PubmedCandidate:
    """A candidate that deterministically adjudicates 'accepted' (see test_candidate_review.py)."""

    return PubmedCandidate(
        pmid=pmid,
        title="GLP-1 receptor agonist treatment for obesity and weight loss",
        abstract=None,
        authors=(),
        publication_year=None,
        venue=None,
        doi=f"10.1000/example-{pmid}",
        pmcid=f"PMC{pmid}",
        open_access=True,
        license="CC BY 4.0",
        pdf_url=f"https://pmc-oa-opendata.s3.amazonaws.com/PMC{pmid}.1/PMC{pmid}.1.pdf",
        xml_url=None,
        status="oa_verified",
        metadata_source="pubmed_efetch",
        pmcid_source="pmc_id_converter",
        oa_source="pmc_cloud_service",
    )


def _held_candidate(pmid: str) -> PubmedCandidate:
    """A metadata-only candidate that deterministically adjudicates as 'rejected'."""

    return PubmedCandidate(
        pmid=pmid,
        title="Pediatric obesity outcomes",
        abstract=None,
        authors=(),
        publication_year=None,
        venue=None,
        doi=None,
        pmcid=None,
        open_access=False,
        license=None,
        pdf_url=None,
        xml_url=None,
        status="metadata_only",
        metadata_source="pubmed_efetch",
        pmcid_source=None,
        oa_source=None,
    )


def _discovery_result(query: str, retstart: int, *candidates: PubmedCandidate) -> DiscoveryResult:
    return DiscoveryResult(
        query=query, retstart=retstart, limit=len(candidates), candidates=candidates
    )


def test_discovery_cycle_run_writes_a_ready_for_review_worksheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = "GLP-1 receptor agonist AND obesity"
    service = FakeDiscoveryService(
        [_discovery_result(query, 0, _accepted_candidate("1"), _held_candidate("2"))]
    )
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: service)

    state_path = tmp_path / "state.json"
    ledger_path = tmp_path / "ledger.csv"
    output_path = tmp_path / "cycle.json"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "discovery-cycle-run",
            "--query",
            query,
            "--state",
            str(state_path),
            "--ledger",
            str(ledger_path),
            "--output",
            str(output_path),
            "--limit",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [(query, 2, 0)]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["candidates_discovered"] == 2
    assert payload["deterministically_accepted"] == 1
    assert payload["rejected_by_adjudication"] == 1
    assert payload["already_in_rejected_ledger"] == 0
    assert len(payload["ready_for_scope_review"]) == 1
    assert payload["ready_for_scope_review"][0]["pmid"] == "1"
    assert payload["next_retstart"] == 2

    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_payload["next_retstart"] == 2
    assert state_payload["cycles_run"] == 1

    unwrapped = _unwrapped(result.output)
    assert "Discovery cycle 1 complete" in unwrapped
    assert "Not evidence, not acquired" in unwrapped


def test_discovery_cycle_run_excludes_a_candidate_already_in_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = "GLP-1 receptor agonist AND obesity"
    service = FakeDiscoveryService([_discovery_result(query, 0, _accepted_candidate("1"))])
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: service)

    ledger_path = tmp_path / "ledger.csv"
    ledger_path.write_text(
        "pmid,doi,title,reason_category,batch_label,rejected_date,notes\n"
        "1,,Already rejected,off_target_primary_disease,retstart=0,2026-08-01,\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "discovery-cycle-run",
            "--query",
            query,
            "--state",
            str(tmp_path / "state.json"),
            "--ledger",
            str(ledger_path),
            "--output",
            str(tmp_path / "cycle.json"),
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads((tmp_path / "cycle.json").read_text(encoding="utf-8"))
    assert payload["deterministically_accepted"] == 1
    assert payload["already_in_rejected_ledger"] == 1
    assert payload["ready_for_scope_review"] == []


def test_discovery_cycle_run_resumes_from_persisted_retstart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = "GLP-1 receptor agonist AND obesity"
    service = FakeDiscoveryService(
        [
            _discovery_result(query, 0, _accepted_candidate("1")),
            _discovery_result(query, 2, _accepted_candidate("2")),
        ]
    )
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: service)

    state_path = tmp_path / "state.json"
    ledger_path = tmp_path / "ledger.csv"

    CliRunner().invoke(
        entrypoint.app,
        [
            "discovery-cycle-run",
            "--query",
            query,
            "--state",
            str(state_path),
            "--ledger",
            str(ledger_path),
            "--output",
            str(tmp_path / "cycle1.json"),
            "--limit",
            "2",
        ],
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "discovery-cycle-run",
            "--query",
            query,
            "--state",
            str(state_path),
            "--ledger",
            str(ledger_path),
            "--output",
            str(tmp_path / "cycle2.json"),
            "--limit",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert service.calls == [(query, 2, 0), (query, 2, 2)]
    unwrapped = _unwrapped(result.output)
    assert "Discovery cycle 2 complete" in unwrapped
    assert "retstart 2 -> next 4" in unwrapped


def test_discovery_cycle_run_rejects_a_query_mismatch_against_persisted_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = FakeDiscoveryService([])
    monkeypatch.setattr(entrypoint, "_pubmed_discovery_service", lambda: service)

    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "query": "first query",
                "next_retstart": 25,
                "limit": 25,
                "cycles_run": 1,
                "updated_at": "",
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "discovery-cycle-run",
            "--query",
            "a different query",
            "--state",
            str(state_path),
            "--ledger",
            str(tmp_path / "ledger.csv"),
            "--output",
            str(tmp_path / "cycle.json"),
            "--limit",
            "25",
        ],
    )

    assert result.exit_code == 1
    assert "tracks query" in _unwrapped(result.output)
    assert service.calls == []
