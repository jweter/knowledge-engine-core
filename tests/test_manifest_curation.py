from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from knowledge_engine.manifest_curation import ManifestCurationError, export_manifest_curation_draft

RULES_VERSION = "m14-candidate-adjudication-v1"


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _adjudication() -> dict[str, object]:
    return {
        "pmid": "100",
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "authors": ["Ada Lovelace", "Trial Group"],
        "publication_year": 2024,
        "venue": "Journal of Verified Results",
        "doi": "10.1000/example",
        "pmcid": "PMC100",
        "open_access": True,
        "reported_license": "CC BY 4.0",
        "pdf_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC100.1/PMC100.1.pdf",
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
        "evidence_provenance": ["pubmed_metadata", "pmc_cloud_service"],
        "unresolved_ambiguities": [],
    }


def _worksheet(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 2,
        "rules_version": RULES_VERSION,
        "candidate_count": len(items),
        "items": items,
    }


def _receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "acquired_count": 1,
        "items": [
            {
                "pmid": "100",
                "pmcid": "PMC100",
                "license": "CC BY 4.0",
                "filename": "PMC100.pdf",
                "byte_count": 123,
                "sha256": "a" * 64,
            }
        ],
    }


def test_export_manifest_curation_draft_populates_proven_fields(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    _write(worksheet, _worksheet([_adjudication()]))
    _write(receipt, _receipt())

    draft = export_manifest_curation_draft(worksheet, receipt)
    rows = list(csv.DictReader(io.StringIO(draft.to_csv())))

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "pmc-100"
    assert row["other_identifier"] == "PMC100"
    assert row["local_path"] == "PMC100.pdf"
    assert row["expected_content_hash"] == "a" * 64
    assert row["inclusion_reason"] == "ALL_REQUIRED_RULES_PASSED"
    assert row["authors"] == "Ada Lovelace; Trial Group"
    assert row["publication_year"] == "2024"
    assert row["venue"] == "Journal of Verified Results"
    assert row["notes"] == f"Automated adjudication ruleset: {RULES_VERSION}"


def test_receipt_license_mismatch_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    payload = _receipt()
    payload["items"][0]["license"] = "CC BY-NC"  # type: ignore[index]
    _write(worksheet, _worksheet([_adjudication()]))
    _write(receipt, payload)

    with pytest.raises(ManifestCurationError, match="does not match"):
        export_manifest_curation_draft(worksheet, receipt)


def test_held_adjudication_is_excluded_without_human_input(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    held = _adjudication()
    held.update(
        {
            "decision": "held",
            "reason_codes": ["SCIENTIFIC_SCOPE_INSUFFICIENT"],
            "inclusion_rule_result": "insufficient_title_evidence",
            "unresolved_ambiguities": ["scientific_relevance"],
        }
    )
    _write(worksheet, _worksheet([held]))
    _write(receipt, {"schema_version": 1, "acquired_count": 0, "items": []})

    with pytest.raises(ManifestCurationError, match="No reconciled acquired records"):
        export_manifest_curation_draft(worksheet, receipt)


def test_accepted_superset_of_receipt_is_reconciled_by_selection(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    selected = _adjudication()
    not_selected = _adjudication()
    not_selected.update({"pmid": "200", "pmcid": "PMC200"})
    _write(worksheet, _worksheet([selected, not_selected]))
    _write(receipt, _receipt())

    draft = export_manifest_curation_draft(worksheet, receipt)
    rows = list(csv.DictReader(io.StringIO(draft.to_csv())))

    assert len(rows) == 1
    assert rows[0]["pmid"] == "100"


def test_receipt_pmid_without_accepted_adjudication_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    other = _adjudication()
    other.update({"pmid": "300", "pmcid": "PMC300"})
    _write(worksheet, _worksheet([other]))
    _write(receipt, _receipt())

    with pytest.raises(ManifestCurationError, match="without an accepted adjudication"):
        export_manifest_curation_draft(worksheet, receipt)


def test_malformed_author_metadata_is_rejected(tmp_path: Path) -> None:
    worksheet = tmp_path / "review.json"
    receipt = tmp_path / "receipt.json"
    adjudication = _adjudication()
    adjudication["authors"] = ["Ada Lovelace", ""]
    _write(worksheet, _worksheet([adjudication]))
    _write(receipt, _receipt())

    with pytest.raises(ManifestCurationError, match="Author evidence is malformed"):
        export_manifest_curation_draft(worksheet, receipt)
