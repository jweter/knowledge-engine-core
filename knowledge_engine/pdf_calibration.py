"""Empirical, tolerance-aware calibration of acquired research PDFs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PDF_HEADER = re.compile(rb"%PDF-(\d\.\d)")
EOF_MARKER = b"%%EOF"
MAX_SAMPLE_SIZE = 4


class PdfCalibrationError(RuntimeError):
    """Sanitized calibration failure."""


@dataclass(frozen=True)
class PdfCalibrationFinding:
    """One evidence-backed intake finding."""

    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class PdfCalibrationItem:
    """Observable properties for one acquired PDF."""

    filename: str
    byte_count: int
    sha256: str
    pdf_version: str | None
    has_eof_marker: bool
    receipt_hash_matches: bool
    findings: tuple[PdfCalibrationFinding, ...]


@dataclass(frozen=True)
class PdfCalibrationReport:
    """Deterministic pilot report for a bounded real-file sample."""

    schema_version: int
    sample_count: int
    items: tuple[PdfCalibrationItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def calibrate_pdf_sample(receipt_path: Path, pdf_directory: Path) -> PdfCalibrationReport:
    """Inspect 1-4 receipt-backed PDFs without assuming perfect metadata."""

    receipt = _load_object(receipt_path)
    if receipt.get("schema_version") != 1:
        raise PdfCalibrationError("Acquisition receipt schema_version must be 1.")
    rows = receipt.get("items")
    if not isinstance(rows, list) or receipt.get("acquired_count") != len(rows):
        raise PdfCalibrationError("Acquisition receipt count does not reconcile.")
    if not 1 <= len(rows) <= MAX_SAMPLE_SIZE:
        raise PdfCalibrationError("Calibration sample must contain between 1 and 4 PDFs.")
    if pdf_directory.is_symlink() or not pdf_directory.is_dir():
        raise PdfCalibrationError("PDF directory must be a real directory.")

    items: list[PdfCalibrationItem] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise PdfCalibrationError("Acquisition receipt contains a malformed item.")
        filename = _required(row, "filename")
        expected_hash = _required(row, "sha256").casefold()
        if filename in seen:
            raise PdfCalibrationError("Acquisition receipt contains a duplicate filename.")
        seen.add(filename)
        path = pdf_directory / filename
        if path.parent != pdf_directory or path.is_symlink() or not path.is_file():
            raise PdfCalibrationError("Receipt-backed PDF path is missing or unsafe.")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise PdfCalibrationError("Receipt-backed PDF could not be read.") from exc

        digest = hashlib.sha256(payload).hexdigest()
        header = PDF_HEADER.match(payload[:16])
        findings: list[PdfCalibrationFinding] = []
        if header is None:
            findings.append(
                PdfCalibrationFinding(
                    "invalid_pdf_signature",
                    "hard_failure",
                    "Payload does not begin with a PDF signature.",
                )
            )
        if not payload.rstrip().endswith(EOF_MARKER):
            findings.append(
                PdfCalibrationFinding(
                    "missing_terminal_eof",
                    "warning",
                    "Terminal PDF EOF marker is absent or displaced.",
                )
            )
        if digest != expected_hash:
            findings.append(
                PdfCalibrationFinding(
                    "receipt_hash_mismatch",
                    "hard_failure",
                    "PDF hash does not match the acquisition receipt.",
                )
            )
        if b"/Title" not in payload:
            findings.append(
                PdfCalibrationFinding(
                    "embedded_title_absent",
                    "warning",
                    "Embedded PDF title metadata was not observed.",
                )
            )
        if b"/Author" not in payload:
            findings.append(
                PdfCalibrationFinding(
                    "embedded_author_absent",
                    "warning",
                    "Embedded PDF author metadata was not observed.",
                )
            )
        if b"/Encrypt" in payload:
            findings.append(
                PdfCalibrationFinding(
                    "encrypted_pdf",
                    "review_required",
                    "PDF advertises encryption and requires parser review.",
                )
            )

        items.append(
            PdfCalibrationItem(
                filename,
                len(payload),
                digest,
                header.group(1).decode("ascii") if header else None,
                payload.rstrip().endswith(EOF_MARKER),
                digest == expected_hash,
                tuple(findings),
            )
        )

    return PdfCalibrationReport(1, len(items), tuple(items))


def _load_object(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise PdfCalibrationError("Acquisition receipt must not be a symbolic link.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PdfCalibrationError("Acquisition receipt could not be read as JSON.") from exc
    if not isinstance(value, dict):
        raise PdfCalibrationError("Acquisition receipt must be a JSON object.")
    return value


def _required(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PdfCalibrationError("Acquisition receipt contains incomplete evidence.")
    return value.strip()
