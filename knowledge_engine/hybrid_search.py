"""Merge independently-ranked lexical and vector search signals into one list.

Implements the gap `entrypoint.py`'s own `vector_search` command docstring
names explicitly: "combining the two into one ranked list is not yet
implemented." Unlike `search_fusion.fuse_rankings` (Reciprocal Rank Fusion
over RANK POSITION, used elsewhere in this project), this combines each
signal's own RAW SCORES after independently min-max normalizing each
signal to [0, 1] -- the contract this slice was scoped to build.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from knowledge_engine.search import SearchResult


@dataclass(frozen=True)
class HybridSearchResult:
    """One paper's combined lexical + vector relevance.

    `lexical_score`/`vector_score` are each signal's own min-max normalized
    score in [0, 1], or 0.0 if the paper was absent from that signal.
    `combined_score` is always their sum, so a paper present in only one
    signal keeps exactly that signal's normalized score as its combined
    score.
    """

    paper_id: int
    combined_score: float
    lexical_score: float
    vector_score: float


def _normalized(raw_scores: Mapping[int, float]) -> dict[int, float]:
    """Min-max normalize `raw_scores` to [0, 1]; a constant signal maps to 1.0."""
    if not raw_scores:
        return {}
    low = min(raw_scores.values())
    high = max(raw_scores.values())
    if high == low:
        return {paper_id: 1.0 for paper_id in raw_scores}
    spread = high - low
    return {paper_id: (value - low) / spread for paper_id, value in raw_scores.items()}


def merge_lexical_and_vector_results(
    lexical: Sequence[SearchResult],
    vector_scores: Mapping[int, float],
) -> list[HybridSearchResult]:
    """Combine a lexical result list with a vector-search score mapping.

    Each signal is independently min-max normalized across all papers
    present in that signal before combining, so the two systems'
    incomparable raw score scales (FTS5's bm25 vs FAISS's raw similarity)
    never need direct comparison. Lexical scores are FTS5 bm25 values, where
    lower (more negative) is a better match; they are negated before
    normalizing so the best lexical match scores 1.0. No input paper_id is ever dropped.
    Results are sorted by `combined_score` descending, ties broken by
    ascending `paper_id` for determinism.
    """
    # SQLite FTS5 bm25() is lower-is-better (SearchService orders by it ascending), so negate it to
    # the same higher-is-better orientation as the vector similarity before normalizing.
    lexical_raw = {result.paper_id: -result.score for result in lexical}
    lexical_normalized = _normalized(lexical_raw)
    vector_normalized = _normalized(vector_scores)

    all_paper_ids = set(lexical_normalized) | set(vector_normalized)
    merged = [
        HybridSearchResult(
            paper_id=paper_id,
            combined_score=(
                lexical_normalized.get(paper_id, 0.0) + vector_normalized.get(paper_id, 0.0)
            ),
            lexical_score=lexical_normalized.get(paper_id, 0.0),
            vector_score=vector_normalized.get(paper_id, 0.0),
        )
        for paper_id in all_paper_ids
    ]
    merged.sort(key=lambda result: (-result.combined_score, result.paper_id))
    return merged
