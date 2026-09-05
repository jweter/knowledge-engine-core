from typing import Any

from knowledge_engine.cli import REQUIRED_EVIDENCE_FIELDS, _validate_evidence_record
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


def _paper(paper_id: int = 7, doi: str | None = "10.1038/example") -> PaperMetadata:
    return PaperMetadata(paper_id=paper_id, doi=doi, title="Example Trial of a GLP-1 Agonist")


def _to_record_dict(
    item: DraftEvidenceItem,
    evidence_record_id: str = "draft-1",
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a record dict from the item's own fields, plus reviewer-supplied
    values for fields the module leaves None (evidence_record_id, provenance)
    -- mirroring how a real reviewer would complete a draft item."""

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
        "provenance": item.provenance or provenance or {"created_by": "test"},
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
        "paper_id": 7,
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


def test_confidence_interval_is_extracted_from_the_candidate_sentence_itself() -> None:
    """Unlike PICO, a CI is claim-level, not paper-level: it must come from
    this exact candidate's own sentence, not a value broadcast paper-wide."""

    sentence = "Mean weight loss was greater with the study drug (95% CI, 1.1 to 3.4 kg)."
    item = build_draft_evidence_item(_paper(), _framing(_candidate(sentence)))

    assert item.confidence_interval == sentence
    assert item.confidence_interval_extraction_rules_version


def test_confidence_interval_is_none_when_the_sentence_states_no_ci() -> None:
    item = build_draft_evidence_item(_paper(), _framing())

    assert item.confidence_interval is None
    assert item.confidence_interval_extraction_rules_version is not None


def test_confidence_interval_is_not_broadcast_across_a_papers_other_candidates() -> None:
    paper = _paper()
    with_ci = "Response rate improved significantly (95% CI, 1.2 to 4.8)."
    without_ci = "Patients tolerated the regimen well."
    framings = [_framing(_candidate(with_ci)), _framing(_candidate(without_ci))]

    items = build_draft_evidence_items(paper, framings)

    assert items[0].confidence_interval == with_ci
    assert items[1].confidence_interval is None


def test_duration_is_extracted_from_the_candidate_sentence_itself() -> None:
    """Like confidence_interval, duration is claim-level, not paper-level: it
    must come from this exact candidate's own sentence."""

    sentence = "Response rates were assessed following a 24-week treatment period."
    item = build_draft_evidence_item(_paper(), _framing(_candidate(sentence)))

    assert item.duration == sentence
    assert item.duration_extraction_rules_version


def test_duration_is_none_when_the_sentence_states_no_duration() -> None:
    item = build_draft_evidence_item(_paper(), _framing())

    assert item.duration is None
    assert item.duration_extraction_rules_version is not None


def test_duration_is_not_broadcast_across_a_papers_other_candidates() -> None:
    paper = _paper()
    with_duration = "Patients were monitored over the 8-week follow-up period."
    without_duration = "Patients tolerated the regimen well."
    framings = [_framing(_candidate(with_duration)), _framing(_candidate(without_duration))]

    items = build_draft_evidence_items(paper, framings)

    assert items[0].duration == with_duration
    assert items[1].duration is None


def test_dose_is_extracted_from_the_candidate_sentence_itself() -> None:
    """Like confidence_interval/duration, dose is claim-level, not
    paper-level: a dose-escalation study can state several different doses
    of the same intervention within one paper."""

    sentence = "Patients in the escalation cohort received liraglutide 1.8 mg once-daily."
    item = build_draft_evidence_item(_paper(), _framing(_candidate(sentence)))

    assert item.dose == sentence
    assert item.dose_extraction_rules_version


def test_dose_is_none_when_the_sentence_states_no_dose() -> None:
    item = build_draft_evidence_item(_paper(), _framing())

    assert item.dose is None
    assert item.dose_extraction_rules_version is not None


def test_dose_is_not_broadcast_across_a_papers_other_candidates() -> None:
    paper = _paper()
    with_dose = "The dose was increased to 20 mg after one month."
    without_dose = "Patients tolerated the regimen well."
    framings = [_framing(_candidate(with_dose)), _framing(_candidate(without_dose))]

    items = build_draft_evidence_items(paper, framings)

    assert items[0].dose == with_dose
    assert items[1].dose is None


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
    assert item.provenance is None
    assert item.schema_version is None
    assert item.evidence_record_id is None


def test_paper_with_no_doi_produces_none_source_doi_not_a_guess() -> None:
    item = build_draft_evidence_item(_paper(doi=None), _framing())

    assert item.source_doi is None


def test_paper_id_traces_source_span_even_when_doi_is_none() -> None:
    """Titles are not a unique identity in this repository, so a DOI-less
    paper's draft items must still carry a stable local identifier a
    reviewer can use to resolve the source_span back to the exact paper."""

    item = build_draft_evidence_item(_paper(paper_id=42, doi=None), _framing())

    assert item.source_span["paper_id"] == 42


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


def test_draft_item_has_no_provenance_field_populated() -> None:
    """provenance is required by _validate_evidence_record but has no
    honest deterministic source here (created_by/created_date/license info
    are all external to ClaimCandidate/ClaimFraming/PaperMetadata) -- it
    must be represented on the dataclass so a reviewer knows to complete
    it, never silently omitted or fabricated."""

    item = build_draft_evidence_item(_paper(), _framing())

    assert item.provenance is None


def test_draft_item_fails_existing_evidence_validator() -> None:
    """A draft item must be genuinely incomplete, not merely labeled as such:
    the schema's own non-empty-string checks must reject it until a
    reviewer supplies research_question and evidence_direction. provenance
    is supplied here as a stand-in for what a real reviewer would add,
    isolating this assertion to the fields the module itself must leave
    incomplete."""

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert any("research_question is required" in error for error in errors)
    assert any("evidence_direction is required" in error for error in errors)


def test_draft_item_fails_validator_on_missing_provenance_too() -> None:
    """Confirms provenance is one of the fields a reviewer must complete --
    without the module-level docstring's claim being taken on faith."""

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})
    record["provenance"] = None

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert any("provenance must be a non-empty object" in error for error in errors)


