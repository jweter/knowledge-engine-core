"""Attach reference-layer context to draft extraction-review items.

`docs/reference_knowledge_layer_design.md`'s Addendum names three
integration points buildable now, without waiting on a Phase 5 report
renderer or Phase 4's Knowledge Graph: a coverage-gap flag for terms with
no reference-layer match (item 2), provenance-footer discipline for any
reference text surfaced anywhere (item 3), and a reviewer aid surfacing a
term's reference-layer definition inline for the human deciding
`research_question`/`evidence_direction` around `ke
extraction-review-promote` (item 4). This module builds all three at
once: it reads the draft evidence items `ke extraction-review-generate`/
`extraction-review-batch-generate` already produced and attaches a
`reference_context` object to each one, built only from PICO fields M28's
deterministic extraction already populated -- no new term-extraction
logic, no guessing which term matters.

Field-to-source mapping follows each lookup source's own established
purpose: `intervention`/`comparator` (PICO's two treatment-role fields)
route through M42's RxNorm lookup, since both name a drug or treatment;
`population`/`outcome` route through M43's MeSH lookup, since both
describe a medical concept rather than a drug. A PICO field that is
itself `None` (nothing detected) gets a `None` `reference_context` entry
-- distinct from a field that resolved but found no reference-layer
match (`found: false`), which is written out explicitly rather than
omitted, per the Addendum's coverage-gap item. Every embedded lookup
result carries its own `source_url`/`license`/`retrieved_at`, satisfying
the provenance-footer item without any extra rendering logic -- those
fields already exist on `RxNormLookupResult`/`MeshLookupResult`.

This is deliberately a separate, opt-in step from `extraction-review-
generate`/`-batch-generate`: those commands must stay network-free so
running them at the corpus's real scale (M40: 13,588 draft items across
943 papers) never makes an unbounded number of live API calls. A reviewer
runs this command by hand against the specific paper(s) they are actually
about to review -- the same "explicit network access, never automatic"
posture every M41-M44 lookup command's console warning already
established. Within one run, identical terms are looked up once and
reused across every draft item that shares them, bounding network calls
to the number of *distinct* terms, not the number of items.

Like every reference-layer module, this is explicitly background
context, not evidence: it never sets, infers, or defaults
`research_question` or `evidence_direction`, and does not change `ke
extraction-review-promote`'s existing refusal to promote a record
missing either.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormLookupResult

EXTRACTION_REVIEW_ANNOTATE_RULES_VERSION = "m45-extraction-review-annotate-v1"

RXNORM_REFERENCE_FIELDS = ("intervention", "comparator")
MESH_REFERENCE_FIELDS = ("population", "outcome")


class RxNormLookup(Protocol):
    """Structural interface for the RxNorm lookup dependency this module needs."""

    def lookup(self, term: str) -> RxNormLookupResult:
        """Resolve one term to its RxNorm concept."""


class MeshLookup(Protocol):
    """Structural interface for the MeSH lookup dependency this module needs."""

    def lookup(self, term: str) -> MeshLookupResult:
        """Resolve one term to its MeSH descriptor."""


@dataclass(frozen=True)
class AnnotationSummary:
    """How many draft items were annotated and how many distinct terms were looked up."""

    item_count: int
    rxnorm_terms_looked_up: int
    mesh_terms_looked_up: int


def annotate_draft_items(
    items: list[dict[str, Any]],
    *,
    rxnorm_service: RxNormLookup,
    mesh_service: MeshLookup,
) -> tuple[list[dict[str, Any]], AnnotationSummary]:
    """Attach a `reference_context` object to each draft item.

    Returns new dicts; `items` is not mutated. A term repeated across many
    items in the same file is only looked up once -- `rxnorm_cache`/
    `mesh_cache` hold every distinct term's result for the duration of one
    call.
    """

    rxnorm_cache: dict[str, dict[str, Any]] = {}
    mesh_cache: dict[str, dict[str, Any]] = {}
    annotated: list[dict[str, Any]] = []

    for item in items:
        reference_context: dict[str, Any] = {}
        for field in RXNORM_REFERENCE_FIELDS:
            reference_context[field] = _lookup_cached(
                item.get(field), rxnorm_cache, "rxnorm", rxnorm_service.lookup
            )
        for field in MESH_REFERENCE_FIELDS:
            reference_context[field] = _lookup_cached(
                item.get(field), mesh_cache, "mesh", mesh_service.lookup
            )
        annotated_item = dict(item)
        annotated_item["reference_context"] = reference_context
        annotated.append(annotated_item)

    summary = AnnotationSummary(
        item_count=len(items),
        rxnorm_terms_looked_up=len(rxnorm_cache),
        mesh_terms_looked_up=len(mesh_cache),
    )
    return annotated, summary


def _lookup_cached(
    term: object,
    cache: dict[str, dict[str, Any]],
    source_label: str,
    lookup: Callable[[str], RxNormLookupResult | MeshLookupResult],
) -> dict[str, Any] | None:
    if not isinstance(term, str) or not term.strip():
        return None
    normalized = term.strip()
    if normalized not in cache:
        payload = asdict(lookup(normalized))
        payload["source"] = source_label
        cache[normalized] = payload
    return cache[normalized]
