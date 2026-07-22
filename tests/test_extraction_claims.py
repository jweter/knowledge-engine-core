from knowledge_engine.extraction import (
    CLAIM_CANDIDATE_RULES_VERSION,
    SectionSpan,
    detect_claim_candidates,
    detect_sections,
)
from knowledge_engine.parser import ParsedPage


def _results_section(text: str, *, page_number: int = 1) -> SectionSpan:
    return SectionSpan(
        section_type="results",
        start_page_number=page_number,
        start_offset=0,
        end_page_number=page_number,
        end_offset=len(text),
        heading_text="Results",
        rules_version="test",
    )


def test_percentage_signal_is_detected() -> None:
    pages = [ParsedPage(page_number=1, text="Body weight decreased by 12.4% from baseline.")]
    sections = [_results_section(pages[0].text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].matched_signal == "percentage"
    assert candidates[0].sentence_text == "Body weight decreased by 12.4% from baseline."
    assert candidates[0].rules_version == CLAIM_CANDIDATE_RULES_VERSION


def test_p_value_signal_is_detected() -> None:
    pages = [
        ParsedPage(page_number=1, text="The difference was statistically significant p < 0.001.")
    ]
    sections = [_results_section(pages[0].text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].matched_signal == "p_value"


def test_confidence_interval_signal_is_detected() -> None:
    pages = [ParsedPage(page_number=1, text="The mean difference was 4.2 kg (95% CI 3.1-5.3).")]
    sections = [_results_section(pages[0].text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].matched_signal == "confidence_interval"


def test_comparative_phrase_signal_is_detected() -> None:
    pages = [
        ParsedPage(
            page_number=1,
            text="Weight loss was significantly greater than placebo among participants.",
        )
    ]
    sections = [_results_section(pages[0].text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].matched_signal == "comparative_phrase"


def test_sentence_without_signal_is_not_a_candidate() -> None:
    pages = [ParsedPage(page_number=1, text="Participants attended their scheduled visits.")]
    sections = [_results_section(pages[0].text)]

    assert detect_claim_candidates(pages, sections) == ()


def test_quantitative_sentence_outside_results_or_conclusion_is_ignored() -> None:
    text = "Participants were assessed at 12.4% attrition during follow-up."
    pages = [ParsedPage(page_number=1, text=text)]
    methods_section = SectionSpan(
        section_type="methods",
        start_page_number=1,
        start_offset=0,
        end_page_number=1,
        end_offset=len(text),
        heading_text="Methods",
        rules_version="test",
    )

    assert detect_claim_candidates(pages, [methods_section]) == ()


def test_multiple_sentences_only_matching_ones_returned_in_order() -> None:
    text = (
        "Participants completed the study. "
        "Body weight decreased by 12.4%. "
        "Adverse events were mild. "
        "The result was significant p < 0.01."
    )
    pages = [ParsedPage(page_number=1, text=text)]
    sections = [_results_section(text)]

    candidates = detect_claim_candidates(pages, sections)

    assert [candidate.matched_signal for candidate in candidates] == ["percentage", "p_value"]
    assert candidates[0].start_offset < candidates[1].start_offset


def test_abbreviation_does_not_cause_false_sentence_split() -> None:
    text = "The semaglutide group vs. placebo group showed a 12.4% greater reduction in weight."
    pages = [ParsedPage(page_number=1, text=text)]
    sections = [_results_section(text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].sentence_text == text


def test_et_al_abbreviation_does_not_cause_false_sentence_split() -> None:
    text = "As reported by Smith et al. Weight loss reached 12.4% in the treatment arm."
    pages = [ParsedPage(page_number=1, text=text)]
    sections = [_results_section(text)]

    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].sentence_text == text


def test_no_detected_sections_produces_no_candidates() -> None:
    pages = [ParsedPage(page_number=1, text="Body weight decreased by 12.4% from baseline.")]

    assert detect_claim_candidates(pages, []) == ()


def test_integrates_with_real_detect_sections_output() -> None:
    pages = [
        ParsedPage(
            page_number=1,
            text=(
                "Methods\n\nParticipants were randomized to treatment or placebo.\n\n"
                "Results\n\nBody weight decreased by 12.4% relative to baseline."
            ),
        )
    ]

    sections = detect_sections(pages)
    candidates = detect_claim_candidates(pages, sections)

    assert len(candidates) == 1
    assert candidates[0].section_type == "results"
    assert "12.4%" in candidates[0].sentence_text


def test_section_spanning_page_boundary_is_fully_scanned() -> None:
    pages = [
        ParsedPage(page_number=1, text="Results\n\nParticipants tolerated treatment well."),
        ParsedPage(page_number=2, text="Body weight decreased by 12.4% from baseline."),
    ]
    section = SectionSpan(
        section_type="results",
        start_page_number=1,
        start_offset=len("Results\n\n"),
        end_page_number=2,
        end_offset=len(pages[1].text),
        heading_text="Results",
        rules_version="test",
    )

    candidates = detect_claim_candidates(pages, [section])

    assert len(candidates) == 1
    assert candidates[0].page_number == 2
