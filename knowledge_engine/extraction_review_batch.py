"""Batch orchestration for running the extraction-review pipeline at scale.

`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
names the gap this closes: M16-M28's deterministic extraction pipeline has
been unit-tested against synthetic fixtures and, as of M38/M38-follow-up,
measured in aggregate across the real 943-paper corpus -- but `ke
extraction-review-generate` (M19/M20) only ever runs against one paper at a
time, so the real corpus's actual draft-evidence-item review queue, the
material a human reviewer works from, has never been generated at scale.
The real corpus still has exactly two `EvidenceRecord` rows, both
hand-authored before any of this automation existed.

This module does not change that human-review boundary: it runs the exact
same pipeline `ke extraction-review-generate` runs for one paper, across
however many papers are supplied, and returns draft evidence items --
never a validated `EvidenceRecord`. Promoting a draft item into real
evidence remains `ke extraction-review-promote`'s job, which still refuses
any record missing a human-supplied `research_question`/
`evidence_direction`. This module only removes the one-paper-at-a-time
friction of generating the queue a reviewer works from.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from knowledge_engine.extraction import (
    STUDY_DESIGN_RULES_VERSION,
    PicoFields,
    build_draft_evidence_items,
    classify_claim_framing,
    classify_study_type,
    detect_claim_candidates,
    detect_sections,
    extract_limitations,
    extract_pico,
)
from knowledge_engine.extraction.evidence_items import DraftEvidenceItem, PaperMetadata
from knowledge_engine.parser import ParsedPage

EXTRACTION_REVIEW_BATCH_RULES_VERSION = "m40-extraction-review-batch-v1"


@dataclass(frozen=True)
class PaperExtractionReviewResult:
    """One paper's draft-evidence-item generation result.

    Mirrors exactly what `ke extraction-review-generate` computes for a
    single paper -- factored out here so the batch command and the
    single-paper command share one pipeline implementation instead of two
    copies that could silently drift apart.
    """

    paper_id: int
    page_count: int
    section_count: int
    candidate_count: int
    study_type: str | None
    limitations: list[str] | None
    pico: PicoFields
    draft_items: tuple[DraftEvidenceItem, ...]


def run_extraction_review_for_paper(
    paper: PaperMetadata, pages: Sequence[ParsedPage]
) -> PaperExtractionReviewResult:
    """Run the deterministic extraction-review pipeline for one paper.

    `pages` must be non-empty; callers are responsible for that precondition
    (the single-paper CLI command rejects a zero-page paper outright, the
    batch command skips and counts it instead -- two different tolerances
    for the same precondition, not two different pipelines).
    """

    sections = detect_sections(pages)
    candidates = detect_claim_candidates(pages, sections)
    framings = classify_claim_framing(candidates)
    study_type = classify_study_type(pages, sections)
    limitations = extract_limitations(pages, sections)
    pico = extract_pico(pages, sections)
    items = build_draft_evidence_items(
        paper,
        framings,
        study_type=study_type,
        limitations=limitations,
        study_design_rules_version=STUDY_DESIGN_RULES_VERSION,
        population=pico.population,
        intervention=pico.intervention,
        comparator=pico.comparator,
        outcome=pico.outcome,
        pico_extraction_rules_version=pico.rules_version,
    )
    return PaperExtractionReviewResult(
        paper_id=paper.paper_id,
        page_count=len(pages),
        section_count=len(sections),
        candidate_count=len(candidates),
        study_type=study_type,
        limitations=limitations,
        pico=pico,
        draft_items=items,
    )


@dataclass(frozen=True)
class BatchExtractionReviewSummary:
    """Aggregate result of running the extraction-review pipeline across many papers."""

    rules_version: str
    paper_count: int
    papers_with_zero_pages: int
    papers_with_zero_candidates: int
    total_draft_item_count: int
    results: tuple[PaperExtractionReviewResult, ...]


def run_batch_extraction_review(
    paper_pages: Iterable[tuple[PaperMetadata, Sequence[ParsedPage]]],
) -> BatchExtractionReviewSummary:
    """Run the deterministic extraction-review pipeline across many papers.

    A paper with zero persisted pages is skipped and counted, not a hard
    failure -- at batch scale, one paper missing page-level provenance
    (M15) should not abort review-queue generation for every other paper.
    """

    results: list[PaperExtractionReviewResult] = []
    zero_pages = 0
    for paper, pages in paper_pages:
        if not pages:
            zero_pages += 1
            continue
        results.append(run_extraction_review_for_paper(paper, pages))

    zero_candidates = sum(1 for result in results if not result.draft_items)
    total_items = sum(len(result.draft_items) for result in results)

    return BatchExtractionReviewSummary(
        rules_version=EXTRACTION_REVIEW_BATCH_RULES_VERSION,
        paper_count=len(results),
        papers_with_zero_pages=zero_pages,
        papers_with_zero_candidates=zero_candidates,
        total_draft_item_count=total_items,
        results=tuple(results),
    )
