from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from knowledge_engine.corpus_readiness import CorpusReadinessError, validate_corpus_readiness


def test_ready_corpus_reconciles_manifest_receipt_and_pdf(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    body = b"%PDF-1.7\nvalidated"
    (papers / "PMC100.pdf").write_bytes(body)
    manifest = _write_manifest(tmp_path, filename="PMC100.pdf")
    receipt = _write_receipt(tmp_path, filename="PMC100.pdf", body=body)

    report = validate_corpus_readiness(
        manifest_path=manifest,
        receipt_paths=(receipt,),
        papers_directory=papers,
        expected_count=1,
    )

    assert report.ready is True
    assert report.accepted_count == 1
    assert report.receipt_count == 1
    assert report.file_count == 1
    assert report.items[0].source_id == "source-1"
    assert report.items[0].filename == "PMC100.pdf"
    assert str(tmp_path) not in report.to_json()


def test_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "PMC100.pdf").write_bytes(b"%PDF-changed")
    manifest = _write_manifest(tmp_path, filename="PMC100.pdf")
    receipt = _write_receipt(tmp_path, filename="PMC100.pdf", body=b"%PDF-original")

    with pytest.raises(CorpusReadinessError, match="hash does not match"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def test_unexpected_pdf_is_rejected(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    body = b"%PDF-1.7\nvalidated"
    (papers / "PMC100.pdf").write_bytes(body)
    (papers / "unexpected.pdf").write_bytes(body)
    manifest = _write_manifest(tmp_path, filename="PMC100.pdf")
    receipt = _write_receipt(tmp_path, filename="PMC100.pdf", body=body)

    with pytest.raises(CorpusReadinessError, match="unexpected PDF"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def test_unsafe_manifest_path_is_rejected(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    body = b"%PDF-1.7\nvalidated"
    (papers / "PMC100.pdf").write_bytes(body)
    manifest = _write_manifest(tmp_path, filename="../PMC100.pdf")
    receipt = _write_receipt(tmp_path, filename="PMC100.pdf", body=body)

    with pytest.raises(CorpusReadinessError, match="unsafe local path"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def test_nonapproved_usage_status_is_rejected(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    body = b"%PDF-1.7\nvalidated"
    (papers / "PMC100.pdf").write_bytes(body)
    manifest = _write_manifest(
        tmp_path,
        filename="PMC100.pdf",
        usage_status="metadata_only",
    )
    receipt = _write_receipt(tmp_path, filename="PMC100.pdf", body=body)

    with pytest.raises(CorpusReadinessError, match="approved usage status"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def _write_manifest(
    tmp_path: Path,
    *,
    filename: str,
    usage_status: str = "approved_open_access",
) -> Path:
    path = tmp_path / "sources.csv"
    fieldnames = [
        "source_id",
        "pmid",
        "other_identifier",
        "local_path",
        "license_type",
        "usage_status",
        "inclusion_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "source_id": "source-1",
                "pmid": "100",
                "other_identifier": "PMC100",
                "local_path": filename,
                "license_type": "CC-BY",
                "usage_status": usage_status,
                "inclusion_status": "included",
            }
        )
    return path


def _write_receipt(tmp_path: Path, *, filename: str, body: bytes) -> Path:
    path = tmp_path / "receipt.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "pmcid": "PMC100",
                        "license": "CC BY",
                        "filename": filename,
                        "byte_count": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
