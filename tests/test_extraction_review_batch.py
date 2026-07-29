from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_batch import (
    EXTRACTION_REVIEW_BATCH_RULES_VERSION,
    run_batch_extraction_review,
    run_extraction_review_for_paper,
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


def _paper(paper_id: int, *, doi: str | None = "10.1/example") -> PaperMetadata:
    return PaperMetadata(paper_id=paper_id, doi=doi, title=f"Paper {paper_id}")


def test_run_extraction_review_for_paper_on_a_rich_paper() -> None:
    result = run_extraction_review_for_paper(_paper(1), _pages(_RICH_PAPER_TEXT))

    assert result.paper_id == 1
    assert result.page_count == 1
    assert result.section_count > 0
    assert result.candidate_count > 0
    assert result.study_type == "randomized_controlled_trial"
    assert result.limitations == ["This study was limited by a short follow-up period."]
    assert result.pico.population is not None
    assert result.pico.intervention is not None
    assert result.pico.comparator is not None
    assert result.pico.outcome is not None
    assert len(result.draft_items) == result.candidate_count
    assert all(item.source_span["paper_id"] == 1 for item in result.draft_items)


def test_run_extraction_review_for_paper_on_a_sparse_paper() -> None:
    result = run_extraction_review_for_paper(_paper(2), _pages(_SPARSE_PAPER_TEXT))

    assert result.section_count == 0
    assert result.candidate_count == 0
    assert result.study_type is None
    assert result.limitations is None
    assert result.pico.population is None
    assert result.draft_items == ()


def test_run_batch_extraction_review_aggregates_across_papers() -> None:
    paper_pages = [
        (_paper(1), _pages(_RICH_PAPER_TEXT)),
        (_paper(2), _pages(_SPARSE_PAPER_TEXT)),
        (_paper(3), []),
    ]

    summary = run_batch_extraction_review(paper_pages)

    assert summary.rules_version == EXTRACTION_REVIEW_BATCH_RULES_VERSION
    assert summary.paper_count == 2
    assert summary.papers_with_zero_pages == 1
    assert summary.papers_with_zero_candidates == 1
    assert summary.total_draft_item_count == len(summary.results[0].draft_items)
    assert [result.paper_id for result in summary.results] == [1, 2]


def test_run_batch_extraction_review_preserves_per_paper_traceability() -> None:
    """Every draft item in a multi-paper batch must trace back to its own paper,
    never another paper's, even though items are aggregated into one summary."""

    paper_pages = [
        (_paper(10), _pages(_RICH_PAPER_TEXT)),
        (_paper(20), _pages(_RICH_PAPER_TEXT)),
    ]

    summary = run_batch_extraction_review(paper_pages)

    assert summary.paper_count == 2
    result_by_paper_id = {result.paper_id: result for result in summary.results}
    assert all(item.source_span["paper_id"] == 10 for item in result_by_paper_id[10].draft_items)
    assert all(item.source_span["paper_id"] == 20 for item in result_by_paper_id[20].draft_items)


def test_run_batch_extraction_review_handles_no_papers() -> None:
    summary = run_batch_extraction_review([])

    assert summary.paper_count == 0
    assert summary.papers_with_zero_pages == 0
    assert summary.papers_with_zero_candidates == 0
    assert summary.total_draft_item_count == 0
    assert summary.results == ()
