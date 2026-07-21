"""Bounded multi-page PubMed candidate discovery for larger M14 review intakes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol

from knowledge_engine.pubmed_discovery import DiscoveryResult, PubmedCandidate

MAX_TOTAL_CANDIDATES = 5_000
MAX_PAGE_SIZE = 100


class DiscoveryService(Protocol):
    """Structural interface for one bounded page-discovery call."""

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        """Return a bounded, deterministic page of candidates."""


@dataclass(frozen=True)
class BatchDiscoveryResult:
    """One deterministic, deduplicated multi-page discovery result."""

    query: str
    retstart: int
    requested_limit: int
    page_size: int
    fetched_page_count: int
    duplicate_pmids_removed: int
    exhausted: bool
    candidates: tuple[PubmedCandidate, ...]

    def to_json(self) -> str:
        """Render stable review-only JSON."""

        payload = {
            "query": self.query,
            "retstart": self.retstart,
            "requested_limit": self.requested_limit,
            "page_size": self.page_size,
            "fetched_page_count": self.fetched_page_count,
            "candidate_count": len(self.candidates),
            "duplicate_pmids_removed": self.duplicate_pmids_removed,
            "exhausted": self.exhausted,
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def discover_candidate_batch(
    service: DiscoveryService,
    query: str,
    *,
    total_limit: int,
    retstart: int = 0,
    page_size: int = MAX_PAGE_SIZE,
) -> BatchDiscoveryResult:
    """Aggregate bounded discovery pages while preserving first-seen PMID order."""

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("PubMed query must not be empty.")
    if not 1 <= total_limit <= MAX_TOTAL_CANDIDATES:
        raise ValueError(f"Total discovery limit must be between 1 and {MAX_TOTAL_CANDIDATES}.")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"Discovery page size must be between 1 and {MAX_PAGE_SIZE}.")
    if retstart < 0:
        raise ValueError("Discovery retstart must be non-negative.")

    candidates: list[PubmedCandidate] = []
    seen_pmids: set[str] = set()
    duplicate_count = 0
    fetched_page_count = 0
    next_retstart = retstart
    exhausted = False

    while len(candidates) < total_limit:
        request_limit = min(page_size, total_limit - len(candidates))
        page = service.discover(
            normalized_query,
            limit=request_limit,
            retstart=next_retstart,
        )
        fetched_page_count += 1

        if not page.candidates:
            exhausted = True
            break

        for candidate in page.candidates:
            if candidate.pmid in seen_pmids:
                duplicate_count += 1
                continue
            seen_pmids.add(candidate.pmid)
            candidates.append(candidate)
            if len(candidates) == total_limit:
                break

        if len(page.candidates) < request_limit:
            exhausted = True
            break
        next_retstart += request_limit

    return BatchDiscoveryResult(
        query=normalized_query,
        retstart=retstart,
        requested_limit=total_limit,
        page_size=page_size,
        fetched_page_count=fetched_page_count,
        duplicate_pmids_removed=duplicate_count,
        exhausted=exhausted,
        candidates=tuple(candidates),
    )
