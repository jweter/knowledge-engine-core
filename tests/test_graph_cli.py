from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, GraphRepository, PaperRepository
from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.parser import ParsedPaper
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


class FakeRxNormService:
    def lookup(self, term: str) -> RxNormLookupResult:
        if term == "Semaglutide":
            return RxNormLookupResult(
                term=term,
                found=True,
                rxcui="1991302",
                name="semaglutide",
                term_type="IN",
                synonym=None,
                ingredients=(),
                source_url="https://rxnav.nlm.nih.gov/REST/rxcui/1991302",
                license="Free, non-proprietary content (RxNorm, National Library of Medicine)",
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
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


class FakeMeshService:
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
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())


def _evidence_record(evidence_record_id: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": evidence_record_id,
        "population": "Adults with obesity",
        "intervention": "Semaglutide",
        "comparator": None,
        "outcome": None,
    }
    record.update(overrides)
    return record


def _write_jsonl(path: Path, *records: dict[str, object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def test_graph_build_cli_populates_claims_and_concepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))

    result = CliRunner().invoke(entrypoint.app, ["graph-build", "--evidence", str(evidence_path)])

    assert result.exit_code == 0, result.output
    assert "1 claim(s) processed" in _unwrapped(result.output)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.find_claim_by_evidence_id("ev-1")
        assert claim is not None
        concepts = repository.concepts_for_claim(claim.id)
        assert {c.label for c in concepts} == {"semaglutide", "Obesity"}


def test_graph_build_cli_skips_network_lookups_for_already_graphed_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M54: re-running graph-build against an unchanged evidence file must do zero new lookups."""

    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    rxnorm_calls: list[str] = []
    mesh_calls: list[str] = []
    real_rxnorm = FakeRxNormService()
    real_mesh = FakeMeshService()

    class TrackingRxNormService:
        def lookup(self, term: str) -> RxNormLookupResult:
            rxnorm_calls.append(term)
            return real_rxnorm.lookup(term)

    class TrackingMeshService:
        def lookup(self, term: str) -> MeshLookupResult:
            mesh_calls.append(term)
            return real_mesh.lookup(term)

    monkeypatch.setattr(
        entrypoint, "RxNormLookupService", lambda transport: TrackingRxNormService()
    )
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: TrackingMeshService())

    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))

    first = CliRunner().invoke(entrypoint.app, ["graph-build", "--evidence", str(evidence_path)])
    assert first.exit_code == 0, first.output
    assert rxnorm_calls and mesh_calls

    rxnorm_calls.clear()
    mesh_calls.clear()

    second = CliRunner().invoke(entrypoint.app, ["graph-build", "--evidence", str(evidence_path)])

    assert second.exit_code == 0, second.output
    assert rxnorm_calls == []
    assert mesh_calls == []
    unwrapped = _unwrapped(second.output)
    assert "1 claim(s) processed" in unwrapped
    assert "already in the graph -- no new network lookups needed" in unwrapped


def test_graph_build_cli_only_looks_up_the_new_record_in_a_mixed_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    rxnorm_calls: list[str] = []
    real_rxnorm = FakeRxNormService()
    real_mesh = FakeMeshService()

    class TrackingRxNormService:
        def lookup(self, term: str) -> RxNormLookupResult:
            rxnorm_calls.append(term)
            return real_rxnorm.lookup(term)

    class PassthroughMeshService:
        def lookup(self, term: str) -> MeshLookupResult:
            return real_mesh.lookup(term)

    monkeypatch.setattr(
        entrypoint, "RxNormLookupService", lambda transport: TrackingRxNormService()
    )
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: PassthroughMeshService())

    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))
    CliRunner().invoke(entrypoint.app, ["graph-build", "--evidence", str(evidence_path)])
    rxnorm_calls.clear()

    grown_evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2", intervention="Tirzepatide"),
    )

    result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(grown_evidence_path)]
    )

    assert result.exit_code == 0, result.output
    assert rxnorm_calls == ["Tirzepatide"]
    unwrapped = _unwrapped(result.output)
    assert "2 claim(s) processed" in unwrapped
    assert "1 new record(s) (1 already in the graph, skipped)" in unwrapped


def test_graph_build_cli_links_a_relationship_between_two_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-1",
            "target_evidence_record_id": "ev-2",
            "relationship_type": "supports",
            "rationale": "Both report the same direction.",
        },
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1 relationship edge(s) created" in _unwrapped(result.output)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.find_claim_by_evidence_id("ev-1")
        assert claim is not None
        relationships = repository.relationships_for_claim(claim.id)
        assert [r.relationship_id for r in relationships] == ["rel-1"]


def test_graph_build_cli_links_a_supersedes_relationship_between_two_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M50: `supersedes` builds and renders through the graph exactly like
    the original four relationship types, and is excluded from
    `graph-relationship-candidates` like any other existing edge."""

    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-older"),
        _evidence_record("ev-newer"),
    )
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-newer",
            "target_evidence_record_id": "ev-older",
            "relationship_type": "supersedes",
            "rationale": "A later, larger trial revises the earlier estimate.",
        },
    )

    build_result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output
    assert "1 relationship edge(s) created" in _unwrapped(build_result.output)

    report_result = CliRunner().invoke(
        entrypoint.app, ["graph-report", "--evidence-record-id", "ev-newer"]
    )
    assert report_result.exit_code == 0, report_result.output
    assert "supersedes (source)" in _unwrapped(report_result.output)
    assert "ev-older" in _unwrapped(report_result.output)

    candidates_result = CliRunner().invoke(entrypoint.app, ["graph-relationship-candidates"])
    assert candidates_result.exit_code == 0, candidates_result.output
    assert "Candidate pairs found: 0" in _unwrapped(candidates_result.output)


