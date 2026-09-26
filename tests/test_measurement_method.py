from knowledge_engine.extraction.measurement_method import (
    MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION,
    extract_measurement_method,
)


def test_matches_ambulatory_blood_pressure_monitoring_with_a_qualifier() -> None:
    sentence = (
        "Blood pressure was measured using 24-hour ambulatory blood pressure monitoring (ABPM)."
    )

    assert extract_measurement_method(sentence) == sentence


def test_matches_automated_oscillometric_measurement() -> None:
    sentence = "Blood pressure was assessed via automated oscillometric measurement."

    assert extract_measurement_method(sentence) == sentence


def test_matches_a_sphygmomanometer_with_a_qualifier() -> None:
    sentence = "Blood pressure was measured with a validated sphygmomanometer at each visit."

    assert extract_measurement_method(sentence) == sentence


def test_matches_home_blood_pressure_monitoring() -> None:
    sentence = (
        "Home blood pressure was measured using home blood pressure monitoring (HBPM) diaries."
    )

    assert extract_measurement_method(sentence) == sentence


def test_matches_the_hamilton_depression_rating_scale() -> None:
    sentence = (
        "Depression severity was assessed using the Hamilton Depression Rating Scale (HAM-D)."
    )

    assert extract_measurement_method(sentence) == sentence


def test_matches_hba1c_with_an_intervening_clause() -> None:
    sentence = "Glycemic control was evaluated by change in HbA1c from baseline."

    assert extract_measurement_method(sentence) == sentence


def test_matches_a_method_after_a_longer_same_clause_qualifier() -> None:
    """Codex review finding on this PR: three or more plain qualifier words
    between the cue and a recognized method, all within the same clause
    (no intervening sentence/clause boundary), must still match -- clause
    boundaries bound the search window, not a fixed word count."""

    sentence = "Serum IL-6 concentration was measured using a commercially available ELISA kit."

    assert extract_measurement_method(sentence) == sentence


def test_matches_a_real_corpus_ihc_sentence_via_its_second_cue() -> None:
    """Real oncology-corpus sentence: the first cue ("evaluated by H-Score")
    has no recognized method immediately after it, but the sentence's own
    second cue ("assessed by IHC") does -- every cue occurrence must be
    checked, not only the first."""

    sentence = (
        "ERO1A expression was evaluated by H-Score, and PD-L1 positivity was "
        "assessed by IHC using the SP263 antibody."
    )

    assert extract_measurement_method(sentence) == sentence


def test_matches_a_real_corpus_hplc_sentence_across_a_line_break() -> None:
    sentence = (
        "Carotenoid levels in Osteocol sauce were analyzed using\n\nHPLC and "
        "compared to those in a control sauce (Supplemental Fig. 1)."
    )

    assert extract_measurement_method(sentence) == sentence


def test_returns_none_without_any_measurement_cue() -> None:
    sentence = "Participants wore an ABPM monitor during the study."

    assert extract_measurement_method(sentence) is None


def test_returns_none_for_a_bare_context_free_sentence() -> None:
    sentence = "Participants tolerated the regimen well."

    assert extract_measurement_method(sentence) is None


def test_returns_none_for_a_statistical_test_bridged_to_an_unrelated_later_method() -> None:
    """v2's dominant real-corpus false-positive shape: a cue attached to a
    statistical-test name is not itself a measurement method, and an
    unrelated method keyword mentioned several clauses later in the same
    sentence must not be bridged past to manufacture a match."""

    sentence = (
        "Each value represents mean SEM (n = 5), *** p < 0.001; p values were "
        "measured by one-way ANOVA with Tukey's multiple comparison test. "
        "(S) Representative PET-CT images show pulmonary tumors."
    )

    assert extract_measurement_method(sentence) is None


def test_returns_none_for_a_correlation_statistic_bridged_to_an_unrelated_platform_name() -> None:
    """Real corpus shape: "concordance measured by Spearman [rho]" states a
    correlation statistic, not a measurement method; "RT-qPCR" appearing
    later in the same sentence, naming an unrelated sequencing platform, must
    not be bridged past to manufacture a match."""

    sentence = (
        "Schematic comparison of platform-specific concordance measured by "
        "Spearman correlation across the three simulated transcriptomic "
        "platforms (HTG EdgeSeq, NanoString nCounter, and RT-qPCR)."
    )

    assert extract_measurement_method(sentence) is None


def test_returns_none_for_a_measurement_timepoint_bridged_to_an_unrelated_scan() -> None:
    """Real corpus shape: a p-value's own statistical-test cue is followed,
    several sentences later in the same claim/result field, by an unrelated
    imaging modality (Positron Emission Computed Tomography) describing a
    completely different procedure on the same subjects."""

    sentence = (
        "The p value was measured by unpaired two-tailed Student's t test. "
        "Lung cancer bone metastasis patients then underwent Positron "
        "Emission Computed Tomography."
    )

    assert extract_measurement_method(sentence) is None


def test_a_skipped_word_never_crosses_a_sentence_boundary() -> None:
    """A skippable word must be immediately followed by whitespace, not a
    period, so a match can never be assembled from a token ending one
    sentence plus a method keyword beginning an unrelated next sentence."""

    sentence = "Response was measured by RECIST. Unrelated Computed Tomography imaging followed."

    # RECIST itself is a recognized method occurring immediately after the
    # cue, so this sentence still matches -- but only via that direct
    # adjacency, not by treating "RECIST." as a skippable word en route to
    # the later, unrelated "Computed Tomography".
    assert extract_measurement_method(sentence) == sentence


def test_rules_version_is_a_non_empty_string() -> None:
    assert MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION
    assert isinstance(MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION, str)
