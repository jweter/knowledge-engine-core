"""Deterministic fusion of lexical and semantic search result rankings.

`docs/phase3_design.md`'s Open Questions named this the last undesigned
piece of Phase 3: `ke search`/`ke answer` (lexical, SQLite FTS5) and
`ke vector-search` (semantic, FAISS/Qdrant) return two separate ranked
lists over the same paper_id space, with no way to combine them into one.

Reciprocal Rank Fusion (RRF) is used here: a paper's fused score is the sum,
over each input ranking it appears in, of `1 / (k + rank)`, where `rank` is
its 1-indexed position in that ranking and `k` is a fixed damping constant
(60, RRF's standard default from the original TREC work it comes from). RRF
needs only rank position, not the two systems' incomparable raw scores
(FTS5's bm25 vs FAISS's squared L2 distance, where lower is better) -- no
arbitrary cross-system weighting decision, no training data, no new
dependency, matching this project's deterministic, no-ML extraction
methodology.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SEARCH_FUSION_RULES_VERSION = "m39-search-fusion-v1"

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class FusedResult:
    """One paper's combined rank across a lexical and a semantic ranking.

    `fused_score` is higher-is-better (the opposite convention from FAISS's
    raw distance score) -- callers should not assume it is comparable to
    either input ranking's own score. `lexical_rank`/`semantic_rank` are
    `None` when the paper did not appear in that ranking at all, so callers
    can explain why a result is present (e.g. "matched lexically only").
    """

    paper_id: int
    fused_score: float
    lexical_rank: int | None
    semantic_rank: int | None


def fuse_rankings(
    lexical_paper_ids: Sequence[int],
    semantic_paper_ids: Sequence[int],
    *,
    k: int = DEFAULT_RRF_K,
) -> tuple[FusedResult, ...]:
    """Combine two independently-ranked paper_id lists via Reciprocal Rank Fusion.

    Each input must already be in rank order (best match first); this
    function does not re-rank within either list, only combines across
    them. A paper appearing in only one list still receives a fused score
    from that list alone -- absence from the other list contributes no
    penalty beyond simply not adding a second term. Results are sorted by
    `fused_score` descending, ties broken by ascending `paper_id` for
    determinism. Duplicate paper_ids within one input list are not expected
    from either `SearchService`/`VectorIndex` and are not deduplicated here.
    """

    if k <= 0:
        raise ValueError("k must be positive")

    lexical_ranks = {paper_id: rank for rank, paper_id in enumerate(lexical_paper_ids, start=1)}
    semantic_ranks = {paper_id: rank for rank, paper_id in enumerate(semantic_paper_ids, start=1)}

    fused: list[FusedResult] = []
    for paper_id in set(lexical_ranks) | set(semantic_ranks):
        lexical_rank = lexical_ranks.get(paper_id)
        semantic_rank = semantic_ranks.get(paper_id)
        score = 0.0
        if lexical_rank is not None:
            score += 1.0 / (k + lexical_rank)
        if semantic_rank is not None:
            score += 1.0 / (k + semantic_rank)
        fused.append(
            FusedResult(
                paper_id=paper_id,
                fused_score=score,
                lexical_rank=lexical_rank,
                semantic_rank=semantic_rank,
            )
        )

    fused.sort(key=lambda result: (-result.fused_score, result.paper_id))
    return tuple(fused)
