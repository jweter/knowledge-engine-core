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


def test_matches_confidence_levels_other_than_95_and_99() -> None:
    """Real corpus text uses 80%/90% confidence levels too, not just 95/99."""

    sentence = "Least squares mean difference -2.1, upper limit 1-sided 80% CI -1.09."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_the_plural_cis() -> None:
    sentence = "Adjusted HRs (95% CIs) were 1.93 (1.72-2.17) for IFG progression."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_the_spelled_out_confidence_interval() -> None:
    sentence = "Mean difference was -0.13, 95% confidence interval -0.13 to 0.05."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_the_spelled_out_plural_confidence_intervals() -> None:
    sentence = "Horizontal lines indicate 95% confidence intervals around each estimate."

    assert extract_confidence_interval(sentence) == sentence


def test_matches_ci_stated_before_the_percentage() -> None:
    sentence = "The estimate was 0.702 (CI 95%: 0.403-0.957) in the validation cohort."

    assert extract_confidence_interval(sentence) == sentence


def test_returns_none_when_no_ci_is_stated() -> None:
    sentence = "Body weight decreased by 12.4% from baseline."

    assert extract_confidence_interval(sentence) is None


def test_returns_none_for_a_bare_percentage_that_is_not_a_ci() -> None:
    """A plain percentage must not be mistaken for a confidence interval --
    the pattern requires the literal "CI" marker, not just a "%" sign."""

    sentence = "95% of participants completed the study."

    assert extract_confidence_interval(sentence) is None


def test_returns_none_when_ci_and_a_percentage_are_not_adjacent() -> None:
    """A "CI" mention elsewhere in a long sentence must not be paired with an
    unrelated percentage -- only a directly adjacent pairing counts."""

    sentence = "The CI computation used bootstrap resampling; 42% of runs converged."

    assert extract_confidence_interval(sentence) is None


def test_rules_version_is_a_non_empty_string() -> None:
    assert CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION
    assert isinstance(CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION, str)
