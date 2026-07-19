"""Offline reconciliation of a curated corpus manifest, acquisition receipts, and PDFs."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

APPROVED_USAGE_STATUSES = {"approved_open_access", "public_domain"}
REQUIRED_COLUMNS = {
    "source_id",
    "pmid",
    "other_identifier",
    "local_path",
    "license_type",
    "usage_status",
    "inclusion_status",
}


class CorpusReadinessError(RuntimeError):
    """Sanitized corpus-readiness validation failure."""


@dataclass(frozen=True)
class CorpusReadinessItem:
    """Sanitized evidence for one reconciled source."""

    source_id: str
    pmid: str
    pmcid: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class CorpusReadinessReport:
    """Deterministic evidence that the corpus entry gate is satisfied."""

    schema_version: int
    ready: bool
    expected_count: int
    accepted_count: int
    receipt_count: int
    file_count: int
    manifest_sha256: str
    items: tuple[CorpusReadinessItem, ...]

    def to_json(self) -> str:
        """Render stable JSON without absolute local paths."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def validate_corpus_readiness(
    *,
    manifest_path: Path,
    receipt_paths: tuple[Path, ...],
    papers_directory: Path,
    expected_count: int = 500,
) -> CorpusReadinessReport:
    """Reconcile all accepted rows, receipts, and local files exactly."""

    if expected_count < 1:
        raise CorpusReadinessError("Expected corpus count must be positive.")
    _reject_symlink(manifest_path, label="Manifest")
    _reject_symlink(papers_directory, label="Papers directory")
    if not papers_directory.is_dir():
        raise CorpusReadinessError("Papers directory is not readable.")

    manifest_bytes = _read_bytes(manifest_path, label="Manifest")
    rows = _load_manifest(manifest_bytes)
    if len(rows) != expected_count:
        raise CorpusReadinessError("Accepted manifest row count does not match the expected count.")

    receipts = _load_receipts(receipt_paths)
    if len(receipts) != expected_count:
        raise CorpusReadinessError("Acquisition receipt count does not match the expected count.")

    items: list[CorpusReadinessItem] = []
    seen_source_ids: set[str] = set()
    seen_pmids: set[str] = set()
    seen_pmcids: set[str] = set()
    seen_filenames: set[str] = set()
    matched_receipt_keys: set[tuple[str, str]] = set()

    for row in rows:
        source_id = _required(row, "source_id", label="Manifest row")
        pmid = _required(row, "pmid", label="Manifest row")
        pmcid = _required(row, "other_identifier", label="Manifest row")
        filename = _safe_filename(_required(row, "local_path", label="Manifest row"))
        license_type = _required(row, "license_type", label="Manifest row")
        usage_status = _required(row, "usage_status", label="Manifest row")
        inclusion_status = _required(row, "inclusion_status", label="Manifest row")

        if inclusion_status != "included":
            raise CorpusReadinessError("Manifest contains a non-included row.")
        if usage_status not in APPROVED_USAGE_STATUSES:
            raise CorpusReadinessError("Manifest contains a row without approved usage status.")
        if not license_type:
            raise CorpusReadinessError("Manifest contains a row without an explicit license.")
        _add_unique(seen_source_ids, source_id, label="source_id")
        _add_unique(seen_pmids, pmid, label="PMID")
        _add_unique(seen_pmcids, pmcid, label="PMCID")
        _add_unique(seen_filenames, filename, label="filename")

        receipt = receipts.get((pmid, pmcid))
        if receipt is None:
            raise CorpusReadinessError("Manifest row has no matching acquisition receipt.")
        if receipt["filename"] != filename:
            raise CorpusReadinessError("Manifest filename does not match the acquisition receipt.")
        matched_receipt_keys.add((pmid, pmcid))

        file_path = papers_directory / filename
        _reject_symlink(file_path, label="Corpus PDF")
        body = _read_bytes(file_path, label="Corpus PDF")
        sha256 = hashlib.sha256(body).hexdigest()
        if len(body) != receipt["byte_count"]:
            raise CorpusReadinessError(
                "Corpus PDF byte count does not match the acquisition receipt."
            )
        if sha256 != receipt["sha256"]:
            raise CorpusReadinessError("Corpus PDF hash does not match the acquisition receipt.")
        items.append(
            CorpusReadinessItem(
                source_id=source_id,
                pmid=pmid,
                pmcid=pmcid,
                filename=filename,
                byte_count=len(body),
                sha256=sha256,
            )
        )

    if matched_receipt_keys != set(receipts):
        raise CorpusReadinessError(
            "Acquisition receipts contain entries not present in the manifest."
        )

    actual_files = {
        path.name
        for path in papers_directory.iterdir()
        if path.is_file() and path.suffix.casefold() == ".pdf"
    }
    if actual_files != seen_filenames:
        raise CorpusReadinessError("Papers directory contains missing or unexpected PDF files.")

    ordered = tuple(sorted(items, key=lambda item: item.source_id))
    return CorpusReadinessReport(
        schema_version=1,
        ready=True,
        expected_count=expected_count,
        accepted_count=len(rows),
        receipt_count=len(receipts),
        file_count=len(actual_files),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        items=ordered,
    )


