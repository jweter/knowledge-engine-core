"""Validated export from Europe PMC adjudication to acquisition approvals.

Mirrors `reviewed_approval.py`'s "select exactly N accepted records, in
worksheet order, with every required rule re-verified" contract for M34's
Europe PMC pipeline, but is a deliberately separate module rather than a
retrofit of that one: `europepmc_candidate_review.py`'s worksheet schema
uses different identity (Europe PMC ID, DOI-anchored, no PMCID
requirement), a different accepted PDF host (`europepmc.org`, not PMC's S3
bucket), and different rule-result field names
(`reported_license`/`pmc_overlap_rule_result`/etc.) than M14's worksheet.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from knowledge_engine.europepmc_http import EUROPEPMC_PDF_HOST

SAFE_EUROPEPMC_ID = re.compile(r"^[A-Za-z0-9]+$")
WORKSHEET_ORDER_SELECTION_RULE = "accepted_in_worksheet_order"


class EuropePmcReviewedApprovalError(RuntimeError):
    """Sanitized adjudicated-approval export failure."""


@dataclass(frozen=True)
class EuropePmcReviewedApproval:
    """One acquisition approval backed by deterministic Europe PMC evidence."""

    europepmc_id: str
    doi: str
    license: str
    pdf_url: str
    filename: str


@dataclass(frozen=True)
class EuropePmcReviewedApprovalBatch:
    """Acquisition-compatible approvals plus deterministic selection evidence."""

    schema_version: int
    rules_version: str
    selection_rule: str
    source_candidate_count: int
    source_accepted_count: int
    selected_count: int
    approvals: tuple[EuropePmcReviewedApproval, ...]

    def to_json(self) -> str:
        """Render deterministic acquisition approval JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def export_europepmc_reviewed_approvals(
    worksheet_path: Path,
    *,
    selection_limit: int | None = None,
) -> EuropePmcReviewedApprovalBatch:
    """Validate accepted adjudications and select them in immutable worksheet order."""

    if selection_limit is not None and selection_limit < 1:
        raise EuropePmcReviewedApprovalError("Approval selection limit must be at least 1.")

    payload = _load_object(worksheet_path)
    if payload.get("schema_version") != 1:
        raise EuropePmcReviewedApprovalError("Adjudication worksheet schema_version must be 1.")
    worksheet_rules_version = _required_string(payload, "rules_version")
    rows = payload.get("items")
    candidate_count = payload.get("candidate_count")
    if (
        not isinstance(rows, list)
        or not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or candidate_count != len(rows)
    ):
        raise EuropePmcReviewedApprovalError("Adjudication worksheet count does not reconcile.")

    approvals: list[EuropePmcReviewedApproval] = []
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise EuropePmcReviewedApprovalError(
                "Adjudication worksheet contains a malformed item."
            )
        decision = _required_string(row, "decision").casefold()
        if decision in {"rejected", "held"}:
            continue
        if decision != "accepted":
            raise EuropePmcReviewedApprovalError(
                "Adjudication worksheet contains an unsupported decision."
            )

        if _required_string(row, "rules_version") != worksheet_rules_version:
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication rules_version does not reconcile."
            )
        _adjudicated_timestamp(row)
        _required_string_list(row, "reason_codes")
        _required_string_list(row, "evidence_provenance")
        ambiguities = row.get("unresolved_ambiguities")
        if ambiguities != []:
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication contains unresolved ambiguity."
            )
        for field in (
            "inclusion_rule_result",
            "identity_rule_result",
            "license_rule_result",
            "full_text_rule_result",
            "pmc_overlap_rule_result",
        ):
            if _required_string(row, field) != "passed":
                raise EuropePmcReviewedApprovalError(
                    "Accepted adjudication contains a non-passing rule."
                )
        if _required_string(row, "duplicate_rule_result") != "passed_exact_identifier_uniqueness":
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication duplicate evidence did not pass."
            )

        europepmc_id = _required_string(row, "europepmc_id")
        doi = _required_string(row, "doi")
        license_name = _required_string(row, "reported_license")
        pdf_url = _required_string(row, "pdf_url")
        if row.get("open_access") is not True:
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication lacks verified open-access evidence."
            )
        if row.get("in_pmc") is not False:
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication is not out of PMC's own pipeline scope."
            )
        if not SAFE_EUROPEPMC_ID.fullmatch(europepmc_id):
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication contains an invalid Europe PMC id."
            )
        parsed = urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != EUROPEPMC_PDF_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudication contains an unsupported PDF URL."
            )
        if europepmc_id in seen_ids or doi in seen_dois:
            raise EuropePmcReviewedApprovalError(
                "Accepted adjudications contain duplicate identifiers."
            )
        seen_ids.add(europepmc_id)
        seen_dois.add(doi)
        approvals.append(
            EuropePmcReviewedApproval(
                europepmc_id=europepmc_id,
                doi=doi,
                license=license_name,
                pdf_url=pdf_url,
                filename=f"europepmc-{europepmc_id}.pdf",
            )
        )

    if not approvals:
        raise EuropePmcReviewedApprovalError(
            "Adjudication worksheet contains no accepted approvals."
        )
    if selection_limit is not None and len(approvals) < selection_limit:
        raise EuropePmcReviewedApprovalError(
            "Adjudication worksheet contains fewer accepted approvals than the selection limit."
        )

    selected = approvals if selection_limit is None else approvals[:selection_limit]
    return EuropePmcReviewedApprovalBatch(
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
        raise EuropePmcReviewedApprovalError("Adjudication worksheet must not be a symbolic link.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EuropePmcReviewedApprovalError(
            "Adjudication worksheet could not be read as JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise EuropePmcReviewedApprovalError("Adjudication worksheet must be a JSON object.")
    return payload


def _required_string(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise EuropePmcReviewedApprovalError("Accepted adjudication is missing required evidence.")
    return value.strip()


def _required_string_list(row: dict[str, object], field: str) -> tuple[str, ...]:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise EuropePmcReviewedApprovalError("Accepted adjudication is missing required evidence.")
    return tuple(item.strip() for item in value)


def _adjudicated_timestamp(row: dict[str, object]) -> datetime:
    value = _required_string(row, "adjudicated_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EuropePmcReviewedApprovalError(
            "Accepted adjudication has an invalid timestamp."
        ) from exc
    if parsed.tzinfo is None:
        raise EuropePmcReviewedApprovalError(
            "Accepted adjudication timestamp must include a timezone."
        )
    return parsed
