"""Search service backed by SQLite FTS5."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

NATURAL_LANGUAGE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "do",
    "does",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class SearchResult:
    """A paper returned from a search query."""

    paper_id: int
    title: str
    abstract: str | None
    publication_year: int | None
    doi: str | None
    score: float
    snippet: str
    matched_query: str


class SearchService:
    """Keyword and phrase search over indexed paper text."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search indexed papers using SQLite FTS5 ranking."""

        normalized_query = query.strip()
        if not normalized_query:
            return []
        return self._search_fts(normalized_query, limit=limit)

    def answer_retrieval(self, question: str, limit: int = 5) -> list[SearchResult]:
        """Retrieve papers relevant to a natural-language question.

        This is retrieval only. It converts a question into a conservative FTS
        query and returns ranked papers without synthesizing scientific claims.
        """

        fts_query = build_natural_language_fts_query(question)
        if not fts_query:
            return []
        return self._search_fts(fts_query, limit=limit)

    def _search_fts(self, fts_query: str, limit: int) -> list[SearchResult]:
        """Run an FTS5 query and return ranked papers."""

        rows = self.session.execute(
            text("""
                SELECT
                    p.id,
                    p.title,
                    p.abstract,
                    p.publication_year,
                    p.doi,
                    bm25(paper_search, 5.0, 3.0, 1.0, 0.5) AS score,
                    snippet(paper_search, -1, '[', ']', ' ... ', 32) AS snippet
                FROM paper_search
                JOIN papers p ON p.id = paper_search.rowid
                WHERE paper_search MATCH :query
                ORDER BY score
                LIMIT :limit
                """),
            {"query": fts_query, "limit": limit},
        )
        return [
            SearchResult(
                paper_id=int(row.id),
                title=str(row.title),
                abstract=row.abstract,
                publication_year=row.publication_year,
                doi=row.doi,
                score=float(row.score),
                snippet=str(row.snippet or ""),
                matched_query=fts_query,
            )
            for row in rows
        ]


def build_natural_language_fts_query(question: str) -> str:
    """Convert a natural-language question into a safe SQLite FTS query."""

    tokens = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]+", question.lower()):
        if len(token) < 3 or token in NATURAL_LANGUAGE_STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return " OR ".join(tokens)
