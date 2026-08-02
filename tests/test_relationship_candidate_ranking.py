from knowledge_engine.models import GraphClaim, GraphConcept
from knowledge_engine.relationship_candidate_ranking import rank_candidates_by_similarity


def _claim(evidence_record_id: str, claim_id: int) -> GraphClaim:
    return GraphClaim(
        id=claim_id, evidence_record_id=evidence_record_id, created_at="2026-01-01T00:00:00Z"
    )


def _concept(label: str, concept_id: int) -> GraphConcept:
    return GraphConcept(id=concept_id, label=label, source="pico")


class FakeGenerator:
    """Deterministic fake: returns a fixed vector per known text, unknown text errors."""

    def __init__(self, vectors_by_text: dict[str, tuple[float, ...]]) -> None:
        self._vectors_by_text = vectors_by_text

    def generate(self, text: str) -> tuple[float, ...]:
        return self._vectors_by_text[text]


def test_rank_candidates_orders_by_descending_similarity() -> None:
    claim_a = _claim("ev-a", 1)
    claim_b = _claim("ev-b", 2)
    claim_c = _claim("ev-c", 3)
    concepts = [_concept("semaglutide", 1)]

    candidates = [
        (claim_a, claim_b, concepts),
        (claim_a, claim_c, concepts),
    ]
    evidence_records_by_id = {
        "ev-a": {"outcome": "Body weight change.", "result_summary": "Weight down."},
        "ev-b": {"outcome": "Body weight change.", "result_summary": "Weight down too."},
        "ev-c": {
            "outcome": "Unrelated ovulatory function.",
            "result_summary": "Cycles normalized.",
        },
    }
    generator = FakeGenerator(
        {
            "Body weight change. Weight down.": (1.0, 0.0),
            "Body weight change. Weight down too.": (0.9, 0.1),
            "Unrelated ovulatory function. Cycles normalized.": (0.0, 1.0),
        }
    )

    ranked = rank_candidates_by_similarity(candidates, evidence_records_by_id, generator)

    assert ranked[0].claim_b.evidence_record_id == "ev-b"
    assert ranked[1].claim_b.evidence_record_id == "ev-c"
    assert ranked[0].similarity is not None
    assert ranked[1].similarity is not None
    assert ranked[0].similarity > ranked[1].similarity


def test_rank_candidates_embeds_each_unique_claim_once() -> None:
    claim_a = _claim("ev-a", 1)
    claim_b = _claim("ev-b", 2)
    claim_c = _claim("ev-c", 3)
    concepts: list[GraphConcept] = []

    candidates = [
        (claim_a, claim_b, concepts),
        (claim_a, claim_c, concepts),
        (claim_b, claim_c, concepts),
    ]
    evidence_records_by_id = {
        "ev-a": {"outcome": "A", "result_summary": ""},
        "ev-b": {"outcome": "B", "result_summary": ""},
        "ev-c": {"outcome": "C", "result_summary": ""},
    }
    calls: list[str] = []

    class TrackingGenerator:
        def generate(self, text: str) -> tuple[float, ...]:
            calls.append(text)
            return (1.0, 0.0)

    rank_candidates_by_similarity(candidates, evidence_records_by_id, TrackingGenerator())

    assert sorted(calls) == ["A", "B", "C"]


def test_rank_candidates_puts_missing_similarity_last() -> None:
    claim_a = _claim("ev-a", 1)
    claim_b = _claim("ev-b", 2)
    claim_c = _claim("ev-c", 3)
    concepts: list[GraphConcept] = []

    candidates = [
        (claim_a, claim_b, concepts),
        (claim_a, claim_c, concepts),
    ]
    evidence_records_by_id = {
        "ev-a": {"outcome": "Body weight.", "result_summary": ""},
        "ev-b": {"outcome": "Body weight.", "result_summary": ""},
        # ev-c has no outcome/result_summary text at all, and is also
        # missing from the dict for a second pair to prove both cases
        # degrade the same way.
    }
    generator = FakeGenerator({"Body weight.": (1.0, 0.0)})

    ranked = rank_candidates_by_similarity(candidates, evidence_records_by_id, generator)

    assert ranked[0].similarity is not None
    assert ranked[1].similarity is None
    assert ranked[1].claim_b.evidence_record_id == "ev-c"
