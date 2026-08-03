"""Extraction-accuracy benchmark: deterministic extraction vs human-reviewed ground truth.

`docs/roadmap.md`'s priority-list item 5 -- "an extraction-accuracy
benchmark" -- names the gap this closes. M38/M40 measured Phase 2's
deterministic extraction pipeline's *coverage* (how often a field is
detected at all) across the real corpus at scale, but never its
*accuracy* against a known-correct answer, since nothing in this
project's history has compared the pipeline's own output to independent
ground truth.

The real corpus's own `EvidenceRecord`s supply that ground truth for a
small subset: records whose `extraction_method` is a genuine,
independent human read of the source paper (`manual_human_review`/
`manual`), not `m52-evidence-classification-v1`. M52's automated records
are deliberately excluded from ground truth here -- they template
`study_type`/PICO fields *from this same deterministic pipeline's own
output*, so comparing deterministic extraction against an M52 record
would be circular, not a real accuracy measurement.

This module re-runs `run_extraction_review_for_paper` (the same pipeline
`ke extraction-review-generate` runs) against each ground-truth record's
own source paper and compares the fresh deterministic output to the
promoted, human-reviewed field values already on file. `study_type` gets
an exact-match rate (a closed, deterministic vocabulary, so exact match
is the honest metric). Free-text PICO fields and `limitations` cannot be
compared by exact string equality -- a human-edited sentence will never
character-match a heuristically-extracted span -- so they get two
honest, simple signals instead: presence agreement (did both sides
detect *something*) and token-overlap ratio (Jaccard similarity of
lowercased word sets) when both sides have text. Never a fuzzy
similarity model or an invented accuracy score -- just what the numbers
actually show.

Read-only: no draft items, no extraction runs, no `EvidenceRecord` rows
produced or mutated, matching M38's own measurement-only posture.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass

from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_batch import run_extraction_review_for_paper
from knowledge_engine.parser import ParsedPage

EXTRACTION_ACCURACY_BENCHMARK_RULES_VERSION = "m65-extraction-accuracy-benchmark-v1"

# extraction_method values representing real, independent human ground truth --
# never an M52-derived record, since M52 templates these same fields from this
# same deterministic pipeline (see module docstring).
GROUND_TRUTH_EXTRACTION_METHODS = frozenset({"manual_human_review", "manual"})

PICO_FIELDS = ("population", "intervention", "comparator", "outcome")

PaperResolver = Callable[[str], "tuple[PaperMetadata, list[ParsedPage]] | None"]


def _tokens(text: str | None) -> set[str]:
    """Lowercased alphanumeric tokens longer than 2 characters."""

    if not text:
        return set()
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {token for token in cleaned.split() if len(token) > 2}


def _token_overlap(ground_truth: str | None, detected: str | None) -> float | None:
    """Jaccard overlap of both sides' tokens. `None` when both sides are empty."""

    gt_tokens, detected_tokens = _tokens(ground_truth), _tokens(detected)
    if not gt_tokens and not detected_tokens:
        return None
    if not gt_tokens or not detected_tokens:
        return 0.0
    return len(gt_tokens & detected_tokens) / len(gt_tokens | detected_tokens)


@dataclass(frozen=True)
class RecordBenchmarkResult:
    """One ground-truth evidence record's deterministic-extraction comparison."""

    evidence_record_id: str
    paper_id: int
    study_type_ground_truth: str | None
    study_type_detected: str | None
    study_type_exact_match: bool
    limitations_ground_truth_present: bool
    limitations_detected_present: bool
    limitations_presence_match: bool
    pico_overlap: dict[str, float | None]
    pico_presence_match: dict[str, bool]


