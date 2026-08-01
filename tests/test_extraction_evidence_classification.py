from typing import Any

from knowledge_engine.extraction import (
    EVIDENCE_CLASSIFICATION_RULES_VERSION,
    build_automated_evidence_record,
    classify_evidence_direction,
    generate_research_question,
)


def _draft_item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": None,
        "evidence_record_id": None,
        "extraction_method": "m19-draft-evidence-item-v1",
        "extraction_status": "draft_review_required",
        "source_doi": "10.1000/example",
        "source_title": "An example paper",
        "source_type": "paper",
        "study_type": "randomized_controlled_trial",
        "research_question": None,
        "claim_text": "Semaglutide reduced body weight by 12.4% versus placebo (p<0.001).",
        "evidence_direction": None,
        "population": "Adults with obesity.",
        "intervention": "Semaglutide 2.4 mg weekly.",
        "comparator": "Placebo.",
        "outcome": "Percentage change in body weight.",
        "result_summary": "Body weight decreased by 12.4% with semaglutide versus placebo.",
        "source_span": {"paper_id": 1, "page_number": 2},
        "limitations": None,
        "uncertainty_notes": None,
        "confidence_note": None,
        "provenance": None,
        "created_for_milestone": "M19",
    }
    base.update(overrides)
    return base


def test_rules_version_is_stable() -> None:
    assert EVIDENCE_CLASSIFICATION_RULES_VERSION == "m52-evidence-classification-v1"


def test_generate_research_question_requires_all_four_pico_fields() -> None:
    assert (
        generate_research_question(
            "Adults with obesity.", "Semaglutide.", None, "Body weight change."
        )
        is None
    )
    assert generate_research_question("", "Semaglutide.", "Placebo.", "Body weight.") is None


def test_generate_research_question_declines_an_overlong_field() -> None:
    overlong = "x" * 301
    assert generate_research_question("Adults.", overlong, "Placebo.", "Body weight.") is None


def test_generate_research_question_includes_all_four_fields() -> None:
    question = generate_research_question(
        "Adults with obesity.",
        "Semaglutide 2.4 mg weekly.",
        "Placebo.",
        "Percentage change in body weight.",
    )
    assert question is not None
    assert "Adults with obesity." in question
    assert "Semaglutide 2.4 mg weekly." in question
    assert "Placebo." in question
    assert "Percentage change in body weight." in question


def test_classify_evidence_direction_defaults_to_supports() -> None:
    direction, cue = classify_evidence_direction(
        "Semaglutide reduced body weight by 12.4% versus placebo (p<0.001)."
    )
    assert direction == "supports"
    assert cue is None


def test_classify_evidence_direction_detects_no_significant_difference() -> None:
    direction, cue = classify_evidence_direction(
        "There was no significant difference in HbA1c between groups."
    )
    assert direction == "qualifies"
    assert cue == "no significant difference"


def test_classify_evidence_direction_detects_did_not_differ() -> None:
    direction, _cue = classify_evidence_direction(
        "Fasting glucose did not differ between the intervention and control arms."
    )
    assert direction == "qualifies"


def test_classify_evidence_direction_detects_contradicts_cue() -> None:
    direction, cue = classify_evidence_direction(
        "This result is in contrast to earlier reports of minimal effect."
    )
    assert direction == "contradicts"
    assert cue == "in contrast to"


def test_classify_evidence_direction_detects_contextualizes_cue() -> None:
    direction, cue = classify_evidence_direction(
        "This finding is consistent with prior trials showing weight loss."
    )
    assert direction == "contextualizes"
    assert cue == "consistent with"


def test_build_automated_evidence_record_fills_required_fields() -> None:
    record = build_automated_evidence_record(_draft_item())

    assert record is not None
    assert record["research_question"] is not None
    assert record["evidence_direction"] == "supports"
    assert record["extraction_method"] == EVIDENCE_CLASSIFICATION_RULES_VERSION
    assert record["extraction_method"] != "manual_human_review"
    assert record["review_status"] == "draft"
    assert record["review_checklist"]["human_reviewed"] is False
    assert "no human read or confirmed" in record["review_notes"]
    assert record["uncertainty_notes"]
    assert record["confidence_note"]
    assert record["provenance"]
    assert record["claim_text"] == _draft_item()["claim_text"]


def test_build_automated_evidence_record_never_overwrites_existing_notes() -> None:
    record = build_automated_evidence_record(
        _draft_item(
            uncertainty_notes="existing note",
            confidence_note="existing confidence",
            provenance={"created_by": "existing"},
        )
    )

    assert record is not None
    assert record["uncertainty_notes"] == "existing note"
    assert record["confidence_note"] == "existing confidence"
    assert record["provenance"] == {"created_by": "existing"}


def test_build_automated_evidence_record_returns_none_without_claim_text() -> None:
    assert build_automated_evidence_record(_draft_item(claim_text=None)) is None


def test_build_automated_evidence_record_returns_none_without_result_summary() -> None:
    assert build_automated_evidence_record(_draft_item(result_summary="")) is None


def test_build_automated_evidence_record_returns_none_missing_a_pico_field() -> None:
    assert build_automated_evidence_record(_draft_item(comparator=None)) is None


def test_build_automated_evidence_record_returns_none_for_overlong_pico_field() -> None:
    assert build_automated_evidence_record(_draft_item(intervention="x" * 400)) is None
