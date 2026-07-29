from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, GraphRepository


def build_database(tmp_path: Path) -> Database:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
    )
    database = Database(settings)
    database.initialize()
    return database


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
