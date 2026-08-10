from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, GraphRepository, PaperRepository
from knowledge_engine.parser import ParsedPaper


def build_database(tmp_path: Path) -> Database:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
    )
    database = Database(settings)
    database.initialize()
    return database


def _parsed_paper(tmp_path: Path, suffix: str) -> ParsedPaper:
    return ParsedPaper(
        source_path=tmp_path / f"paper-{suffix}.pdf",
        content_hash=suffix * 64,
        title=f"Paper {suffix}",
        authors=["Author One"],
        abstract="An abstract.",
        doi=f"10.1234/{suffix}",
        page_count=1,
        word_count=10,
        raw_text="Body text.",
        body_text="Body text.",
    )


def test_get_or_create_concept_dedupes_by_source_and_reference_id(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        first = repository.get_or_create_concept(
            label="Obesity",
            source="mesh",
            source_reference_id="D009765",
            definition="A condition of excess body fat.",
            source_url="https://meshb.nlm.nih.gov/D009765",
            license="public-domain",
            retrieved_at="2026-07-29T00:00:00Z",
        )
        second = repository.get_or_create_concept(
            label="Obesity (duplicate label)",
            source="mesh",
            source_reference_id="D009765",
            definition="A condition of excess body fat.",
            source_url="https://meshb.nlm.nih.gov/D009765",
            license="public-domain",
            retrieved_at="2026-07-29T00:00:00Z",
        )
        assert first.id == second.id
        assert second.label == "Obesity"

    with database.session() as session:
        repository = GraphRepository(session)
        fetched = repository.get_concept(first.id)
        assert fetched is not None
        assert fetched.label == "Obesity"
        assert fetched.definition == "A condition of excess body fat."


def test_get_or_create_concept_never_dedupes_bare_pico_concepts(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        first = repository.get_or_create_concept(
            label="Adults with obesity",
            source="pico",
            source_reference_id=None,
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        second = repository.get_or_create_concept(
            label="Adults with obesity",
            source="pico",
            source_reference_id=None,
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        assert first.id != second.id


def test_get_or_create_concept_rejects_invalid_source(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with pytest.raises(IntegrityError), database.session() as session:
        repository = GraphRepository(session)
        repository.get_or_create_concept(
            label="Bogus",
            source="not-a-real-source",
            source_reference_id=None,
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )


def test_get_or_create_claim_is_idempotent(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        first = repository.get_or_create_claim("ev-glp1-step5-body-weight-week104-001")
        second = repository.get_or_create_claim("ev-glp1-step5-body-weight-week104-001")
        assert first.id == second.id

    with database.session() as session:
        repository = GraphRepository(session)
        fetched = repository.get_claim(first.id)
        assert fetched is not None
        assert fetched.evidence_record_id == "ev-glp1-step5-body-weight-week104-001"


def test_get_or_create_claim_sets_corpus_id_only_on_creation(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        created = repository.get_or_create_claim("ev-a", corpus_id="glp1_weight_loss")
        assert created.corpus_id == "glp1_weight_loss"

        fetched_again = repository.get_or_create_claim(
            "ev-a", corpus_id="oncology_nsclc_checkpoint_inhibitors"
        )
        assert fetched_again.id == created.id
        assert fetched_again.corpus_id == "glp1_weight_loss"


def test_get_or_create_claim_defaults_corpus_id_to_none(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-a")
        assert claim.corpus_id is None


def test_backfill_claim_corpus_id_fills_only_unscoped_matching_claims(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        unscoped = repository.get_or_create_claim("ev-unscoped")
        already_scoped = repository.get_or_create_claim(
            "ev-already-scoped", corpus_id="oncology_nsclc_checkpoint_inhibitors"
        )

        updated = repository.backfill_claim_corpus_id(
            ["ev-unscoped", "ev-already-scoped", "ev-does-not-exist"], "glp1_weight_loss"
        )

        assert updated == 1
        refetched_unscoped = repository.get_claim(unscoped.id)
        refetched_already_scoped = repository.get_claim(already_scoped.id)
        assert refetched_unscoped is not None
        assert refetched_already_scoped is not None
        assert refetched_unscoped.corpus_id == "glp1_weight_loss"
        assert refetched_already_scoped.corpus_id == "oncology_nsclc_checkpoint_inhibitors"


def test_backfill_claim_corpus_id_returns_zero_for_empty_input(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        assert repository.backfill_claim_corpus_id([], "glp1_weight_loss") == 0


def test_find_claim_by_evidence_id_is_read_only(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        repository.get_or_create_claim("ev-1")

    with database.session() as session:
        repository = GraphRepository(session)
        found = repository.find_claim_by_evidence_id("ev-1")
        assert found is not None
        assert found.evidence_record_id == "ev-1"

        missing = repository.find_claim_by_evidence_id("ev-does-not-exist")
        assert missing is None

    with database.session() as session:
        repository = GraphRepository(session)
        counts = repository.population_counts()
        assert counts["claims"] == 1


def test_link_claim_concept_is_idempotent_per_edge_role(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        concept = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )

        first_edge = repository.link_claim_concept(claim.id, concept.id, "intervention")
        second_edge = repository.link_claim_concept(claim.id, concept.id, "intervention")
        assert first_edge.id == second_edge.id

        other_role_edge = repository.link_claim_concept(claim.id, concept.id, "outcome")
        assert other_role_edge.id != first_edge.id


def test_concept_edges_for_claim_preserves_edge_role(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        semaglutide = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        placebo = repository.get_or_create_concept(
            label="Placebo",
            source="rxnorm",
            source_reference_id="999999",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        repository.link_claim_concept(claim.id, semaglutide.id, "intervention")
        repository.link_claim_concept(claim.id, placebo.id, "comparator")

        claim_id = claim.id

    with database.session() as session:
        repository = GraphRepository(session)
        edges = repository.concept_edges_for_claim(claim_id)
        assert [(role, concept.label) for role, concept in edges] == [
            ("comparator", "Placebo"),
            ("intervention", "Semaglutide"),
        ]


def test_link_claim_concept_rejects_invalid_edge_role(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with pytest.raises(IntegrityError), database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        concept = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        repository.link_claim_concept(claim.id, concept.id, "not-a-real-role")


def test_get_or_create_relationship_edge_is_idempotent(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        source_claim = repository.get_or_create_claim("ev-source")
        target_claim = repository.get_or_create_claim("ev-target")

        first = repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=source_claim.id,
            target_claim_id=target_claim.id,
            relationship_type="supports",
            rationale="Both records report consistent weight-loss outcomes.",
        )
        second = repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=source_claim.id,
            target_claim_id=target_claim.id,
            relationship_type="supports",
            rationale="Both records report consistent weight-loss outcomes.",
        )
        assert first.id == second.id


def test_get_or_create_relationship_edge_accepts_supersedes(tmp_path: Path) -> None:
    """M50: `supersedes` is a fifth valid relationship_type -- a newer claim
    explicitly revising an older one, the Stability Score revision-event
    mechanism `docs/stability_and_tracking_design.md` designed."""

    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        older_claim = repository.get_or_create_claim("ev-older")
        newer_claim = repository.get_or_create_claim("ev-newer")

        edge = repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=newer_claim.id,
            target_claim_id=older_claim.id,
            relationship_type="supersedes",
            rationale="A later, larger trial revises the earlier estimate.",
        )
        assert edge.relationship_type == "supersedes"


def test_get_or_create_relationship_edge_rejects_invalid_type(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with pytest.raises(IntegrityError), database.session() as session:
        repository = GraphRepository(session)
        source_claim = repository.get_or_create_claim("ev-source")
        target_claim = repository.get_or_create_claim("ev-target")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=source_claim.id,
            target_claim_id=target_claim.id,
            relationship_type="not-a-real-type",
            rationale="Bogus.",
        )


def test_traversal_queries(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        other_claim = repository.get_or_create_claim("ev-2")
        population_concept = repository.get_or_create_concept(
            label="Adults with obesity",
            source="pico",
            source_reference_id=None,
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        intervention_concept = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        repository.link_claim_concept(claim.id, population_concept.id, "population")
        repository.link_claim_concept(claim.id, intervention_concept.id, "intervention")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=claim.id,
            target_claim_id=other_claim.id,
            relationship_type="supports",
            rationale="Consistent outcomes.",
        )

        claim_id = claim.id
        other_claim_id = other_claim.id
        population_concept_id = population_concept.id
        intervention_concept_id = intervention_concept.id

    with database.session() as session:
        repository = GraphRepository(session)

        concepts = repository.concepts_for_claim(claim_id)
        assert {concept.id for concept in concepts} == {
            population_concept_id,
            intervention_concept_id,
        }

        claims = repository.claims_for_concept(population_concept_id)
        assert [claim.id for claim in claims] == [claim_id]

        relationships_from_source = repository.relationships_for_claim(claim_id)
        assert len(relationships_from_source) == 1
        assert relationships_from_source[0].relationship_id == "rel-1"

        relationships_from_target = repository.relationships_for_claim(other_claim_id)
        assert len(relationships_from_target) == 1
        assert relationships_from_target[0].relationship_id == "rel-1"


def test_traversal_queries_dedupe_concept_linked_via_multiple_edge_roles(
    tmp_path: Path,
) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim = repository.get_or_create_claim("ev-1")
        concept = repository.get_or_create_concept(
            label="Placebo",
            source="rxnorm",
            source_reference_id="999999",
            definition=None,
            source_url=None,
            license=None,
            retrieved_at="2026-07-29T00:00:00Z",
        )
        repository.link_claim_concept(claim.id, concept.id, "intervention")
        repository.link_claim_concept(claim.id, concept.id, "comparator")

        claim_id = claim.id
        concept_id = concept.id

    with database.session() as session:
        repository = GraphRepository(session)

        concepts = repository.concepts_for_claim(claim_id)
        assert [c.id for c in concepts] == [concept_id]

        claims = repository.claims_for_concept(concept_id)
        assert [c.id for c in claims] == [claim_id]


def test_add_citation_edge_is_idempotent(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        paper_repository = PaperRepository(session)
        citing = paper_repository.add_parsed_paper(_parsed_paper(tmp_path, "a"))
        cited = paper_repository.add_parsed_paper(_parsed_paper(tmp_path, "b"))

        repository = GraphRepository(session)
        first = repository.add_citation_edge(
            citing_paper_id=citing.id,
            cited_paper_id=cited.id,
            raw_citation_text="1. Some cited work. doi: 10.1234/b",
        )
        second = repository.add_citation_edge(
            citing_paper_id=citing.id,
            cited_paper_id=cited.id,
            raw_citation_text="1. Some cited work. doi: 10.1234/b",
        )
        assert first.id == second.id


def test_add_citation_edge_rejects_self_citation(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with pytest.raises(IntegrityError), database.session() as session:
        paper_repository = PaperRepository(session)
        paper = paper_repository.add_parsed_paper(_parsed_paper(tmp_path, "a"))

        repository = GraphRepository(session)
        repository.add_citation_edge(
            citing_paper_id=paper.id,
            cited_paper_id=paper.id,
            raw_citation_text="Self-citation, should be rejected.",
        )


def test_citations_for_paper_returns_edges_in_both_directions(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        paper_repository = PaperRepository(session)
        citing = paper_repository.add_parsed_paper(_parsed_paper(tmp_path, "a"))
        cited = paper_repository.add_parsed_paper(_parsed_paper(tmp_path, "b"))

        repository = GraphRepository(session)
        repository.add_citation_edge(
            citing_paper_id=citing.id,
            cited_paper_id=cited.id,
            raw_citation_text="1. Some cited work. doi: 10.1234/b",
        )

        citing_id = citing.id
        cited_id = cited.id

    with database.session() as session:
        repository = GraphRepository(session)

        as_citer = repository.citations_for_paper(citing_id)
        assert len(as_citer) == 1
        assert as_citer[0].citing_paper_id == citing_id

        as_cited = repository.citations_for_paper(cited_id)
        assert len(as_cited) == 1
        assert as_cited[0].cited_paper_id == cited_id

        counts = repository.population_counts()
        assert counts["citation_edges"] == 1


def test_unconfirmed_claims_returns_only_claims_with_no_relationship_edge(
    tmp_path: Path,
) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        confirmed_source = repository.get_or_create_claim("ev-confirmed-source")
        confirmed_target = repository.get_or_create_claim("ev-confirmed-target")
        unconfirmed = repository.get_or_create_claim("ev-unconfirmed")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=confirmed_source.id,
            target_claim_id=confirmed_target.id,
            relationship_type="supports",
            rationale="Both records report consistent weight-loss outcomes.",
        )

        results = repository.unconfirmed_claims()

        assert [claim.evidence_record_id for claim in results] == ["ev-unconfirmed"]
        assert unconfirmed.id in {claim.id for claim in results}


def test_unconfirmed_claims_is_empty_when_every_claim_has_an_edge(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        source = repository.get_or_create_claim("ev-source")
        target = repository.get_or_create_claim("ev-target")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=source.id,
            target_claim_id=target.id,
            relationship_type="supersedes",
            rationale="A later trial revises the earlier estimate.",
        )

        assert repository.unconfirmed_claims() == []


def test_relationship_candidates_surfaces_pairs_sharing_a_concept(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim_a = repository.get_or_create_claim("ev-a")
        claim_b = repository.get_or_create_claim("ev-b")
        semaglutide = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition="A GLP-1 receptor agonist.",
            source_url="https://rxnav.nlm.nih.gov/123456",
            license="public-domain",
            retrieved_at="2026-07-30T00:00:00Z",
        )
        repository.link_claim_concept(claim_a.id, semaglutide.id, "intervention")
        repository.link_claim_concept(claim_b.id, semaglutide.id, "intervention")

        candidates = repository.relationship_candidates()

        assert len(candidates) == 1
        found_a, found_b, shared_concepts = candidates[0]
        assert {found_a.id, found_b.id} == {claim_a.id, claim_b.id}
        assert [concept.id for concept in shared_concepts] == [semaglutide.id]


def test_relationship_candidates_excludes_pairs_with_an_existing_relationship_edge(
    tmp_path: Path,
) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim_a = repository.get_or_create_claim("ev-a")
        claim_b = repository.get_or_create_claim("ev-b")
        concept = repository.get_or_create_concept(
            label="Obesity",
            source="mesh",
            source_reference_id="D009765",
            definition="A condition of excess body fat.",
            source_url="https://meshb.nlm.nih.gov/D009765",
            license="public-domain",
            retrieved_at="2026-07-30T00:00:00Z",
        )
        repository.link_claim_concept(claim_a.id, concept.id, "population")
        repository.link_claim_concept(claim_b.id, concept.id, "population")
        repository.get_or_create_relationship_edge(
            "rel-1",
            source_claim_id=claim_a.id,
            target_claim_id=claim_b.id,
            relationship_type="contextualizes",
            rationale="A reviewer already linked these two records.",
        )

        assert repository.relationship_candidates() == []


def test_relationship_candidates_respects_minimum_shared_concepts(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim_a = repository.get_or_create_claim("ev-a")
        claim_b = repository.get_or_create_claim("ev-b")
        population = repository.get_or_create_concept(
            label="Obesity",
            source="mesh",
            source_reference_id="D009765",
            definition="A condition of excess body fat.",
            source_url="https://meshb.nlm.nih.gov/D009765",
            license="public-domain",
            retrieved_at="2026-07-30T00:00:00Z",
        )
        repository.link_claim_concept(claim_a.id, population.id, "population")
        repository.link_claim_concept(claim_b.id, population.id, "population")

        assert repository.relationship_candidates(minimum_shared_concepts=2) == []
        assert len(repository.relationship_candidates(minimum_shared_concepts=1)) == 1


def test_relationship_candidates_corpus_id_scopes_to_matching_claims_only(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim_a = repository.get_or_create_claim("ev-a", corpus_id="glp1_weight_loss")
        claim_b = repository.get_or_create_claim("ev-b", corpus_id="glp1_weight_loss")
        claim_c = repository.get_or_create_claim(
            "ev-c", corpus_id="oncology_nsclc_checkpoint_inhibitors"
        )
        semaglutide = repository.get_or_create_concept(
            label="Semaglutide",
            source="rxnorm",
            source_reference_id="123456",
            definition="A GLP-1 receptor agonist.",
            source_url="https://rxnav.nlm.nih.gov/123456",
            license="public-domain",
            retrieved_at="2026-08-10T00:00:00Z",
        )
        repository.link_claim_concept(claim_a.id, semaglutide.id, "intervention")
        repository.link_claim_concept(claim_b.id, semaglutide.id, "intervention")
        repository.link_claim_concept(claim_c.id, semaglutide.id, "intervention")

        unscoped = repository.relationship_candidates()
        assert len(unscoped) == 3

        scoped = repository.relationship_candidates(corpus_id="glp1_weight_loss")
        assert len(scoped) == 1
        found_a, found_b, _shared = scoped[0]
        assert {found_a.id, found_b.id} == {claim_a.id, claim_b.id}


def test_relationship_candidates_corpus_id_excludes_unscoped_claims(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = GraphRepository(session)
        claim_a = repository.get_or_create_claim("ev-a", corpus_id="glp1_weight_loss")
        claim_b_unscoped = repository.get_or_create_claim("ev-b")
        concept = repository.get_or_create_concept(
            label="Obesity",
            source="mesh",
            source_reference_id="D009765",
            definition="A condition of excess body fat.",
            source_url="https://meshb.nlm.nih.gov/D009765",
            license="public-domain",
            retrieved_at="2026-08-10T00:00:00Z",
        )
        repository.link_claim_concept(claim_a.id, concept.id, "population")
        repository.link_claim_concept(claim_b_unscoped.id, concept.id, "population")

        assert repository.relationship_candidates(corpus_id="glp1_weight_loss") == []
