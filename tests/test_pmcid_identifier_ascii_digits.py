from knowledge_engine.corpus.validation import _PMCID_PATTERN


def test_ascii_pmcids_are_recognized_in_either_case() -> None:
    assert _PMCID_PATTERN.fullmatch("PMC123456")
    assert _PMCID_PATTERN.fullmatch("pmc42")


def test_non_ascii_digits_are_not_a_pmcid() -> None:
    assert _PMCID_PATTERN.fullmatch("PMC١٢٣") is None  # Arabic-Indic digits
    assert _PMCID_PATTERN.fullmatch("PMC１２") is None  # fullwidth digits


def test_other_identifiers_are_still_not_a_pmcid() -> None:
    assert _PMCID_PATTERN.fullmatch("PMC") is None
    assert _PMCID_PATTERN.fullmatch("PMID123") is None
    assert _PMCID_PATTERN.fullmatch("PMC12a") is None
