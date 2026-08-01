from pathlib import Path

import pytest

from knowledge_engine.rejected_candidates import (
    REJECTED_LEDGER_RULES_VERSION,
    RejectedCandidate,
    RejectedCandidatesError,
    append_rejected_candidates,
    check_candidates_against_ledger,
    extract_candidates,
    load_rejected_ledger,
    parse_rejected_candidate,
)


def _record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "pmid": "12345678",
        "title": "A busulfan pharmacokinetics study",
        "reason_category": "off_target_primary_disease",
        "batch_label": "retstart=3000",
    }
    base.update(overrides)
    return base


def test_rules_version_is_stable() -> None:
    assert REJECTED_LEDGER_RULES_VERSION == "m53-rejected-candidates-v1"


def test_load_rejected_ledger_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    assert load_rejected_ledger(tmp_path / "missing.csv") == {}


def test_parse_rejected_candidate_defaults_date_and_notes() -> None:
    candidate = parse_rejected_candidate(_record())

    assert candidate.pmid == "12345678"
    assert candidate.doi is None
    assert candidate.reason_category == "off_target_primary_disease"
    assert candidate.rejected_date
    assert candidate.notes == ""


def test_parse_rejected_candidate_rejects_missing_pmid() -> None:
    with pytest.raises(RejectedCandidatesError, match="pmid"):
        parse_rejected_candidate(_record(pmid=""))


def test_parse_rejected_candidate_rejects_missing_batch_label() -> None:
    with pytest.raises(RejectedCandidatesError, match="batch_label"):
        parse_rejected_candidate(_record(batch_label=""))


def test_parse_rejected_candidate_rejects_unknown_reason_category() -> None:
    with pytest.raises(RejectedCandidatesError, match="reason_category"):
        parse_rejected_candidate(_record(reason_category="not_a_real_category"))


def test_append_rejected_candidates_writes_header_and_rows(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    record = parse_rejected_candidate(_record())

    appended, skipped = append_rejected_candidates(ledger_path, [record])

    assert appended == [record]
    assert skipped == []
    loaded = load_rejected_ledger(ledger_path)
    assert loaded["12345678"] == record


def test_append_rejected_candidates_never_overwrites_an_existing_pmid(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    first = parse_rejected_candidate(_record(title="First decision"))
    append_rejected_candidates(ledger_path, [first])

    second = parse_rejected_candidate(_record(title="A different later decision"))
    appended, skipped = append_rejected_candidates(ledger_path, [second])

    assert appended == []
    assert skipped == ["12345678"]
    loaded = load_rejected_ledger(ledger_path)
    assert loaded["12345678"].title == "First decision"


def test_append_rejected_candidates_dedupes_within_the_same_batch(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.csv"
    record = parse_rejected_candidate(_record())
    duplicate = parse_rejected_candidate(_record(title="Same pmid, different title"))

    appended, skipped = append_rejected_candidates(ledger_path, [record, duplicate])

    assert len(appended) == 1
    assert skipped == ["12345678"]


def test_extract_candidates_reads_discovery_shape() -> None:
    payload = {"candidates": [{"pmid": "1"}, {"pmid": "2"}]}
    assert extract_candidates(payload) == [{"pmid": "1"}, {"pmid": "2"}]


def test_extract_candidates_reads_worksheet_shape() -> None:
    payload = {"items": [{"pmid": "1"}]}
    assert extract_candidates(payload) == [{"pmid": "1"}]


def test_extract_candidates_returns_empty_list_for_unknown_shape() -> None:
    assert extract_candidates({"unexpected": []}) == []


def test_check_candidates_against_ledger_splits_correctly() -> None:
    ledger = {
        "12345678": RejectedCandidate(
            pmid="12345678",
            doi=None,
            title="Rejected paper",
            reason_category="off_target_primary_disease",
            batch_label="retstart=3000",
            rejected_date="2026-07-01",
            notes="",
        )
    }
    candidates = [{"pmid": "12345678"}, {"pmid": "99999999"}]

    net_new, already_rejected = check_candidates_against_ledger(candidates, ledger)

    assert net_new == [{"pmid": "99999999"}]
    assert len(already_rejected) == 1
    assert already_rejected[0].pmid == "12345678"
