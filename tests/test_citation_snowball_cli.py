from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    FederatedCandidate,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeSemanticScholarProvider:
    """Stands in for `SemanticScholarProvider` without any network access."""

    def __init__(self, results: list[CitationTraversalResult]) -> None:
        self._results = deque(results)
        self.queries: list[CitationTraversalQuery] = []

    @property
    def name(self) -> str:
        return "semantic_scholar"

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        self.queries.append(query)
        result = self._results.popleft()
        assert result.query == query
        return result


def _candidate(provider_id: str, *, doi: str | None = None) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"semantic_scholar:{provider_id}",
        title=f"Paper {provider_id}",
        doi=doi,
        observations=(
            ProviderObservation(
                provider="semantic_scholar",
                provider_id=provider_id,
                title=f"Paper {provider_id}",
                semantic_scholar_id=provider_id,
                doi=doi,
            ),
        ),
    )


def _result(
    seed: str,
    direction: CitationDirection,
    discovered: tuple[str, ...],
    *,
    limit: int = 25,
    outcome: ProviderOutcome = ProviderOutcome.SUCCESS,
    reason: str | None = None,
) -> CitationTraversalResult:
    query = CitationTraversalQuery(seed_identifier=seed, direction=direction, limit=limit)
    candidates = tuple(_candidate(provider_id) for provider_id in discovered)
    edges = tuple(
        CitationEdge(
            provider="semantic_scholar",
            seed_identifier=seed,
            related_provider_id=provider_id,
            direction=direction,
            retrieved_at="2026-08-18T12:00:00+00:00",
        )
        for provider_id in discovered
    )
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="semantic_scholar",
            outcome=outcome,
            attempted=True,
            result_count=len(discovered),
            reason=reason,
        ),
        candidates=candidates,
        edges=edges,
    )


def _patch_provider(
    monkeypatch: pytest.MonkeyPatch, results: list[CitationTraversalResult]
) -> FakeSemanticScholarProvider:
    fake = FakeSemanticScholarProvider(results)
    monkeypatch.setattr(entrypoint, "SemanticScholarProvider", lambda **kwargs: fake)
    return fake


class FakeOpenAlexCitationAdapter:
    """Stands in for `OpenAlexCitationAdapter` without any network access."""

    def __init__(self, results: list[CitationTraversalResult]) -> None:
        self._results = deque(results)
        self.queries: list[CitationTraversalQuery] = []

    @property
    def name(self) -> str:
        return "openalex"

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        self.queries.append(query)
        result = self._results.popleft()
        assert result.query == query
        return result


def _openalex_candidate(provider_id: str, *, doi: str | None = None) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"openalex:{provider_id}",
        title=f"Paper {provider_id}",
        doi=doi,
        observations=(
            ProviderObservation(
                provider="openalex",
                provider_id=provider_id,
                title=f"Paper {provider_id}",
                openalex_id=provider_id,
                doi=doi,
            ),
        ),
    )


def _openalex_result(
    seed: str,
    direction: CitationDirection,
    discovered: tuple[str, ...],
    *,
    limit: int = 25,
    outcome: ProviderOutcome = ProviderOutcome.SUCCESS,
    reason: str | None = None,
) -> CitationTraversalResult:
    query = CitationTraversalQuery(seed_identifier=seed, direction=direction, limit=limit)
    candidates = tuple(_openalex_candidate(provider_id) for provider_id in discovered)
    edges = tuple(
        CitationEdge(
            provider="openalex",
            seed_identifier=seed,
            related_provider_id=provider_id,
            direction=direction,
            retrieved_at="2026-08-19T12:00:00+00:00",
        )
        for provider_id in discovered
    )
    attempted = outcome not in {ProviderOutcome.SKIPPED, ProviderOutcome.DISABLED}
    return CitationTraversalResult(
        query=query,
        provider_status=ProviderStatus(
            provider="openalex",
            outcome=outcome,
            attempted=attempted,
            result_count=len(discovered),
            reason=reason,
        ),
        candidates=candidates,
        edges=edges,
    )


def _patch_openalex_adapter(
    monkeypatch: pytest.MonkeyPatch, results: list[CitationTraversalResult]
) -> FakeOpenAlexCitationAdapter:
    fake = FakeOpenAlexCitationAdapter(results)
    monkeypatch.setattr(entrypoint, "OpenAlexCitationAdapter", lambda **kwargs: fake)
    return fake


