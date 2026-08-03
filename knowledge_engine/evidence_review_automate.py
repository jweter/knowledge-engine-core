"""M69's automated evidence-review pipeline: batch orchestration.

`docs/roadmap/long_term_vision.md`'s "Decision: automated evidence review
at scale" replaces the human-reading review gate with a grounding-verified
LLM extraction path. This module is the batch driver: for each still-automated
`EvidenceRecord`, it re-derives `population`/`intervention`/`comparator`/
`outcome` per candidate (via `knowledge_engine.extraction.llm_grounded_pico`,
scoped to the claim page plus page 1 when they differ), accepts only fields that pass
`knowledge_engine.extraction.grounding.verify_grounding`, and honestly
labels the result. It never touches `claim_text`, `research_question`, or
`evidence_direction` -- those stay on their existing deterministic path,
per the decision doc's own scoping.

This module only edits `EvidenceRecord` dicts in memory; it does not read
or write the graph database, and does not re-run `ke graph-build`. A
record whose PICO fields change needs its stale `graph_claims`/
`graph_claim_concepts` rows cleared before the next `ke graph-build` run
picks up the correction (M54's incremental design skips any
`evidence_record_id` that already has a graph row) -- the same manual step
M68 needed by hand; the CLI command surfaces this as a reminder rather
than silently touching the graph itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from knowledge_engine.extraction import (
    LLM_GROUNDED_PICO_RULES_VERSION,
    ClaimCandidate,
    extract_pico_for_candidate,
)
from knowledge_engine.extraction.grounding import DEFAULT_MIN_SIMILARITY
from knowledge_engine.llm import LocalLLM

EVIDENCE_REVIEW_AUTOMATE_RULES_VERSION = "m69-evidence-review-automate-v1"

_FIELD_NAMES = ("population", "intervention", "comparator", "outcome")
_MANUAL_EXTRACTION_METHODS = frozenset({"manual_human_review", "manual"})


@dataclass(frozen=True)
class AutomatedReviewResult:
    """One record's outcome from a single automated-review pass.

    `updated` is `True` only when at least one field passed grounding and
    the record was actually edited -- a record where the LLM found nothing
    grounded stays untouched (`updated=False`), not silently downgraded.
    """

    evidence_record_id: str
    updated: bool
    fields_grounded: tuple[str, ...]
    skipped_reason: str | None


def automate_review_for_record(
    llm: LocalLLM,
    record: dict[str, Any],
    page_text: str | None,
    *,
    paper_first_page_text: str | None = None,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> AutomatedReviewResult:
    """Run the LLM-grounded PICO pipeline for one automated `EvidenceRecord`.

    Mutates `record` in place when at least one field is accepted -- callers
    own the decision of whether/how to persist the change. Never mutates
    `claim_text`, `research_question`, or `evidence_direction`. A field
    that fails grounding is left at its existing value, never blanked --
    the pipeline can only make a record more accurate, never less.
    """

    evidence_record_id = str(record.get("evidence_record_id", ""))

    review_checklist = record.get("review_checklist")
    already_human_reviewed = (
        isinstance(review_checklist, dict) and review_checklist.get("human_reviewed") is True
    )
    if record.get("extraction_method") in _MANUAL_EXTRACTION_METHODS or already_human_reviewed:
        return AutomatedReviewResult(evidence_record_id, False, (), "already manually reviewed")

    claim_text = record.get("claim_text")
    if not isinstance(claim_text, str) or not claim_text.strip():
        return AutomatedReviewResult(evidence_record_id, False, (), "no claim_text on this record")

    if page_text is None or not page_text.strip():
        return AutomatedReviewResult(evidence_record_id, False, (), "source page text unavailable")

    source_span = record.get("source_span") or {}
    candidate = ClaimCandidate(
        sentence_text=claim_text,
        section_type=str(source_span.get("section") or "results"),
        page_number=int(source_span.get("page_number") or 0),
        start_offset=int(source_span.get("start_offset") or 0),
        end_offset=int(source_span.get("end_offset") or 0),
        matched_signal="reconstructed-from-evidence-record",
        rules_version=EVIDENCE_REVIEW_AUTOMATE_RULES_VERSION,
    )

    extraction = extract_pico_for_candidate(
        llm,
        candidate,
        page_text,
        paper_first_page_text=paper_first_page_text,
        min_similarity=min_similarity,
    )

    grounded_fields: list[str] = []
    for field_name in _FIELD_NAMES:
        grounded_field = getattr(extraction, field_name)
        if grounded_field.value is not None:
            record[field_name] = grounded_field.value
            grounded_fields.append(field_name)

    if not grounded_fields:
        return AutomatedReviewResult(
            evidence_record_id, False, (), "no PICO field passed grounding"
        )

    record["extraction_method"] = LLM_GROUNDED_PICO_RULES_VERSION
    existing_checklist = record.get("review_checklist")
    merged_checklist: dict[str, Any] = (
        dict(existing_checklist) if isinstance(existing_checklist, dict) else {}
    )
    merged_checklist.update(
        {
            "automated_classification": True,
            "llm_grounded": True,
            "human_reviewed": False,
            "fields_grounded": list(grounded_fields),
        }
    )
    record["review_checklist"] = merged_checklist
    record["review_notes"] = (
        "M69 automated review: LLM-proposed PICO fields "
        f"({', '.join(grounded_fields)}) verified against bounded source "
        "context (the claim page plus page 1 when different) before being "
        "accepted; any field that failed grounding "
        "was left unchanged. No human read this record."
    )

    return AutomatedReviewResult(evidence_record_id, True, tuple(grounded_fields), None)
