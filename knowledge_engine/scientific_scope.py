"""Deterministic scientific-scope evidence check, shared across discovery sources.

Originally part of `knowledge_engine.candidate_review` (M14's PubMed/PMC
adjudication engine). Extracted so a second discovery pipeline -- Europe PMC
(M34), and any future source -- applies the identical obesity/metabolic-disease
therapeutics scope criteria rather than a copy that can drift out of sync.
Pure text evaluation over a title/abstract; carries no provider-specific
knowledge (no PMID, PMCID, or host assumptions).
"""

from __future__ import annotations

_DISEASE_TERMS = (
    "obesity",
    "obese",
    "overweight",
    "type 2 diabetes",
    "type ii diabetes",
    "t2d",
    "metabolic syndrome",
)
_INTERVENTION_TERMS = (
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
)
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


def evaluate_scientific_scope(title: str, abstract: str | None) -> str:
    """Return a scope-evidence result string for one candidate's title/abstract.

    One of: "passed", "non_primary_content_title_evidence",
    "insufficient_title_abstract_evidence", or
    "pediatric_population_title_evidence". Never raises on ordinary text;
    callers decide what a non-"passed" result means for their own
    accept/reject/hold policy.
    """

    normalized_title = " ".join(title.casefold().split())
    if normalized_title.startswith(_NON_PRIMARY_TITLE_PREFIXES):
        return "non_primary_content_title_evidence"

    evidence = title if abstract is None else f"{title} {abstract}"
    normalized = " ".join(evidence.casefold().split())
    has_disease = any(term in normalized for term in _DISEASE_TERMS)
    has_intervention = any(term in normalized for term in _INTERVENTION_TERMS)
    if not (has_disease and has_intervention):
        return "insufficient_title_abstract_evidence"

    has_pediatric_term = any(term in normalized_title for term in _PEDIATRIC_POPULATION_TERMS)
    has_adult_term = any(term in normalized_title for term in _ADULT_INCLUSION_TERMS)
    if has_pediatric_term and not has_adult_term:
        return "pediatric_population_title_evidence"
    return "passed"
