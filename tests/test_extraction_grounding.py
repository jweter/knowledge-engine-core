from knowledge_engine.extraction import GROUNDING_RULES_VERSION, verify_grounding

_SOURCE_TEXT = (
    "Participants were adults aged 18 to 75 years with a body mass index "
    "of 30 or greater. Patients received once-weekly subcutaneous "
    "semaglutide 2.4 mg or matching placebo for 68 weeks. The primary "
    "endpoint was percent change in body weight from baseline to week 68. "
    "Semaglutide reduced body weight by 14.9% compared with 2.4% for "
    "placebo, a treatment difference of -12.4 percentage points (p<0.001)."
)


def test_exact_substring_is_grounded() -> None:
    result = verify_grounding(
        "Semaglutide reduced body weight by 14.9% compared with 2.4% for placebo",
        _SOURCE_TEXT,
    )

    assert result.grounded is True
    assert result.match_type == "exact_substring"
    assert result.similarity == 1.0
    assert result.rules_version == GROUNDING_RULES_VERSION


def test_light_formatting_difference_is_a_near_match() -> None:
    """A light punctuation/wording edit -- not a heavier paraphrase -- is
    exactly what an LLM re-quoting a source sentence is expected to
    produce; the extraction prompt is designed to ask for near-verbatim
    quotes, the same "extract, don't paraphrase" discipline the
    deterministic extractors already use."""

    result = verify_grounding(
        "Semaglutide reduced body weight by 14.9%, compared with 2.4% for "
        "placebo, a treatment difference of -12.4 percentage points.",
        _SOURCE_TEXT,
    )

    assert result.grounded is True
    assert result.match_type == "near_match"
    assert result.similarity >= 0.75
    assert result.matched_source_excerpt is not None


def test_fabricated_text_is_not_grounded() -> None:
    result = verify_grounding(
        "Tirzepatide reduced HbA1c by 2.1% compared with insulin glargine.",
        _SOURCE_TEXT,
    )

    assert result.grounded is False
    assert result.match_type == "not_grounded"
    assert result.matched_source_excerpt is None


def test_unrelated_but_plausible_sentence_is_not_grounded() -> None:
    """A real-sounding clinical sentence that is simply absent from this
    source must still fail -- grounding checks presence, not plausibility."""

    result = verify_grounding(
        "No serious adverse events were reported during the 68-week trial.",
        _SOURCE_TEXT,
    )

    assert result.grounded is False


def test_empty_proposed_text_is_not_grounded() -> None:
    result = verify_grounding("", _SOURCE_TEXT)

    assert result.grounded is False
    assert result.match_type == "not_grounded"
    assert result.similarity == 0.0


def test_whitespace_only_proposed_text_is_not_grounded() -> None:
    result = verify_grounding("   \n\t  ", _SOURCE_TEXT)

    assert result.grounded is False


def test_empty_source_text_is_not_grounded() -> None:
    result = verify_grounding("Semaglutide reduced body weight.", "")

    assert result.grounded is False


def test_case_and_whitespace_differences_still_match_exactly() -> None:
    result = verify_grounding(
        "  SEMAGLUTIDE reduced   body weight by 14.9% compared with 2.4% for placebo  ",
        _SOURCE_TEXT,
    )

    assert result.grounded is True
    assert result.match_type == "exact_substring"


def test_custom_min_similarity_narrows_acceptance() -> None:
    proposed = "Semaglutide reduced body weight by 14.9 percent versus 2.4 percent for placebo."

    lenient = verify_grounding(proposed, _SOURCE_TEXT, min_similarity=0.3)
    strict = verify_grounding(proposed, _SOURCE_TEXT, min_similarity=0.999)

    assert lenient.grounded is True
    assert strict.grounded is False
