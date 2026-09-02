"""CORE-GQR-5: bridge GQR-acquired papers into validated, promoted Evidence Records.

GQR-4 (`general_question_acquisition_failures.py` and friends) turns a
persisted federated-discovery lead into a durably persisted `Paper` row, but
that Paper's text remains non-Evidence-Record material until it has been
extracted, verified against its own source text, and validated against the
Evidence Record schema. This module is that bridge: given one of the four
GQR acquisition routes' persistence receipts (PMC, Europe PMC, CORE,
Unpaywall -- all four share the same `search_run_id`/`research_question_id`/
`items[].paper_id`/`items[].persistence_status` shape), it re-derives the
receipt's paper IDs, runs the existing deterministic extraction pipeline
(`extraction_review_batch.run_batch_extraction_review`, M17-M28) plus the
existing deterministic autoclassifier
(`knowledge_engine.extraction.build_automated_evidence_record`, M52) against
each paper's persisted pages, and reuses `knowledge_engine.cli`'s own
`_promote_evidence_records` -- the exact validator `ke evidence-validate` and
`ke extraction-review-promote` already use -- as the sole schema-validation
and append gate. Nothing here duplicates that validation logic.

Grounding is structural, not a separate LLM call: M17's claim-candidate
detection sets `claim_text`/`result_summary` to a verbatim sentence drawn
directly from the paper's own persisted pages
(`knowledge_engine.extraction.evidence_items.build_draft_evidence_items`), so
a deterministically autoclassified record cannot describe text the source
paper does not contain. `ke evidence-review-automate`'s separate
LLM-grounded PICO refinement (M69, requires a local Ollama model) is not
invoked here; a record this module promotes keeps its autoclassified
`review_status="draft"` until that follow-up step -- or a human -- reviews
it, exactly like any other `ke extraction-review-autoclassify` output.

Every paper or candidate record that does not reach promotion gets a
sanitized, durable rejection reason recorded next to the receipt (mirroring
`general_question_acquisition_failures.py`'s failure-record pattern), never
only a console line -- "keep failures independently inspectable" applies to
this stage exactly as it did to GQR-4's acquisition stage.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

import knowledge_engine.cli as cli
from knowledge_engine.database import PaperRepository
from knowledge_engine.extraction import build_automated_evidence_record
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_batch import run_batch_extraction_review
from knowledge_engine.import_runs._helpers import utc_now
from knowledge_engine.parser import ParsedPage

GENERAL_QUESTION_EXTRACTION_PROMOTION_RULES_VERSION = "core-gqr-5-extraction-promotion-v1"
EXTRACTION_REJECTION_RECORD_SCHEMA_VERSION = 1

_ELIGIBLE_PERSISTENCE_STATUSES = ("persisted", "reused")


@dataclass(frozen=True)
class GeneralQuestionExtractionRejection:
    """One paper or candidate record that did not reach promotion, and why.

    ``stage`` is one of ``paper_not_found`` (receipt named a paper ID with no
    matching persisted row), ``no_parsed_pages``, ``no_claim_candidates``
    (M17 found nothing to extract), ``autoclassify_declined`` (M52 could not
    derive a `research_question` from any candidate's PICO fields), or
    ``promotion_validation_failed`` (the record built but failed
    `ke evidence-validate`'s own schema check).
    """

    paper_id: int
    stage: str
    reason: str


@dataclass(frozen=True)
class GeneralQuestionExtractionPromotionSummary:
    """Outcome of running CORE-GQR-5 against one acquisition receipt.

    The three ``*_duration_ms`` fields answer issue #433's "Grounded
    extraction/promotion" bottleneck-instrumentation ask: ``duration_ms`` is
    this call's total wall-clock time; ``extraction_duration_ms`` covers both
    ``run_batch_extraction_review`` (M17-M28 deterministic extraction) and
    the immediately following ``build_automated_evidence_record`` loop (M52
    autoclassification) -- the two run back to back with no other work
    between them, so timing only the first would silently misattribute
    autoclassification's cost to neither stage; ``promotion_duration_ms``
    covers only the ``_promote_evidence_records`` validation/append call,
    and is ``0`` when no candidate records reached promotion. They are
    additive JSON fields; existing callers that ignore them are unaffected.

    ``evidence_store_record_count`` answers issue #433's "re-retrieval
    readiness" ask: the total number of valid records in
    ``evidence_output_path`` after this call, whether or not this call itself
    promoted anything. Promotion only ever appends, so this count is
    monotonically non-decreasing across repeated calls against the same
    evidence file -- a caller (e.g. the AI orchestration loop, currently
    polling per acquisition receipt) can treat it as a cheap revision
    identifier: if the value has not changed since a prior call, no new
    Evidence Record became available and there is no reason to re-retrieve
    yet, instead of always waiting for an entire maximal acquisition batch.
    """

    schema_version: str
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    paper_count: int
    promoted_count: int
    duplicate_count: int
    rejected: tuple[GeneralQuestionExtractionRejection, ...]
    rejection_record_path: Path | None
    duration_ms: int
    extraction_duration_ms: int
    promotion_duration_ms: int
    evidence_store_record_count: int

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable form, including the ``*_duration_ms`` timings.

        `docs/core_interface_contract.md` warns consumers not to parse
        Rich-formatted console output because it may reflow -- this is the
        supported structured alternative (see the CLI's optional
        ``--output <path.json>``), not the two commands' human-readable
        summary line.
        """

        return {
            "schema_version": self.schema_version,
            "search_run_id": self.search_run_id,
            "research_question_id": self.research_question_id,
            "acquisition_route": self.acquisition_route,
            "paper_count": self.paper_count,
            "promoted_count": self.promoted_count,
            "duplicate_count": self.duplicate_count,
            "rejected": [asdict(rejection) for rejection in self.rejected],
            "rejection_record_path": (
                str(self.rejection_record_path) if self.rejection_record_path is not None else None
            ),
            "duration_ms": self.duration_ms,
            "extraction_duration_ms": self.extraction_duration_ms,
            "promotion_duration_ms": self.promotion_duration_ms,
            "evidence_store_record_count": self.evidence_store_record_count,
        }


def extraction_rejection_record_path(receipt_path: Path) -> Path:
    """Return the durable rejection-record path derived from a receipt path.

    Kept alongside, never inside, the receipt path -- the same convention
    `general_question_acquisition_failures.failure_record_path` already
    established for this same receipt file.
    """

    return receipt_path.with_name(receipt_path.name + ".extraction_rejections.json")


def _write_rejection_records(
    receipt_path: Path,
    *,
    search_run_id: str,
    research_question_id: str,
    acquisition_route: str,
    rejections: list[GeneralQuestionExtractionRejection],
) -> Path | None:
    """Persist sanitized rejection records next to `receipt_path`, or clear a stale file.

    Written via a temporary file plus an atomic `os.replace`, matching
    `general_question_acquisition_failures.write_acquisition_failure_record`'s
    own durability guarantee: a reader never observes a truncated record, and
    a pre-existing symlink at the destination is replaced outright rather
    than followed and written through.
    """

    path = extraction_rejection_record_path(receipt_path)
    if not rejections:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        return None

    payload = {
        "schema_version": EXTRACTION_REJECTION_RECORD_SCHEMA_VERSION,
        "search_run_id": search_run_id,
        "research_question_id": research_question_id,
        "acquisition_route": acquisition_route,
        "occurred_at": utc_now(),
        "rejections": [asdict(rejection) for rejection in rejections],
    }
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)
            raise
    return path


def _count_evidence_records(evidence_output_path: Path) -> int:
    """Count valid Evidence Records currently in `evidence_output_path`.

    Mirrors the same tolerant line-by-line parsing
    `cli._promote_evidence_records` already uses to detect pre-existing
    `evidence_record_id`s: a blank line, invalid JSON, or a non-object line
    is skipped rather than raised, since this is a read-only count, not a
    validation pass -- `ke evidence-validate` remains the sole correctness
    gate. Returns 0 when the file does not exist yet (no record has ever
    been promoted to it).
    """

    if not evidence_output_path.exists():
        return 0
    count = 0
    for line in evidence_output_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and isinstance(record.get("evidence_record_id"), str):
            count += 1
    return count


def _receipt_paper_ids(receipt: dict[str, Any]) -> list[int]:
    items = receipt.get("items")
    if not isinstance(items, list):
        return []
    paper_ids: list[int] = []
    seen: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("persistence_status") not in _ELIGIBLE_PERSISTENCE_STATUSES:
            continue
        paper_id = item.get("paper_id")
        if isinstance(paper_id, int) and paper_id not in seen:
            seen.add(paper_id)
            paper_ids.append(paper_id)
    return paper_ids


def run_general_question_extraction_and_promotion(
    session: Session,
    *,
    receipt_path: Path,
    evidence_output_path: Path,
) -> GeneralQuestionExtractionPromotionSummary:
    """Extract, autoclassify, and promote every paper named in one GQR receipt.

    `receipt_path` is any of the four routes' persistence receipts (they
    share one structural shape -- see module docstring). `evidence_output_path`
    is appended to, never overwritten, exactly like `ke extraction-review-promote`;
    an already-promoted record (same deterministic `evidence_record_id`) is
    skipped as a duplicate rather than re-appended, so re-running this
    command against the same receipt is idempotent.
    """

    run_started = time.monotonic()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    search_run_id = str(receipt.get("search_run_id", ""))
    research_question_id = str(receipt.get("research_question_id", ""))
    acquisition_route = str(receipt.get("acquisition_route", ""))
    paper_ids = _receipt_paper_ids(receipt)

    rejections: list[GeneralQuestionExtractionRejection] = []

    papers = PaperRepository(session).get_many(paper_ids) if paper_ids else []
    found_ids = {paper.id for paper in papers}
    for missing_id in sorted(set(paper_ids) - found_ids):
        rejections.append(
            GeneralQuestionExtractionRejection(
                paper_id=missing_id,
                stage="paper_not_found",
                reason="Receipt named a paper ID with no matching persisted Paper record.",
            )
        )

    paper_pages: list[tuple[PaperMetadata, list[ParsedPage]]] = []
    for paper in sorted(papers, key=lambda paper: paper.id):
        pages = [
            ParsedPage(page_number=page.page_number, text=page.text, table_text=page.table_text)
            for page in paper.pages
        ]
        if not pages:
            rejections.append(
                GeneralQuestionExtractionRejection(
                    paper_id=paper.id,
                    stage="no_parsed_pages",
                    reason="Paper has no persisted pages to extract from.",
                )
            )
            continue
        paper_pages.append(
            (PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title), pages)
        )

    extraction_started = time.monotonic()
    batch_summary = run_batch_extraction_review(paper_pages)

    candidate_records: list[dict[str, Any]] = []
    candidate_paper_ids: list[int] = []
    for result in batch_summary.results:
        if not result.draft_items:
            rejections.append(
                GeneralQuestionExtractionRejection(
                    paper_id=result.paper_id,
                    stage="no_claim_candidates",
                    reason=(
                        "Deterministic extraction found no claim candidates in this paper's text."
                    ),
                )
            )
            continue
        built_any = False
        for draft_item in result.draft_items:
            record = build_automated_evidence_record(draft_item.to_dict())
            if record is None:
                continue
            built_any = True
            candidate_records.append(record)
            candidate_paper_ids.append(result.paper_id)
        if not built_any:
            rejections.append(
                GeneralQuestionExtractionRejection(
                    paper_id=result.paper_id,
                    stage="autoclassify_declined",
                    reason=(
                        "No draft claim candidate had enough PICO signal to "
                        "auto-generate a research_question."
                    ),
                )
            )
    extraction_duration_ms = round((time.monotonic() - extraction_started) * 1000)

    promoted_count = 0
    duplicate_count = 0
    promotion_duration_ms = 0
    if candidate_records:
        descriptor, temp_name = tempfile.mkstemp(prefix="ke-gqr5-drafts-", suffix=".jsonl")
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                for record in candidate_records:
                    handle.write(json.dumps(record) + "\n")
            evidence_output_path.parent.mkdir(parents=True, exist_ok=True)
            promotion_started = time.monotonic()
            promotion_result = cli._promote_evidence_records(temp_path, evidence_output_path)
            promotion_duration_ms = round((time.monotonic() - promotion_started) * 1000)
        finally:
            with contextlib.suppress(OSError):
                temp_path.unlink()

        promoted_count = len(promotion_result.promoted)
        duplicate_count = len(promotion_result.duplicates)
        for line_number, errors in promotion_result.rejected:
            rejections.append(
                GeneralQuestionExtractionRejection(
                    paper_id=candidate_paper_ids[line_number - 1],
                    stage="promotion_validation_failed",
                    reason="; ".join(errors),
                )
            )

    rejection_record_path = _write_rejection_records(
        receipt_path,
        search_run_id=search_run_id,
        research_question_id=research_question_id,
        acquisition_route=acquisition_route,
        rejections=rejections,
    )

    return GeneralQuestionExtractionPromotionSummary(
        schema_version=GENERAL_QUESTION_EXTRACTION_PROMOTION_RULES_VERSION,
        search_run_id=search_run_id,
        research_question_id=research_question_id,
        acquisition_route=acquisition_route,
        paper_count=len(paper_ids),
        promoted_count=promoted_count,
        duplicate_count=duplicate_count,
        rejected=tuple(rejections),
        rejection_record_path=rejection_record_path,
        duration_ms=round((time.monotonic() - run_started) * 1000),
        extraction_duration_ms=extraction_duration_ms,
        promotion_duration_ms=promotion_duration_ms,
        evidence_store_record_count=_count_evidence_records(evidence_output_path),
    )


__all__ = [
    "EXTRACTION_REJECTION_RECORD_SCHEMA_VERSION",
    "GENERAL_QUESTION_EXTRACTION_PROMOTION_RULES_VERSION",
    "GeneralQuestionExtractionPromotionSummary",
    "GeneralQuestionExtractionRejection",
    "extraction_rejection_record_path",
    "run_general_question_extraction_and_promotion",
]