def test_confidence_interval_is_additive_not_required() -> None:
    """A record promoted before M74's confidence_interval field existed, and
    still missing the key entirely, must remain valid -- adding a new
    required key would retroactively break every already-promoted evidence
    record in the corpus. `_to_record_dict` never sets the key, matching
    that pre-M74 shape exactly."""

    assert "confidence_interval" not in REQUIRED_EVIDENCE_FIELDS

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})
    assert "confidence_interval" not in record

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert not any("confidence_interval" in error for error in errors)


def test_duration_is_additive_not_required() -> None:
    """A record promoted before M75's duration field existed, and still
    missing the key entirely, must remain valid -- adding a new required key
    would retroactively break every already-promoted evidence record in the
    corpus. `_to_record_dict` never sets the key, matching that pre-M75
    shape exactly."""

    assert "duration" not in REQUIRED_EVIDENCE_FIELDS

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})
    assert "duration" not in record

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert not any("duration" in error for error in errors)


def test_dose_is_additive_not_required() -> None:
    """A record promoted before M76's dose field existed, and still missing
    the key entirely, must remain valid -- adding a new required key would
    retroactively break every already-promoted evidence record in the
    corpus. `_to_record_dict` never sets the key, matching that pre-M76
    shape exactly."""

    assert "dose" not in REQUIRED_EVIDENCE_FIELDS

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})
    assert "dose" not in record

    errors: list[str] = []
    _validate_evidence_record(
        record, line_number=1, seen_ids=set(), errors=errors, require_review_fields=False
    )

    assert not any("dose" in error for error in errors)


def test_draft_item_mechanically_derived_fields_pass_their_own_validator_checks() -> None:
    """The fields this module does populate must be valid, not merely present."""

    item = build_draft_evidence_item(_paper(), _framing())
    record = _to_record_dict(item, provenance={"created_by": "test"})

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
