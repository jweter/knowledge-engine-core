from knowledge_engine.extraction import (
    STUDY_DESIGN_RULES_VERSION,
    SectionSpan,
    classify_study_type,
    extract_limitations,
)
from knowledge_engine.parser import ParsedPage


def _section(
    section_type: str, text: str, heading_text: str, *, page_number: int = 1
) -> SectionSpan:
    return SectionSpan(
        section_type=section_type,
        start_page_number=page_number,
        start_offset=0,
        end_page_number=page_number,
        end_offset=len(text),
        heading_text=heading_text,
        rules_version="test",
    )


def test_study_design_rules_version_is_stable() -> None:
    assert STUDY_DESIGN_RULES_VERSION == "m26-study-design-v1"


def test_classify_study_type_detects_randomized_controlled_trial() -> None:
    text = "This was a randomized, double-blind, placebo-controlled trial."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "randomized_controlled_trial"
    )


def test_classify_study_type_prefers_meta_analysis_over_rct_mention() -> None:
    text = "We performed a meta-analysis of 12 randomized controlled trials."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "meta_analysis"
    )


def test_classify_study_type_detects_systematic_review() -> None:
    text = "A systematic review of the available evidence was conducted."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "systematic_review"
    )


def test_classify_study_type_detects_cohort_study() -> None:
    text = "We conducted a prospective cohort study of adults with obesity."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == "cohort_study"


def test_classify_study_type_ignores_discussion_section_mentions() -> None:
    """A study-design phrase in Discussion describes prior work, not this paper."""

    text = "This is consistent with prior randomized controlled trials."
    sections = [_section("discussion", text, "Discussion")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) is None


def test_classify_study_type_returns_none_without_abstract_or_methods() -> None:
    assert classify_study_type([ParsedPage(page_number=1, text="No sections here.")], []) is None


def test_classify_study_type_returns_none_without_a_cue() -> None:
    text = "Participants attended their scheduled visits."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) is None


def test_extract_limitations_returns_section_text_without_heading() -> None:
    text = "Limitations\n\nThe sample size was small and follow-up was short."
    sections = [_section("limitations", text, "Limitations")]

    result = extract_limitations([ParsedPage(page_number=1, text=text)], sections)

    assert result == ["The sample size was small and follow-up was short."]


def test_extract_limitations_returns_none_without_a_limitations_section() -> None:
    text = "Results\n\nWe observed a large effect."
    sections = [_section("results", text, "Results")]

    assert extract_limitations([ParsedPage(page_number=1, text=text)], sections) is None


def test_extract_limitations_returns_none_for_empty_content() -> None:
    text = "Limitations"
    sections = [_section("limitations", text, "Limitations")]

    assert extract_limitations([ParsedPage(page_number=1, text=text)], sections) is None


def test_extract_limitations_spans_multiple_pages() -> None:
    page1_text = "Limitations\n\nThe sample size was small."
    page2_text = "Follow-up was also short."
    sections = [
        SectionSpan(
            section_type="limitations",
            start_page_number=1,
            start_offset=0,
            end_page_number=2,
            end_offset=len(page2_text),
            heading_text="Limitations",
            rules_version="test",
        )
    ]
    pages = [
        ParsedPage(page_number=1, text=page1_text),
        ParsedPage(page_number=2, text=page2_text),
    ]

    result = extract_limitations(pages, sections)

    assert result == ["The sample size was small.\n\nFollow-up was also short."]
