"""Semantic-similarity ranking for relationship-candidate pairs.

M61: with the 2+-shared-concept tier exhausted (M56/M59), most remaining
candidate pairs share only a weak, near-universal concept (`placebo`
matches almost any RCT). This module re-ranks candidates by actual
`outcome`/`result_summary` text similarity instead, so a limited review
session spends its time on the pairs most likely to be real
relationships first.

Ranking only -- never a relationship decision itself. A high similarity
score means "these two claims are probably about a similar comparison,
worth classifying first," not "these two claims are related." M72's
`relationship_classification.classify_relationship` is what actually
decides whether, and how, two claims relate -- an LLM proposal accepted
only after its quoted evidence passes deterministic grounding
verification, the default automated path `ke relationship-classify-automate`
runs over this ranking's own output. Authoring a relationship by hand
(`ke relationship-review-worksheet`/`ke relationship-validate`) remains
available, not required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from knowledge_engine.models import GraphClaim, GraphConcept


class SimilarityEmbeddingGenerator(Protocol):
    """The subset of `EmbeddingGenerator` this module needs."""

    def generate(self, text: str) -> tuple[float, ...]: ...


@dataclass(frozen=True)
class RankedCandidate:
    """One candidate pair, optionally scored by semantic similarity."""

    claim_a: GraphClaim
    claim_b: GraphClaim
    shared_concepts: list[GraphConcept]
    similarity: float | None


def _similarity_text(record: dict[str, Any] | None) -> str | None:
    """Build the short text used for similarity comparison from one evidence record.

    `outcome` and `result_summary` are the two fields most indicative of
    what a claim is actually about -- closer to the comparison itself
    than `population`/`intervention`/`comparator`, which two very
    different claims can still share (e.g. both about semaglutide,
    entirely different outcomes).
    """

    if record is None:
        return None
    parts = [record.get("outcome"), record.get("result_summary")]
    text = " ".join(str(part) for part in parts if part)
    return text.strip() or None


def _cosine_similarity(vector_a: tuple[float, ...], vector_b: tuple[float, ...]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def rank_candidates_by_similarity(
    candidates: list[tuple[GraphClaim, GraphClaim, list[GraphConcept]]],
    evidence_records_by_id: dict[str, dict[str, Any]],
    generator: SimilarityEmbeddingGenerator,
) -> list[RankedCandidate]:
    """Re-sort candidate pairs by cosine similarity of their outcome/result text.

    Embeds each unique claim once (not once per pair) -- with N unique
    claims across the candidate list, this is N `generate()` calls, not
    2x the pair count. A claim missing from `evidence_records_by_id`, or
    with no `outcome`/`result_summary` text to embed, gets `similarity =
    None` for every pair it appears in and sorts after every pair that
    has a real score, never a guessed middle value.
    """

    unique_ids = {
        claim.evidence_record_id
        for claim_a, claim_b, _shared in candidates
        for claim in (claim_a, claim_b)
    }
    embeddings: dict[str, tuple[float, ...] | None] = {}
    for evidence_record_id in unique_ids:
        text = _similarity_text(evidence_records_by_id.get(evidence_record_id))
        embeddings[evidence_record_id] = generator.generate(text) if text else None

    ranked: list[RankedCandidate] = []
    for claim_a, claim_b, shared_concepts in candidates:
        vector_a = embeddings.get(claim_a.evidence_record_id)
        vector_b = embeddings.get(claim_b.evidence_record_id)
        similarity = (
            _cosine_similarity(vector_a, vector_b)
            if vector_a is not None and vector_b is not None
            else None
        )
        ranked.append(
            RankedCandidate(
                claim_a=claim_a,
                claim_b=claim_b,
                shared_concepts=shared_concepts,
                similarity=similarity,
            )
        )

    ranked.sort(key=lambda item: (item.similarity is None, -(item.similarity or 0.0)))
    return ranked