def test_citation_snowball_persists_a_run_and_reports_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _patch_provider(
        monkeypatch,
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result("W1", CitationDirection.CITATIONS, ("W3",)),
        ],
    )

    ledger_root = tmp_path / "ledger"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert [query.normalized_seed_identifier for query in fake.queries] == ["W1", "W1"]

    unwrapped = _unwrapped(result.output)
    assert "Completeness: complete" in unwrapped
    assert "2 candidate(s)" in unwrapped
    assert "Paper W2" in unwrapped
    assert "Paper W3" in unwrapped

    persisted = list(ledger_root.glob("*.json"))
    assert len(persisted) == 1
    payload = json.loads(persisted[0].read_text(encoding="utf-8"))
    assert payload["provider"] == "semantic_scholar"
    assert payload["completeness"] == "complete"
    assert payload["truncated"] is False
    assert sorted(payload["candidate_ids"]) == ["semantic_scholar:W2", "semantic_scholar:W3"]
    assert len(payload["edges"]) == 2


def test_citation_snowball_writes_full_output_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(
        monkeypatch,
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
        ],
    )

    output_path = tmp_path / "snowball.json"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--directions",
            "references",
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["provider"] == "semantic_scholar"
    assert payload["plan"]["seed_identifiers"] == ["W1"]
    assert payload["plan"]["directions"] == ["references"]
    assert payload["completeness"] == "complete"
    assert [candidate["canonical_id"] for candidate in payload["candidates"]] == [
        "semantic_scholar:W2"
    ]
    assert payload["edges"][0]["direction"] == "references"
    assert payload["edges"][0]["related_provider_id"] == "W2"


def test_citation_snowball_rejects_an_unknown_direction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(monkeypatch, [])

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--directions",
            "backlinks",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code != 0
    assert "Unknown direction" in result.output


def test_citation_snowball_reports_partial_completeness_on_a_failed_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(
        monkeypatch,
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result(
                "W1",
                CitationDirection.CITATIONS,
                (),
                outcome=ProviderOutcome.FAILED,
                reason="rate_limited",
            ),
        ],
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Completeness: partial" in unwrapped


def test_citation_snowball_report_reads_back_a_persisted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(
        monkeypatch,
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result("W1", CitationDirection.CITATIONS, ()),
        ],
    )

    ledger_root = tmp_path / "ledger"
    run_result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--ledger-root",
            str(ledger_root),
        ],
    )
    assert run_result.exit_code == 0, run_result.output

    persisted = list(ledger_root.glob("*.json"))
    assert len(persisted) == 1
    snowball_run_id = persisted[0].stem

    report_result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball-report",
            snowball_run_id,
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert report_result.exit_code == 0, report_result.output
    unwrapped = _unwrapped(report_result.output)
    assert snowball_run_id in unwrapped
    assert "Completeness: complete" in unwrapped
    assert "semantic_scholar" in unwrapped


def test_citation_snowball_report_rejects_an_unknown_run_id(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball-report",
            "00000000-0000-0000-0000-000000000000",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 1
    assert "No citation-snowball run found" in result.output


def test_citation_snowball_defaults_to_semantic_scholar_when_no_provider_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(
        monkeypatch,
        [
            _result("W1", CitationDirection.REFERENCES, ("W2",)),
            _result("W1", CitationDirection.CITATIONS, ()),
        ],
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Semantic Scholar" in _unwrapped(result.output)


def test_citation_snowball_can_traverse_openalex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _patch_openalex_adapter(
        monkeypatch,
        [
            _openalex_result("W1", CitationDirection.REFERENCES, ("W2",)),
            _openalex_result("W1", CitationDirection.CITATIONS, ("W3",)),
        ],
    )

    ledger_root = tmp_path / "ledger"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--provider",
            "openalex",
            "--openalex-api-key",
            "test-key",
            "--ledger-root",
            str(ledger_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert [query.normalized_seed_identifier for query in fake.queries] == ["W1", "W1"]

    unwrapped = _unwrapped(result.output)
    assert "OpenAlex" in unwrapped
    assert "Completeness: complete" in unwrapped
    assert "Paper W2" in unwrapped
    assert "Paper W3" in unwrapped

    persisted = list(ledger_root.glob("*.json"))
    assert len(persisted) == 1
    payload = json.loads(persisted[0].read_text(encoding="utf-8"))
    assert payload["provider"] == "openalex"
    assert sorted(payload["candidate_ids"]) == ["openalex:W2", "openalex:W3"]


def test_citation_snowball_openalex_reports_disabled_without_an_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_openalex_adapter(
        monkeypatch,
        [
            _openalex_result(
                "W1",
                CitationDirection.REFERENCES,
                (),
                outcome=ProviderOutcome.DISABLED,
                reason="missing_api_key",
            ),
            _openalex_result(
                "W1",
                CitationDirection.CITATIONS,
                (),
                outcome=ProviderOutcome.DISABLED,
                reason="missing_api_key",
            ),
        ],
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--provider",
            "openalex",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Completeness: failed" in unwrapped


def test_citation_snowball_rejects_an_unknown_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_provider(monkeypatch, [])
    _patch_openalex_adapter(monkeypatch, [])

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "citation-snowball",
            "--seeds",
            "W1",
            "--provider",
            "unpaywall",
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code != 0
    assert "Unknown provider" in result.output
