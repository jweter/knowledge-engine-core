from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_engine.europepmc_reviewed_approval import (
    EuropePmcReviewedApprovalError,
    export_europepmc_reviewed_approvals,
)

RULES_VERSION = "m34-europepmc-candidate-adjudication-v1"


def _write_worksheet(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rules_version": RULES_VERSION,
                "candidate_count": len(items),
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def _accepted(index: int = 100) -> dict[str, object]:
    return {
        "europepmc_id": f"EPMC{index}",
        "source": "MED",
        "doi": f"10.1000/example-{index}",
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "open_access": True,
        "in_pmc": False,
        "reported_license": "CC BY 4.0",
        "pdf_url": f"https://europepmc.org/articles/EPMC{index}?pdf=render",
        "decision": "accepted",
        "reason_codes": ["ALL_REQUIRED_RULES_PASSED"],
        "rules_version": RULES_VERSION,
        "adjudicated_at": "2026-07-20T12:00:00+00:00",
        "inclusion_rule_result": "passed",
        "identity_rule_result": "passed",
        "license_rule_result": "passed",
        "full_text_rule_result": "passed",
        "pmc_overlap_rule_result": "passed",
        "duplicate_rule_result": "passed_exact_identifier_uniqueness",
        "evidence_provenance": ["europepmc_search"],
        "unresolved_ambiguities": [],
    }


def test_export_europepmc_reviewed_approvals_builds_acquisition_schema(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    batch = export_europepmc_reviewed_approvals(worksheet)

    assert batch.schema_version == 1
    assert batch.rules_version == RULES_VERSION
    assert batch.selection_rule == "accepted_in_worksheet_order"
    assert batch.source_candidate_count == 1
    assert batch.source_accepted_count == 1
    assert batch.selected_count == 1
    assert len(batch.approvals) == 1
    approval = batch.approvals[0]
    assert approval.europepmc_id == "EPMC100"
    assert approval.doi == "10.1000/example-100"
    assert approval.license == "CC BY 4.0"
    assert approval.filename == "europepmc-EPMC100.pdf"
    assert "reviewer" not in batch.to_json()


def test_rejected_and_held_items_are_omitted(tmp_path: Path) -> None:
    accepted = _accepted()
    rejected = _accepted(101)
    rejected["decision"] = "rejected"
    held = _accepted(102)
    held.update(
        {
            "decision": "held",
            "reason_codes": ["SCIENTIFIC_SCOPE_INSUFFICIENT"],
            "inclusion_rule_result": "insufficient_title_evidence",
            "unresolved_ambiguities": ["scientific_relevance"],
        }
    )
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [accepted, rejected, held])

    batch = export_europepmc_reviewed_approvals(worksheet)

    assert [item.europepmc_id for item in batch.approvals] == ["EPMC100"]
    assert batch.source_candidate_count == 3
    assert batch.source_accepted_count == 1


def test_selection_limit_preserves_worksheet_order(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted(300), _accepted(100), _accepted(200)])

    batch = export_europepmc_reviewed_approvals(worksheet, selection_limit=2)

    assert [item.europepmc_id for item in batch.approvals] == ["EPMC300", "EPMC100"]
    assert batch.source_accepted_count == 3
    assert batch.selected_count == 2


def test_selection_limit_fails_when_acceptances_are_insufficient(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    with pytest.raises(EuropePmcReviewedApprovalError, match="fewer accepted approvals"):
        export_europepmc_reviewed_approvals(worksheet, selection_limit=2)


def test_selection_limit_must_be_positive(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    with pytest.raises(EuropePmcReviewedApprovalError, match="at least 1"):
        export_europepmc_reviewed_approvals(worksheet, selection_limit=0)


def test_boolean_candidate_count_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rules_version": RULES_VERSION,
                "candidate_count": True,
                "items": [_accepted()],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EuropePmcReviewedApprovalError, match="count does not reconcile"):
        export_europepmc_reviewed_approvals(worksheet)


def test_unsupported_decision_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["decision"] = "pending"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="unsupported decision"):
        export_europepmc_reviewed_approvals(worksheet)


def test_incomplete_accepted_adjudication_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["reason_codes"] = []
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="missing required evidence"):
        export_europepmc_reviewed_approvals(worksheet)


def test_metadata_only_acceptance_is_rejected(tmp_path: Path) -> None:
    item = _accepted()
    item["open_access"] = False
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="lacks verified open-access"):
        export_europepmc_reviewed_approvals(worksheet)


def test_in_pmc_acceptance_is_rejected(tmp_path: Path) -> None:
    item = _accepted()
    item["in_pmc"] = True
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="not out of PMC's own pipeline scope"):
        export_europepmc_reviewed_approvals(worksheet)


def test_unresolved_ambiguity_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["unresolved_ambiguities"] = ["license"]
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="unresolved ambiguity"):
        export_europepmc_reviewed_approvals(worksheet)


def test_non_passing_rule_result_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["license_rule_result"] = "held_third_party_host"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="non-passing rule"):
        export_europepmc_reviewed_approvals(worksheet)


def test_unsupported_pdf_host_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["pdf_url"] = "https://attacker.example/EPMC100.pdf"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="unsupported PDF URL"):
        export_europepmc_reviewed_approvals(worksheet)


def test_invalid_europepmc_id_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["europepmc_id"] = "EPMC-100!"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="invalid Europe PMC id"):
        export_europepmc_reviewed_approvals(worksheet)


def test_duplicate_identifiers_stop_export(tmp_path: Path) -> None:
    first = _accepted(100)
    duplicate_id = _accepted(100)
    duplicate_id["doi"] = "10.1000/example-different"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [first, duplicate_id])

    with pytest.raises(EuropePmcReviewedApprovalError, match="duplicate identifiers"):
        export_europepmc_reviewed_approvals(worksheet)


def test_wrong_schema_version_stops_export(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "rules_version": RULES_VERSION,
                "candidate_count": 1,
                "items": [_accepted()],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EuropePmcReviewedApprovalError, match="schema_version must be 1"):
        export_europepmc_reviewed_approvals(worksheet)


def test_no_accepted_records_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["decision"] = "rejected"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(EuropePmcReviewedApprovalError, match="no accepted approvals"):
        export_europepmc_reviewed_approvals(worksheet)
