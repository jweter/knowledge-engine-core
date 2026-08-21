"""Search service backed by SQLite FTS5."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from knowledge_engine.utils import normalize_doi

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

EVIDENCE_CANDIDATE_LIMIT = 500
EVIDENCE_FIELD_WEIGHTS = {
    "research_question": 5.0,
    "claim_text": 3.0,
    "pico": 2.0,
    "result_summary": 1.0,
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
    evidence_alignment_score: float = 0.0


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

    def answer_retrieval(
        self,
        question: str,
        limit: int = 5,
        *,
        evidence_records: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[SearchResult]:
        """Retrieve papers relevant to a natural-language question.

        This is retrieval only. It converts a question into a conservative FTS
        query and returns ranked papers without synthesizing scientific claims.
        """

        fts_query = build_natural_language_fts_query(question)
        if not fts_query:
            return []
        evidence_by_doi = _index_evidence_records_by_doi(evidence_records or ())
        candidate_limit = max(limit, EVIDENCE_CANDIDATE_LIMIT) if evidence_by_doi else limit
        candidates = self._search_fts(fts_query, limit=candidate_limit)
        if not evidence_by_doi:
            return candidates

        question_tokens = _retrieval_tokens(question)
        token_weights = self._token_idf_weights(question_tokens)
        ranked: list[tuple[float, int, SearchResult]] = []
        for lexical_rank, candidate in enumerate(candidates):
            records = evidence_by_doi.get(normalize_doi(candidate.doi or ""), ())
            alignment = max(
                (_evidence_alignment(question_tokens, token_weights, record) for record in records),
                default=0.0,
            )
            ranked.append(
                (
                    alignment,
                    lexical_rank,
                    replace(candidate, evidence_alignment_score=alignment),
                )
            )
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[:limit]]

    def _token_idf_weights(self, tokens: set[str]) -> dict[str, float]:
        """Return a smoothed inverse-document-frequency weight per question token."""

        if not tokens:
            return {}
        total_papers = self.session.execute(text("SELECT count(*) FROM paper_search")).scalar_one()
        weights: dict[str, float] = {}
        for token in tokens:
            document_frequency = self.session.execute(
                text("SELECT count(*) FROM paper_search WHERE paper_search MATCH :token"),
                {"token": token},
            ).scalar_one()
            weights[token] = math.log((total_papers + 1) / (document_frequency + 1)) + 1
        return weights

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


def _index_evidence_records_by_doi(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        source_doi = record.get("source_doi")
        if not isinstance(source_doi, str) or not source_doi.strip():
            continue
        indexed.setdefault(normalize_doi(source_doi), []).append(record)
    return {doi: tuple(values) for doi, values in indexed.items()}


def _retrieval_tokens(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]+", value.lower())
        if len(token) >= 3 and token not in NATURAL_LANGUAGE_STOPWORDS
    }


def _weighted_token_coverage(
    question_tokens: set[str], token_weights: Mapping[str, float], text_tokens: set[str]
) -> float:
    if not question_tokens:
        return 0.0
    total_weight = sum(token_weights.get(token, 1.0) for token in question_tokens)
    if total_weight <= 0:
        return 0.0
    matched_weight = sum(token_weights.get(token, 1.0) for token in question_tokens & text_tokens)
    return matched_weight / total_weight


def _evidence_alignment(
    question_tokens: set[str],
    token_weights: Mapping[str, float],
    evidence: Mapping[str, Any],
) -> float:
    pico = " ".join(
        value
        for field in ("population", "intervention", "comparator", "outcome")
        if isinstance((value := evidence.get(field)), str)
    )
    fields = {
        "research_question": evidence.get("research_question"),
        "claim_text": evidence.get("claim_text"),
        "pico": pico,
        "result_summary": evidence.get("result_summary"),
    }
    weighted_coverage = sum(
        EVIDENCE_FIELD_WEIGHTS[field]
        * _weighted_token_coverage(
            question_tokens,
            token_weights,
            _retrieval_tokens(value),
        )
        for field, value in fields.items()
    )
    return weighted_coverage / sum(EVIDENCE_FIELD_WEIGHTS.values())
