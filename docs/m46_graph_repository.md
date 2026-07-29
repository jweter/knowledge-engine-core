# M46 Phase 4: GraphRepository

## Purpose

`docs/phase4_design.md` resolved Phase 4's open architectural questions
(SQLite-relational first, no Neo4j; a plain application-validated string
reference where the graph would otherwise point at a JSONL-only record)
but shipped no code. M46 is the first Phase 4 milestone: the schema, the
`GraphRepository` persistence layer, and a `ke graph-build` command that
populates the graph from real, already-validated evidence and
relationship records.

**M46 stays on the design doc's side of the seam.** Every method here
stores or links an already-authored signal -- a validated `EvidenceRecord`,
a resolved RxNorm/MeSH concept, a human-authored `RelationshipRecord`. None
of them compute, default, or infer a confidence rating; that remains the
future `knowledge-engine-ai` layer's job per
`docs/roadmap/long_term_vision.md`.

## Schema

Four tables, exactly as designed in `docs/phase4_design.md`'s Architecture
section, added at schema version 8:

- **`graph_concepts`** -- one resolved reference-layer term or PICO field
  value. `definition`/`source_url`/`license` hold the actual M41-M45
  lookup content (a row here is its only durable home once linked into
  the graph). Deduplicated by `(source, source_reference_id)` when a real
  lookup identity exists; a bare `source='pico'` concept (reserved for
  future use, not populated by `ke graph-build`) has no lookup identity
  and is never deduplicated.
- **`graph_claims`** -- one validated `EvidenceRecord`, referenced by its
  `evidence_record_id`. This is a plain, application-validated string
  column, not a SQL foreign key: `EvidenceRecord`s are JSONL objects
  appended by `_promote_evidence_records`, never rows in any SQLAlchemy
  table, so there is no table for `ForeignKey()` to target.
- **`graph_claim_concepts`** -- a real foreign-key edge linking a claim to
  a concept via the PICO field that produced it (`population`/
  `intervention`/`comparator`/`outcome`). Unique per
  `(claim_id, concept_id, edge_role)`.
- **`graph_claim_relationships`** -- a graph-queryable projection of an
  M24 `RelationshipRecord`, keyed the same non-enforced way as
  `graph_claims.evidence_record_id` and for the same reason. Does not
  replace `RelationshipRecord`s or `ke relationship-validate` -- a
  projection of the same validated data, not a second source of truth.

`graph_citations` remains deliberately absent, per the design doc's Open
Questions: citation-list extraction is unscoped, real-corpus-verification
-requiring work, not yet built.

## GraphRepository

`knowledge_engine/database.py`'s `GraphRepository` mirrors
`PaperRepository`/`ExtractionRunRepository`'s exact shape (constructed
from a `Session`, `add()`+`flush()`, no file I/O): `get_or_create_concept`,
`get_concept`, `get_or_create_claim`, `get_claim`, `link_claim_concept`,
`get_or_create_relationship_edge`, and the traversal queries
`concepts_for_claim`/`claims_for_concept`/`relationships_for_claim`
(both edge directions). `population_counts()` reports the graph's total
current row counts, for `ke graph-build`'s summary and any future
corpus-scale report.

Validating that an `evidence_record_id`/`relationship_id` string actually
corresponds to a real JSONL record happens at the caller layer (`ke
graph-build`, mirroring how `ke relationship-validate --evidence <file>`
already validates `RelationshipRecord` endpoint IDs), not inside
`GraphRepository` itself.

## `ke graph-build`

```bash
ke graph-build --evidence evidence_records.jsonl [--relationships relationships.jsonl] [--output summary.json]
```

Reads an `--evidence` JSONL file (expected to have already passed `ke
evidence-validate`) and creates one `graph_claims` row per record. Reuses
M45's `annotate_draft_items` unchanged to resolve each record's
`population`/`intervention`/`comparator`/`outcome` PICO field against
RxNorm/MeSH -- `EvidenceRecord` dicts carry the exact same PICO key names
`annotate_draft_items` already operates on, so no adapter was needed. A
field with no confident reference-layer match (`found: false`)
contributes no concept node.

An optional `--relationships` JSONL file (expected to have already passed
`ke relationship-validate`) adds one `graph_claim_relationships` row per
record. A relationship whose endpoint `evidence_record_id` is not among
the records in `--evidence` is skipped with a clear message listing the
skipped `relationship_id`s, never a silent drop or a hard failure of the
whole run.

Same network posture as every M41-M45 lookup command: prints a "Network
access" warning before querying RxNav/E-utilities, and the same
"expect on the order of a minute or more of network calls, not a
near-instant operation" cost as `ke extraction-review-annotate` applies
here too, since it calls the identical annotation function.

## Live verification against the real corpus

Run against the repo's only committed `EvidenceRecord` file,
`data/corpora/glp1_weight_loss/evidence_records.jsonl` (2 real,
hand-authored records from the VS-7/VS-11 prototype work), against a
scratch database:

```
Graph build complete: 2 claim(s) processed, 4 claim-concept link(s) created, 0 relationship edge(s) created.
Graph totals -- concepts: 2 {'rxnorm': 2}, claims: 2, claim-concept edges: 4, relationship edges: 0.
```

Both records' `intervention`/`comparator` fields resolved to two distinct
RxNorm concepts (semaglutide and placebo), each shared across both claims
-- 2 concepts, 4 edges. Neither record's `population`/`outcome` field
produced a MeSH concept: both are long, real-world paragraphs (not
isolated terms), and `annotate_draft_items`' ambiguity rule declines a
field where more than one distinct candidate resolves rather than
guessing which one is "the" concept -- the same, already-verified real
behavior `ke extraction-review-annotate` exhibits, not a new gap this
milestone introduces. No `--relationships` file exists anywhere in the
repo yet (confirmed via `find data -iname "*relationship*"`), so the
relationship-edge path is untested against real data, only against
`tests/test_graph_repository.py`'s synthetic fixtures.

This is a genuine measurement of graph population against the real,
if small, corpus of validated evidence -- consistent with the design
doc's committed Testing Strategy promise, and an honest illustration of
the claim-node sparsity risk the design doc already named: two validated
`EvidenceRecord`s produce a very small graph.

## What is deliberately not built yet

- `graph_citations` and any citation-edge methods -- unscoped, deferred
  per the design doc's Open Questions.
- No PICO-label deduplication for bare `source='pico'` concepts -- `ke
  graph-build` does not create them at all; only resolved reference-layer
  concepts (`source='rxnorm'`/`'mesh'`) are populated in this first
  slice.
- No Stability Score (claim revision history) or Tracking the Unknown
  (uncertainty/gap entities) schema -- both remain named as this phase's
  motivation, not delivered by the first schema, per the design doc.
- No caching or persistence of RxNorm/MeSH lookups across separate `ke
  graph-build` invocations, the same known gap `ke
  extraction-review-annotate` already has and has not yet addressed.
