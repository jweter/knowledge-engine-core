from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormLookupResult


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


class _FakeRxNormService:
    def lookup(self, term: str) -> RxNormLookupResult:
        return RxNormLookupResult(
            term=term,
            found=False,
            rxcui=None,
            name=None,
            term_type=None,
            synonym=None,
            ingredients=(),
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00+00:00",
        )


class _FakeMeshService:
    def lookup(self, term: str) -> MeshLookupResult:
        if term == "obesity":
            return MeshLookupResult(
                term=term,
                found=True,
                mesh_id="D009765",
                heading="Obesity",
                scope_note="An excessive amount of adipose tissue in the body.",
                synonyms=("Obesities",),
                source_url="https://id.nlm.nih.gov/mesh/D009765",
                license="Free, non-proprietary content, National Library of Medicine (MeSH)",
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
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


def _patch_lookup_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: _FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: _FakeMeshService())


def _evidence_record(evidence_record_id: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": evidence_record_id,
        "population": "Adults with obesity",
        "intervention": None,
        "comparator": None,
        "outcome": "Body weight change.",
        "claim_text": "Semaglutide reduced body weight versus placebo (p<0.001).",
        "result_summary": "Mean difference -12.4 kg (95% CI -13.4 to -11.5).",
    }
    record.update(overrides)
    return record


def _write_jsonl(path: Path, *records: dict[str, object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


class _FakeClassifierLLM:
    def __init__(self, *, model: str, host: str) -> None:
        self.model = model
        self.host = host

    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        del prompt, max_tokens
        return (
            '{"relationship_type": "supports", '
            '"quoted_evidence": "Semaglutide reduced body weight versus placebo (p<0.001).", '
            '"rationale": "Both trials report semaglutide reducing body weight versus placebo."}'
        )


class _RefusingClassifierLLM(_FakeClassifierLLM):
    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        del prompt, max_tokens
        return (
            '{"relationship_type": "supports", '
            '"quoted_evidence": "This is not present in either claim at all.", '
            '"rationale": "Fabricated."}'
        )


def test_relationship_classify_automate_appends_an_accepted_relationship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeClassifierLLM)

    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record(
            "ev-2",
            claim_text="A second trial confirmed weight loss with semaglutide.",
            result_summary="Consistent with the first trial's direction of effect.",
        ),
    )
    relationships_path = tmp_path / "relationships.jsonl"
    relationships_path.write_text("", encoding="utf-8")

    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-classify-automate",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
            "--model",
            "fake-model",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _unwrapped(result.output)
    assert "supports" in output
    assert "Appended 1 relationship(s), skipped 0" in output
    assert "Graph not rebuilt" in output

    written = [
        json.loads(line) for line in relationships_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(written) == 1
    record = written[0]
    assert record["source_evidence_record_id"] == "ev-1"
    assert record["target_evidence_record_id"] == "ev-2"
    assert record["relationship_type"] == "supports"
    assert record["provenance"]["created_by"] == "automated (M70 relationship classification)"
    assert record["created_for_milestone"] == "M70"


def test_relationship_classify_automate_skips_an_ungrounded_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _RefusingClassifierLLM)

    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    relationships_path = tmp_path / "relationships.jsonl"
    relationships_path.write_text("", encoding="utf-8")

    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-classify-automate",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
            "--model",
            "fake-model",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _unwrapped(result.output)
    assert "skipped" in output
    assert "Appended 0 relationship(s), skipped 1" in output
    assert relationships_path.read_text(encoding="utf-8") == ""


def test_relationship_classify_automate_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeClassifierLLM)

    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    relationships_path = tmp_path / "relationships.jsonl"
    relationships_path.write_text("", encoding="utf-8")

    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-classify-automate",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
            "--model",
            "fake-model",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Dry run" in _unwrapped(result.output)
    assert relationships_path.read_text(encoding="utf-8") == ""


def test_relationship_classify_automate_requires_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KE_LLM_MODEL", raising=False)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))
    relationships_path = tmp_path / "relationships.jsonl"
    relationships_path.write_text("", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-classify-automate",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )

    assert result.exit_code != 0
    assert "No model given" in _unwrapped(result.output)
