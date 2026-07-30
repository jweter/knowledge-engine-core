# Phase 4 Design: Knowledge Graph

Status: This is the Phase 4 design sketch, written before any Phase 4
implementation milestone -- the same role `docs/phase2_design.md` played
for Phase 2 and `docs/phase3_design.md` played for Phase 3. It turns
`docs/roadmap.md`'s four-bullet Phase 4 goal statement ("model concepts,
claims, citations, support, contradiction, and uncertainty"; "add Neo4j
or another graph backend behind a repository interface") into an
implementation-ready architecture, grounded in a fresh measurement of the
real 951-paper corpus rather than the abstract roadmap bullet alone (see
Prerequisite below), and resolves the graph backend decision before any
graph-storage code is written, the same way Phase 2's Extraction
Methodology section and Phase 3's embedding-generation section did. It
also names, rather than papers over, the real gaps Codex review on PR
#186 caught between this design's stated goals and its first schema --
`EvidenceRecord`/`RelationshipRecord` references are application-level,
not database-enforced foreign keys (both are JSONL, not tables); concept
nodes store the actual reference-layer definition and provenance, not
just an identity; and Stability Score/Tracking the Unknown are named as
this phase's motivation but deliberately not schema-designed in this
first slice (see Open Questions). No Phase 4 code exists yet; this
document is the plan.

## Mission

Model the connections `core`'s existing Evidence and Relationship Layers
already capture, plus two structural relationships they do not yet
capture at all (citations between papers, concepts as entities distinct
from the claims that mention them), as an explicit graph -- queryable by
traversal, not just by row lookup. This is not new judgment logic: every
node and edge Phase 4 populates must already be either (a) something
`core`'s deterministic extraction or a human reviewer already produced
(an `EvidenceRecord`, a `RelationshipRecord`, a reference-layer lookup
result), or (b) a new deterministic extraction target with the same
"never guess" discipline every prior milestone held to (citation-list
parsing). Phase 4 is a new *storage and traversal* layer over trustworthy
material `core` already has or can deterministically extract -- it is
not where judgment about what a claim means gets added. See Out of Scope
below for the boundary this holds to.

## Principle

Same principle as every phase before it: never guess. A citation edge
exists only when a reference-list entry was actually parsed and matched
to another corpus paper by DOI or an unambiguous title match, not
inferred from topical similarity. A concept node exists only when M41-M45's
reference-layer lookups actually resolved it, or a PICO field was
actually detected -- never a speculative entity invented to make the
graph look more complete. An empty or sparse corner of the graph is
correct output when the corpus's own coverage is sparse there (see
Prerequisite below), not a defect to paper over.

## Prerequisite: measured graph-readiness of the real corpus

Before designing a schema, `scripts/m38_extraction_corpus_report.py` was
re-run fresh against the full, current 951-paper corpus (not the
943-paper number M38 itself measured) to ground this design in what the
corpus actually contains, the same "read real data before writing
patterns" discipline `docs/phase2_design.md`'s PICO section and every
reference-layer milestone (M41-M45) already followed.

| Signal | Coverage | Graph relevance |
|---|---|---|
| Claim candidates detected | 13,791 total; 264/951 papers (28%) with zero | Raw candidate pool; only validated `EvidenceRecord`s become claim nodes (see Architecture) |
| Study type classified | 414/951 (44%) | Confidence-rating input signal (Stability Score's siblings); majority of the corpus (56%) has none |
| — meta-analysis / RCT / cohort / systematic review / cross-sectional / other | 96 / 47 / 89 / 39 / 50 / 93 | |
| PICO: population | 497/951 (52%) | Concept-node source |
| PICO: intervention | 594/951 (62%) | Concept-node source |
| PICO: comparator | 719/951 (76%) | Concept-node source |
| PICO: outcome | 551/951 (58%) | Concept-node source |
| **PICO: all four fields** | 249/951 (26%) | |
| Limitations text detected | 115/951 (12%) | Confidence-rating input signal |
| Publication year (recency) | 951/951 (100%) | Already-captured metadata, confidence-rating input signal |
| **Structured citations (reference-list entries parsed, cross-linked to corpus)** | **0/951 (0%) -- not built** | Citation edges: blocked entirely on new extraction work |
| Validated `EvidenceRecord`s | 2 (both hand-authored, pre-M19) | Claim nodes: currently near-empty regardless of graph existing |
| `RelationshipRecord`s (M24) | 100% human-authored, 0% automated | Support/contradiction edges: exist today only where a human already wrote one by hand |

Two conclusions follow directly from these numbers, not from the abstract
roadmap bullet:

1. **Citation edges cannot be built from what exists today.** There is no
   reference-list parser anywhere in this codebase --
   `REFERENCE_HEADING_PATTERN` in `parser.py` only detects *where* a
   paper's References section starts (used by section detection to bound
   the main body), it does not parse individual entries. This is real,
   unscoped extraction work and Phase 4's actual first prerequisite, not
   an afterthought.