def _load_manifest(manifest_bytes: bytes) -> list[dict[str, str]]:
    try:
        text = manifest_bytes.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise CorpusReadinessError("Manifest is missing required columns.")
        rows = [dict(row) for row in reader]
    except UnicodeDecodeError as exc:
        raise CorpusReadinessError("Manifest is not valid UTF-8 CSV.") from exc
    return rows


def _load_receipts(receipt_paths: tuple[Path, ...]) -> dict[tuple[str, str], dict[str, object]]:
    if not receipt_paths:
        raise CorpusReadinessError("At least one acquisition receipt is required.")
    receipts: dict[tuple[str, str], dict[str, object]] = {}
    filenames: set[str] = set()
    for path in receipt_paths:
        _reject_symlink(path, label="Acquisition receipt")
        try:
            payload = json.loads(_read_bytes(path, label="Acquisition receipt").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorpusReadinessError("Acquisition receipt is not valid JSON.") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise CorpusReadinessError("Acquisition receipt schema_version must be 1.")
        items = payload.get("items")
        if not isinstance(items, list):
            raise CorpusReadinessError("Acquisition receipt is missing items.")
        if payload.get("acquired_count") != len(items):
            raise CorpusReadinessError("Acquisition receipt count does not reconcile.")
        for item in items:
            if not isinstance(item, dict):
                raise CorpusReadinessError("Acquisition receipt contains a malformed item.")
            pmid = _json_string(item, "pmid")
            pmcid = _json_string(item, "pmcid")
            filename = _safe_filename(_json_string(item, "filename"))
            sha256 = _json_string(item, "sha256")
            byte_count = item.get("byte_count")
            if not isinstance(byte_count, int) or byte_count < 1:
                raise CorpusReadinessError("Acquisition receipt has an invalid byte count.")
            if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
                raise CorpusReadinessError("Acquisition receipt has an invalid SHA-256 value.")
            key = (pmid, pmcid)
            if key in receipts:
                raise CorpusReadinessError("Acquisition receipts contain a duplicate identifier.")
            _add_unique(filenames, filename, label="receipt filename")
            receipts[key] = {
                "filename": filename,
                "byte_count": byte_count,
                "sha256": sha256,
            }
    return receipts


def _safe_filename(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 1 or path.name in {"", ".", ".."}:
        raise CorpusReadinessError("Manifest or receipt contains an unsafe local path.")
    if path.suffix.casefold() != ".pdf":
        raise CorpusReadinessError("Manifest or receipt local path must name a PDF.")
    return path.name


def _required(row: dict[str, str], key: str, *, label: str) -> str:
    value = row.get(key, "").strip()
    if not value:
        raise CorpusReadinessError(f"{label} is missing required evidence.")
    return value


def _json_string(item: dict[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise CorpusReadinessError("Acquisition receipt item is missing required evidence.")
    return value


def _add_unique(values: set[str], value: str, *, label: str) -> None:
    if value in values:
        raise CorpusReadinessError(f"Corpus contains a duplicate {label}.")
    values.add(value)


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise CorpusReadinessError(f"{label} must not be a symbolic link.")


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CorpusReadinessError(f"{label} could not be read.") from exc
