from knowledge_engine.extraction.confidence_interval import (
    CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION,
    extract_confidence_interval,
)


def test_returns_the_sentence_when_it_states_a_95_percent_ci() -> None:
    sentence = "Mean systolic BP rose 4.2 mmHg (95% CI, 1.1 to 7.3) versus placebo."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_99_percent_ci_too() -> None:
    sentence = "The odds ratio was 1.8 (99% CI 1.2-2.6)."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_case_insensitively_and_with_stray_whitespace() -> None:
    sentence = "Risk increased (95 %   ci: 1.02-1.09)."

    assert extract_confidence_interval(sentence) == sentence


def test_returns_none_when_no_ci_is_stated() -> None:
    sentence = "Body weight decreased by 12.4% from baseline."

    assert extract_confidence_interval(sentence) is None


def test_returns_none_for_a_bare_percentage_that_is_not_a_ci() -> None:
    """A plain percentage must not be mistaken for a confidence interval --
    the pattern requires the literal "CI" marker, not just a "%" sign."""

    sentence = "95% of participants completed the study."

    assert extract_confidence_interval(sentence) is None


def test_rules_version_is_a_non_empty_string() -> None:
    assert CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION
    assert isinstance(CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION, str)
