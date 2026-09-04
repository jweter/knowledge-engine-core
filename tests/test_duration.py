from knowledge_engine.extraction.duration import (
    DURATION_EXTRACTION_RULES_VERSION,
    extract_duration,
)


def test_matches_a_lead_in_preposition_before_a_bare_unit() -> None:
    sentence = "Mice were treated with vehicle or 10% glucose water for 4 weeks."

    assert extract_duration(sentence) == sentence


def test_matches_over_the_hyphenated_unit_follow_up() -> None:
    sentence = (
        "HAMD-24 scores decreased significantly in both groups over the 8-week "
        "follow-up, with a statistically significant between-group difference."
    )

    assert extract_duration(sentence) == sentence


def test_matches_a_hyphenated_unit_followed_by_a_duration_noun() -> None:
    sentence = "The remission rate was assessed following a 24-week treatment period."

    assert extract_duration(sentence) == sentence


def test_matches_a_hyphenated_unit_with_intervening_adjectives_before_trial() -> None:
    """Real corpus phrasing: several comma-separated adjectives can sit
    between the hyphenated duration and the noun it modifies."""

    sentence = (
        "In an 8-week, multicentre, double-blind, randomized, placebo-controlled "
        "trial, adding agomelatine to ongoing SSRI treatment did not improve outcomes."
    )

    assert extract_duration(sentence) == sentence


def test_matches_the_literal_word_duration_preceding_the_unit() -> None:
    sentence = (
        "At the data cutoff date, the median follow-up duration was 18.6 months "
        "(95% CI: 13.1-24.0 months)."
    )

    assert extract_duration(sentence) == sentence


def test_matches_duration_of_n_months_of_treatment() -> None:
    sentence = (
        "Patients who stopped durvalumab due to treatment side effects achieved a "
        "median duration of 10 months of treatment, and 53% were still alive at 2 years."
    )

    assert extract_duration(sentence) == sentence


def test_matches_a_bare_unit_threshold_with_follow_up_context() -> None:
    sentence = (
        "A subgroup analysis showed a significant HDRS reduction when follow-up "
        "duration was >=6 months (MD -0.96, 95% CI -1.86 to -0.05, P=0.04)."
    )

    assert extract_duration(sentence) == sentence


def test_matches_hyphenated_year_follow_up() -> None:
    sentence = (
        "GLP-1 therapy was associated with significantly lower risk of acute DVT "
        "at both 1- and 3-year follow-up in obese patients with chronic venous "
        "insufficiency."
    )

    assert extract_duration(sentence) == sentence


def test_matches_case_insensitively_and_with_stray_whitespace() -> None:
    sentence = "Patients were monitored for  6   WEEKS during the treatment PERIOD."

    assert extract_duration(sentence) == sentence


def test_returns_none_when_no_duration_is_stated() -> None:
    sentence = "Body weight decreased by 12.4% from baseline."

    assert extract_duration(sentence) is None


def test_returns_none_for_an_age_stated_in_years() -> None:
    """A bare age mention must never be mislabeled as a duration."""

    sentence = "The median age was 69 years, and 54% were male."

    assert extract_duration(sentence) is None


def test_returns_none_for_an_aged_threshold_with_a_duration_word_nearby() -> None:
    """Real corpus false-positive case: an age threshold followed, in an
    unrelated clause, by a genuine duration-context word must not match."""

    sentence = (
        "Findings remained significant beyond 24 months and stronger among "
        "patients over 60 years, without diabetic complications."
    )

    assert extract_duration(sentence) is None


def test_returns_none_for_a_hyphenated_age_descriptor() -> None:
    sentence = "The trial enrolled 65-year-old participants with stage III disease."

    assert extract_duration(sentence) is None


def test_returns_none_for_years_of_age_phrasing() -> None:
    sentence = "Eligible participants were 65 years of age or older at enrollment."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_dose_interval() -> None:
    """A dosing interval ("every 2 weeks") must not be mistaken for a
    study/intervention/follow-up duration."""

    sentence = "The drug was administered at 5 mg every 2 weeks (Q2W)."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_survival_timepoint() -> None:
    """Real corpus false-positive case: a survival/response measurement at a
    fixed landmark timepoint is not a duration, even though it uses the same
    hyphenated "N-unit" shape a genuine duration does."""

    sentence = (
        "Concurrent CRT plus durvalumab achieved superior 2-year progression-free "
        "survival compared with sequential CRT."
    )

    assert extract_duration(sentence) is None


def test_returns_none_for_a_landmark_analysis_timepoint() -> None:
    sentence = "A 12-week landmark analysis including 323 patients was performed."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_study_population_unrelated_to_a_nearby_number() -> None:
    """Real corpus false-positive case: "study" describing a population, with
    an unrelated number stated later in the same clause, must not bridge."""

    sentence = "The median PFS in the study population was 2.5 months (95% CI, 1.5-3.0)."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_measurement_window_anchored_to_treatment_start() -> None:
    """A window measured from an anchor event ("treatment start") is not the
    same as how long the treatment itself lasted."""

    sentence = "Mortality within 90 days of treatment start was 3.8% for PS 0-1."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_word_containing_treatment_as_a_substring() -> None:
    """ "retreatment" must not be mistaken for the context word "treatment"."""

    sentence = "The median OS for platinum retreatment with or without ICI was 27.2 months."

    assert extract_duration(sentence) is None


def test_returns_none_for_an_age_threshold_using_over() -> None:
    sentence = "Efficacy was similar in patients over 65 years compared with younger patients."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_measurement_timepoint_after_treatment() -> None:
    """A fixed timepoint stated relative to treatment ("after treatment") is
    not the same as how long the treatment itself lasted."""

    sentence = "Blood pressure was measured 3 months after treatment."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_measurement_timepoint_before_the_intervention() -> None:
    sentence = "Symptoms were assessed 6 weeks before the intervention."

    assert extract_duration(sentence) is None


def test_returns_none_for_a_measurement_timepoint_following_the_intervention() -> None:
    sentence = "Quality of life was assessed 12 weeks following the intervention."

    assert extract_duration(sentence) is None


def test_matches_a_leading_duration_noun_followed_by_after_as_intervening_text() -> None:
    """The after/before/following exclusion is trailing-only: here "after"
    is legitimate text between a leading duration noun ("period") and the
    unit, not a bridge past an anchor reached from the trailing direction."""

    sentence = "The follow-up period after surgery was 6 months."

    assert extract_duration(sentence) == sentence


def test_matches_a_leading_duration_noun_followed_by_following_as_intervening_text() -> None:
    sentence = "The study duration following enrollment was 6 months."

    assert extract_duration(sentence) == sentence


def test_rules_version_is_a_non_empty_string() -> None:
    assert DURATION_EXTRACTION_RULES_VERSION
    assert isinstance(DURATION_EXTRACTION_RULES_VERSION, str)
