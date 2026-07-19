from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_engine.reviewed_approval import ReviewedApprovalError, export_reviewed_approvals


def _write_worksheet(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "candidate_count": len(items), "items": items}),
        encoding="utf-8",
    )


def _accepted() -> dict[str, object]:
    return {
        "pmid": "100",
        "title": "Trial title",
        "doi": "10.1000/example",
        "pmcid": "PMC100",
        "open_access": True,
        "reported_license": "CC BY",
        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
        "discovery_status": "oa_verified",
        "decision": "accepted",
        "inclusion_review": "Meets criteria",
        "license_review": "Reusable under CC BY",
        "identity_review": "Identifiers match",
        "reviewer": "reviewer-1",
        "reviewed_at": "2026-07-19T12:00:00Z",
    }


def test_export_reviewed_approvals_builds_acquisition_schema(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [_accepted()])

    batch = export_reviewed_approvals(worksheet)

    assert batch.schema_version == 1
    assert len(batch.approvals) == 1
    approval = batch.approvals[0]
    assert approval.pmid == "100"
    assert approval.pmcid == "PMC100"
    assert approval.license == "CC BY"
    assert approval.filename == "PMC100.pdf"
    assert "reviewer" not in batch.to_json()


def test_rejected_items_are_omitted(tmp_path: Path) -> None:
    accepted = _accepted()
    rejected = _accepted()
    rejected["pmid"] = "101"
    rejected["pmcid"] = "PMC101"
    rejected["decision"] = "rejected"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [accepted, rejected])

    batch = export_reviewed_approvals(worksheet)

    assert [item.pmid for item in batch.approvals] == ["100"]


def test_pending_item_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["decision"] = "pending"
    worksheet = tmp_path / "review.json"
    _write_worksheet(worksheet, [item])

    with pytest.raises(ReviewedApprovalError, match="unresolved decision"):
        export_reviewed_approvals(worksheet)


def test_incomplete_accepted_review_stops_export(tmp_path: Path) -> None:
    item = _accepted()
    item["license_review"] = ""
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
