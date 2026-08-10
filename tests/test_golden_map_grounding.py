from knowledge_engine.golden_map_grounding import (
    GOLDEN_MAP_GROUNDING_RULES_VERSION,
    check_record_numeric_grounding,
    extract_numbers,
)


def test_extract_numbers_finds_decimals_and_integers() -> None:
    numbers = extract_numbers("HR 0.65, 95% CI [0.61, 0.71], n=157 patients")

    assert numbers == {"0.65", "0.61", "0.71", "95", "157"}


def test_extract_numbers_treats_range_hyphen_as_separator_not_sign() -> None:
    """A confidence-interval range like "0.75-0.90" must yield the two positive
    bounds, not a fabricated negative number -- the exact case this module's
    docstring documents as the reason it does not do sign-aware parsing."""

    numbers = extract_numbers("hazard ratio 0.82; 95% CI [0.75-0.90]")

    assert numbers == {"0.82", "95", "0.75", "0.90"}
    assert "-0.90" not in numbers


def test_extract_numbers_handles_none_and_empty_text() -> None:
    assert extract_numbers(None) == frozenset()
    assert extract_numbers("") == frozenset()
    assert extract_numbers("no digits here") == frozenset()


def test_check_record_numeric_grounding_passes_when_every_number_is_present() -> None:
    result = check_record_numeric_grounding(
        "ev-1",
        "Response was higher with treatment (28.2% vs 14.3%; OR 2.36, 95% CI [1.0, 5.6]).",
        "response rate was 28.2% versus 14.3% (odds ratio 2.36, 95% CI 1.0-5.6, p=0.05)",
    )

    assert result.evidence_record_id == "ev-1"
    assert result.source_page_found is True
    assert result.numbers_checked == 6
    assert result.missing_numbers == ()
    assert result.fully_grounded is True


def test_check_record_numeric_grounding_reports_missing_numbers() -> None:
    result = check_record_numeric_grounding(
        "ev-2",
        "OS improved with HR 0.65 (95% CI 0.61-0.71); a secondary analysis found HR 1.26.",
        "the primary analysis found HR 0.65 (95% CI 0.61-0.71) favoring treatment",
    )

    assert result.source_page_found is True
    assert result.missing_numbers == ("1.26",)
    assert result.fully_grounded is False


def test_check_record_numeric_grounding_reports_missing_source_page_distinctly() -> None:
    result = check_record_numeric_grounding("ev-3", "HR 0.65 (95% CI 0.61-0.71).", None)

    assert result.source_page_found is False
    assert result.numbers_checked == 0
    assert result.missing_numbers == ()
    assert result.fully_grounded is False


def test_check_record_numeric_grounding_handles_missing_result_summary() -> None:
    result = check_record_numeric_grounding("ev-4", None, "some source text with 42 in it")

    assert result.source_page_found is True
    assert result.numbers_checked == 0
    assert result.fully_grounded is True


def test_rules_version_is_exported() -> None:
    assert GOLDEN_MAP_GROUNDING_RULES_VERSION == "golden-map-numeric-grounding-v1"
