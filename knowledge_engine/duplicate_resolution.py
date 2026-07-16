"""Pre-persistence duplicate evidence resolution for corpus import items."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository
from knowledge_engine.duplicates import DuplicateCandidate, DuplicateDecision, decide_duplicate
from knowledge_engine.models import ImportItem, Paper
from knowledge_engine.parser import ParsedPaper
from knowledge_engine.utils import normalize_doi


def resolve_duplicate_before_persistence(
    session: Session,
    *,
    item: ImportItem,
    parsed: ParsedPaper,
) -> DuplicateDecision:
    """Resolve duplicate evidence and persist only item-level decision metadata.

    This function must run before any paper, paper-text, author, keyword, or FTS
    persistence. It intentionally has no dependency on ``PaperRepository``.
    """

    repository = DuplicateQueryRepository(session)
    candidate_doi = normalize_doi(parsed.doi) if parsed.doi else item.normalized_doi

    exact_item = repository.same_run_item_by_content_hash(
        item.import_run_id,
        parsed.content_hash,
        exclude_import_item_id=item.import_item_id,
    )
    exact_paper = repository.paper_by_content_hash(parsed.content_hash)

    doi_item = None
    if candidate_doi:
        doi_item = repository.same_run_item_by_normalized_doi(
            item.import_run_id,
            candidate_doi,
            exclude_import_item_id=item.import_item_id,
        )
    doi_paper = repository.paper_by_normalized_doi(candidate_doi)

    exact_match = _item_candidate(exact_item) or _paper_candidate(exact_paper)
    doi_match = _item_candidate(doi_item) or _paper_candidate(doi_paper)
    decision = decide_duplicate(
        candidate_content_hash=parsed.content_hash,
        candidate_normalized_doi=candidate_doi,
        exact_hash_match=exact_match,
        doi_match=doi_match,
    )

    item.computed_content_hash = parsed.content_hash
    item.duplicate_outcome = decision.duplicate_outcome
    item.matched_paper_id = decision.matched_paper_id
    item.matched_import_item_id = decision.matched_import_item_id
    item.duplicate_evidence_json = json.dumps(
        {
            "candidate": {
                "content_hash": parsed.content_hash,
                "normalized_doi": candidate_doi,
            },
            "decision": {
                "item_status": decision.item_status,
                "duplicate_outcome": decision.duplicate_outcome,
                "reason_code": decision.reason_code,
            },
            "matches": {
                "exact_hash": _candidate_evidence(exact_match),
                "doi": _candidate_evidence(doi_match),
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    session.flush()
    return decision


def _paper_candidate(paper: Paper | None) -> DuplicateCandidate | None:
    if paper is None:
        return None
    return DuplicateCandidate(
        paper_id=paper.id,
        content_hash=paper.content_hash,
        normalized_doi=normalize_doi(paper.doi) if paper.doi else None,
    )


def _item_candidate(item: ImportItem | None) -> DuplicateCandidate | None:
    if item is None:
        return None
    return DuplicateCandidate(
        paper_id=item.matched_paper_id,
        import_item_id=item.import_item_id,
        content_hash=item.computed_content_hash,
        normalized_doi=item.normalized_doi,
    )


def _candidate_evidence(candidate: DuplicateCandidate | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    return {
        "paper_id": candidate.paper_id,
        "import_item_id": candidate.import_item_id,
        "content_hash": candidate.content_hash,
        "normalized_doi": candidate.normalized_doi,
    }
