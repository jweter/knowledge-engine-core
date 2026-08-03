from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_accuracy_benchmark import (
    EXTRACTION_ACCURACY_BENCHMARK_RULES_VERSION,
    benchmark_evidence_record,
    run_extraction_accuracy_benchmark,
)
from knowledge_engine.parser import ParsedPage

_RICH_PAPER_TEXT = (
    "Abstract\n"
    "We enrolled 253 adults with obesity in this trial.\n"
    "Participants received semaglutide once weekly for 68 weeks.\n"
    "Weight loss was compared with placebo over the study period.\n"
    "The primary outcome was change in body weight from baseline.\n\n"
    "Methods\n"
    "This was a randomized, double-blind, placebo-controlled trial.\n\n"
    "Results\n"
    "Mean weight loss was 15.3% (95% CI, 12.1-18.5) versus 2.6% with placebo.\n\n"
    "Limitations\n"
    "This study was limited by a short follow-up period.\n\n"
    "Conclusion\n"
    "Semaglutide produced significantly greater weight loss than placebo.\n"
)

_SPARSE_PAPER_TEXT = "This is an unstructured document with no recognizable headings at all."


def _pages(text: str) -> list[ParsedPage]:
    return [ParsedPage(page_number=1, text=text)]


def _paper(paper_id: int = 1) -> PaperMetadata:
    return PaperMetadata(paper_id=paper_id, doi="10.1/example", title="Example paper")


def _ground_truth_record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "evidence_record_id": "ev-1",
        "extraction_method": "manual_human_review",
        "source_doi": "10.1/example",
        "study_type": "randomized_controlled_trial",
        "population": "adults with obesity enrolled in the trial",
        "intervention": "semaglutide once weekly",
        "comparator": "placebo",
        "outcome": "change in body weight",
        "limitations": ["Short follow-up period."],
    }
    base.update(overrides)
    return base


def test_benchmark_evidence_record_exact_study_type_match() -> None:
    result = benchmark_evidence_record(_ground_truth_record(), _paper(), _pages(_RICH_PAPER_TEXT))

    assert result.evidence_record_id == "ev-1"
    assert result.paper_id == 1
    assert result.study_type_ground_truth == "randomized_controlled_trial"
    assert result.study_type_detected == "randomized_controlled_trial"
    assert result.study_type_exact_match is True


def test_benchmark_evidence_record_limitations_presence_match() -> None:
    result = benchmark_evidence_record(_ground_truth_record(), _paper(), _pages(_RICH_PAPER_TEXT))

    assert result.limitations_ground_truth_present is True
    assert result.limitations_detected_present is True
    assert result.limitations_presence_match is True


def test_benchmark_evidence_record_pico_overlap_and_presence() -> None:
    result = benchmark_evidence_record(_ground_truth_record(), _paper(), _pages(_RICH_PAPER_TEXT))

    for field_name in ("population", "intervention", "comparator", "outcome"):
        assert result.pico_presence_match[field_name] is True
        overlap = result.pico_overlap[field_name]
        assert overlap is not None
        assert overlap > 0.0


def test_benchmark_evidence_record_on_sparse_paper_detects_nothing() -> None:
    result = benchmark_evidence_record(_ground_truth_record(), _paper(), _pages(_SPARSE_PAPER_TEXT))

    assert result.study_type_detected is None
    assert result.study_type_exact_match is False
    assert result.limitations_detected_present is False
    assert result.limitations_presence_match is False
    for field_name in ("population", "intervention", "comparator", "outcome"):
        assert result.pico_presence_match[field_name] is False
        assert result.pico_overlap[field_name] == 0.0


def test_run_excludes_m52_records_from_ground_truth() -> None:
    records = [
        _ground_truth_record(evidence_record_id="ev-manual"),
        _ground_truth_record(
            evidence_record_id="ev-auto", extraction_method="m52-evidence-classification-v1"
        ),
    ]

    def resolve(doi: str) -> tuple[PaperMetadata, list[ParsedPage]] | None:
        return _paper(), _pages(_RICH_PAPER_TEXT)

    summary = run_extraction_accuracy_benchmark(records, resolve)

    assert summary.rules_version == EXTRACTION_ACCURACY_BENCHMARK_RULES_VERSION
    assert summary.ground_truth_records_considered == 1
    assert summary.records_benchmarked == 1
    assert summary.results[0].evidence_record_id == "ev-manual"


def test_run_skips_records_with_no_paper_match() -> None:
    records = [_ground_truth_record()]

    def resolve(doi: str) -> tuple[PaperMetadata, list[ParsedPage]] | None:
        return None

    summary = run_extraction_accuracy_benchmark(records, resolve)

    assert summary.records_benchmarked == 0
    assert summary.records_skipped_no_paper_match == ["ev-1"]
    assert summary.study_type_exact_match_rate is None


def test_run_skips_records_with_no_pages() -> None:
    records = [_ground_truth_record()]

    def resolve(doi: str) -> tuple[PaperMetadata, list[ParsedPage]] | None:
        return _paper(), []

    summary = run_extraction_accuracy_benchmark(records, resolve)

    assert summary.records_benchmarked == 0
    assert summary.records_skipped_no_pages == ["ev-1"]


def test_run_aggregates_rates_across_multiple_records() -> None:
    records = [
        _ground_truth_record(evidence_record_id="ev-1", source_doi="10.1/example"),
        _ground_truth_record(
            evidence_record_id="ev-2", source_doi="10.1/sparse", study_type="cohort_study"
        ),
    ]

    def resolve(doi: str) -> tuple[PaperMetadata, list[ParsedPage]] | None:
        if doi == "10.1/example":
            return _paper(1), _pages(_RICH_PAPER_TEXT)
        return _paper(2), _pages(_SPARSE_PAPER_TEXT)

    summary = run_extraction_accuracy_benchmark(records, resolve)

    assert summary.records_benchmarked == 2
    assert summary.study_type_exact_match_rate == 0.5
    payload = summary.to_json()
    assert "ev-1" in payload
    assert "ev-2" in payload
