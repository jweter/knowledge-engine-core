"""Draft extraction review-item generation.

Combines a ClaimCandidate (M17) and its ClaimFraming (M18) with a paper's own
corpus metadata into a draft extraction review item -- not a fully valid
EvidenceRecord. See `REQUIRED_EVIDENCE_FIELDS` in `knowledge_engine/cli.py`
for the full schema this eventually feeds.

`source_doi`/`source_title` are mechanically available from the paper itself
and populated directly. `research_question` has no source anywhere in this
codebase -- it is inherently supplied by whoever compiles a corpus around a
question, not derivable from a paper's own text. M18 already established
that `evidence_direction` is defined relative to a `research_question`
(`docs/vs7_manual_evidence_record.md`), so it cannot be honestly populated
without one either. These fields, and every other field requiring real
judgment (PICO, study_type, limitations, uncertainty_notes, confidence_note),
are left explicitly `None` -- a draft item is intentionally incomplete and
is never claimed to be a valid EvidenceRecord.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_engine.extraction.direction import ClaimFraming

DRAFT_EVIDENCE_ITEM_RULES_VERSION = "m19-draft-evidence-item-v1"

_SOURCE_TYPE = "paper"
_EXTRACTION_STATUS = "draft_review_required"
_CREATED_FOR_MILESTONE = "M19"


@dataclass(frozen=True)
class PaperMetadata:
    """The minimal paper metadata a draft evidence item needs.

    A plain dataclass rather than the `Paper` ORM model, so this module has
    no database dependency and stays testable with synthetic fixtures.
    """

    doi: str | None
    title: str


@dataclass(frozen=True)
class DraftEvidenceItem:
    """An intentionally incomplete evidence-record draft awaiting review.

    Fields mirror `REQUIRED_EVIDENCE_FIELDS` where a value can be honestly
    derived from `claim_framing` and paper metadata alone. Every field this
    module cannot honestly fill is `None`, never a guessed placeholder.
    """

    claim_framing: ClaimFraming
    extraction_method: str
    extraction_status: str
    source_type: str
    source_doi: str | None
    source_title: str
    claim_text: str
    result_summary: str
    source_span: dict[str, int | str]
    created_for_milestone: str
    research_question: str | None = None
    evidence_direction: str | None = None
    study_type: str | None = None
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    limitations: list[str] | None = None
    uncertainty_notes: str | None = None
    confidence_note: str | None = None
    schema_version: str | None = None
    evidence_record_id: str | None = None


def build_draft_evidence_item(paper: PaperMetadata, framing: ClaimFraming) -> DraftEvidenceItem:
    """Build one draft evidence item from a paper and a classified candidate."""

    candidate = framing.candidate
    return DraftEvidenceItem(
        claim_framing=framing,
        extraction_method=DRAFT_EVIDENCE_ITEM_RULES_VERSION,
        extraction_status=_EXTRACTION_STATUS,
        source_type=_SOURCE_TYPE,
        source_doi=paper.doi,
        source_title=paper.title,
        claim_text=candidate.sentence_text,
        result_summary=candidate.sentence_text,
        source_span={
            "page_number": candidate.page_number,
            "section": candidate.section_type,
            "start_offset": candidate.start_offset,
            "end_offset": candidate.end_offset,
        },
        created_for_milestone=_CREATED_FOR_MILESTONE,
    )


def build_draft_evidence_items(
    paper: PaperMetadata, framings: Sequence[ClaimFraming]
) -> tuple[DraftEvidenceItem, ...]:
    """Build one draft evidence item per classified candidate, order preserved."""

    return tuple(build_draft_evidence_item(paper, framing) for framing in framings)
