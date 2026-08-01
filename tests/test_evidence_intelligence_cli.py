from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, GraphRepository


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _database(tmp_path: Path, name: str = "source") -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / name,
            database_url=f"sqlite:///{tmp_path / name}.sqlite3",
        )
    )
    database.initialize()
    return database


def _write_evidence_jsonl(tmp_path: Path, records: list[dict[str, object]]) -> Path:
    path = tmp_path / "evidence_records.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    return path


def _manual_record(evidence_record_id: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": evidence_record_id,
        "study_type": "randomized_controlled_trial",
        "extraction_method": "manual_human_review",
        "review_checklist": {"source_verified": True},
        "limitations": ["A limitation."],
        "uncertainty_notes": ["An uncertainty."],
    }
    record.update(overrides)
    return record


def test_evidence_intelligence_shows_insufficient_consensus_with_no_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        GraphRepository(session).get_or_create_claim("ev-1")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    evidence_path = _write_evidence_jsonl(tmp_path, [_manual_record("ev-1")])

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-intelligence",
            "--evidence",
            str(evidence_path),
            "--evidence-record-id",
            "ev-1",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _unwrapped(result.output)
    assert "Evidence Quality" in output
    assert "not yet assessable" in output
    assert "Reliability: insufficient" in output


def test_evidence_intelligence_computes_consensus_with_two_supports_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        other_a = repository.get_or_create_claim("ev-2")
        other_b = repository.get_or_create_claim("ev-3")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=other_a.id,
            target_claim_id=claim.id,
            relationship_type="supports",
            rationale="Same direction, independent trial.",
        )
        repository.get_or_create_relationship_edge(
            "rel-2",
            source_claim_id=other_b.id,
            target_claim_id=claim.id,
            relationship_type="supports",
            rationale="Same direction, pooled meta-analysis.",
        )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    evidence_path = _write_evidence_jsonl(
        tmp_path,
        [_manual_record("ev-1"), _manual_record("ev-2"), _manual_record("ev-3")],
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-intelligence",
            "--evidence",
            str(evidence_path),
            "--evidence-record-id",
            "ev-1",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _unwrapped(result.output)
    assert "Evidence Consensus" in output
    assert "Score: 100/100" in output
    assert "Claim Confidence" in output
    assert "not yet assessable" not in output


def test_evidence_intelligence_rejects_unknown_evidence_record_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    evidence_path = _write_evidence_jsonl(tmp_path, [_manual_record("ev-1")])

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-intelligence",
            "--evidence",
            str(evidence_path),
            "--evidence-record-id",
            "ev-does-not-exist",
        ],
    )

    assert result.exit_code != 0
    assert "No evidence record found" in _unwrapped(result.output)


def test_evidence_intelligence_rejects_a_record_not_yet_in_the_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    evidence_path = _write_evidence_jsonl(tmp_path, [_manual_record("ev-1")])

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-intelligence",
            "--evidence",
            str(evidence_path),
            "--evidence-record-id",
            "ev-1",
        ],
    )

    assert result.exit_code != 0
    assert "No graph claim found" in _unwrapped(result.output)


def test_evidence_intelligence_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        GraphRepository(session).get_or_create_claim("ev-1")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    evidence_path = _write_evidence_jsonl(tmp_path, [_manual_record("ev-1")])
    output_path = tmp_path / "report.md"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-intelligence",
            "--evidence",
            str(evidence_path),
            "--evidence-record-id",
            "ev-1",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert "Evidence Quality" in output_path.read_text(encoding="utf-8")