2. **The graph's most valuable near-term content is concept and
   claim-review scaffolding, not a citation network.** Concept nodes
   (from M41-M45's reference layer plus PICO fields) and claim nodes
   (from `EvidenceRecord`s, however few exist today) have a real,
   populated -- if partial -- source today. A citation network has zero.

## Goals (from `docs/roadmap.md`'s Phase 4 bullet)

- Model concepts, claims, citations, support, contradiction, and
  uncertainty as an explicit, traversable graph.
- Add a graph backend behind a repository interface, matching the
  pattern `PaperRepository`/`VectorIndex` already established --
  Phase 4's own code should not care which concrete backend answers a
  query.
- **Named here as the roadmap's stated motivation for Phase 4, not
  delivered by this first schema.** `docs/roadmap/long_term_vision.md`
  says Stability Score (claim revision history) and Tracking the Unknown
  (missing experiments, weak-evidence areas, unanswered questions as
  first-class entities) have no graph-shaped home before Phase 4 exists
  -- true, and the reason this phase is worth building at all. Codex
  review on PR #186 correctly caught that the Architecture section below
  does not actually include a claim-version/revision-history table or an
  uncertainty/gap-entity table, so this first slice makes the graph
  *exist* (a real prerequisite neither capability had before) without
  yet *populating* either one. See Open Questions for why that schema
  design is deliberately deferred rather than guessed here.
- Give reference-layer definitions (M41 Wikipedia, M42 RxNorm, M43 MeSH,
  M44 PubChem) a home as Graph concept-node content, distinct from the
  paper-level evidence nodes that cite them -- `docs/reference_knowledge_layer_design.md`'s
  Addendum item 10.

## Out of Scope

Same seam every milestone before this one has held to, restated here
because Phase 4 is the phase most likely to tempt a violation of it (a
graph with typed support/contradiction edges *looks* like it could
compute a confidence score by itself):

- **No confidence rating computation.** Phase 4 stores the typed edges
  (`supports`/`contradicts`/`qualifies`/`contextualizes`) a future
  `knowledge-engine-ai` layer would traverse to compute one -- it does
  not compute the rating itself. See `docs/core_interface_contract.md`'s
  "the seam" and `docs/roadmap/long_term_vision.md`'s Confidence Rating
  Design Guidance. A graph traversal that returns "this claim has 3
  supporting edges and 1 contradicting edge" is a query result; deciding
  what that means for a research question's confidence is still the AI
  layer's job.
- **No automated `research_question`/`evidence_direction` assignment.**
  Unchanged from every prior phase.
- **No LLM-based relationship inference.** `docs/roadmap/long_term_vision.md`'s
  Minimizing Human-Typed Fields section names automating candidate-pair
  *surfacing* for the Relationship Layer as a real, worthwhile future
  improvement -- "surfacing candidate pairs automatically so a human
  confirms rather than composes from scratch." That is in scope as a
  possible Phase 4 addition (see Open Questions); a system that
  auto-*decides* `relationship_type`/`rationale` without human
  confirmation is not.
- **No citation-network content beyond what deterministic parsing
  produces.** No "this paper is probably related to that one" inference
  from topic similarity -- that already exists as `ke fused-search`
  (Phase 3) and is explicitly a *retrieval* signal, not a *graph edge*.

## Decision: graph backend

The roadmap names "Neo4j or another graph backend behind a repository
interface" without picking one. This is the same class of decision Phase
3's embedding-generation choice was (a new dependency/infrastructure
question with a real offline-posture tradeoff, escalated explicitly
rather than decided silently) -- documented here with the same rigor,
and resolved rather than left open, per the project owner's standing
direction to keep moving without waiting for a check-in on each decision
as long as it stays true to the vision and roadmap.

