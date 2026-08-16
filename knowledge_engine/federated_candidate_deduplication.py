"""Deterministic high-confidence deduplication for federated discovery candidates."""

from __future__ import annotations

from dataclasses import replace

from knowledge_engine.federated_discovery import FederatedCandidate
from knowledge_engine.utils import normalize_doi


def deduplicate_candidates_by_exact_doi(
    candidates: tuple[FederatedCandidate, ...],
) -> tuple[FederatedCandidate, ...]:
    """Collapse candidates only when they share one unambiguous normalized DOI.

    Candidate order is stable. The first candidate carrying a DOI becomes the
    canonical shell, while all provider observations are retained in encounter
    order. Candidates with no DOI or internally conflicting DOI assertions are
    never merged by this rule.
    """

    merged: list[FederatedCandidate] = []
    doi_indexes: dict[str, int] = {}

    for candidate in candidates:
        doi = _unambiguous_candidate_doi(candidate)
        if doi is None:
            merged.append(candidate)
            continue

        existing_index = doi_indexes.get(doi)
        if existing_index is None:
            doi_indexes[doi] = len(merged)
            merged.append(_with_normalized_doi(candidate, doi))
            continue

        existing = merged[existing_index]
        merged[existing_index] = replace(
            existing,
            canonical_id=f"doi:{doi}",
            observations=existing.observations + candidate.observations,
            doi=doi,
        )

    return tuple(merged)


def _unambiguous_candidate_doi(candidate: FederatedCandidate) -> str | None:
    asserted = {
        normalized
        for value in (candidate.doi, *(observation.doi for observation in candidate.observations))
        if value is not None and (normalized := normalize_doi(value))
    }
    if len(asserted) != 1:
        return None
    return next(iter(asserted))


def _with_normalized_doi(candidate: FederatedCandidate, doi: str) -> FederatedCandidate:
    if candidate.doi == doi:
        return candidate
    return replace(candidate, doi=doi)
