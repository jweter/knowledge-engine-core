from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from knowledge_engine.manifest_curation import ManifestCurationError, export_manifest_curation_draft


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _review() -> dict[str, object]:
    return {
        "pmid": "100",
        "title": "Trial title",
        "authors": ["Ada Lovelace", "Trial Group"],
        "publication_year": 2024,
        "venue": "Journal of Verified Results",
        "doi": "10.1000/example",
        "pmcid": "PMC100",
        "open_access": True,
        "reported_license": "CC BY",
        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
        "discovery_status": "oa_verified",
        "decision": "accepted",
        "inclusion_review": "Meets criteria",
        "license_review": "Reusable",
        "identity_review": "Identifiers match",
        "reviewer": "reviewer-1",
        "reviewed_at": "2026-07-19T12:00:00Z",
    }


def _receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "acquired_count": 1,
        "items": [
            {
                "pmid": "100",
                "pmcid": "PMC100",
                "license": "CC BY",
                "filename": "PMC100.pdf",
                "byte_count": 123,
                "sha256": "a" * 64,
            }
        ],
    }


def test_export_manifest_curation_draft_populates_only_proven_fields(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    _write(worksheet, {"schema_version": 1, "candidate_count": 1, "items": [_review()]})
    _write(receipt, _receipt())

    draft = export_manifest_curation_draft(worksheet, receipt)
    rows = list(csv.DictReader(io.StringIO(draft.to_csv())))

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "pmc-100"
    assert row["other_identifier"] == "PMC100"
    assert row["local_path"] == "PMC100.pdf"
    assert row["expected_content_hash"] == "a" * 64
    assert row["inclusion_reason"] == "Meets criteria"
    assert row["authors"] == "Ada Lovelace; Trial Group"
    assert row["publication_year"] == "2024"
    assert row["venue"] == "Journal of Verified Results"
    assert row["study_type"] == ""


def test_receipt_license_mismatch_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    payload = _receipt()
    payload["items"][0]["license"] = "CC BY-NC"  # type: ignore[index]
    _write(worksheet, {"schema_version": 1, "candidate_count": 1, "items": [_review()]})
    _write(receipt, payload)

    with pytest.raises(ManifestCurationError, match="does not match"):
        export_manifest_curation_draft(worksheet, receipt)


def test_unresolved_review_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    review = _review()
    review["decision"] = "pending"
    _write(worksheet, {"schema_version": 1, "candidate_count": 1, "items": [review]})
    _write(receipt, _receipt())

    with pytest.raises(ManifestCurationError, match="unresolved decision"):
        export_manifest_curation_draft(worksheet, receipt)


def test_malformed_author_metadata_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    review = _review()
    review["authors"] = ["Ada Lovelace", ""]
    _write(worksheet, {"schema_version": 1, "candidate_count": 1, "items": [review]})
    _write(receipt, _receipt())

    with pytest.raises(ManifestCurationError, match="Author evidence is malformed"):
        export_manifest_curation_draft(worksheet, receipt)
