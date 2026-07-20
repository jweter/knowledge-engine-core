from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_engine.reviewed_approval import ReviewedApprovalError, export_reviewed_approvals

RULES_VERSION = "m14-candidate-adjudication-v1"


def _write_worksheet(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "rules_version": RULES_VERSION,
                "candidate_count": len(items),
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def _accepted(index: int = 100) -> dict[str, object]:
    return {
        "pmid": str(index),
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "doi": f"10.1000/example-{index}",
        "pmcid": f"PMC{index}",
        "open_access": True,
        "reported_license": "CC BY 4.0",
        "pdf_url": f"https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/{index}.pdf",
        "discovery_status": "oa_verified",
        "decision": "accepted",
        "reason_codes": ["ALL_REQUIRED_RULES_PASSED"],
        "rules_version": RULES_VERSION,
        "adjudicated_at": "2026-07-20T12:00:00+00:00",
        "inclusion_rule_result": "passed",
        "identity_rule_result": "passed",
        "license_rule_result": "passed",
        "full_text_rule_result": "passed",
        "duplicate_rule_result": "passed_exact_identifier_uniqueness",
        "evidence_provenance": ["pubmed_metadata", "pmc_oa_service"],
        "unresolved_ambiguities": [],
    }


def test_export_reviewed_approvals_builds_acquisition_schema(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    batch = export_reviewed_approvals(worksheet)

    assert batch.schema_version == 1
    assert batch.rules_version == RULES_VERSION
    assert batch.selection_rule == "accepted_in_worksheet_order"
    assert batch.source_candidate_count == 1
    assert batch.source_accepted_count == 1
    assert batch.selected_count == 1
    assert len(batch.approvals) == 1
    approval = batch.approvals[0]
    assert approval.pmid == "100"
    assert approval.pmcid == "PMC100"
    assert approval.license == "CC BY 4.0"
    assert approval.filename == "PMC100.pdf"
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

    batch = export_reviewed_approvals(worksheet)

    assert [item.pmid for item in batch.approvals] == ["100"]
    assert batch.source_candidate_count == 3
    assert batch.source_accepted_count == 1


def test_selection_limit_preserves_worksheet_order(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted(300), _accepted(100), _accepted(200)])

    batch = export_reviewed_approvals(worksheet, selection_limit=2)

    assert [item.pmid for item in batch.approvals] == ["300", "100"]
    assert batch.source_accepted_count == 3
    assert batch.selected_count == 2


def test_selection_limit_fails_when_acceptances_are_insufficient(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    with pytest.raises(ReviewedApprovalError, match="fewer accepted approvals"):
        export_reviewed_approvals(worksheet, selection_limit=2)


def test_selection_limit_must_be_positive(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    with pytest.raises(ReviewedApprovalError, match="at least 1"):
        export_reviewed_approvals(worksheet, selection_limit=0)


def test_boolean_candidate_count_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    worksheet.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "rules_version": RULES_VERSION,
                "candidate_count": True,
                "items": [_accepted()],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReviewedApprovalError, match="count does not reconcile"):
        export_reviewed_approvals(worksheet)


def test_unsupported_decision_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["decision"] = "pending"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(ReviewedApprovalError, match="unsupported decision"):
        export_reviewed_approvals(worksheet)


def test_incomplete_accepted_adjudication_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["reason_codes"] = []
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(ReviewedApprovalError, match="missing required evidence"):
        export_reviewed_approvals(worksheet)


def test_metadata_only_acceptance_is_rejected(tmp_path: Path) -> None:
    item = _accepted()
    item["open_access"] = False
    item["discovery_status"] = "metadata_only"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(ReviewedApprovalError, match="lacks verified PMC OA evidence"):
        export_reviewed_approvals(worksheet)
