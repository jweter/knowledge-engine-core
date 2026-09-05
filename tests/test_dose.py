from knowledge_engine.extraction.dose import (
    DOSE_EXTRACTION_RULES_VERSION,
    extract_dose,
)


def test_returns_the_sentence_when_it_states_a_plain_mg_dose() -> None:
    sentence = "In the STEP 5 trial, once-weekly semaglutide 2.4 mg reduced body weight."

    assert extract_dose(sentence) == sentence


def test_matches_a_per_weight_mg_per_kg_dose() -> None:
    """mg/kg is itself a standard dosing unit, not a lab concentration --
    the "/kg" denominator must not be excluded the way "/dL" is."""

    sentence = "Monotherapy dose expansion used INBRX-105 dose: 0.3 mg/kg."

    assert extract_dose(sentence) == sentence


def test_matches_a_per_body_surface_area_dose() -> None:
    sentence = "Patients received pemetrexed 500 mg/m2 every three weeks."

    assert extract_dose(sentence) == sentence


def test_matches_a_dose_stated_with_the_literal_word_dose() -> None:
    sentence = "One month later the dose was increased to 20 mg."

    assert extract_dose(sentence) == sentence


def test_matches_an_iu_dose() -> None:
    sentence = "Patients self-administered 100 IU of insulin glargine at bedtime."

    assert extract_dose(sentence) == sentence


def test_matches_a_milliliter_dose() -> None:
    sentence = "The oral suspension was dosed at 10 mL twice daily."

    assert extract_dose(sentence) == sentence


def test_matches_case_insensitively_and_with_a_hyphen() -> None:
    sentence = "A total of 134/162 patients reached a dose of 14mg of oral semaglutide."

    assert extract_dose(sentence) == sentence


def test_returns_none_when_no_dose_is_stated() -> None:
    sentence = "Body weight decreased by 12.4% from baseline."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_lab_concentration_in_mg_per_dl() -> None:
    """The dominant false-positive shape found in the real corpora: a lab
    value sharing the mg unit prefix with a genuine dose but measured per
    deciliter, not administered as an intervention dose."""

    sentence = "The median baseline serum triglyceride was 128.0 mg/dL."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_lab_concentration_in_iu_per_l() -> None:
    sentence = "The median baseline serum ALT was 31.0 IU/L."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_lab_concentration_in_g_per_l() -> None:
    sentence = "Albumin was 41.0 g/L in patients with disease control."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_creatinine_clearance_rate_in_ml_per_min() -> None:
    sentence = "Creatinine clearance was >80 mL/min in most participants."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_figure_panel_reference() -> None:
    """A bare gram unit is deliberately unsupported: "2G"/"4G" figure-panel
    suffixes have no separating space, the same shape a genuine "<n> g" dose
    would have if grams were matched without a mandatory context check."""

    sentence = "Corroborating the in vitro results (Fig. 2G), BBB function improved."

    assert extract_dose(sentence) is None


def test_returns_none_for_a_gram_effect_size() -> None:
    sentence = "The pooled mean difference was -3.37 g (95% CI -5.42 to -1.33)."

    assert extract_dose(sentence) is None


def test_rules_version_is_a_non_empty_string() -> None:
    assert DOSE_EXTRACTION_RULES_VERSION
    assert isinstance(DOSE_EXTRACTION_RULES_VERSION, str)
