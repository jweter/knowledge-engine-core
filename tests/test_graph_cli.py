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


def test_graph_build_cli_corpus_flag_sets_corpus_id_on_new_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))

    result = CliRunner().invoke(
        entrypoint.app,
        ["graph-build", "--evidence", str(evidence_path), "--corpus", "glp1_weight_loss"],
    )

    assert result.exit_code == 0, result.output

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.find_claim_by_evidence_id("ev-1")
        assert claim is not None
        assert claim.corpus_id == "glp1_weight_loss"


def test_graph_build_cli_corpus_flag_backfills_a_pre_existing_unscoped_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))

    first = CliRunner().invoke(entrypoint.app, ["graph-build", "--evidence", str(evidence_path)])
    assert first.exit_code == 0, first.output

    second = CliRunner().invoke(
        entrypoint.app,
        ["graph-build", "--evidence", str(evidence_path), "--corpus", "glp1_weight_loss"],
    )

    assert second.exit_code == 0, second.output
    assert "backfilled corpus_id=glp1_weight_loss on 1 previously-unscoped claim" in _unwrapped(
        second.output
    )

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.find_claim_by_evidence_id("ev-1")
        assert claim is not None
        assert claim.corpus_id == "glp1_weight_loss"


def test_graph_build_cli_corpus_flag_never_overwrites_an_existing_corpus_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))

    first = CliRunner().invoke(
        entrypoint.app,
        ["graph-build", "--evidence", str(evidence_path), "--corpus", "glp1_weight_loss"],
    )
    assert first.exit_code == 0, first.output

    second = CliRunner().invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(evidence_path),
            "--corpus",
            "oncology_nsclc_checkpoint_inhibitors",
        ],
    )
    assert second.exit_code == 0, second.output

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.find_claim_by_evidence_id("ev-1")
        assert claim is not None
        assert claim.corpus_id == "glp1_weight_loss"


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


def test_graph_relationship_candidates_corpus_flag_scopes_to_matching_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    glp1_evidence_path = _write_jsonl(
        tmp_path / "glp1_evidence.jsonl",
        _evidence_record("ev-glp1-1"),
        _evidence_record("ev-glp1-2"),
    )
    oncology_evidence_path = _write_jsonl(
        tmp_path / "oncology_evidence.jsonl",
        _evidence_record("ev-onc-1"),
        _evidence_record("ev-onc-2"),
    )
    runner = CliRunner()
    build_glp1 = runner.invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(glp1_evidence_path),
            "--corpus",
            "glp1_weight_loss",
        ],
    )
    assert build_glp1.exit_code == 0, build_glp1.output
    build_oncology = runner.invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(oncology_evidence_path),
            "--corpus",
            "oncology_nsclc_checkpoint_inhibitors",
        ],
    )
    assert build_oncology.exit_code == 0, build_oncology.output

    unscoped = runner.invoke(entrypoint.app, ["graph-relationship-candidates"])
    assert unscoped.exit_code == 0, unscoped.output
    assert "Candidate pairs found: 6" in _unwrapped(unscoped.output)

    scoped = runner.invoke(
        entrypoint.app, ["graph-relationship-candidates", "--corpus", "glp1_weight_loss"]
    )
    assert scoped.exit_code == 0, scoped.output
    scoped_unwrapped = _unwrapped(scoped.output)
    assert "Corpus: glp1_weight_loss" in scoped_unwrapped
    assert "Candidate pairs found: 1" in scoped_unwrapped
    assert "ev-glp1-1 <-> ev-glp1-2" in scoped_unwrapped
    assert "ev-onc-1" not in scoped_unwrapped


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


def test_relationship_review_worksheet_shows_full_fields_for_a_candidate_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-1",
            source_title="Trial One",
            source_doi="10.1000/one",
            study_type="randomized_controlled_trial",
            outcome="Body weight change.",
            result_summary="Semaglutide reduced body weight versus placebo.",
        ),
        _evidence_record(
            "ev-2",
            source_title="Trial Two",
            outcome="Body weight change.",
            result_summary="A second trial reporting the same direction.",
        ),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        ["relationship-review-worksheet", "--evidence", str(evidence_path)],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Candidate pairs total: 1" in unwrapped
    assert "Trial One" in unwrapped
    assert "Trial Two" in unwrapped
    assert "10.1000/one" in unwrapped
    assert "Semaglutide reduced body weight versus placebo." in unwrapped
    assert '"source_evidence_record_id": "ev-1"' in unwrapped
    assert '"target_evidence_record_id": "ev-2"' in unwrapped
    assert "never infers, scores, or suggests a relationship" in unwrapped


