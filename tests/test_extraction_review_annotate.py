from __future__ import annotations

from typing import Any

from knowledge_engine.extraction_review_annotate import (
    _candidate_terms,
    annotate_draft_items,
)
from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormIngredient, RxNormLookupResult

_RXNORM_KNOWN = {
    "semaglutide": ("1991302", "semaglutide", (("1991302", "semaglutide"),)),
    "placebo": ("8375", "placebo", (("8375", "placebo"),)),
}
_MESH_KNOWN = {
    "obesity": ("D009765", "Obesity"),
}


class FakeRxNormService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup(self, term: str) -> RxNormLookupResult:
        self.calls.append(term)
        known = _RXNORM_KNOWN.get(term.lower())
        if known is None:
            return RxNormLookupResult(
                term=term,
                found=False,
                rxcui=None,
                name=None,
                term_type=None,
                synonym=None,
                ingredients=(),
                source_url=None,
                license=None,
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
        rxcui, name, ingredient_pairs = known
        return RxNormLookupResult(
            term=term,
            found=True,
            rxcui=rxcui,
            name=name,
            term_type="IN",
            synonym=None,
            ingredients=tuple(
                RxNormIngredient(rxcui=pair[0], name=pair[1]) for pair in ingredient_pairs
            ),
            source_url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
            license="Non-proprietary content, National Library of Medicine (RxNorm API)",
            retrieved_at="2026-07-29T00:00:00+00:00",
        )


class FakeMeshService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup(self, term: str) -> MeshLookupResult:
        self.calls.append(term)
        known = _MESH_KNOWN.get(term.lower())
        if known is None:
            return MeshLookupResult(
                term=term,
                found=False,
                mesh_id=None,
                heading=None,
                scope_note=None,
                synonyms=(),
                source_url=None,
                license=None,
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
        mesh_id, heading = known
        return MeshLookupResult(
            term=term,
            found=True,
            mesh_id=mesh_id,
            heading=heading,
            scope_note="An excessive amount of adipose tissue in the body.",
            synonyms=("Obesities",),
            source_url=f"https://id.nlm.nih.gov/mesh/{mesh_id}",
            license="Free, non-proprietary content, National Library of Medicine (MeSH)",
            retrieved_at="2026-07-29T00:00:00+00:00",
        )


def _draft_item(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "evidence_record_id": None,
        "research_question": None,
        "evidence_direction": None,
        "population": "obesity",
        "intervention": "semaglutide",
        "comparator": "placebo",
        "outcome": "percent body weight change",
    }
    record.update(overrides)
    return record


def test_annotate_attaches_reference_context_for_all_pico_fields() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()

    annotated, summary = annotate_draft_items(
        [_draft_item()], rxnorm_service=rxnorm, mesh_service=mesh
    )

    context = annotated[0]["reference_context"]
    assert context["intervention"]["source"] == "rxnorm"
    assert context["intervention"]["found"] is True
    assert context["intervention"]["rxcui"] == "1991302"
    assert context["comparator"]["source"] == "rxnorm"
    assert context["comparator"]["found"] is True
    assert context["comparator"]["rxcui"] == "8375"
    assert context["population"]["source"] == "mesh"
    assert context["population"]["mesh_id"] == "D009765"
    assert context["outcome"]["source"] == "mesh"
    assert context["outcome"]["found"] is False
    assert summary.item_count == 1


def test_annotate_sets_none_for_missing_pico_fields() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(intervention=None, population=None)

    annotated, _summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["intervention"] is None
    assert context["population"] is None
    assert rxnorm.calls == ["placebo"]
    assert mesh.calls  # outcome candidates were still tried


def test_annotate_treats_blank_string_the_same_as_missing() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(intervention="   ", comparator=None, population=None, outcome=None)

    annotated, _summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["intervention"] is None
    assert rxnorm.calls == []
    assert mesh.calls == []


def test_annotate_finds_a_term_inside_a_realistic_noisy_sentence() -> None:
    """The real bug this fix addresses: M28's PICO fields are routinely entire
    multi-line, citation-laden paragraphs, not isolated terms (real corpus
    example, lightly trimmed)."""

    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(
        intervention=(
            "Participants received semaglutide once weekly for 68 weeks "
            "according to the randomized, double-blind protocol described above."
        )
    )

    annotated, _summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["intervention"]["found"] is True
    assert context["intervention"]["rxcui"] == "1991302"
    assert context["intervention"]["term"] == "semaglutide"


def test_annotate_declines_when_multiple_distinct_concepts_appear_in_one_field() -> None:
    """Real corpus example: a comparator sentence naming both drugs at once
    must not silently pick one -- same ambiguity discipline as M43/M44."""

    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(
        comparator="Compared with placebo, semaglutide induced significant weight loss."
    )

    annotated, _summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["comparator"]["found"] is False
    assert "placebo" in rxnorm.calls
    assert "semaglutide" in rxnorm.calls


def test_annotate_caches_repeated_candidates_within_one_call() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    items = [_draft_item(), _draft_item()]

    annotated, _summary = annotate_draft_items(items, rxnorm_service=rxnorm, mesh_service=mesh)

    assert rxnorm.calls.count("semaglutide") == 1
    assert annotated[0]["reference_context"]["intervention"]["rxcui"] == "1991302"
    assert annotated[1]["reference_context"]["intervention"]["rxcui"] == "1991302"


def test_annotate_does_not_mutate_the_original_items() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    original = _draft_item()

    annotated, _summary = annotate_draft_items([original], rxnorm_service=rxnorm, mesh_service=mesh)

    assert "reference_context" not in original
    assert annotated[0] is not original
    assert annotated[0]["research_question"] is None
    assert annotated[0]["evidence_direction"] is None


def test_candidate_terms_drops_stopwords_and_short_tokens() -> None:
    candidates = _candidate_terms("The participants were randomized to a low dose of drug X.")

    assert "the" not in [c.lower() for c in candidates]
    assert "to" not in [c.lower() for c in candidates]
    assert "a" not in [c.lower() for c in candidates]
    assert "low" in candidates
    assert "dose" in candidates


def test_candidate_terms_deduplicates_case_insensitively() -> None:
    candidates = _candidate_terms("Obesity, obesity, and OBESITY were the enrollment criteria.")

    assert candidates.count("Obesity") == 1


def test_candidate_terms_is_bounded_for_very_long_noisy_text() -> None:
    long_text = " ".join(f"word{i}" for i in range(500))

    candidates = _candidate_terms(long_text)

    assert len(candidates) <= 20
