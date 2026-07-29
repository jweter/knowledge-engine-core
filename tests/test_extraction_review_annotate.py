from __future__ import annotations

from typing import Any

from knowledge_engine.extraction_review_annotate import annotate_draft_items
from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormLookupResult


class FakeRxNormService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup(self, term: str) -> RxNormLookupResult:
        self.calls.append(term)
        if term == "Semaglutide":
            return RxNormLookupResult(
                term=term,
                found=True,
                rxcui="1991302",
                name="semaglutide",
                term_type="IN",
                synonym=None,
                ingredients=(),
                source_url="https://rxnav.nlm.nih.gov/REST/rxcui/1991302",
                license="Free, non-proprietary content (RxNorm, National Library of Medicine)",
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
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


class FakeMeshService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def lookup(self, term: str) -> MeshLookupResult:
        self.calls.append(term)
        if term == "Adults with obesity":
            return MeshLookupResult(
                term=term,
                found=True,
                mesh_id="D009765",
                heading="Obesity",
                scope_note="An excessive amount of adipose tissue in the body.",
                synonyms=("Obesities",),
                source_url="https://id.nlm.nih.gov/mesh/D009765",
                license="Free, non-proprietary content, National Library of Medicine (MeSH)",
                retrieved_at="2026-07-29T00:00:00+00:00",
            )
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


def _draft_item(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "evidence_record_id": None,
        "research_question": None,
        "evidence_direction": None,
        "population": "Adults with obesity",
        "intervention": "Semaglutide",
        "comparator": "Placebo",
        "outcome": "Percent body weight change",
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
    assert context["comparator"]["found"] is False
    assert context["population"]["source"] == "mesh"
    assert context["population"]["mesh_id"] == "D009765"
    assert context["outcome"]["source"] == "mesh"
    assert context["outcome"]["found"] is False
    assert summary.item_count == 1
    assert summary.rxnorm_terms_looked_up == 2
    assert summary.mesh_terms_looked_up == 2


def test_annotate_sets_none_for_missing_pico_fields() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(intervention=None, population=None)

    annotated, summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["intervention"] is None
    assert context["population"] is None
    assert rxnorm.calls == ["Placebo"]
    assert mesh.calls == ["Percent body weight change"]


def test_annotate_treats_blank_string_the_same_as_missing() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    item = _draft_item(intervention="   ", comparator=None, population=None, outcome=None)

    annotated, _summary = annotate_draft_items([item], rxnorm_service=rxnorm, mesh_service=mesh)

    context = annotated[0]["reference_context"]
    assert context["intervention"] is None
    assert rxnorm.calls == []
    assert mesh.calls == []


def test_annotate_caches_repeated_terms_within_one_call() -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    items = [_draft_item(), _draft_item()]

    annotated, summary = annotate_draft_items(items, rxnorm_service=rxnorm, mesh_service=mesh)

    assert rxnorm.calls.count("Semaglutide") == 1
    assert summary.item_count == 2
    assert summary.rxnorm_terms_looked_up == 2
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