def test_graph_build_cli_skips_a_relationship_with_an_unknown_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-1",
            "target_evidence_record_id": "ev-does-not-exist",
            "relationship_type": "supports",
            "rationale": "n/a",
        },
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Skipped 1 relationship" in _unwrapped(result.output)


def _parsed_paper(
    tmp_path: Path, content_hash: str, *, title: str, doi: str, raw_text: str
) -> ParsedPaper:
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title=title,
        authors=["Ada Scientist"],
        abstract="An abstract.",
        doi=doi,
        page_count=1,
        word_count=10,
        raw_text=raw_text,
        body_text=raw_text,
    )


def test_graph_citations_build_cli_creates_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper_repository = PaperRepository(session)
        cited = paper_repository.add_parsed_paper(
            _parsed_paper(
                tmp_path,
                "a" * 64,
                title="The Cited Paper",
                doi="10.1234/cited",
                raw_text="Body text with no bibliography.",
            )
        )
        paper_repository.add_parsed_paper(
            _parsed_paper(
                tmp_path,
                "b" * 64,
                title="The Citing Paper",
                doi="10.1234/citing",
                raw_text=(
                    "Body text.\n\nReferences\n\n"
                    "1. Someone. The Cited Paper. Journal. doi: 10.1234/cited\n"
                ),
            )
        )
        cited_id = cited.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    first = CliRunner().invoke(entrypoint.app, ["graph-citations-build"])
    assert first.exit_code == 0, first.output
    assert "1 new citation edge(s) created" in _unwrapped(first.output)

    second = CliRunner().invoke(entrypoint.app, ["graph-citations-build"])
    assert second.exit_code == 0, second.output
    assert "0 new citation edge(s) created" in _unwrapped(second.output)

    with database.session() as session:
        repository = GraphRepository(session)
        edges = repository.citations_for_paper(cited_id)
        assert len(edges) == 1


def test_graph_report_summary_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        GraphRepository(session).get_or_create_claim("ev-1")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(entrypoint.app, ["graph-report"])

    assert result.exit_code == 0, result.output
    assert "Corpus Totals" in _unwrapped(result.output)
    assert "Claims: 1" in _unwrapped(result.output)


def test_graph_report_claim_mode_shows_concepts_and_relationships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        other = repository.get_or_create_claim("ev-2")
        concept = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="1991302",
            definition="semaglutide; IN",
            source_url="https://rxnav.nlm.nih.gov/REST/rxcui/1991302",
            license="Free, non-proprietary content (RxNorm, National Library of Medicine)",
            retrieved_at="2026-07-29T00:00:00Z",
        )
        repository.link_claim_concept(claim.id, concept.id, "intervention")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=claim.id,
            target_claim_id=other.id,
            relationship_type="supports",
            rationale="Both report the same direction.",
        )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--evidence-record-id", "ev-1"])

    assert result.exit_code == 0, result.output
    assert "intervention: Semaglutide" in _unwrapped(result.output)
    assert "supports (source)" in _unwrapped(result.output)
    assert "ev-2" in _unwrapped(result.output)


def test_graph_report_claim_mode_rejects_unknown_evidence_record_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        entrypoint.app, ["graph-report", "--evidence-record-id", "ev-does-not-exist"]
    )

    assert result.exit_code != 0
    assert "No graph claim found" in _unwrapped(result.output)


def test_graph_report_paper_mode_shows_citations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper_repository = PaperRepository(session)
        citing = paper_repository.add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Citing Paper", doi="10.1/a", raw_text="text")
        )
        cited = paper_repository.add_parsed_paper(
            _parsed_paper(tmp_path, "b" * 64, title="Cited Paper", doi="10.1/b", raw_text="text")
        )
        GraphRepository(session).add_citation_edge(
            citing_paper_id=citing.id,
            cited_paper_id=cited.id,
            raw_citation_text="1. Cited Paper. doi: 10.1/b",
        )
        citing_id = citing.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--paper-id", str(citing_id)])

    assert result.exit_code == 0, result.output
    assert "Cites (1)" in _unwrapped(result.output)
    assert "Cited Paper" in _unwrapped(result.output)


def test_graph_report_paper_mode_rejects_unknown_paper_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--paper-id", "999"])

    assert result.exit_code != 0
    assert "No paper found" in _unwrapped(result.output)


