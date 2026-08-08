import copy
import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.cli import app
from knowledge_engine.evidence_map import (
    EvidenceMapError,
    EvidenceMapValidationResult,
    load_evidence_map,
    validate_evidence_map,
)


def _evidence_records(*, review_status: str = "draft") -> list[dict[str, object]]:
    return [
        {
            "evidence_record_id": "ev-1",
            "source_doi": "10.1000/one",
            "limitations": ["One bounded result."],
            "review_status": review_status,
        },
        {
            "evidence_record_id": "ev-2",
            "source_doi": "10.1000/two",
            "limitations": ["A different population."],
            "review_status": review_status,
        },
    ]


def _relationships(*, relationship_type: str = "supports") -> list[dict[str, object]]:
    return [
        {
            "relationship_id": "rel-1",
            "source_evidence_record_id": "ev-1",
            "target_evidence_record_id": "ev-2",
            "relationship_type": relationship_type,
        }
    ]


def _map_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "map_id": "test-map-v1",
        "title": "Test Evidence Map",
        "research_question": "Does the intervention affect the outcome?",
        "map_status": "provisional",
        "scope": {
            "population": "Adults.",
            "intervention": "Intervention.",
            "outcome": "Outcome.",
            "exclusions": "Other populations.",
        },
        "evidence_nodes": [
            {
                "evidence_record_id": "ev-1",
                "role": "landmark_trial",
                "inclusion_rationale": "Direct randomized evidence.",
            },
            {
                "evidence_record_id": "ev-2",
                "role": "population_extension",
                "inclusion_rationale": "A bounded population extension.",
            },
        ],
        "relationship_ids": ["rel-1"],
        "population_groups": [
            {
                "label": "Adults",
                "evidence_record_ids": ["ev-1", "ev-2"],
                "interpretation_boundary": "Populations are not interchangeable.",
            }
        ],
        "comparator_groups": [
            {
                "label": "Comparators",
                "evidence_record_ids": ["ev-1", "ev-2"],
                "interpretation_boundary": "Comparator differences remain visible.",
            }
        ],
        "contradiction_assessment": {
            "status": "none_identified_in_bounded_map",
            "statement": "No aligned contradiction was identified in this bounded map.",
            "evidence_record_ids": [],
        },
        "limitations": ["This map is bounded."],
        "known_gaps": ["Secondary review remains."],
        "review": {
            "method": "Curated from existing records.",
            "status": "secondary_review_required",
            "notes": "This is not a scientific conclusion.",
        },
    }


def _validate(
    payload: dict[str, object],
    *,
    evidence_records: list[dict[str, object]] | None = None,
    relationships: list[dict[str, object]] | None = None,
) -> EvidenceMapValidationResult:
    return validate_evidence_map(
        payload,
        evidence_records=evidence_records or _evidence_records(),
        relationship_records=relationships or _relationships(),
        citation_dois={"10.1000/one", "10.1000/two"},
    )


def test_valid_provisional_map_preserves_review_warning_and_counts() -> None:
    result = _validate(_map_payload())

    assert result.valid
    assert result.evidence_node_count == 2
    assert result.relationship_count == 1
    assert result.citation_count == 2
    assert result.role_counts == {"landmark_trial": 1, "population_extension": 1}
    assert result.relationship_type_counts == {"supports": 1}
    assert result.warnings == (
        "2 selected Evidence Records remain draft; secondary review is required.",
    )


def test_schema_version_is_exact_integer_one() -> None:
    for invalid_version in (True, 2, "1"):
        payload = _map_payload()
        payload["schema_version"] = invalid_version

        result = _validate(payload)

        assert "schema_version must be integer 1." in result.errors


def test_reviewed_map_rejects_draft_evidence() -> None:
    payload = _map_payload()
    payload["map_status"] = "reviewed"

    result = _validate(payload)

    assert not result.valid
    assert any("reviewed map cannot reference" in error for error in result.errors)


def test_reviewed_map_accepts_reviewed_evidence() -> None:
    payload = _map_payload()
    payload["map_status"] = "reviewed"
    payload["review"] = {
        "method": "Independent source audit.",
        "status": "reviewed",
        "reviewed_by": "Independent reviewer",
        "reviewer_type": "source_audit",
        "review_date": "2026-08-03",
        "notes": "Source fidelity only; not scientific truth.",
    }

    result = _validate(payload, evidence_records=_evidence_records(review_status="reviewed"))

    assert result.valid
    assert result.warnings == ()


def test_reviewed_map_requires_matching_review_provenance() -> None:
    payload = _map_payload()
    payload["map_status"] = "reviewed"
    evidence_records = _evidence_records(review_status="reviewed")

    result = _validate(payload, evidence_records=evidence_records)

    assert not result.valid
    assert "A reviewed map must have review.status set to 'reviewed'." in result.errors

    payload["review"] = {
        "method": "Independent source audit.",
        "status": "reviewed",
        "notes": "Source fidelity only.",
    }
    result = _validate(payload, evidence_records=evidence_records)

    assert "review.reviewed_by must be non-empty text." in result.errors
    assert "review.reviewer_type must be non-empty text." in result.errors
    assert "review.review_date must be non-empty text." in result.errors