**Decision: relational tables in the existing SQLite database first,
behind a `GraphRepository` interface. No Neo4j or other external graph
database for the first slice.**

Rationale, mirroring Phase 3's own FAISS-before-Qdrant sequencing
precedent exactly:

- Every dependency this project has added required explicit
  justification against its "runs fully offline," "no new dependency
  without justification" defaults (see the PMC Cloud Service migration
  ADR, and Phase 3's own embedding-generation decision, which frames
  breaking offline-by-default as a real cost, not a free choice). Neo4j
  requires a running server process -- the same tradeoff Qdrant carries
  in Phase 3, where the project's own answer was "FAISS (embedded, no
  server) first; Qdrant only as an explicitly optional second backend,
  added when a real operator need appears, not built proactively."
- A property graph's core operations Phase 4 actually needs at this
  stage -- "which claims cite this concept," "which evidence records
  support or contradict this one," "what does this paper cite" -- are
  ordinary foreign-key joins at the corpus's current and foreseeable
  scale (951 papers, capped at 1,000 per the owner's own GitHub-size
  decision recorded in `docs/roadmap.md`'s corpus-growth section). A
  dedicated graph database's real advantage -- efficient deep/variable-length
  traversal at large scale -- has no evidence of being needed yet.
- SQLAlchemy models plus a `GraphRepository` class (mirroring
  `PaperRepository`) require no new dependency at all, need no operator
  setup, and keep the "fresh clone, `ke init`, works immediately"
  property every milestone so far has preserved.
- The `GraphRepository` interface is designed so a future Neo4j (or
  other) backend can be added later exactly the way `QdrantVectorIndex`
  was added alongside `FaissVectorIndex` -- a second implementation
  behind the same interface, built when a real, evidenced need for
  graph-native traversal at a scale relational joins can't handle
  actually appears. Nothing here forecloses that; it is deliberately not
  built proactively.

## Architecture

New tables, all additive (no change to existing `papers`/`evidence`
tables), following this project's lightweight-migration model
(`docs/technical_debt.md`'s "Lightweight migrations only" entry --
unchanged posture, not revisited by this phase):

- **`graph_concepts`** -- one row per resolved reference-layer term or
  PICO field value. Columns: `id`, `label` (the resolved heading/name --
  e.g. MeSH's `heading`, RxNorm's `name`), `source` (`wikipedia`/
  `rxnorm`/`mesh`/`pubchem`/`pico`), `source_reference_id` (the M41-M45
  lookup result's own identity -- `mesh_id`, `rxcui`, `cid`, or null for
  a bare PICO-derived concept with no resolved reference-layer match),
  `definition` (the actual content the Addendum item 10 goal above
  requires: Wikipedia's `extract`, MeSH's `scope_note`, RxNorm's
  `name`/`term_type`/`synonym` joined into one string, or PubChem's
  `iupac_name`/`molecular_formula` joined -- null for a bare
  PICO-derived concept with nothing to store), `source_url`, `license`,
  `retrieved_at`. A concept node is created only when a reference-layer
  lookup actually resolved (`found: true`) or a PICO field was actually
  detected -- never speculatively. Codex review on PR #186 caught that
  the first version of this table stored only identity fields, not the
  actual definition/provenance content the stated goal (concept nodes as
  "the textbook-style content hanging off a Graph concept node")
  requires -- a real gap between the claim and the schema, fixed here.
  This means a `graph_concepts` row *is* the persisted lookup record for
  that concept -- M41-M45's own lookup results are not separately
  persisted anywhere today, so this table becomes their only durable
  home once a concept is linked into the graph.
- **`graph_claims`** -- one row per *validated* `EvidenceRecord`, not per
  raw claim candidate. **Not a real SQL foreign key**: Codex review on
  PR #186 caught that `EvidenceRecord`s are JSONL objects appended by
  `_promote_evidence_records` (`knowledge_engine/cli.py`), never rows in
  any SQLAlchemy table -- there is no `evidence_records` table for a
  `ForeignKey()` to reference, so `Database` would refuse to create this
  constraint as originally described. `evidence_record_id` is instead a
  plain indexed string column holding the JSONL record's own
  `evidence_record_id` value, an application-level reference the
  `GraphRepository` layer validates against the JSONL file at write time
  (the same way `ke relationship-validate --evidence` already validates
  `RelationshipRecord` endpoint IDs against a supplied evidence file),
  not one the database enforces. A claim node inherits its parent
  `EvidenceRecord`'s own `research_question`/`evidence_direction`/
  `confidence_note` by reference (not duplicated) -- the graph never
  stores a second copy of judgment fields that could drift from the
  source record.
- **`graph_claim_concepts`** -- many-to-many edge table linking a
  `graph_claims` row to the `graph_concepts` row(s) its PICO fields or
  `reference_context` (M45) resolved, with an `edge_role` column
  (`population`/`intervention`/`comparator`/`outcome`) recording *which*
  PICO field produced the link. Real SQL foreign keys on both sides --
  both endpoints are genuine `graph_*` table rows.
- **`graph_claim_relationships`** -- Phase 4's storage for M24's existing
  `RelationshipRecord`s as graph edges: `source_claim_id`,
  `target_claim_id` (both real foreign keys into `graph_claims`),
  `relationship_type` (reusing `ALLOWED_RELATIONSHIP_TYPES` unchanged:
  `supports`/`contradicts`/`qualifies`/`contextualizes`), `rationale`,
  and `relationship_id` -- the same non-enforced, application-validated
  string reference as `graph_claims.evidence_record_id` above, for the
  same reason: `RelationshipRecord`s are JSONL too, with no table to
  reference. This table does not replace `RelationshipRecord`s or `ke
  relationship-validate`; it is a graph-queryable projection of the same
  validated data, same "one source of truth, graph is a view over it"
  posture `graph_claims` uses for `EvidenceRecord`s -- "projection," not
  "foreign key," is the accurate description of that relationship.
- **`graph_citations`** (blocked on new extraction work -- see
  Prerequisite above) -- `citing_paper_id`, `cited_paper_id` (both
  foreign keys into `papers`, only populated when a reference-list entry
  was parsed and matched to another *corpus* paper specifically, not an
  external DOI with no corresponding row), `raw_citation_text` (the
  original reference-list entry, for audit). A real, separate
  extraction milestone (see Open Questions) must land before this table
  can be populated; the table is designed now so `GraphRepository`'s
  interface is complete from the start, matching how M30 shipped
  `VectorIndex` before M31's embedding generators existed.

`GraphRepository` (mirroring `PaperRepository`'s constructor-takes-a-session
shape): `add_concept`, `get_concept`, `add_claim`, `link_claim_concept`,
`add_relationship_edge`, `add_citation_edge`, plus traversal queries
(`concepts_for_claim`, `claims_for_concept`, `relationships_for_claim`,
`citations_for_paper`) -- ordinary SQLAlchemy joins under the interface,
swappable for a different backend's native traversal later without
changing any caller.

## Testing Strategy

Same shape every prior phase's foundation milestone used: unit tests
against synthetic fixtures for `GraphRepository`'s CRUD and traversal
methods (no live network, no real corpus dependency), plus one
measurement pass against the real corpus (mirroring M38's own corpus
report) once the first slice is built, to report real graph population
counts the same way this design doc's Prerequisite section already
does -- not to claim success, but to keep the "measured, not assumed"
discipline continuous from design through implementation.

## Open Questions (owner decisions, not resolved here)

- **Stability Score / Tracking the Unknown schema.** Deliberately not
  designed in this document. A claim-revision-history table needs a real
  answer to "what counts as a revision" (a new `EvidenceRecord` promoted
  for the same underlying finding? a `research_question`/
  `evidence_direction` edit? neither exists as a defined event today) and
  an uncertainty/gap-entity table needs a real answer to "what makes a
  gap real rather than just 'no evidence record happens to exist yet'" --
  both are the same class of "verify against real data before writing a
  schema" question M28's PICO patterns and M45's Codex-caught term-extraction
  fix already went through, not something to guess under time pressure
  in this design doc. The first Phase 4 milestone builds the schema
  below (fully populatable today); Stability Score and Tracking the
  Unknown get their own dedicated follow-up design once the graph itself
  exists to prototype against. **Resolved by M50** (`docs/stability_and_tracking_design.md`,
  written once M46-M49 gave this a real graph to design against): a
  revision event is a `supersedes` `RelationshipRecord`/
  `graph_claim_relationships` edge (the fifth `relationship_type`, no
  new table); an honest, non-inferred "gap" is a claim with zero
  relationship edges of any type. The actual Stability sub-score formula
  and a richer "weak evidence area" report both stay explicitly out of
  `core`'s scope -- see that document's own Open Questions.
- **Whether `evidence_record_id`/`relationship_id` should become real
  foreign keys eventually**, i.e. whether `EvidenceRecord`/
  `RelationshipRecord` should move from JSONL to a proper SQLAlchemy
  table. A real, separate architectural question (JSONL has served
  Phase 2 fine for validation-only purposes; Phase 4 is the first
  consumer that would benefit from a DB-enforced reference) -- not
  decided here, since it's bigger than Phase 4's own scope and would
  affect `ke evidence-validate`/`ke extraction-review-promote`/`ke
  relationship-validate` too, not just the graph.
- **Citation-list parsing approach.** A real, separate design question
  with its own real-corpus verification needed before writing any
  pattern-matching code (matching M28's PICO precedent and M45's
  Codex-caught lesson that guessing free-text structure without
  real-sample verification produces a feature that doesn't work). Not
  scoped here; the first Phase 4 milestone should build
  `graph_concepts`/`graph_claims`/`graph_claim_concepts`/
  `graph_claim_relationships` (fully populatable today) and leave
  `graph_citations` for a dedicated follow-up milestone once reference-list
  parsing is designed and verified against real corpus text.
- **Automated relationship candidate-surfacing.** `docs/roadmap/long_term_vision.md`
  names this as a real future improvement (PICO-overlap or citation-based
  candidate pairs a human confirms rather than composes from scratch).
  Real, worthwhile, but needs its own scoping once `graph_claims`/
  `graph_claim_concepts` exist to compute overlap against -- not
  attempted in the first slice.
- **Whether low study_type/limitations coverage (44%/12%) should be
  improved before or alongside Phase 4**, since both are named
  confidence-rating-signal inputs the future AI layer will eventually
  consume. This design doc takes no position -- it is a Phase 2
  extraction-recall question, not a Phase 4 storage question, and is
  named here only so it is not silently forgotten while Phase 4 work
  proceeds.
- **Neo4j (or another backend) as a second `GraphRepository`
  implementation.** Not ruled out, matching Qdrant's own status --
  revisit only when a real, evidenced traversal-performance or
  graph-native-query need appears, not proactively.

## Potential Risks

- **Claim-node sparsity.** With only 2 validated `EvidenceRecord`s today,
  `graph_claims`/`graph_claim_relationships` will be nearly empty
  regardless of the graph layer's own correctness -- this is a Phase 2
  promotion-throughput fact, not a Phase 4 defect, and should not be
  mistaken for one when the first measurement pass runs.
- **Concept-node duplication across sources.** The same real-world
  concept (e.g. "obesity") can appear as both a MeSH-resolved concept
  node (via a `population` PICO field routed through M45) and,
  separately, a bare PICO-derived concept node with no reference-layer
  match for a different paper's slightly different phrasing. No
  deduplication/entity-resolution logic is proposed in this first slice --
  a real future need, named here rather than silently deferred, once
  real graph data shows how much this actually matters in practice.
