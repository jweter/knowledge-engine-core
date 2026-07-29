from knowledge_engine.extraction_corpus_report import (
    EXTRACTION_CORPUS_REPORT_RULES_VERSION,
    build_extraction_corpus_report,
    summarize_paper_extraction,
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


def test_summarize_paper_extraction_detects_full_coverage_on_a_rich_paper() -> None:
    summary = summarize_paper_extraction(1, _pages(_RICH_PAPER_TEXT))

    assert summary.paper_id == 1
    assert summary.page_count == 1
    assert summary.section_count > 0
    assert "abstract" in summary.section_types
    assert "results" in summary.section_types
    assert summary.claim_candidate_count > 0
    assert summary.study_type == "randomized_controlled_trial"
    assert summary.has_limitations is True
    assert summary.has_population is True
    assert summary.has_intervention is True
    assert summary.has_comparator is True
    assert summary.has_outcome is True


def test_summarize_paper_extraction_detects_nothing_on_a_sparse_paper() -> None:
    summary = summarize_paper_extraction(2, _pages(_SPARSE_PAPER_TEXT))

    assert summary.section_count == 0
    assert summary.section_types == ()
    assert summary.claim_candidate_count == 0
    assert summary.study_type is None
    assert summary.has_limitations is False
    assert summary.has_population is False
    assert summary.has_intervention is False
    assert summary.has_comparator is False
    assert summary.has_outcome is False


def test_build_extraction_corpus_report_aggregates_across_papers() -> None:
    paper_pages = [
        (1, _pages(_RICH_PAPER_TEXT)),
        (2, _pages(_SPARSE_PAPER_TEXT)),
        (3, []),
    ]

    report = build_extraction_corpus_report(paper_pages)

    assert report.rules_version == EXTRACTION_CORPUS_REPORT_RULES_VERSION
    assert report.paper_count == 2
    assert report.papers_with_zero_pages == 1
    assert report.papers_with_zero_sections == 1
    assert report.papers_with_zero_candidates == 1
    assert report.section_type_coverage["abstract"] == 1
    assert report.study_type_coverage == {
        "randomized_controlled_trial": 1,
        "none": 1,
    }
    assert report.limitations_coverage_count == 1
    assert report.population_coverage_count == 1
    assert report.intervention_coverage_count == 1
    assert report.comparator_coverage_count == 1
    assert report.outcome_coverage_count == 1
    assert report.all_pico_fields_coverage_count == 1
    assert len(report.per_paper) == 2


def test_build_extraction_corpus_report_handles_no_papers() -> None:
    report = build_extraction_corpus_report([])

    assert report.paper_count == 0
    assert report.papers_with_zero_pages == 0
    assert report.papers_with_zero_sections == 0
    assert report.papers_with_zero_candidates == 0
    assert report.section_type_coverage == {}
    assert report.study_type_coverage == {}
    assert report.per_paper == ()


def test_report_to_json_is_stable_and_complete() -> None:
    report = build_extraction_corpus_report([(1, _pages(_RICH_PAPER_TEXT))])

    payload = report.to_json()

    assert '"rules_version": "m38-extraction-corpus-report-v1"' in payload
    assert '"paper_id": 1' in payload
    assert payload.endswith("\n")
