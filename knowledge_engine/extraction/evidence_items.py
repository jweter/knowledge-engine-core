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
without one either. Those two fields, `uncertainty_notes`, `confidence_note`, and `provenance`
require real judgment or external input and are left explicitly `None`.
`study_type`, `limitations`, and PICO's population/intervention/comparator/
outcome are different: M26's deterministic study-design classification and
limitations extraction (`knowledge_engine.extraction.study_design`), and
M28's deterministic PICO extraction (`knowledge_engine.extraction.pico`),
populate them from the paper's own text when a caller supplies them, since
all are paper-intrinsic facts, not judgment relative to a research
question -- see `docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed
Fields section. A draft item is intentionally incomplete and is never
claimed to be a valid EvidenceRecord.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

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

    `paper_id` is always present and always unique (the `Paper` row's
    primary key), unlike `doi` (nullable) or `title` (not a unique
    identity in this repository). It is carried into `source_span` so a
    reviewer can always resolve a draft item's offsets back to the exact
    paper they came from, even when `doi` is `None`.
    """

    paper_id: int
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
    study_design_rules_version: str | None = None
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    pico_extraction_rules_version: str | None = None
    limitations: list[str] | None = None
    uncertainty_notes: str | None = None
    confidence_note: str | None = None
    provenance: dict[str, Any] | None = None
    schema_version: str | None = None
    evidence_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-ready dict for a review-queue file.

        Every schema field is present, including the `None`-valued ones, so
        a reviewer sees exactly what still needs completing. `extraction_context`
        is not part of `REQUIRED_EVIDENCE_FIELDS` -- it carries the M17/M18
        audit trail (matched signal, framing, matched cue, rule versions) a
        reviewer needs to judge the extraction without re-deriving it.
        """

        candidate = self.claim_framing.candidate
        return {
            "schema_version": self.schema_version,
            "evidence_record_id": self.evidence_record_id,
            "extraction_method": self.extraction_method,
            "extraction_status": self.extraction_status,
            "source_doi": self.source_doi,
            "source_title": self.source_title,
            "source_type": self.source_type,
            "study_type": self.study_type,
            "research_question": self.research_question,
            "claim_text": self.claim_text,
            "evidence_direction": self.evidence_direction,
            "population": self.population,
            "intervention": self.intervention,
            "comparator": self.comparator,
            "outcome": self.outcome,
            "result_summary": self.result_summary,
            "source_span": self.source_span,
            "limitations": self.limitations,
            "uncertainty_notes": self.uncertainty_notes,
            "confidence_note": self.confidence_note,
            "provenance": self.provenance,
            "created_for_milestone": self.created_for_milestone,
            "extraction_context": {
                "matched_signal": candidate.matched_signal,
                "section_type": candidate.section_type,
                "framing": self.claim_framing.framing,
                "matched_cue": self.claim_framing.matched_cue,
                "candidate_rules_version": candidate.rules_version,
                "framing_rules_version": self.claim_framing.rules_version,
                "study_design_rules_version": self.study_design_rules_version,
                "pico_extraction_rules_version": self.pico_extraction_rules_version,
            },
        }


def build_draft_evidence_item(
    paper: PaperMetadata,
    framing: ClaimFraming,
    *,
    study_type: str | None = None,
    limitations: list[str] | None = None,
    study_design_rules_version: str | None = None,
    population: str | None = None,
    intervention: str | None = None,
    comparator: str | None = None,
    outcome: str | None = None,
    pico_extraction_rules_version: str | None = None,
) -> DraftEvidenceItem:
    """Build one draft evidence item from a paper and a classified candidate.

    `study_type`/`limitations`/PICO fields are paper-level facts (the same
    value applies to every candidate from the same paper), so the caller
    computes them once per paper -- typically via `classify_study_type`/
    `extract_limitations`/`extract_pico` -- rather than this function
    deriving them itself. `study_design_rules_version`/
    `pico_extraction_rules_version` record which ruleset produced them (or
    found nothing), mirroring `candidate_rules_version`/
    `framing_rules_version`, so a later ruleset revision doesn't leave a
    draft item's provenance unrecorded.
    """

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
            "paper_id": paper.paper_id,
            "page_number": candidate.page_number,
            "section": candidate.section_type,
            "start_offset": candidate.start_offset,
            "end_offset": candidate.end_offset,
        },
        created_for_milestone=_CREATED_FOR_MILESTONE,
        study_type=study_type,
        limitations=limitations,
        study_design_rules_version=study_design_rules_version,
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcome=outcome,
        pico_extraction_rules_version=pico_extraction_rules_version,
    )


def build_draft_evidence_items(
    paper: PaperMetadata,
    framings: Sequence[ClaimFraming],
    *,
    study_type: str | None = None,
    limitations: list[str] | None = None,
    study_design_rules_version: str | None = None,
    population: str | None = None,
    intervention: str | None = None,
    comparator: str | None = None,
    outcome: str | None = None,
    pico_extraction_rules_version: str | None = None,
) -> tuple[DraftEvidenceItem, ...]:
    """Build one draft evidence item per classified candidate, order preserved."""

    return tuple(
        build_draft_evidence_item(
            paper,
            framing,
            study_type=study_type,
            limitations=limitations,
            study_design_rules_version=study_design_rules_version,
            population=population,
            intervention=intervention,
            comparator=comparator,
            outcome=outcome,
            pico_extraction_rules_version=pico_extraction_rules_version,
        )
        for framing in framings
    )
