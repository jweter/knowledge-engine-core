from __future__ import annotations

from knowledge_engine.scientific_scope import evaluate_scientific_scope


def test_disease_and_intervention_evidence_passes() -> None:
    result = evaluate_scientific_scope("Semaglutide therapy for adults with obesity", None)
    assert result == "passed"


def test_abstract_can_supply_missing_evidence() -> None:
    result = evaluate_scientific_scope(
        "A randomized controlled trial", "Adults with obesity received metformin therapy."
    )
    assert result == "passed"


def test_missing_disease_or_intervention_terms_is_insufficient() -> None:
    result = evaluate_scientific_scope("A survey of unrelated materials science topics", None)
    assert result == "insufficient_title_abstract_evidence"


def test_correction_notice_title_is_non_primary_content() -> None:
    result = evaluate_scientific_scope(
        "Correction: Semaglutide therapy for adults with obesity", None
    )
    assert result == "non_primary_content_title_evidence"


def test_pediatric_only_title_is_flagged() -> None:
    result = evaluate_scientific_scope("Semaglutide therapy for obesity in adolescents", None)
    assert result == "pediatric_population_title_evidence"


def test_pediatric_and_adult_title_passes() -> None:
    result = evaluate_scientific_scope(
        "Semaglutide therapy for obesity in adolescents and adults", None
    )
    assert result == "passed"
