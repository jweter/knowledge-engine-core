"""Search service backed by SQLite FTS5."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SearchResult:
    """A paper returned from a search query."""

    paper_id: int
    title: str
    abstract: str | None
    score: float
    snippet: str


class SearchService:
    """Keyword and phrase search over indexed paper text."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search indexed papers using SQLite FTS5 ranking."""

        normalized_query = query.strip()
        if not normalized_query:
            return []

        rows = self.session.execute(
            text("""
                SELECT
                    p.id,
                    p.title,
                    p.abstract,
                    bm25(paper_search, 5.0, 3.0, 1.0, 0.5) AS score,
                    snippet(paper_search, 2, '[', ']', ' ... ', 32) AS snippet
                FROM paper_search
                JOIN papers p ON p.id = paper_search.rowid
                WHERE paper_search MATCH :query
                ORDER BY score
                LIMIT :limit
                """),
            {"query": normalized_query, "limit": limit},
        )
        return [
            SearchResult(
                paper_id=int(row.id),
                title=str(row.title),
                abstract=row.abstract,
                score=float(row.score),
                snippet=str(row.snippet or ""),
            )
            for row in rows
        ]
