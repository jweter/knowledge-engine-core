"""Deterministic scientific-scope evidence check, shared across discovery sources.

Originally part of `knowledge_engine.candidate_review` (M14's PubMed/PMC
adjudication engine). Extracted so a second discovery pipeline -- Europe PMC
(M34), and any future source -- applies the identical scope-matching logic
rather than a copy that can drift out of sync. Pure text evaluation over a
title/abstract; carries no provider-specific knowledge (no PMID, PMCID, or
host assumptions).

`docs/roadmap.md`'s "Decision: domain diversification beyond GLP-1" is why
the disease/intervention vocabulary below is a parameter
(`ScopeVocabulary`), not a hardcoded module constant: a second corpus (e.g.
oncology) needs different scope terms without forking this module or
weakening the GLP-1/metabolic corpus's own criteria. `GLP1_METABOLIC_SCOPE`
is the original, still-default vocabulary -- every existing caller that
does not pass `vocabulary` explicitly keeps its exact prior behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeVocabulary:
    """One corpus's disease/condition and intervention term sets.

    Both are lowercase, casefold-matched substrings evaluated against a
    candidate's title (and abstract, when supplied) -- see
    `evaluate_scientific_scope`. A candidate must match at least one term
    from each set to pass; neither set alone is sufficient, matching this
    project's existing "identifies a domain term AND identifies a named
    intervention" inclusion-criteria shape.
    """

    corpus_id: str
    disease_terms: tuple[str, ...]
    intervention_terms: tuple[str, ...]


GLP1_METABOLIC_SCOPE = ScopeVocabulary(
    corpus_id="glp1_weight_loss",
    disease_terms=(
        "obesity",
        "obese",
        "overweight",
        "type 2 diabetes",
        "type ii diabetes",
        "t2d",
        "metabolic syndrome",
    ),
    intervention_terms=(
        "treatment",
        "therapy",
        "therapeutic",
        "intervention",
        "pharmacotherapy",
        "drug",
        "medication",
        "glp-1",
        "glp1",
        "glucagon-like peptide-1",
        "semaglutide",
        "liraglutide",
        "tirzepatide",
        "metformin",
        "sglt2",
        "sodium-glucose cotransporter 2",
    ),
)

ONCOLOGY_NSCLC_CHECKPOINT_SCOPE = ScopeVocabulary(
    corpus_id="oncology_nsclc_checkpoint_inhibitors",
    disease_terms=(
        "non-small-cell lung cancer",
        "non-small cell lung cancer",
        "nsclc",
        "lung cancer",
        "lung carcinoma",
        "lung adenocarcinoma",
    ),
    intervention_terms=(
        "treatment",
        "therapy",
        "therapeutic",
        "immunotherapy",
        "immune checkpoint inhibitor",
        "checkpoint inhibitor",
        "pd-1",
        "pd-l1",
        "programmed death-1",
        "programmed death-ligand 1",
        "pembrolizumab",
        "nivolumab",
        "atezolizumab",
        "durvalumab",
        "cemiplimab",
    ),
)
"""See `docs/oncology_corpus_scoping.md` for the full rationale. Mirrors
`GLP1_METABOLIC_SCOPE`'s shape: one bounded population/intervention pair
(advanced NSCLC / anti-PD-1/PD-L1 checkpoint inhibitors), not "cancer" or
"immunotherapy" in general -- narrow enough to be evidence-map-defensible
the same way the GLP-1 corpus is."""

_SCOPE_VOCABULARIES_BY_CORPUS_ID: dict[str, ScopeVocabulary] = {
    GLP1_METABOLIC_SCOPE.corpus_id: GLP1_METABOLIC_SCOPE,
    ONCOLOGY_NSCLC_CHECKPOINT_SCOPE.corpus_id: ONCOLOGY_NSCLC_CHECKPOINT_SCOPE,
}


def resolve_scope_vocabulary(corpus_id: str) -> ScopeVocabulary:
    """Look up a known corpus's `ScopeVocabulary` by its `corpus_id`.

    Raises `KeyError` on an unrecognized id -- callers (typically a CLI
    command) translate that into a user-facing error rather than silently
    falling back to a different corpus's scope terms.
    """

    try:
        return _SCOPE_VOCABULARIES_BY_CORPUS_ID[corpus_id]
    except KeyError:
        known = ", ".join(sorted(_SCOPE_VOCABULARIES_BY_CORPUS_ID))
        raise KeyError(f"Unknown corpus id {corpus_id!r}. Known corpora: {known}.") from None


_PEDIATRIC_POPULATION_TERMS = (
    "pediatric",
    "paediatric",
    "child",
    "infant",
    "neonat",
    "adolescent",
    "youth",
)
_ADULT_INCLUSION_TERMS = ("adult",)
"""Matches only the title -- not the abstract. An adult study's abstract can
mention pediatric research as background context without the study itself
being pediatric; a title is a much stronger population signal.
`exclusion_criteria.md` requires excluding sources "limited to" pediatric
populations, not merely mentioning one -- a title also naming an adult
population (e.g. "...in adolescents and adults") is evidence of a
mixed-age study, not one limited to pediatric, so `_ADULT_INCLUSION_TERMS`
overrides the pediatric match rather than holding otherwise-valid
adult-inclusive evidence. A title match with no adult term returns a
non-"passed" scope result, which routes to `held` (never a silent
rejection), matching how every other scope-insufficient title is already
treated."""
_NON_PRIMARY_TITLE_PREFIXES = (
    "correction:",
    "corrigendum:",
    "erratum:",
    "retraction:",
    "retracted:",
    "publisher correction:",
    "author correction:",
)
"""A correction/erratum/retraction notice for an original article is not
itself a scientific paper, systematic review, meta-analysis, or clinical
research report -- it is typically a page or two amending a figure, table,
or author list in the original. Journals mark these with a stable title
prefix, so checking the title's start (case-insensitively) is a reliable,
still-deterministic signal, unlike scanning for "correction" as a bare
substring, which would also match a legitimate title like "Confidence
interval correction for measurement bias in obesity studies"."""


def evaluate_scientific_scope(
    title: str,
    abstract: str | None,
    *,
    vocabulary: ScopeVocabulary = GLP1_METABOLIC_SCOPE,
) -> str:
    """Return a scope-evidence result string for one candidate's title/abstract.

    One of: "passed", "non_primary_content_title_evidence",
    "insufficient_title_abstract_evidence", or
    "pediatric_population_title_evidence". Never raises on ordinary text;
    callers decide what a non-"passed" result means for their own
    accept/reject/hold policy. `vocabulary` defaults to the original GLP-1/
    metabolic-disease terms -- pass a different `ScopeVocabulary` for a
    different corpus rather than editing this module's defaults.
    """

    normalized_title = " ".join(title.casefold().split())
    if normalized_title.startswith(_NON_PRIMARY_TITLE_PREFIXES):
        return "non_primary_content_title_evidence"

    evidence = title if abstract is None else f"{title} {abstract}"
    normalized = " ".join(evidence.casefold().split())
    has_disease = any(term in normalized for term in vocabulary.disease_terms)
    has_intervention = any(term in normalized for term in vocabulary.intervention_terms)
    if not (has_disease and has_intervention):
        return "insufficient_title_abstract_evidence"

    has_pediatric_term = any(term in normalized_title for term in _PEDIATRIC_POPULATION_TERMS)
    has_adult_term = any(term in normalized_title for term in _ADULT_INCLUSION_TERMS)
    if has_pediatric_term and not has_adult_term:
        return "pediatric_population_title_evidence"
    return "passed"
