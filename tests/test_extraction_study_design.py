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
    assert STUDY_DESIGN_RULES_VERSION == "m26-study-design-v4"


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


def test_classify_study_type_detects_narrative_review() -> None:
    text = "In this narrative review, we summarize the evidence on GLP-1 agonists."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "narrative_review"
    )


def test_classify_study_type_prefers_narrative_review_over_rct_mention() -> None:
    text = "This narrative review discusses several randomized controlled trials."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "narrative_review"
    )


def test_classify_study_type_prefers_cross_over_trial_over_rct_mention() -> None:
    text = "This was a randomized, double-blind, placebo-controlled crossover trial."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "cross_over_trial"
    )


def test_classify_study_type_detects_hyphenated_cross_over_trial() -> None:
    text = "We conducted a cross-over trial comparing the two dosing regimens."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "cross_over_trial"
    )


def test_classify_study_type_detects_retrospective_study_without_cohort_phrasing() -> None:
    text = "We performed a retrospective analysis of electronic health records."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "retrospective_study"
    )


def test_classify_study_type_prefers_cohort_study_over_retrospective_study() -> None:
    text = "We conducted a retrospective cohort study of adults with obesity."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == ("cohort_study")


def test_classify_study_type_detects_case_series() -> None:
    text = "We describe a case series of five patients with severe hypoglycemia."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == ("case_series")


def test_classify_study_type_detects_case_report() -> None:
    text = "We present a case report of a patient with a rare adverse event."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == ("case_report")


def test_classify_study_type_prefers_case_control_study_over_case_report() -> None:
    text = "We conducted a case-control study of adults with obesity."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "case_control_study"
    )


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


def test_classify_study_type_detects_rct_with_interleaved_descriptor_words() -> None:
    """v3: real corpus phrasing (paper 918) interleaves descriptor words in an
    order the original fixed-sequence pattern couldn't match."""

    text = "This is an open-label randomized and decentralized clinical trial."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "randomized_controlled_trial"
    )


def test_classify_study_type_rct_pattern_does_not_match_plural_trials() -> None:
    """The widened RCT pattern still requires singular "trial", preserving the
    existing protection against a review abstract that merely discusses
    multiple prior randomized controlled trials in passing."""

    text = "Several randomized controlled trials have examined this question."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) is None


def test_classify_study_type_detects_cohort_analysis_phrasing() -> None:
    """v3: real corpus phrasing (paper 465) says "cohort analysis", not
    "cohort study"."""

    text = "This was a single-center cohort analysis of prospectively collected data."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == "cohort_study"


def test_classify_study_type_detects_cross_sectional_survey_phrasing() -> None:
    """v3: real corpus phrasing (paper 591) says "cross-sectional online
    survey", not "cross-sectional study"."""

    text = "A cross-sectional online survey was conducted among adults with obesity."
    sections = [_section("methods", text, "Methods")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == (
        "cross_sectional_study"
    )


def test_classify_study_type_detects_we_report_a_case_phrasing() -> None:
    """v3: real corpus phrasing (papers 67/629) opens with "We report a case"
    rather than the literal words "case report"."""

    text = "We report a case of a patient with a rare adverse event."
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == "case_report"


def test_classify_study_type_cohort_study_still_wins_over_case_report_phrasing() -> None:
    """Ordering is unchanged: cohort_study is still checked before
    case_report, so a cohort study that incidentally uses "we report a case"
    phrasing elsewhere in its own abstract is not misclassified."""

    text = (
        "We conducted a prospective cohort study of adults with obesity. "
        "We report a case of one participant with a severe adverse event."
    )
    sections = [_section("abstract", text, "Abstract")]

    assert classify_study_type([ParsedPage(page_number=1, text=text)], sections) == "cohort_study"


def test_extract_limitations_falls_back_to_discussion_cue_sentences() -> None:
    """No "Limitations" heading exists, but Discussion states one explicitly."""

    text = (
        "Discussion\n\nOur findings support the hypothesis. "
        "Several limitations of this study should be acknowledged. "
        "The sample size was small."
    )
    sections = [_section("discussion", text, "Discussion")]

    result = extract_limitations([ParsedPage(page_number=1, text=text)], sections)

    assert result == ["Several limitations of this study should be acknowledged."]


def test_extract_limitations_fallback_excludes_a_table_derived_candidate() -> None:
    """A long, punctuation-free table dump containing the word "limitation"
    (e.g. a table column header like "Limitation category") is excluded when
    it overlaps heavily with the page's own detected `table_text`."""

    table_text = "Limitation category Sample size Follow-up Bias risk Confounding " * 8
    table_dump = table_text.strip()
    real_sentence = "Several limitations of this study should be acknowledged."
    text = f"Discussion\n\n{table_dump}. {real_sentence}"
    sections = [_section("discussion", text, "Discussion")]
    pages = [ParsedPage(page_number=1, text=text, table_text=table_text)]

    result = extract_limitations(pages, sections)

    assert result == [real_sentence]


def test_extract_limitations_fallback_returns_every_cue_sentence_in_order() -> None:
    text = (
        "Discussion\n\nSeveral limitations of this study should be acknowledged. "
        "The sample was drawn from a single center. "
        "Another limitation is the lack of a placebo arm."
    )
    sections = [_section("discussion", text, "Discussion")]

    result = extract_limitations([ParsedPage(page_number=1, text=text)], sections)

    assert result == [
        "Several limitations of this study should be acknowledged.",
        "Another limitation is the lack of a placebo arm.",
    ]


def test_extract_limitations_prefers_explicit_heading_over_discussion_fallback() -> None:
    """An explicit "Limitations" section, when present, is used as-is and the
    Discussion fallback never runs -- unchanged from pre-v3 behavior."""

    limitations_text = "Limitations\n\nThe sample size was small."
    discussion_text = "Discussion\n\nSeveral limitations of this study should be acknowledged."
    combined = limitations_text + "\n\n" + discussion_text
    sections = [
        SectionSpan(
            section_type="limitations",
            start_page_number=1,
            start_offset=0,
            end_page_number=1,
            end_offset=len(limitations_text),
            heading_text="Limitations",
            rules_version="test",
        ),
        SectionSpan(
            section_type="discussion",
            start_page_number=1,
            start_offset=len(limitations_text) + 2,
            end_page_number=1,
            end_offset=len(combined),
            heading_text="Discussion",
            rules_version="test",
        ),
    ]
    pages = [ParsedPage(page_number=1, text=combined)]

    result = extract_limitations(pages, sections)

    assert result == ["The sample size was small."]


def test_extract_limitations_returns_none_when_discussion_has_no_cue_sentence() -> None:
    text = "Discussion\n\nOur findings are consistent with prior work."
    sections = [_section("discussion", text, "Discussion")]

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