def test_graph_report_rejects_both_filters_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        entrypoint.app,
        ["graph-report", "--evidence-record-id", "ev-1", "--paper-id", "1"],
    )

    assert result.exit_code != 0
    assert "not both" in _unwrapped(result.output)


def test_graph_report_writes_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "report.md"

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--output", str(output_path)])

    assert result.exit_code == 0, result.output
    assert "Wrote graph report" in _unwrapped(result.output)
    assert "Corpus Totals" in output_path.read_text(encoding="utf-8")


def test_graph_report_rejects_an_existing_output_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "report.md"
    output_path.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--output", str(output_path)])

    assert result.exit_code != 0
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_graph_report_rejects_a_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    target = tmp_path / "target.md"
    target.write_text("private", encoding="utf-8")
    output_path = tmp_path / "report.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(
        entrypoint.app, ["graph-report", "--output", str(output_path), "--force"]
    )

    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "private"


def test_graph_report_rejects_a_dangling_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    target = tmp_path / "does-not-exist.md"
    output_path = tmp_path / "report.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(entrypoint.app, ["graph-report", "--output", str(output_path)])

    assert result.exit_code != 0
    assert not target.exists()


def test_graph_relationship_candidates_surfaces_a_shared_concept_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(entrypoint.app, ["graph-relationship-candidates"])

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Candidate pairs found: 1" in unwrapped
    assert "ev-1 <-> ev-2" in unwrapped
    assert "Shared concepts (2): Obesity, semaglutide" in unwrapped or (
        "Shared concepts (2): semaglutide, Obesity" in unwrapped
    )
    assert "never infers, detects, or suggests a relationship" in unwrapped


def test_graph_relationship_candidates_excludes_a_pair_with_an_existing_relationship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-1",
            "target_evidence_record_id": "ev-2",
            "relationship_type": "supports",
            "rationale": "A reviewer already linked these two records.",
        },
    )
    build_result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(entrypoint.app, ["graph-relationship-candidates"])

    assert result.exit_code == 0, result.output
    assert "Candidate pairs found: 0" in _unwrapped(result.output)


def test_graph_relationship_candidates_respects_minimum_shared_concepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app, ["graph-relationship-candidates", "--min-shared-concepts", "3"]
    )

    assert result.exit_code == 0, result.output
    assert "Candidate pairs found: 0" in _unwrapped(result.output)


def test_graph_relationship_candidates_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "candidates.md"

    result = CliRunner().invoke(
        entrypoint.app, ["graph-relationship-candidates", "--output", str(output_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Wrote relationship candidates report" in _unwrapped(result.output)
    assert "Candidate pairs found: 0" in output_path.read_text(encoding="utf-8")


def test_graph_relationship_candidates_rejects_a_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    target = tmp_path / "target.md"
    target.write_text("private", encoding="utf-8")
    output_path = tmp_path / "candidates.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(
        entrypoint.app,
        ["graph-relationship-candidates", "--output", str(output_path), "--force"],
    )

    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "private"


def test_graph_unconfirmed_claims_surfaces_a_claim_with_no_relationship_edge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-confirmed-source"),
        _evidence_record("ev-confirmed-target"),
        _evidence_record("ev-unconfirmed"),
    )
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-confirmed-source",
            "target_evidence_record_id": "ev-confirmed-target",
            "relationship_type": "supports",
            "rationale": "Both report the same direction.",
        },
    )
    build_result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(entrypoint.app, ["graph-unconfirmed-claims"])

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Unconfirmed claims found: 1" in unwrapped
    assert "ev-unconfirmed" in unwrapped
    assert "ev-confirmed-source" not in unwrapped
    assert "ev-confirmed-target" not in unwrapped


def test_graph_unconfirmed_claims_is_empty_when_every_claim_has_an_edge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    relationships_path = _write_jsonl(
        tmp_path / "relationships.jsonl",
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-1",
            "target_evidence_record_id": "ev-2",
            "relationship_type": "supersedes",
            "rationale": "A later trial revises the earlier estimate.",
        },
    )
    build_result = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--relationships",
            str(relationships_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(entrypoint.app, ["graph-unconfirmed-claims"])

    assert result.exit_code == 0, result.output
    assert "Unconfirmed claims found: 0" in _unwrapped(result.output)


def test_graph_unconfirmed_claims_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output_path = tmp_path / "unconfirmed.md"

    result = CliRunner().invoke(
        entrypoint.app, ["graph-unconfirmed-claims", "--output", str(output_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Wrote unconfirmed claims report" in _unwrapped(result.output)
    assert "Unconfirmed claims found: 0" in output_path.read_text(encoding="utf-8")


def test_graph_unconfirmed_claims_rejects_a_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    target = tmp_path / "target.md"
    target.write_text("private", encoding="utf-8")
    output_path = tmp_path / "unconfirmed.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(
        entrypoint.app,
        ["graph-unconfirmed-claims", "--output", str(output_path), "--force"],
    )

    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "private"
