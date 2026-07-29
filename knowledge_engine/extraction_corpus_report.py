"""Aggregate deterministic-extraction coverage across the whole corpus.

`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
names the gap this closes: M16-M28's deterministic extraction rules (section
detection, claim-candidate signals, study-type classification, limitations,
PICO) have been unit-tested against synthetic fixtures and `ke
extraction-review-generate` has been run by hand against individual real
papers, but nothing has measured detection coverage in aggregate across the
real corpus at scale -- exactly the pattern a 500-paper sample was expected
not to reveal. This module runs the same deterministic pipeline
`extraction-review-generate` runs for one paper, across every paper supplied,
and reports coverage counts rather than mutating anything: no draft items are
written, no extraction runs are recorded, and no `EvidenceRecord` is
produced. A separate, read-only measurement pass, matching the M12/M13
scale-readiness precedent this milestone is modeled on.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass

from knowledge_engine.extraction.claims import detect_claim_candidates
from knowledge_engine.extraction.pico import extract_pico
from knowledge_engine.extraction.sections import detect_sections
from knowledge_engine.extraction.study_design import classify_study_type, extract_limitations
from knowledge_engine.parser import ParsedPage

EXTRACTION_CORPUS_REPORT_RULES_VERSION = "m38-extraction-corpus-report-v1"


@dataclass(frozen=True)
class PaperExtractionSummary:
    """One paper's deterministic-extraction coverage, no paper text retained."""

    paper_id: int
    page_count: int
    section_count: int
    section_types: tuple[str, ...]
    claim_candidate_count: int
    study_type: str | None
    has_limitations: bool
    has_population: bool
    has_intervention: bool
    has_comparator: bool
    has_outcome: bool


@dataclass(frozen=True)
class ExtractionCorpusReport:
    """Deterministic-extraction coverage aggregated across a paper set."""

    rules_version: str
    paper_count: int
    papers_with_zero_pages: int
    papers_with_zero_sections: int
    papers_with_zero_candidates: int
    section_type_coverage: dict[str, int]
    study_type_coverage: dict[str, int]
    limitations_coverage_count: int
    population_coverage_count: int
    intervention_coverage_count: int
    comparator_coverage_count: int
    outcome_coverage_count: int
    all_pico_fields_coverage_count: int
    per_paper: tuple[PaperExtractionSummary, ...]

    def to_json(self) -> str:
        """Render deterministic JSON, per-paper detail included."""

        payload = asdict(self)
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def summarize_paper_extraction(
    paper_id: int, pages: Sequence[ParsedPage]
) -> PaperExtractionSummary:
    """Run the deterministic pipeline for one paper and summarize coverage."""

    sections = detect_sections(pages)
    candidates = detect_claim_candidates(pages, sections)
    study_type = classify_study_type(pages, sections)
    limitations = extract_limitations(pages, sections)
    pico = extract_pico(pages, sections)
    return PaperExtractionSummary(
        paper_id=paper_id,
        page_count=len(pages),
        section_count=len(sections),
        section_types=tuple(sorted({section.section_type for section in sections})),
        claim_candidate_count=len(candidates),
        study_type=study_type,
        has_limitations=limitations is not None,
        has_population=pico.population is not None,
        has_intervention=pico.intervention is not None,
        has_comparator=pico.comparator is not None,
        has_outcome=pico.outcome is not None,
    )


def build_extraction_corpus_report(
    paper_pages: Iterable[tuple[int, Sequence[ParsedPage]]],
) -> ExtractionCorpusReport:
    """Summarize deterministic-extraction coverage across a set of papers."""

    summaries: list[PaperExtractionSummary] = []
    zero_pages = 0
    for paper_id, pages in paper_pages:
        if not pages:
            zero_pages += 1
            continue
        summaries.append(summarize_paper_extraction(paper_id, pages))

    section_type_coverage: Counter[str] = Counter()
    study_type_coverage: Counter[str] = Counter()
    zero_sections = 0
    zero_candidates = 0
    limitations_count = 0
    population_count = 0
    intervention_count = 0
    comparator_count = 0
    outcome_count = 0
    all_pico_count = 0

    for summary in summaries:
        if summary.section_count == 0:
            zero_sections += 1
        if summary.claim_candidate_count == 0:
            zero_candidates += 1
        for section_type in summary.section_types:
            section_type_coverage[section_type] += 1
        study_type_coverage[summary.study_type or "none"] += 1
        if summary.has_limitations:
            limitations_count += 1
        if summary.has_population:
            population_count += 1
        if summary.has_intervention:
            intervention_count += 1
        if summary.has_comparator:
            comparator_count += 1
        if summary.has_outcome:
            outcome_count += 1
        if (
            summary.has_population
            and summary.has_intervention
            and summary.has_comparator
            and summary.has_outcome
        ):
            all_pico_count += 1

    return ExtractionCorpusReport(
        rules_version=EXTRACTION_CORPUS_REPORT_RULES_VERSION,
        paper_count=len(summaries),
        papers_with_zero_pages=zero_pages,
        papers_with_zero_sections=zero_sections,
        papers_with_zero_candidates=zero_candidates,
        section_type_coverage=dict(section_type_coverage),
        study_type_coverage=dict(study_type_coverage),
        limitations_coverage_count=limitations_count,
        population_coverage_count=population_count,
        intervention_coverage_count=intervention_count,
        comparator_coverage_count=comparator_count,
        outcome_coverage_count=outcome_count,
        all_pico_fields_coverage_count=all_pico_count,
        per_paper=tuple(summaries),
    )
