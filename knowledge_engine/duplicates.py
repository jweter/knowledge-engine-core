"""Deterministic duplicate identity decisions for corpus ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DuplicateOutcome = Literal[
    "none",
    "exact_hash_duplicate",
    "doi_duplicate",
    "doi_hash_conflict",
    "possible_title_year_duplicate",
]
ItemStatus = Literal["importable", "skipped", "needs_review"]


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """Persisted identity evidence for one possible duplicate match."""

    paper_id: int | None = None
    import_item_id: str | None = None
    content_hash: str | None = None
    normalized_doi: str | None = None
    normalized_title: str | None = None
    publication_year: int | None = None


@dataclass(frozen=True, slots=True)
class DuplicateDecision:
    """Auditable result of evaluating duplicate identity evidence."""

    item_status: ItemStatus
    duplicate_outcome: DuplicateOutcome
    matched_paper_id: int | None
    matched_import_item_id: str | None
    reason_code: str


IMPORTABLE = DuplicateDecision(
    item_status="importable",
    duplicate_outcome="none",
    matched_paper_id=None,
    matched_import_item_id=None,
    reason_code="no_duplicate_signal",
)


def decide_duplicate(
    *,
    candidate_content_hash: str | None,
    candidate_normalized_doi: str | None,
    exact_hash_match: DuplicateCandidate | None = None,
    doi_match: DuplicateCandidate | None = None,
    title_year_match: DuplicateCandidate | None = None,
) -> DuplicateDecision:
    """Apply the M10 evidence hierarchy without silently merging uncertainty.

    Exact content identity is authoritative. DOI identity is safe to skip only
    when both candidate and matched content hashes exist and agree. Missing or
    contradictory hash evidence requires review. Title/year evidence is always
    advisory and review-triggering.
    """

    if exact_hash_match is not None:
        return _matched_decision(
            candidate=exact_hash_match,
            item_status="skipped",
            duplicate_outcome="exact_hash_duplicate",
            reason_code="matching_content_hash",
        )

    if doi_match is not None:
        matched_hash = doi_match.content_hash
        if (
            candidate_content_hash is not None
            and matched_hash is not None
            and candidate_content_hash == matched_hash
        ):
            return _matched_decision(
                candidate=doi_match,
                item_status="skipped",
                duplicate_outcome="doi_duplicate",
                reason_code="matching_doi_and_content_hash",
            )

        reason_code = (
            "matching_doi_conflicting_content_hash"
            if candidate_content_hash is not None and matched_hash is not None
            else "matching_doi_without_reconcilable_content_hash"
        )
        return _matched_decision(
            candidate=doi_match,
            item_status="needs_review",
            duplicate_outcome="doi_hash_conflict",
            reason_code=reason_code,
        )

    if title_year_match is not None:
        return _matched_decision(
            candidate=title_year_match,
            item_status="needs_review",
            duplicate_outcome="possible_title_year_duplicate",
            reason_code="matching_normalized_title_and_publication_year",
        )

    del candidate_normalized_doi
    return IMPORTABLE


def _matched_decision(
    *,
    candidate: DuplicateCandidate,
    item_status: ItemStatus,
    duplicate_outcome: DuplicateOutcome,
    reason_code: str,
) -> DuplicateDecision:
    return DuplicateDecision(
        item_status=item_status,
        duplicate_outcome=duplicate_outcome,
        matched_paper_id=candidate.paper_id,
        matched_import_item_id=candidate.import_item_id,
        reason_code=reason_code,
    )
