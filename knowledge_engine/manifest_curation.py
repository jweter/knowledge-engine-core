"""Reconcile reviewed candidates and acquisition receipts into curation drafts."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
MANIFEST_FIELDS = (
    "source_id",
    "title",
    "authors",
    "publication_year",
    "venue",
    "doi",
    "pmid",
    "arxiv_id",
    "other_identifier",
    "source_url",
    "pdf_url",
    "local_path",
    "access_date",
    "license_type",
    "license_url",
    "usage_status",
    "inclusion_status",
    "inclusion_reason",
    "exclusion_reason",
    "expected_content_hash",
    "source_type",
    "study_type",
    "population",
    "intervention",
    "comparator",
    "outcome_notes",
    "notes",
)


class ManifestCurationError(RuntimeError):
    """Sanitized curation-draft reconciliation failure."""


@dataclass(frozen=True)
class ManifestCurationDraft:
    """Manifest-shaped rows that still require explicit scientific curation."""

    rows: tuple[dict[str, str], ...]

    def to_csv(self) -> str:
        """Render deterministic CSV using the production manifest columns."""

        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.rows)
        return stream.getvalue()


def export_manifest_curation_draft(
    worksheet_path: Path,
    receipt_path: Path,
) -> ManifestCurationDraft:
    """Reconcile accepted reviews with acquired-file evidence without inventing metadata."""

    worksheet = _load_object(worksheet_path, "Review worksheet")
    receipt = _load_object(receipt_path, "Acquisition receipt")
    if worksheet.get("schema_version") != 1 or receipt.get("schema_version") != 1:
        raise ManifestCurationError("Input schema_version must be 1.")
    review_rows = worksheet.get("items")
    receipt_rows = receipt.get("items")
    if not isinstance(review_rows, list) or worksheet.get("candidate_count") != len(review_rows):
        raise ManifestCurationError("Review worksheet count does not reconcile.")
    if not isinstance(receipt_rows, list) or receipt.get("acquired_count") != len(receipt_rows):
        raise ManifestCurationError("Acquisition receipt count does not reconcile.")

    accepted: dict[str, dict[str, object]] = {}
    for row in review_rows:
        if not isinstance(row, dict):
            raise ManifestCurationError("Review worksheet contains a malformed item.")
        decision = _required(row, "decision").casefold()
        if decision == "rejected":
            continue
        if decision != "accepted":
            raise ManifestCurationError("Review worksheet contains an unresolved decision.")
        pmid = _required(row, "pmid")
        if pmid in accepted:
            raise ManifestCurationError("Review worksheet contains a duplicate accepted PMID.")
        for field in (
            "inclusion_review",
            "identity_review",
            "license_review",
            "reviewer",
            "reviewed_at",
        ):
            _required(row, field)
        accepted[pmid] = row

    if len(accepted) != len(receipt_rows):
        raise ManifestCurationError("Accepted review and receipt counts do not reconcile.")

    rows: list[dict[str, str]] = []
    seen_pmcids: set[str] = set()
    for item in receipt_rows:
        if not isinstance(item, dict):
            raise ManifestCurationError("Acquisition receipt contains a malformed item.")
        pmid = _required(item, "pmid")
        review = accepted.get(pmid)
        if review is None:
            raise ManifestCurationError("Receipt references a PMID without an accepted review.")
        pmcid = _required(item, "pmcid")
        license_name = _required(item, "license")
        filename = _required(item, "filename")
        sha256 = _required(item, "sha256")
        if not SAFE_FILENAME.fullmatch(filename):
            raise ManifestCurationError("Receipt contains an unsafe PDF filename.")
        if pmcid in seen_pmcids:
            raise ManifestCurationError("Receipt contains a duplicate PMCID.")
        seen_pmcids.add(pmcid)
        if (
            _required(review, "pmcid") != pmcid
            or _required(review, "reported_license") != license_name
            or _required(review, "pdf_url") == ""
        ):
            raise ManifestCurationError("Reviewed evidence does not match the acquisition receipt.")
        if (
            review.get("open_access") is not True
            or _required(review, "discovery_status") != "oa_verified"
        ):
            raise ManifestCurationError("Accepted review lacks verified PMC OA evidence.")
        row = {field: "" for field in MANIFEST_FIELDS}
        row.update(
            {
                "source_id": f"pmc-{pmcid.removeprefix('PMC')}",
                "title": _required(review, "title"),
                "doi": _optional(review, "doi"),
                "pmid": pmid,
                "other_identifier": pmcid,
                "source_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                "pdf_url": _required(review, "pdf_url"),
                "local_path": filename,
                "license_type": license_name,
                "usage_status": "approved_open_access",
                "inclusion_status": "included",
                "inclusion_reason": _required(review, "inclusion_review"),
                "expected_content_hash": sha256,
                "source_type": "paper",
                "notes": "Generated curation draft; authors, year, venue, study type, population, intervention, comparator, outcome notes, access date, and license URL require explicit curation.",
            }
        )
        rows.append(row)

    if not rows:
        raise ManifestCurationError("No reconciled acquired records were available.")
    return ManifestCurationDraft(rows=tuple(rows))


def _load_object(path: Path, label: str) -> dict[str, object]:
    if path.is_symlink():
        raise ManifestCurationError(f"{label} must not be a symbolic link.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestCurationError(f"{label} could not be read as JSON.") from exc
    if not isinstance(value, dict):
        raise ManifestCurationError(f"{label} must be a JSON object.")
    return value


def _required(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestCurationError("Input evidence is incomplete.")
    return value.strip()


def _optional(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    return value.strip() if isinstance(value, str) else ""
