from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from knowledge_engine.pdf_calibration import PdfCalibrationError, calibrate_pdf_sample


def _write_receipt(path: Path, filename: str, payload: bytes) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 1,
                "items": [
                    {
                        "pmid": "1",
                        "pmcid": "PMC1",
                        "license": "CC BY",
                        "filename": filename,
                        "byte_count": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_valid_pdf_without_embedded_metadata_is_warning_only(tmp_path: Path) -> None:
    payload = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "PMC1.pdf").write_bytes(payload)
    receipt = tmp_path / "receipt.json"
    _write_receipt(receipt, "PMC1.pdf", payload)

    report = calibrate_pdf_sample(receipt, pdfs)

    item = report.items[0]
    assert item.pdf_version == "1.7"
    assert item.receipt_hash_matches is True
    assert {finding.code for finding in item.findings} == {
        "embedded_title_absent",
        "embedded_author_absent",
    }
    assert all(finding.severity == "warning" for finding in item.findings)


def test_hash_mismatch_is_hard_failure_finding(tmp_path: Path) -> None:
    expected = b"%PDF-1.4\n%%EOF\n"
    actual = b"%PDF-1.4\nchanged\n%%EOF\n"
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "PMC1.pdf").write_bytes(actual)
    receipt = tmp_path / "receipt.json"
    _write_receipt(receipt, "PMC1.pdf", expected)

    report = calibrate_pdf_sample(receipt, pdfs)

    findings = {finding.code: finding.severity for finding in report.items[0].findings}
    assert findings["receipt_hash_mismatch"] == "hard_failure"


def test_encryption_is_review_required_not_automatic_rejection(tmp_path: Path) -> None:
    payload = b"%PDF-1.6\n/Encrypt 2 0 R\n/Title (Paper)\n/Author (A)\n%%EOF\n"
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "PMC1.pdf").write_bytes(payload)
    receipt = tmp_path / "receipt.json"
    _write_receipt(receipt, "PMC1.pdf", payload)

    report = calibrate_pdf_sample(receipt, pdfs)

    findings = {finding.code: finding.severity for finding in report.items[0].findings}
    assert findings["encrypted_pdf"] == "review_required"


def test_sample_larger_than_four_is_rejected(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 5,
                "items": [
                    {
                        "filename": f"PMC{i}.pdf",
                        "sha256": "0" * 64,
                    }
                    for i in range(5)
                ],
            }
        ),
        encoding="utf-8",
    )
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()

    with pytest.raises(PdfCalibrationError, match="between 1 and 4"):
        calibrate_pdf_sample(receipt, pdfs)
