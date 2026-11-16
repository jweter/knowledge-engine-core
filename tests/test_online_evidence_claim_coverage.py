from __future__ import annotations

from knowledge_engine.online_evidence_claim_coverage import claim_coverage_ratio


def test_empty_list_returns_zero() -> None:
    assert claim_coverage_ratio([]) == 0.0


def test_mixed_statuses_round_to_four_decimal_places() -> None:
    assert claim_coverage_ratio(["supported", "insufficient_evidence", "contested"]) == 0.6667


def test_all_insufficient_evidence_returns_zero() -> None:
    assert claim_coverage_ratio(["insufficient_evidence", "insufficient_evidence"]) == 0.0


def test_differently_cased_string_counts_as_covered() -> None:
    assert claim_coverage_ratio(["Insufficient_Evidence"]) == 1.0


def test_single_element_insufficient_evidence_returns_zero() -> None:
    assert claim_coverage_ratio(["insufficient_evidence"]) == 0.0


def test_all_covered_list_returns_one() -> None:
    assert claim_coverage_ratio(["supported", "contested", "refuted"]) == 1.0
