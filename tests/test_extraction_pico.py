from knowledge_engine.extraction import (
    PICO_EXTRACTION_RULES_VERSION,
    SectionSpan,
    extract_pico,
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


def test_pico_extraction_rules_version_is_stable() -> None:
    assert PICO_EXTRACTION_RULES_VERSION == "m28-pico-v4"


def test_extract_pico_detects_population_from_cohort_size_clause() -> None:
    text = "Abstract\n\nWe enrolled 253 adults with obesity in this trial."
    sections = [_section("abstract", text, "Abstract")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population == "We enrolled 253 adults with obesity in this trial."
    assert fields.rules_version == PICO_EXTRACTION_RULES_VERSION


def test_extract_pico_detects_intervention_from_received_cue() -> None:
    text = "Methods\n\nParticipants received semaglutide once weekly for 68 weeks."
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.intervention == "Participants received semaglutide once weekly for 68 weeks."


def test_extract_pico_detects_comparator_from_versus_cue() -> None:
    text = "Methods\n\nWeight loss was compared with placebo over the study period."
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.comparator == "Weight loss was compared with placebo over the study period."


def test_extract_pico_detects_outcome_from_primary_outcome_cue() -> None:
    text = "Methods\n\nThe primary outcome was change in body weight from baseline."
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.outcome == "The primary outcome was change in body weight from baseline."


def test_extract_pico_outcome_also_scans_results() -> None:
    text = "Results\n\nThe main outcome improved significantly by week 12."
    sections = [_section("results", text, "Results")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.outcome == "The main outcome improved significantly by week 12."


def test_extract_pico_population_also_scans_results() -> None:
    """v2 (M38 follow-up): a structured "Results:" fragment split out of what
    used to be one undivided abstract span can restate the cohort size."""

    text = "Results\n\nAmong the 253 adults with obesity, weight loss was significant."
    sections = [_section("results", text, "Results")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population == "Among the 253 adults with obesity, weight loss was significant."


def test_extract_pico_intervention_also_scans_results() -> None:
    text = "Results\n\nParticipants who received semaglutide lost more weight."
    sections = [_section("results", text, "Results")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.intervention == "Participants who received semaglutide lost more weight."


def test_extract_pico_comparator_also_scans_conclusion() -> None:
    text = "Conclusion\n\nWeight loss was greater compared with placebo."
    sections = [_section("conclusion", text, "Conclusion")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.comparator == "Weight loss was greater compared with placebo."


def test_extract_pico_outcome_also_scans_conclusion() -> None:
    text = "Conclusion\n\nThe primary outcome was significantly improved."
    sections = [_section("conclusion", text, "Conclusion")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.outcome == "The primary outcome was significantly improved."


def test_extract_pico_ignores_population_cue_outside_scoped_sections() -> None:
    """A cohort-size clause in Discussion describes prior work, not this paper's own cohort."""

    text = "We enrolled 253 adults with obesity in a prior related trial."
    sections = [_section("discussion", text, "Discussion")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population is None


def test_extract_pico_returns_all_none_without_any_cue() -> None:
    text = "Methods\n\nThis study describes trends in metabolic health over time."
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population is None
    assert fields.intervention is None
    assert fields.comparator is None
    assert fields.outcome is None


def test_extract_pico_returns_all_none_without_scoped_sections() -> None:
    text = "No sections here."

    fields = extract_pico([ParsedPage(page_number=1, text=text)], [])

    assert fields.population is None
    assert fields.intervention is None
    assert fields.comparator is None
    assert fields.outcome is None


def test_extract_pico_excludes_a_table_derived_candidate() -> None:
    """A long, punctuation-free table dump containing an intervention cue
    word ("received") is excluded when it overlaps heavily with the page's
    own detected `table_text`; extraction falls through to the next,
    genuinely distinct intervention-cue sentence instead."""

    table_text = "Group Dose Received n Placebo 0mg 51 Semaglutide 2.4mg 51 Week Visit " * 6
    table_dump = table_text.strip()
    real_sentence = "Participants received semaglutide once weekly for 68 weeks."
    text = f"Methods\n\n{table_dump}. {real_sentence}"
    sections = [_section("methods", text, "Methods")]
    pages = [ParsedPage(page_number=1, text=text, table_text=table_text)]

    fields = extract_pico(pages, sections)

    assert fields.intervention == real_sentence


def test_extract_pico_strips_heading_from_matched_sentence() -> None:
    """The section heading must never leak into the extracted sentence value."""

    text = "Methods\n\nWe enrolled 253 adults with obesity."
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population == "We enrolled 253 adults with obesity."


def test_extract_pico_does_not_duplicate_a_sentence_matching_two_fields() -> None:
    """A dense trial sentence can satisfy both the population and intervention
    cue at once ("304 participants ... randomly assigned to ..."). Population
    is extracted first and claims that sentence; intervention must not also
    return it verbatim -- with no other intervention-cue sentence available,
    it is honestly None rather than a duplicate."""

    text = (
        "Methods\n\n"
        "304 participants were randomly assigned to semaglutide 2.4 mg or "
        "placebo. Body weight was measured at baseline and week 68."
    )
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population == (
        "304 participants were randomly assigned to semaglutide 2.4 mg or placebo."
    )
    assert fields.intervention is None


def test_extract_pico_scans_past_a_claimed_sentence_for_a_distinct_match() -> None:
    """When a second, distinct intervention-cue sentence exists, it is used
    instead of the sentence population already claimed."""

    text = (
        "Methods\n\n"
        "304 participants were randomly assigned to semaglutide 2.4 mg or "
        "placebo. All participants also received standard lifestyle counselling."
    )
    sections = [_section("methods", text, "Methods")]

    fields = extract_pico([ParsedPage(page_number=1, text=text)], sections)

    assert fields.population == (
        "304 participants were randomly assigned to semaglutide 2.4 mg or placebo."
    )
    assert fields.intervention == "All participants also received standard lifestyle counselling."
    assert fields.population != fields.intervention
    assert "Methods" not in fields.population
