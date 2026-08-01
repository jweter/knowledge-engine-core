"""Durable rejected-PMID ledger (M53).

`sources.csv` only records what a corpus currently *includes*, not a
durable record of every PMID this project has already discovered and
manually rejected for topical-relevance reasons (off-target primary
disease, diagnostic/measurement-only, no intervention named, and so on --
see `data/corpora/glp1_weight_loss/README.md`'s exclusion-pattern
history). That gap has caused the same real failure mode twice
(documented in `docs/roadmap.md`): a previously-rejected PMID resurfacing
under a later discovery batch's different `retstart` offset, caught only
by manually re-reading README prose history each time -- a process that
does not survive an unattended, continuously-running discovery pipeline.

This module is the structured, durable fix: a per-corpus CSV ledger of
`(pmid, reason_category, batch_label, ...)` rows, plus a check that
splits a fresh discovery batch's candidates into net-new versus
already-rejected *before* a human or agent spends any review time on
them. It never re-decides a rejection itself -- exactly like
`ke evidence-validate`/`ke relationship-validate` elsewhere in this
project, it validates and persists a decision a reviewer already made.

Historical exclusions predating this module (recorded only as prose in
`README.md`, with no PMID captured at the time) are not, and cannot
safely be, backfilled here: reconstructing exact PMIDs from vague title
descriptions would risk silently mismatching a ledger whose entire value
is precision. The ledger starts capturing rejections from this point
forward; that gap is a known, accepted limitation, not a defect in this
module.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REJECTED_LEDGER_RULES_VERSION = "m53-rejected-candidates-v1"

REJECTED_REASON_CATEGORIES = frozenset(
    {
        "off_target_primary_disease",
        "diagnostic_or_measurement_only",
        "no_intervention_named",
        "policy_or_prediction_model_only",
        "type1_diabetes_specific",
        "mechanism_only_primary_research",
        "duplicate_or_already_included",
        "other",
    }
)

_LEDGER_FIELDNAMES = [
    "pmid",
    "doi",
    "title",
    "reason_category",
    "batch_label",
    "rejected_date",
    "notes",
]


class RejectedCandidatesError(RuntimeError):
    """Sanitized rejected-ledger failure."""


@dataclass(frozen=True)
class RejectedCandidate:
    """One durable rejection record."""

    pmid: str
    doi: str | None
    title: str
    reason_category: str
    batch_label: str
    rejected_date: str
    notes: str


def load_rejected_ledger(path: Path) -> dict[str, RejectedCandidate]:
    """Load the ledger, keyed by `pmid`. Returns `{}` if the file doesn't exist yet."""

    if not path.exists():
        return {}
    ledger: dict[str, RejectedCandidate] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            pmid = (row.get("pmid") or "").strip()
            if not pmid:
                continue
            ledger[pmid] = RejectedCandidate(
                pmid=pmid,
                doi=(row.get("doi") or "").strip() or None,
                title=row.get("title") or "",
                reason_category=row.get("reason_category") or "",
                batch_label=row.get("batch_label") or "",
                rejected_date=row.get("rejected_date") or "",
                notes=row.get("notes") or "",
            )
    return ledger


def parse_rejected_candidate(record: Mapping[str, Any]) -> RejectedCandidate:
    """Build a `RejectedCandidate` from one bulk-input JSON object.

    `rejected_date` defaults to today (UTC) when omitted. Raises
    `RejectedCandidatesError` for a missing `pmid`/`title`/`batch_label`
    or an unrecognized `reason_category` -- never silently accepts an
    incomplete or miscategorized rejection.
    """

    pmid = str(record.get("pmid") or "").strip()
    title = str(record.get("title") or "").strip()
    reason_category = str(record.get("reason_category") or "").strip()
    batch_label = str(record.get("batch_label") or "").strip()
    if not pmid:
        raise RejectedCandidatesError("Rejection record is missing pmid.")
    if not title:
        raise RejectedCandidatesError(f"Rejection record for pmid {pmid} is missing title.")
    if not batch_label:
        raise RejectedCandidatesError(f"Rejection record for pmid {pmid} is missing batch_label.")
    if reason_category not in REJECTED_REASON_CATEGORIES:
        allowed = ", ".join(sorted(REJECTED_REASON_CATEGORIES))
        raise RejectedCandidatesError(
            f"Rejection record for pmid {pmid} has unknown reason_category "
            f"'{reason_category}'. Allowed: {allowed}."
        )

    doi = record.get("doi")
    rejected_date = str(record.get("rejected_date") or "").strip()
    if not rejected_date:
        rejected_date = datetime.now(UTC).date().isoformat()

    return RejectedCandidate(
        pmid=pmid,
        doi=str(doi).strip() if isinstance(doi, str) and doi.strip() else None,
        title=title,
        reason_category=reason_category,
        batch_label=batch_label,
        rejected_date=rejected_date,
        notes=str(record.get("notes") or "").strip(),
    )


def append_rejected_candidates(
    path: Path, new_records: Sequence[RejectedCandidate]
) -> tuple[list[RejectedCandidate], list[str]]:
    """Append `new_records` to the ledger, skipping any `pmid` already present.

    Returns `(appended, skipped_duplicate_pmids)`. Never overwrites an
    existing pmid's row -- the first recorded rejection reason wins for
    that pmid; append a fresh row by hand (or via `notes`) if a later
    batch found a different, additional reason.
    """

    existing = load_rejected_ledger(path)
    to_append: list[RejectedCandidate] = []
    skipped: list[str] = []
    seen_in_batch: set[str] = set()
    for record in new_records:
        if record.pmid in existing or record.pmid in seen_in_batch:
            skipped.append(record.pmid)
            continue
        seen_in_batch.add(record.pmid)
        to_append.append(record)

    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_LEDGER_FIELDNAMES)
        if write_header:
            writer.writeheader()
        for record in to_append:
            writer.writerow(asdict(record))
    return to_append, skipped


def extract_candidates(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Pull a candidate list out of either a discovery JSON or an adjudication worksheet.

    Discovery output (`ke pubmed-candidate-discover` and siblings) nests
    candidates under `"candidates"`; `ke candidate-review-cli prepare`'s
    adjudication worksheet nests them under `"items"`. Both shapes carry a
    `pmid` field per entry, which is all this module needs.
    """

    for key in ("candidates", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def check_candidates_against_ledger(
    candidates: Sequence[Mapping[str, Any]], ledger: Mapping[str, RejectedCandidate]
) -> tuple[list[Mapping[str, Any]], list[RejectedCandidate]]:
    """Split `candidates` into `(net_new, already_rejected)` by exact `pmid` match."""

    net_new: list[Mapping[str, Any]] = []
    already_rejected: list[RejectedCandidate] = []
    for candidate in candidates:
        pmid = str(candidate.get("pmid") or "").strip()
        if pmid and pmid in ledger:
            already_rejected.append(ledger[pmid])
        else:
            net_new.append(candidate)
    return net_new, already_rejected