@dataclass(frozen=True)
class ExtractionAccuracyBenchmarkSummary:
    """Aggregate benchmark result across every ground-truth record considered."""

    rules_version: str
    ground_truth_records_considered: int
    records_benchmarked: int
    records_skipped_no_paper_match: list[str]
    records_skipped_no_pages: list[str]
    study_type_exact_match_rate: float | None
    limitations_presence_match_rate: float | None
    pico_presence_match_rate: dict[str, float | None]
    pico_mean_overlap: dict[str, float | None]
    results: list[RecordBenchmarkResult]

    def to_json(self) -> str:
        """Render deterministic JSON, per-record detail included."""

        payload = asdict(self)
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def benchmark_evidence_record(
    record: Mapping[str, object], paper: PaperMetadata, pages: Sequence[ParsedPage]
) -> RecordBenchmarkResult:
    """Compare one ground-truth `EvidenceRecord`'s fields against a fresh extraction."""

    extraction = run_extraction_review_for_paper(paper, pages)

    gt_study_type = record.get("study_type")
    gt_study_type = gt_study_type if isinstance(gt_study_type, str) else None
    detected_study_type = extraction.study_type

    gt_limitations_present = bool(record.get("limitations"))
    detected_limitations_present = bool(extraction.limitations)

    detected_pico = {
        "population": extraction.pico.population,
        "intervention": extraction.pico.intervention,
        "comparator": extraction.pico.comparator,
        "outcome": extraction.pico.outcome,
    }
    pico_overlap: dict[str, float | None] = {}
    pico_presence_match: dict[str, bool] = {}
    for field_name in PICO_FIELDS:
        gt_value = record.get(field_name)
        gt_text = gt_value if isinstance(gt_value, str) else None
        detected_text = detected_pico[field_name]
        pico_overlap[field_name] = _token_overlap(gt_text, detected_text)
        pico_presence_match[field_name] = bool(gt_text) == bool(detected_text)

    return RecordBenchmarkResult(
        evidence_record_id=str(record.get("evidence_record_id") or ""),
        paper_id=paper.paper_id,
        study_type_ground_truth=gt_study_type,
        study_type_detected=detected_study_type,
        study_type_exact_match=(gt_study_type == detected_study_type),
        limitations_ground_truth_present=gt_limitations_present,
        limitations_detected_present=detected_limitations_present,
        limitations_presence_match=(gt_limitations_present == detected_limitations_present),
        pico_overlap=pico_overlap,
        pico_presence_match=pico_presence_match,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def run_extraction_accuracy_benchmark(
    evidence_records: Sequence[Mapping[str, object]], resolve_paper: PaperResolver
) -> ExtractionAccuracyBenchmarkSummary:
    """Run the benchmark across every ground-truth record in `evidence_records`.

    `resolve_paper` looks up a record's source paper by DOI and returns
    `(PaperMetadata, pages)`, or `None` if no matching paper is persisted
    -- injected rather than hard-coded so this module stays DB-free and
    testable against fixtures, the same separation
    `run_extraction_review_for_paper` already establishes.
    """

    ground_truth = [
        record
        for record in evidence_records
        if record.get("extraction_method") in GROUND_TRUTH_EXTRACTION_METHODS
    ]

    results: list[RecordBenchmarkResult] = []
    skipped_no_paper: list[str] = []
    skipped_no_pages: list[str] = []

    for record in ground_truth:
        evidence_record_id = str(record.get("evidence_record_id") or "")
        doi = record.get("source_doi")
        resolved = resolve_paper(str(doi)) if isinstance(doi, str) and doi.strip() else None
        if resolved is None:
            skipped_no_paper.append(evidence_record_id)
            continue
        paper, pages = resolved
        if not pages:
            skipped_no_pages.append(evidence_record_id)
            continue
        results.append(benchmark_evidence_record(record, paper, pages))

    study_type_rate = _mean([1.0 if r.study_type_exact_match else 0.0 for r in results])
    limitations_rate = _mean([1.0 if r.limitations_presence_match else 0.0 for r in results])
    pico_presence_rate = {
        field_name: _mean([1.0 if r.pico_presence_match[field_name] else 0.0 for r in results])
        for field_name in PICO_FIELDS
    }
    pico_mean_overlap = {
        field_name: _mean(
            [overlap for r in results if (overlap := r.pico_overlap[field_name]) is not None]
        )
        for field_name in PICO_FIELDS
    }

    return ExtractionAccuracyBenchmarkSummary(
        rules_version=EXTRACTION_ACCURACY_BENCHMARK_RULES_VERSION,
        ground_truth_records_considered=len(ground_truth),
        records_benchmarked=len(results),
        records_skipped_no_paper_match=skipped_no_paper,
        records_skipped_no_pages=skipped_no_pages,
        study_type_exact_match_rate=study_type_rate,
        limitations_presence_match_rate=limitations_rate,
        pico_presence_match_rate=pico_presence_rate,
        pico_mean_overlap=pico_mean_overlap,
        results=results,
    )
