"""Validated export from completed candidate reviews to acquisition approvals."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

PDF_HOST = "ftp.ncbi.nlm.nih.gov"
SAFE_PMCID = re.compile(r"^PMC[0-9]+$")


class ReviewedApprovalError(RuntimeError):
    """Sanitized reviewed-approval export failure."""


@dataclass(frozen=True)
class ReviewedApproval:
    """One acquisition approval backed by completed human review."""

    pmid: str
    pmcid: str
    license: str
    pdf_url: str
    filename: str


@dataclass(frozen=True)
class ReviewedApprovalBatch:
    """Exact schema consumed by PMC OA acquisition."""

    schema_version: int
    approvals: tuple[ReviewedApproval, ...]

    def to_json(self) -> str:
        """Render deterministic acquisition approval JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def export_reviewed_approvals(worksheet_path: Path) -> ReviewedApprovalBatch:
    """Export accepted, fully reviewed OA records without making decisions."""

    payload = _load_object(worksheet_path)
    if payload.get("schema_version") != 1:
        raise ReviewedApprovalError("Review worksheet schema_version must be 1.")
    rows = payload.get("items")
    if not isinstance(rows, list) or payload.get("candidate_count") != len(rows):
        raise ReviewedApprovalError("Review worksheet count does not reconcile.")

    approvals: list[ReviewedApproval] = []
    seen_pmids: set[str] = set()
    seen_pmcids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewedApprovalError("Review worksheet contains a malformed item.")
        decision = _required_string(row, "decision").casefold()
        if decision == "rejected":
            continue
        if decision != "accepted":
            raise ReviewedApprovalError("Review worksheet contains an unresolved decision.")

        for field in ("inclusion_review", "identity_review", "license_review", "reviewer"):
            _required_string(row, field)
        _reviewed_timestamp(row)

        pmid = _required_string(row, "pmid")
        pmcid = _required_string(row, "pmcid")
        license_name = _required_string(row, "reported_license")
        pdf_url = _required_string(row, "pdf_url")
        status = _required_string(row, "discovery_status")
        if row.get("open_access") is not True or status != "oa_verified":
            raise ReviewedApprovalError("Accepted review lacks verified PMC OA evidence.")
        if not SAFE_PMCID.fullmatch(pmcid):
            raise ReviewedApprovalError("Accepted review contains an invalid PMCID.")
        parsed = urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != PDF_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ReviewedApprovalError("Accepted review contains an unsupported PDF URL.")
        if pmid in seen_pmids or pmcid in seen_pmcids:
            raise ReviewedApprovalError("Accepted reviews contain duplicate identifiers.")
        seen_pmids.add(pmid)
        seen_pmcids.add(pmcid)
        approvals.append(
            ReviewedApproval(
                pmid=pmid,
                pmcid=pmcid,
                license=license_name,
                pdf_url=pdf_url,
                filename=f"{pmcid}.pdf",
            )
        )

    if not approvals:
        raise ReviewedApprovalError("Review worksheet contains no accepted approvals.")
    return ReviewedApprovalBatch(schema_version=1, approvals=tuple(approvals))


def _load_object(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ReviewedApprovalError("Review worksheet must not be a symbolic link.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewedApprovalError("Review worksheet could not be read as JSON.") from exc
    if not isinstance(payload, dict):
        raise ReviewedApprovalError("Review worksheet must be a JSON object.")
    return payload


def _required_string(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReviewedApprovalError("Accepted review is missing required evidence.")
    return value.strip()


def _reviewed_timestamp(row: dict[str, object]) -> datetime:
    value = _required_string(row, "reviewed_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewedApprovalError("Accepted review has an invalid review timestamp.") from exc
    if parsed.tzinfo is None:
        raise ReviewedApprovalError("Accepted review timestamp must include a timezone.")
    return parsed
