from knowledge_engine.extraction.effect_size import (
    EFFECT_SIZE_EXTRACTION_RULES_VERSION,
    extract_effect_size,
)


def test_matches_a_hazard_ratio_abbreviation_with_equals() -> None:
    sentence = "Overall survival favored the study drug (hazard ratio [HR] = 0.29; CI: 0.23-0.38)."

    assert extract_effect_size(sentence) == sentence


def test_matches_a_bare_hr_abbreviation_with_no_equals_sign() -> None:
    sentence = (
        "Event-free survival hazard ratio 0.50 (95% CI 0.34-0.74) favored the pembrolizumab arm."
    )

    assert extract_effect_size(sentence) == sentence


def test_matches_an_odds_ratio_abbreviation() -> None:
    sentence = (
        "Response was higher than with SSRI dose optimization "
        "(odds ratio 2.36, 95% CI [1.0, 5.6], p=0.05)."
    )

    assert extract_effect_size(sentence) == sentence


def test_matches_a_pooled_risk_ratio() -> None:
    sentence = (
        "In the chemoimmunotherapy arm (pooled RR = 1.86, 95% CI: 1.50-2.31), response improved."
    )

    assert extract_effect_size(sentence) == sentence


def test_matches_an_adjusted_or_abbreviation() -> None:
    sentence = "80% increased odds of worsening trajectory (OR adj = 1.809, 95%CI: 1.196, 2.736)."

    assert extract_effect_size(sentence) == sentence


def test_matches_a_mean_difference_with_a_unicode_minus_sign() -> None:
    sentence = "Reduction in triglycerides (least-squares mean difference, −4.36 mg/dL; 95% CI)."

    assert extract_effect_size(sentence) == sentence


def test_matches_a_full_phrase_hazard_ratio_with_parenthetical_abbreviation() -> None:
    sentence = "An adjusted Cox model yielded a hazard ratio (HR) of 0.59 (95% CI: 0.41-0.86)."

    assert extract_effect_size(sentence) == sentence


def test_returns_none_when_no_effect_size_is_stated() -> None:
    sentence = "Body weight decreased by 12.4% from baseline."

    assert extract_effect_size(sentence) is None


def test_returns_none_for_the_english_conjunction_or() -> None:
    """The dominant false-positive shape found in the real corpora: a
    case-insensitive "OR" match hits the ordinary English conjunction, not
    the odds-ratio abbreviation."""

    sentence = "There was no significant difference in accuracy or reaction time between groups."

    assert extract_effect_size(sentence) is None


def test_returns_none_for_a_confidence_interval_percentage_after_the_abbreviation() -> None:
    """A table header/parenthetical like "HR (95% CI)" states which two
    quantities are reported, not a value; the "95" in "95% CI" must not be
    mistaken for the HR itself."""

    sentence = "Results are reported as HR (95% CI) for each subgroup analyzed."

    assert extract_effect_size(sentence) is None


def test_returns_none_for_an_unrelated_number_after_the_full_phrase() -> None:
    """The phrase "relative risk for grade 3/4 TRAE" has no risk-ratio value
    in the sentence; the "3" in "grade 3/4" is an unrelated category label,
    not bridged past by an unrecognized "for ..." connector."""

    sentence = "Forest plot of relative risk for grade 3/4 TRAE in patients with PLELC."

    assert extract_effect_size(sentence) is None


def test_returns_none_for_an_abbreviation_legend_with_no_adjacent_value() -> None:
    sentence = "Abbreviations: OR, odds ratio; CI, confidence interval."

    assert extract_effect_size(sentence) is None


def test_rules_version_is_a_non_empty_string() -> None:
    assert EFFECT_SIZE_EXTRACTION_RULES_VERSION
    assert isinstance(EFFECT_SIZE_EXTRACTION_RULES_VERSION, str)
