from typing import Any

from knowledge_engine.cli import _validate_evidence_record
from knowledge_engine.extraction import (
    CLAIM_FRAMING_RULES_VERSION,
    ClaimCandidate,
    ClaimFraming,
    DraftEvidenceItem,
    PaperMetadata,
    build_draft_evidence_item,
    build_draft_evidence_items,
)


def _candidate(
    sentence_text: str = "Body weight decreased by 12.4% from baseline.",
) -> ClaimCandidate:
    return ClaimCandidate(
        sentence_text=sentence_text,
        section_type="results",
        page_number=3,
        start_offset=100,
        end_offset=100 + len(sentence_text),
        matched_signal="percentage",
        rules_version="m17-claim-candidate-v1",
    )


def _framing(
    candidate: ClaimCandidate | None = None, framing: str = "unclassified"
) -> ClaimFraming:
    return ClaimFraming(
        candidate=candidate or _candidate(),
        framing=framing,
        matched_cue=None,
        rules_version=CLAIM_FRAMING_RULES_VERSION,
    )


def _paper(doi: str | None = "10.1038/example") -> PaperMetadata:
    return PaperMetadata(doi=doi, title="Example Trial of a GLP-1 Agonist")


def _to_record_dict(item: DraftEvidenceItem, evidence_record_id: str = "draft-1") -> dict[str, Any]:
    return {
        "schema_version": item.schema_version,
        "evidence_record_id": item.evidence_record_id or evidence_record_id,
        "extraction_method": item.extraction_method,
        "extraction_status": item.extraction_status,
        "source_doi": item.source_doi,
        "source_title": item.source_title,
        "source_type": item.source_type,
        "study_type": item.study_type,
        "research_question": item.research_question,
        "claim_text": item.claim_text,
        "evidence_direction": item.evidence_direction,
        "population": item.population,
        "intervention": item.intervention,
        "comparator": item.comparator,
        "outcome": item.outcome,
        "result_summary": item.result_summary,
        "source_span": item.source_span,
        "limitations": item.limitations,
        "uncertainty_notes": item.uncertainty_notes,
        "confidence_note": item.confidence_note,
        "provenance": {"created_by": "test"},
        "created_for_milestone": item.created_for_milestone,
    }


def test_mechanically_derivable_fields_are_populated() -> None:
    candidate = _candidate()
    framing = _framing(candidate, framing="contextualizes")
    paper = _paper()

    item = build_draft_evidence_item(paper, framing)

    assert item.claim_framing is framing
    assert item.claim_text == candidate.sentence_text
    assert item.result_summary == candidate.sentence_text
    assert item.source_span == {
        "page_number": 3,
        "section": "results",
        "start_offset": 100,
        "end_offset": 100 + len(candidate.sentence_text),
    }
    assert item.source_doi == "10.1038/example"
    assert item.source_title == "Example Trial of a GLP-1 Agonist"
    assert item.source_type == "paper"
    assert item.extraction_status == "draft_review_required"
    assert item.created_for_milestone == "M19"


def test_fields_requiring_human_input_are_none() -> None:
    item = build_draft_evidence_item(_paper(), _framing())

    assert item.research_question is None
    assert item.evidence_direction is None
    assert item.study_type is None
    assert item.population is None
    assert item.intervention is None
    assert item.comparator is None
    assert item.outcome is None
    assert item.limitations is None
    assert item.uncertainty_notes is None
    assert item.confidence_note is None
    assert item.schema_version is None
    assert item.evidence_record_id is None


def test_paper_with_no_doi_produces_none_source_doi_not_a_guess() -> None:
    item = build_draft_evidence_item(_paper(doi=None), _framing())

    assert item.source_doi is None


def test_batch_produces_one_item_per_candidate_in_order_sharing_paper_metadata() -> None:
    paper = _paper()
    framings = [
        _framing(_candidate("Body weight decreased by 12.4% from baseline.")),
        _framing(_candidate("This is consistent with prior trials."), framing="contextualizes"),
    ]

    items = build_draft_evidence_items(paper, framings)

    assert len(items) == 2
    assert [item.claim_text for item in items] == [f.candidate.sentence_text for f in framings]
    assert all(item.source_doi == paper.doi for item in items)
    assert all(item.source_title == paper.title for item in items)


def test_no_framings_produces_no_items() -> None:
    assert build_draft_evidence_items(_paper(), []) == ()


def test_draft_item_fails_existing_evidence_validator() -> None:
    """A draft item must be genuinely incomplete, not merely labeled as such:
    the schema's own non-empty-string checks must reject it until a
    reviewer supplies research_question and evidence_direction."""

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item)

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert any("research_question is required" in error for error in errors)
    assert any("evidence_direction is required" in error for error in errors)


def test_draft_item_mechanically_derived_fields_pass_their_own_validator_checks() -> None:
    """The fields this module does populate must be valid, not merely present."""

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item)

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert not any("source_doi is required" in error for error in errors)
    assert not any("source_title is required" in error for error in errors)
    assert not any("claim_text is required" in error for error in errors)
    assert not any("result_summary is required" in error for error in errors)
    assert not any("extraction_method is required" in error for error in errors)
    assert not any("extraction_status is required" in error for error in errors)
    assert not any("source_span" in error for error in errors)
