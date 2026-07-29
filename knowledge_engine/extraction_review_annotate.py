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
deterministic extraction already populated.

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

**A PICO field is not an isolated term -- Codex review on PR #184 caught
this as a real, confirmed P1.** `pico.py`'s own docstring calls a PICO
field "the first cue-matching sentence," but re-sampling the real
951-paper corpus (not just this module's own hand-written test fixtures)
showed real field values are routinely entire multi-line, citation-laden
paragraphs -- `sentence_split`'s span boundaries do not reliably track
real PDF-extracted punctuation. The original version of this module
passed that raw text directly to RxNorm's/MeSH's *exact*-match lookups,
which means it returned `found: false` for nearly every real draft item;
verified live: passing "Participants received semaglutide once weekly
for 68 weeks." to RxNorm's exact-name endpoint returns an empty
`idGroup`, even though "semaglutide" alone resolves immediately.

The fix: `_candidate_terms` extracts a small, bounded set of individual
word tokens from the raw field text (first 30 alphabetic tokens, common
stopwords and short tokens dropped, capped at 20 distinct candidates) and
tries each one against the existing *unchanged* exact-match lookup. This
adds no fuzzy matching and no new network behavior to the lookup services
themselves -- a bad candidate word simply resolves `found: false`, never
a wrong-but-confident answer. Multi-word candidate phrases (e.g. "type 2
diabetes") are a known, deliberate gap this version does not attempt: no
real match in the corpus sample this fix was verified against required
one, and guessing multi-word windows without further real-corpus tuning
would repeat the same "ship an unverified pattern" mistake this fix
exists to correct. If more than one *distinct* concept resolves among the
candidates tried (a real, observed case: a comparator field mentioning
both "semaglutide" and "placebo" in the same paragraph), the field
declines (`found: false`) rather than guessing which one is "the" term --
the same ambiguity discipline M43's MeSH lookup and M44's PubChem fix
already established. Verified live against real corpus text after the
fix: `intervention`/`comparator` fields mentioning "semaglutide" and
"placebo" together correctly decline; a paper's `population` field
mentioning only "obesity" correctly resolves it.

This is deliberately a separate, opt-in step from `extraction-review-
generate`/`-batch-generate`: those commands must stay network-free so
running them at the corpus's real scale (M40: 13,588 draft items across
943 papers) never makes an unbounded number of live API calls. A reviewer
runs this command by hand against the specific paper(s) they are actually
about to review -- the same "explicit network access, never automatic"
posture every M41-M44 lookup command's console warning already
established. Within one run, identical candidate terms are looked up
once and reused across every draft item that shares them, bounding
network calls to the number of *distinct* candidate words actually tried,
not the number of items or the raw text length.

**"Bounded" is not "fast," measured honestly.** Live-verified against two
real papers (38 and 41 draft items): even after cross-item candidate
caching, a real paper's draft-item set produced 29-34 distinct MeSH terms
and 31-33 distinct RxNorm terms to look up -- on the order of a minute or
more of live network calls per paper, not a near-instant operation. This
is the real cost of `_candidate_terms`' bounded-but-real scan window, not
a bug; it is disclosed here rather than understated, matching the
"Network access" warning every M41-M44 command already prints before
querying anything.

Like every reference-layer module, this is explicitly background
context, not evidence: it never sets, infers, or defaults
`research_question` or `evidence_direction`, and does not change `ke
extraction-review-promote`'s existing refusal to promote a record
missing either.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormLookupResult

EXTRACTION_REVIEW_ANNOTATE_RULES_VERSION = "m45-extraction-review-annotate-v2"

RXNORM_REFERENCE_FIELDS = ("intervention", "comparator")
MESH_REFERENCE_FIELDS = ("population", "outcome")

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")
_MAX_SCAN_TOKENS = 30
_MAX_CANDIDATE_TERMS = 20
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "to",
        "for",
        "with",
        "on",
        "at",
        "by",
        "from",
        "was",
        "were",
        "is",
        "are",
        "this",
        "that",
        "these",
        "those",
        "as",
        "we",
        "who",
        "which",
        "into",
        "after",
        "over",
        "than",
        "not",
        "all",
        "both",
        "each",
        "no",
    }
)


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

    Returns new dicts; `items` is not mutated. A candidate word repeated
    across many items in the same file is only looked up once --
    `rxnorm_cache`/`mesh_cache` hold every distinct candidate's result for
    the duration of one call.
    """

    rxnorm_cache: dict[str, dict[str, Any]] = {}
    mesh_cache: dict[str, dict[str, Any]] = {}
    annotated: list[dict[str, Any]] = []

    for item in items:
        reference_context: dict[str, Any] = {}
        for field in RXNORM_REFERENCE_FIELDS:
            reference_context[field] = _resolve_reference_context(
                item.get(field), rxnorm_cache, "rxnorm", rxnorm_service.lookup
            )
        for field in MESH_REFERENCE_FIELDS:
            reference_context[field] = _resolve_reference_context(
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


def _candidate_terms(text: str) -> list[str]:
    """Extract a small, bounded list of single-word lookup candidates.

    Real PICO field values are often long, noisy, multi-line paragraphs
    (see module docstring), not isolated terms. Scanning is bounded to
    the first `_MAX_SCAN_TOKENS` alphabetic tokens and at most
    `_MAX_CANDIDATE_TERMS` distinct candidates, so network cost stays
    bounded regardless of how long or noisy the source text is.
    """

    candidates: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_PATTERN.findall(text)[:_MAX_SCAN_TOKENS]:
        if len(token) <= 2:
            continue
        lowered = token.lower()
        if lowered in _STOPWORDS or lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(token)
        if len(candidates) >= _MAX_CANDIDATE_TERMS:
            break
    return candidates


def _resolve_reference_context(
    raw_value: object,
    cache: dict[str, dict[str, Any]],
    source_label: str,
    lookup: Callable[[str], RxNormLookupResult | MeshLookupResult],
) -> dict[str, Any] | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    raw_text = raw_value.strip()

    matches: dict[str, dict[str, Any]] = {}
    for candidate in _candidate_terms(raw_text):
        if candidate not in cache:
            result = lookup(candidate)
            payload = asdict(result)
            payload["source"] = source_label
            cache[candidate] = payload
        payload = cache[candidate]
        if payload["found"]:
            matches.setdefault(_identity_key(payload, source_label), payload)

    if len(matches) == 1:
        return next(iter(matches.values()))
    return _not_found_stub(raw_text, source_label)


def _identity_key(payload: dict[str, Any], source_label: str) -> str:
    """Group matches by underlying concept, not surface string.

    RxNorm keeps a brand name and its generic as distinct `rxcui`s but the
    same underlying `ingredients` -- comparing `ingredients` (falling back
    to `rxcui` when empty) matches M42's own established identity model.
    """

    if source_label == "rxnorm":
        ingredients = payload.get("ingredients") or []
        if ingredients:
            rxcuis = tuple(sorted(str(entry["rxcui"]) for entry in ingredients))
            return f"ingredients:{rxcuis}"
        return f"rxcui:{payload.get('rxcui')}"
    return f"mesh_id:{payload.get('mesh_id')}"


def _not_found_stub(raw_text: str, source_label: str) -> dict[str, Any]:
    """Build a `found: false` entry without an extra network call.

    Used both when zero candidates matched and when more than one
    distinct concept matched (ambiguous) -- both mean the same actionable
    thing to a reviewer: no confident reference-layer context is
    available for this field.
    """

    retrieved_at = datetime.now(UTC).isoformat()
    result: RxNormLookupResult | MeshLookupResult
    if source_label == "rxnorm":
        result = RxNormLookupResult(
            term=raw_text,
            found=False,
            rxcui=None,
            name=None,
            term_type=None,
            synonym=None,
            ingredients=(),
            source_url=None,
            license=None,
            retrieved_at=retrieved_at,
        )
    else:
        result = MeshLookupResult(
            term=raw_text,
            found=False,
            mesh_id=None,
            heading=None,
            scope_note=None,
            synonyms=(),
            source_url=None,
            license=None,
            retrieved_at=retrieved_at,
        )
    payload = asdict(result)
    payload["source"] = source_label
    return payload