def test_relationship_review_worksheet_corpus_flag_excludes_other_corpora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    glp1_evidence_path = _write_jsonl(
        tmp_path / "glp1_evidence.jsonl",
        _evidence_record("ev-glp1-1"),
        _evidence_record("ev-glp1-2"),
    )
    oncology_evidence_path = _write_jsonl(
        tmp_path / "oncology_evidence.jsonl",
        _evidence_record("ev-onc-1"),
        _evidence_record("ev-onc-2"),
    )
    runner = CliRunner()
    build_glp1 = runner.invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(glp1_evidence_path),
            "--corpus",
            "glp1_weight_loss",
        ],
    )
    assert build_glp1.exit_code == 0, build_glp1.output
    build_oncology = runner.invoke(
        entrypoint.app,
        [
            "graph-build",
            "--evidence",
            str(oncology_evidence_path),
            "--corpus",
            "oncology_nsclc_checkpoint_inhibitors",
        ],
    )
    assert build_oncology.exit_code == 0, build_oncology.output

    result = runner.invoke(
        entrypoint.app,
        [
            "relationship-review-worksheet",
            "--evidence",
            str(glp1_evidence_path),
            "--corpus",
            "glp1_weight_loss",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Corpus: glp1_weight_loss" in unwrapped
    assert "Candidate pairs total: 1" in unwrapped
    assert "ev-glp1-1" in unwrapped
    assert "ev-onc-1" not in unwrapped


def test_relationship_review_worksheet_respects_limit_and_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
        _evidence_record("ev-3"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-review-worksheet",
            "--evidence",
            str(evidence_path),
            "--limit",
            "1",
            "--offset",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Candidate pairs total: 3" in unwrapped
    assert "pairs 2-2 of 3" in unwrapped
    assert unwrapped.count("## Pair") == 1


def test_relationship_review_worksheet_notes_a_claim_missing_from_evidence_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    build_evidence_path = _write_jsonl(
        tmp_path / "build_evidence.jsonl",
        _evidence_record("ev-1"),
        _evidence_record("ev-2"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(build_evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    # A --evidence file that no longer contains one of the two claims --
    # e.g. it was trimmed after graph-build already ran against it.
    trimmed_evidence_path = _write_jsonl(
        tmp_path / "trimmed_evidence.jsonl", _evidence_record("ev-1")
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["relationship-review-worksheet", "--evidence", str(trimmed_evidence_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Not found in `--evidence` file" in _unwrapped(result.output)


def test_relationship_review_worksheet_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl", _evidence_record("ev-1"), _evidence_record("ev-2")
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output
    output_path = tmp_path / "worksheet.md"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-review-worksheet",
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote relationship review worksheet" in _unwrapped(result.output)
    assert "Candidate pairs total: 1" in output_path.read_text(encoding="utf-8")


def test_relationship_review_worksheet_rejects_a_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))
    target = tmp_path / "target.md"
    target.write_text("private", encoding="utf-8")
    output_path = tmp_path / "worksheet.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-review-worksheet",
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "private"


class _FakeSimilarityGenerator:
    """Deterministic fake -- avoids downloading a real sentence-transformers model in tests."""

    def __init__(self, vectors_by_text: dict[str, tuple[float, ...]]) -> None:
        self._vectors_by_text = vectors_by_text

    def generate(self, text: str) -> tuple[float, ...]:
        return self._vectors_by_text[text]


def test_relationship_review_worksheet_rank_by_similarity_reorders_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1", outcome="Body weight.", result_summary="Down 10%."),
        _evidence_record("ev-2", outcome="Body weight.", result_summary="Down 9%."),
        _evidence_record("ev-3", outcome="Unrelated.", result_summary="Nothing alike."),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    fake_generator = _FakeSimilarityGenerator(
        {
            "Body weight. Down 10%.": (1.0, 0.0),
            "Body weight. Down 9%.": (0.95, 0.05),
            "Unrelated. Nothing alike.": (0.0, 1.0),
        }
    )
    monkeypatch.setattr(
        entrypoint, "_build_embedding_generator", lambda generator, model: fake_generator
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "relationship-review-worksheet",
            "--evidence",
            str(evidence_path),
            "--rank-by-similarity",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Ordering: semantic similarity (M61), descending" in unwrapped
    assert "Semantic similarity:" in unwrapped
    # ev-1 <-> ev-2 (both body weight) must rank ahead of any pair
    # involving ev-3 (unrelated) -- assert by position, not just presence.
    first_pair_index = unwrapped.index("## Pair 1")
    ev1_ev2_index = unwrapped.index("ev-1 <-> ev-2")
    ev3_index = min(
        i for i in (unwrapped.find("ev-1 <-> ev-3"), unwrapped.find("ev-2 <-> ev-3")) if i != -1
    )
    assert first_pair_index <= ev1_ev2_index < ev3_index


def test_relationship_review_worksheet_without_rank_flag_shows_shared_concept_ordering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl", _evidence_record("ev-1"), _evidence_record("ev-2")
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        ["relationship-review-worksheet", "--evidence", str(evidence_path)],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Ordering: shared-concept count, descending" in unwrapped
    assert "Semantic similarity:" not in unwrapped


def test_evidence_review_queue_ranks_a_record_with_a_relationship_edge_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-tier1", extraction_method="m52-evidence-classification-v1", source_title="Tier One"
        ),
        _evidence_record(
            "ev-tier3",
            extraction_method="m52-evidence-classification-v1",
            source_title="Tier Three",
            population="Adults with a rare, unrelated condition",
            intervention="An unrelated intervention",
            comparator=None,
        ),
        _evidence_record(
            "ev-manual", extraction_method="manual_human_review", source_title="Manual"
        ),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    with database.session() as session:
        repository = GraphRepository(session)
        tier1_claim = repository.find_claim_by_evidence_id("ev-tier1")
        manual_claim = repository.find_claim_by_evidence_id("ev-manual")
        assert tier1_claim is not None and manual_claim is not None
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=tier1_claim.id,
            target_claim_id=manual_claim.id,
            relationship_type="supports",
            rationale="For the test.",
        )

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-review-queue", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Automated (unreviewed) records total: 2" in unwrapped
    assert "ev-manual" not in unwrapped
    tier1_index = unwrapped.index("ev-tier1")
    tier3_index = unwrapped.index("ev-tier3")
    assert tier1_index < tier3_index
    assert "tier 1 (already touches a relationship edge)" in unwrapped
    assert "tier 3 (no relationship signal yet)" in unwrapped


def test_evidence_review_queue_prioritizes_candidate_pair_membership_over_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-shares-concept",
            extraction_method="m52-evidence-classification-v1",
            comparator="Placebo",
        ),
        _evidence_record(
            "ev-isolated",
            extraction_method="m52-evidence-classification-v1",
            population="Adults with a rare condition",
            intervention="An unrelated intervention",
            comparator=None,
        ),
        _evidence_record(
            "ev-other-shares-concept",
            extraction_method="manual_human_review",
            comparator="Placebo",
        ),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-review-queue", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    shares_index = unwrapped.index("ev-shares-concept")
    isolated_index = unwrapped.index("ev-isolated")
    assert shares_index < isolated_index
    assert "tier 2 (appears in a relationship candidate pair)" in unwrapped
    assert "tier 3 (no relationship signal yet)" in unwrapped


def test_evidence_review_queue_respects_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1", extraction_method="m52-evidence-classification-v1"),
        _evidence_record("ev-2", extraction_method="m52-evidence-classification-v1"),
        _evidence_record("ev-3", extraction_method="m52-evidence-classification-v1"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app,
        ["evidence-review-queue", "--evidence", str(evidence_path), "--limit", "2"],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Automated (unreviewed) records total: 3" in unwrapped
    assert "This queue: 2 of 3" in unwrapped


def test_evidence_review_queue_excludes_a_confirmed_automated_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-confirmed",
            extraction_method="m52-evidence-classification-v1",
            review_checklist={"automated_classification": True, "human_reviewed": True},
        ),
        _evidence_record(
            "ev-pending",
            extraction_method="m52-evidence-classification-v1",
            review_checklist={"automated_classification": True, "human_reviewed": False},
        ),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output

    result = CliRunner().invoke(
        entrypoint.app, ["evidence-review-queue", "--evidence", str(evidence_path)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Automated (unreviewed) records total: 1" in unwrapped
    assert "ev-confirmed" not in unwrapped
    assert "ev-pending" in unwrapped


def test_evidence_review_queue_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    _patch_lookup_services(monkeypatch)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record("ev-1", extraction_method="m52-evidence-classification-v1"),
    )
    build_result = CliRunner().invoke(
        entrypoint.app, ["graph-build", "--evidence", str(evidence_path)]
    )
    assert build_result.exit_code == 0, build_result.output
    output_path = tmp_path / "queue.md"

    result = CliRunner().invoke(
        entrypoint.app,
        ["evidence-review-queue", "--evidence", str(evidence_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote evidence review queue" in _unwrapped(result.output)
    assert "Automated (unreviewed) records total: 1" in output_path.read_text(encoding="utf-8")


def test_evidence_review_queue_rejects_a_symbolic_link_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    evidence_path = _write_jsonl(tmp_path / "evidence.jsonl", _evidence_record("ev-1"))
    target = tmp_path / "target.md"
    target.write_text("private", encoding="utf-8")
    output_path = tmp_path / "queue.md"
    output_path.symlink_to(target)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-queue",
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "private"
