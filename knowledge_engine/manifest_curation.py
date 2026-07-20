"""Reconcile automated adjudications and acquisition receipts into manifest drafts."""

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
    """Manifest-shaped rows produced from accepted automated evidence."""

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
    """Reconcile accepted adjudications with acquired-file evidence."""

    worksheet = _load_object(worksheet_path, "Adjudication worksheet")
    receipt = _load_object(receipt_path, "Acquisition receipt")
    if worksheet.get("schema_version") != 2 or receipt.get("schema_version") != 1:
        raise ManifestCurationError("Input schema_version does not match the supported contract.")
    worksheet_rules_version = _required(worksheet, "rules_version")
    adjudication_rows = worksheet.get("items")
    receipt_rows = receipt.get("items")
    if not isinstance(adjudication_rows, list) or worksheet.get("candidate_count") != len(
        adjudication_rows
    ):
        raise ManifestCurationError("Adjudication worksheet count does not reconcile.")
    if not isinstance(receipt_rows, list) or receipt.get("acquired_count") != len(receipt_rows):
        raise ManifestCurationError("Acquisition receipt count does not reconcile.")

    accepted: dict[str, dict[str, object]] = {}
    for row in adjudication_rows:
        if not isinstance(row, dict):
            raise ManifestCurationError("Adjudication worksheet contains a malformed item.")
        decision = _required(row, "decision").casefold()
        if decision in {"rejected", "held"}:
            continue
        if decision != "accepted":
            raise ManifestCurationError("Adjudication worksheet contains an unsupported decision.")
        if _required(row, "rules_version") != worksheet_rules_version:
            raise ManifestCurationError("Accepted adjudication rules_version does not reconcile.")
        if row.get("unresolved_ambiguities") != []:
            raise ManifestCurationError("Accepted adjudication contains unresolved ambiguity.")
        for field in (
            "inclusion_rule_result",
            "identity_rule_result",
            "license_rule_result",
            "full_text_rule_result",
        ):
            if _required(row, field) != "passed":
                raise ManifestCurationError("Accepted adjudication contains a non-passing rule.")
        if _required(row, "duplicate_rule_result") != "passed_exact_identifier_uniqueness":
            raise ManifestCurationError("Accepted adjudication duplicate evidence did not pass.")
        _required_list(row, "reason_codes")
        _required_list(row, "evidence_provenance")
        _required(row, "adjudicated_at")
        pmid = _required(row, "pmid")
        if pmid in accepted:
            raise ManifestCurationError(
                "Adjudication worksheet contains a duplicate accepted PMID."
            )
        accepted[pmid] = row

    if len(accepted) != len(receipt_rows):
        raise ManifestCurationError("Accepted adjudication and receipt counts do not reconcile.")

    rows: list[dict[str, str]] = []
    seen_pmcids: set[str] = set()
    for item in receipt_rows:
        if not isinstance(item, dict):
            raise ManifestCurationError("Acquisition receipt contains a malformed item.")
        pmid = _required(item, "pmid")
        adjudication = accepted.get(pmid)
        if adjudication is None:
            raise ManifestCurationError(
                "Receipt references a PMID without an accepted adjudication."
            )
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
            _required(adjudication, "pmcid") != pmcid
            or _required(adjudication, "reported_license") != license_name
            or not _required(adjudication, "pdf_url")
        ):
            raise ManifestCurationError(
                "Adjudicated evidence does not match the acquisition receipt."
            )
        if (
            adjudication.get("open_access") is not True
            or _required(adjudication, "discovery_status") != "oa_verified"
        ):
            raise ManifestCurationError("Accepted adjudication lacks verified PMC OA evidence.")
        reason_codes = _required_list(adjudication, "reason_codes")
        row = {field: "" for field in MANIFEST_FIELDS}
        row.update(
            {
                "source_id": f"pmc-{pmcid.removeprefix('PMC')}",
                "title": _required(adjudication, "title"),
                "authors": _authors(adjudication),
                "publication_year": _publication_year(adjudication),
                "venue": _optional(adjudication, "venue"),
                "doi": _optional(adjudication, "doi"),
                "pmid": pmid,
                "other_identifier": pmcid,
                "source_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                "pdf_url": _required(adjudication, "pdf_url"),
                "local_path": filename,
                "license_type": license_name,
                "usage_status": "approved_open_access",
                "inclusion_status": "included",
                "inclusion_reason": ";".join(reason_codes),
                "expected_content_hash": sha256,
                "source_type": "paper",
                "notes": f"Automated adjudication ruleset: {worksheet_rules_version}",
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


def _required_list(row: dict[str, object], field: str) -> tuple[str, ...]:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ManifestCurationError("Input evidence is incomplete.")
    return tuple(item.strip() for item in value)


def _optional(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    return value.strip() if isinstance(value, str) else ""


def _authors(row: dict[str, object]) -> str:
    value = row.get("authors", [])
    if not isinstance(value, list) or not all(
        isinstance(author, str) and author.strip() for author in value
    ):
        raise ManifestCurationError("Author evidence is malformed.")
    return "; ".join(author.strip() for author in value)


def _publication_year(row: dict[str, object]) -> str:
    value = row.get("publication_year")
    if value is None:
        return ""
    if not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 9999:
        raise ManifestCurationError("Publication-year evidence is malformed.")
    return str(value)
