"""Validated export from deterministic adjudication to acquisition approvals."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

PDF_HOST = "ftp.ncbi.nlm.nih.gov"
SAFE_PMCID = re.compile(r"^PMC[0-9]+$")
WORKSHEET_ORDER_SELECTION_RULE = "accepted_in_worksheet_order"


class ReviewedApprovalError(RuntimeError):
    """Sanitized adjudicated-approval export failure."""


@dataclass(frozen=True)
class ReviewedApproval:
    """One acquisition approval backed by deterministic evidence."""

    pmid: str
    pmcid: str
    license: str
    pdf_url: str
    filename: str


@dataclass(frozen=True)
class ReviewedApprovalBatch:
    """Acquisition-compatible approvals plus deterministic selection evidence."""

    schema_version: int
    rules_version: str
    selection_rule: str
    source_candidate_count: int
    source_accepted_count: int
    selected_count: int
    approvals: tuple[ReviewedApproval, ...]

    def to_json(self) -> str:
        """Render deterministic acquisition approval JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def export_reviewed_approvals(
    worksheet_path: Path,
    *,
    selection_limit: int | None = None,
) -> ReviewedApprovalBatch:
    """Validate accepted adjudications and select them in immutable worksheet order."""

    if selection_limit is not None and selection_limit < 1:
        raise ReviewedApprovalError("Approval selection limit must be at least 1.")

    payload = _load_object(worksheet_path)
    if payload.get("schema_version") != 2:
        raise ReviewedApprovalError("Adjudication worksheet schema_version must be 2.")
    worksheet_rules_version = _required_string(payload, "rules_version")
    rows = payload.get("items")
    candidate_count = payload.get("candidate_count")
    if (
        not isinstance(rows, list)
        or not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or candidate_count != len(rows)
    ):
        raise ReviewedApprovalError("Adjudication worksheet count does not reconcile.")

    approvals: list[ReviewedApproval] = []
    seen_pmids: set[str] = set()
    seen_pmcids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ReviewedApprovalError("Adjudication worksheet contains a malformed item.")
        decision = _required_string(row, "decision").casefold()
        if decision in {"rejected", "held"}:
            continue
        if decision != "accepted":
            raise ReviewedApprovalError("Adjudication worksheet contains an unsupported decision.")

        if _required_string(row, "rules_version") != worksheet_rules_version:
            raise ReviewedApprovalError("Accepted adjudication rules_version does not reconcile.")
        _adjudicated_timestamp(row)
        _required_string_list(row, "reason_codes")
        _required_string_list(row, "evidence_provenance")
        ambiguities = row.get("unresolved_ambiguities")
        if ambiguities != []:
            raise ReviewedApprovalError("Accepted adjudication contains unresolved ambiguity.")
        for field in (
            "inclusion_rule_result",
            "identity_rule_result",
            "license_rule_result",
            "full_text_rule_result",
        ):
            if _required_string(row, field) != "passed":
                raise ReviewedApprovalError("Accepted adjudication contains a non-passing rule.")
        if _required_string(row, "duplicate_rule_result") != "passed_exact_identifier_uniqueness":
            raise ReviewedApprovalError("Accepted adjudication duplicate evidence did not pass.")

        pmid = _required_string(row, "pmid")
        pmcid = _required_string(row, "pmcid")
        license_name = _required_string(row, "reported_license")
        pdf_url = _required_string(row, "pdf_url")
        status = _required_string(row, "discovery_status")
        if row.get("open_access") is not True or status != "oa_verified":
            raise ReviewedApprovalError("Accepted adjudication lacks verified PMC OA evidence.")
        if not SAFE_PMCID.fullmatch(pmcid):
            raise ReviewedApprovalError("Accepted adjudication contains an invalid PMCID.")
        parsed = urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != PDF_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or not parsed.path.lower().endswith(".pdf")
        ):
            raise ReviewedApprovalError("Accepted adjudication contains an unsupported PDF URL.")
        if pmid in seen_pmids or pmcid in seen_pmcids:
            raise ReviewedApprovalError("Accepted adjudications contain duplicate identifiers.")
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
        raise ReviewedApprovalError("Adjudication worksheet contains no accepted approvals.")
    if selection_limit is not None and len(approvals) < selection_limit:
        raise ReviewedApprovalError(
            "Adjudication worksheet contains fewer accepted approvals than the selection limit."
        )

    selected = approvals if selection_limit is None else approvals[:selection_limit]
    return ReviewedApprovalBatch(
        schema_version=1,
        rules_version=worksheet_rules_version,
        selection_rule=WORKSHEET_ORDER_SELECTION_RULE,
        source_candidate_count=candidate_count,
        source_accepted_count=len(approvals),
        selected_count=len(selected),
        approvals=tuple(selected),
    )


def _load_object(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ReviewedApprovalError("Adjudication worksheet must not be a symbolic link.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewedApprovalError("Adjudication worksheet could not be read as JSON.") from exc
    if not isinstance(payload, dict):
        raise ReviewedApprovalError("Adjudication worksheet must be a JSON object.")
    return payload


def _required_string(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReviewedApprovalError("Accepted adjudication is missing required evidence.")
    return value.strip()


def _required_string_list(row: dict[str, object], field: str) -> tuple[str, ...]:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ReviewedApprovalError("Accepted adjudication is missing required evidence.")
    return tuple(item.strip() for item in value)


def _adjudicated_timestamp(row: dict[str, object]) -> datetime:
    value = _required_string(row, "adjudicated_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewedApprovalError("Accepted adjudication has an invalid timestamp.") from exc
    if parsed.tzinfo is None:
        raise ReviewedApprovalError("Accepted adjudication timestamp must include a timezone.")
    return parsed