def test_unknown_evidence_and_incomplete_citation_are_rejected() -> None:
    payload = _map_payload()
    nodes = copy.deepcopy(payload["evidence_nodes"])
    assert isinstance(nodes, list)
    nodes[1]["evidence_record_id"] = "ev-missing"
    payload["evidence_nodes"] = nodes

    result = _validate(payload)

    assert not result.valid
    assert any("unknown Evidence Record 'ev-missing'" in error for error in result.errors)

    citation_result = validate_evidence_map(
        _map_payload(),
        evidence_records=_evidence_records(),
        relationship_records=_relationships(),
        citation_dois={"10.1000/one"},
    )
    assert any("no complete citation row" in error for error in citation_result.errors)


def test_relationship_endpoints_must_both_be_selected() -> None:
    relationships = _relationships()
    relationships[0]["target_evidence_record_id"] = "ev-3"

    result = _validate(_map_payload(), relationships=relationships)

    assert not result.valid
    assert any("endpoint 'ev-3' is not selected" in error for error in result.errors)


def test_unknown_relationship_is_rejected() -> None:
    payload = _map_payload()
    payload["relationship_ids"] = ["rel-missing"]

    result = _validate(payload)

    assert not result.valid
    assert any("unknown Relationship Record 'rel-missing'" in error for error in result.errors)


def test_population_and_comparator_groups_must_cover_every_node() -> None:
    payload = _map_payload()
    population_groups = copy.deepcopy(payload["population_groups"])
    assert isinstance(population_groups, list)
    population_groups[0]["evidence_record_ids"] = ["ev-1"]
    payload["population_groups"] = population_groups

    result = _validate(payload)

    assert not result.valid
    assert "population_groups do not classify: ev-2." in result.errors


def test_contradiction_assessment_must_match_selected_relationships() -> None:
    result = _validate(
        _map_payload(), relationships=_relationships(relationship_type="contradicts")
    )

    assert not result.valid
    assert any("declares none identified" in error for error in result.errors)


def test_load_evidence_map_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text("{", encoding="utf-8")

    try:
        load_evidence_map(path)
    except EvidenceMapError as exc:
        assert str(exc) == "Evidence map is not valid JSON: map.json"
    else:
        raise AssertionError("Malformed JSON should fail to load.")


def test_committed_glp1_golden_map_passes_cli_validation() -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-validate",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--relationships",
            str(corpus / "relationship_records.jsonl"),
            "--sources",
            str(corpus / "sources.csv"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Evidence map validation passed" in result.output
    assert "Map status: reviewed" in result.output
    assert "Evidence nodes: 14" in result.output
    assert "Relationship records: 19" in result.output
    assert "Complete citations: 14/14" in result.output
    normalized_output = " ".join(result.output.split())
    assert "secondary review is required" not in normalized_output
    assert "No evidence, relationship, or scientific conclusion was inferred" in result.output
    assert "does not constitute legal approval, scientific review" in normalized_output


def test_committed_glp1_golden_map_preserves_secondary_review_provenance() -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    map_payload = json.loads((corpus / "golden_evidence_map.json").read_text(encoding="utf-8"))
    selected_evidence_ids = {node["evidence_record_id"] for node in map_payload["evidence_nodes"]}
    selected_relationship_ids = set(map_payload["relationship_ids"])
    evidence_records = [
        json.loads(line)
        for line in (corpus / "evidence_records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    relationship_records = [
        json.loads(line)
        for line in (corpus / "relationship_records.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    selected_evidence = [
        record
        for record in evidence_records
        if record["evidence_record_id"] in selected_evidence_ids
    ]
    selected_relationships = [
        record
        for record in relationship_records
        if record["relationship_id"] in selected_relationship_ids
    ]

    assert len(selected_evidence) == 14
    assert len(selected_relationships) == 19
    for record in selected_evidence:
        assert record["review_status"] == "reviewed"
        assert record["review_checklist"]["secondary_review_completed"] is True
        assert "human_reviewed" not in record
        review = record["provenance"]["secondary_review"]
        assert review["reviewer_type"] == "ai_assisted_independent_source_audit"
    for relationship in selected_relationships:
        review = relationship["provenance"]["secondary_review"]
        assert review["reviewer_type"] == "ai_assisted_independent_source_audit"


def test_cli_rejects_invalid_map_without_inference(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    map_path = tmp_path / "invalid-map.json"
    map_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-validate",
            str(map_path),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--relationships",
            str(corpus / "relationship_records.jsonl"),
            "--sources",
            str(corpus / "sources.csv"),
        ],
    )

    assert result.exit_code == 1
    assert "Evidence map validation failed" in result.output
    assert "map.map_id must be non-empty text" in result.output
    assert "No evidence, relationship, or scientific conclusion was inferred" in result.output
