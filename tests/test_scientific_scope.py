from __future__ import annotations

import pytest

from knowledge_engine.scientific_scope import (
    GLP1_METABOLIC_SCOPE,
    ONCOLOGY_NSCLC_CHECKPOINT_SCOPE,
    ScopeVocabulary,
    evaluate_scientific_scope,
    resolve_scope_vocabulary,
)


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


def test_default_vocabulary_is_glp1_metabolic_scope() -> None:
    with_default = evaluate_scientific_scope("Pembrolizumab for non-small-cell lung cancer", None)
    with_explicit_default = evaluate_scientific_scope(
        "Pembrolizumab for non-small-cell lung cancer", None, vocabulary=GLP1_METABOLIC_SCOPE
    )
    assert with_default == with_explicit_default == "insufficient_title_abstract_evidence"


def test_oncology_vocabulary_passes_a_matching_oncology_title() -> None:
    result = evaluate_scientific_scope(
        "Pembrolizumab therapy for adults with non-small-cell lung cancer",
        None,
        vocabulary=ONCOLOGY_NSCLC_CHECKPOINT_SCOPE,
    )
    assert result == "passed"


def test_oncology_vocabulary_rejects_a_glp1_title() -> None:
    result = evaluate_scientific_scope(
        "Semaglutide therapy for adults with obesity",
        None,
        vocabulary=ONCOLOGY_NSCLC_CHECKPOINT_SCOPE,
    )
    assert result == "insufficient_title_abstract_evidence"


def test_glp1_vocabulary_rejects_an_oncology_title() -> None:
    result = evaluate_scientific_scope(
        "Pembrolizumab therapy for adults with non-small-cell lung cancer",
        None,
        vocabulary=GLP1_METABOLIC_SCOPE,
    )
    assert result == "insufficient_title_abstract_evidence"


def test_oncology_vocabulary_pediatric_title_without_adult_term_is_flagged() -> None:
    result = evaluate_scientific_scope(
        "Pembrolizumab therapy for non-small-cell lung cancer in adolescents",
        None,
        vocabulary=ONCOLOGY_NSCLC_CHECKPOINT_SCOPE,
    )
    assert result == "pediatric_population_title_evidence"


def test_resolve_scope_vocabulary_returns_the_matching_vocabulary() -> None:
    assert resolve_scope_vocabulary("glp1_weight_loss") is GLP1_METABOLIC_SCOPE
    assert resolve_scope_vocabulary("oncology_nsclc_checkpoint_inhibitors") is (
        ONCOLOGY_NSCLC_CHECKPOINT_SCOPE
    )


def test_resolve_scope_vocabulary_raises_on_unknown_corpus_id() -> None:
    with pytest.raises(KeyError, match="Unknown corpus id 'not_a_real_corpus'"):
        resolve_scope_vocabulary("not_a_real_corpus")


def test_scope_vocabulary_is_frozen() -> None:
    vocabulary = ScopeVocabulary(corpus_id="test", disease_terms=("x",), intervention_terms=("y",))
    with pytest.raises(AttributeError):
        vocabulary.corpus_id = "changed"  # type: ignore[misc]
