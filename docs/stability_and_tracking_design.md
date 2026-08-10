# Stability Score and Tracking the Unknown: Design

Status: `docs/phase4_design.md`'s Open Questions explicitly deferred this
design -- "Stability Score and Tracking the Unknown get their own
dedicated follow-up design once the graph itself exists to prototype
against" -- rather than guess a schema before there was a real graph
(`graph_claims`/`graph_claim_concepts`/`graph_claim_relationships`) to
design it in terms of. M46-M49 built that graph. This document is the
deferred design, written the same way `docs/phase4_design.md` itself was
written before Phase 4's first line of code: grounded in what the real
system currently does (and does not) support, resolving what can be
resolved without guessing, and naming what genuinely cannot be resolved
here as an owner decision.

## Mission

`docs/founding_vision.md`'s Confidence Framework names Stability
("historical consistency, frequency of revision") as one of four
per-claim sub-scores, and its Addendum names Tracking the Unknown --
explicitly representing gaps, not just knowledge -- as a founding
principle. Both are named `core`'s responsibility to make *representable*
in the graph; scoring and surfacing them for a human reader is the future
`knowledge-engine-ai`/`-web` layers' job, the same boundary
`docs/roadmap/long_term_vision.md`'s Confidence Rating Design Guidance
already draws for Evidence Quality and Consensus. This document scopes
only the representable-in-`core` half.

## Principle

Same principle as every phase before it: never guess, and never build
new machinery where existing machinery already fits. A "revision" event
must be something explicitly asserted by whoever authors it (an AI agent
or a human -- no human required), the same way a `supports`/`contradicts`
relationship is today -- never inferred from
text similarity or promotion order. A "gap" must be a real, queryable
absence in the graph's own data (zero relationship edges on a claim,
concretely), never a heuristic guess about what evidence "should" exist.

## Prerequisite: what the real system currently does and does not support

- **No revision mechanism exists anywhere today.** `_promote_evidence_records`
  (`knowledge_engine/cli.py`) treats an `evidence_record_id` already
  present in the output file as a duplicate and always skips it --
  never overwrites, never versions. `EvidenceRecord`s are plain JSONL
  lines; nothing prevents a human from hand-editing an existing line
  outside `ke extraction-review-promote`, but no code path tracks that
  edit as an event, checks it, or reports on it. This is the literal
  gap `docs/phase4_design.md`'s Open Question named: "a
  `research_question`/`evidence_direction` edit... neither exists as a
  defined event today."
- **The real corpus has zero `RelationshipRecord`s.** `docs/phase4_design.md`'s
  own measurement table recorded this (100% human-authored,
  0 today) and it remains true: `data/corpora/glp1_weight_loss/` has no
  committed relationships file. There is no real revision or
  contradiction history to prototype a scoring formula against yet, only
  the mechanism that would let one start accumulating.
- **`RelationshipRecord`/`graph_claim_relationships` already support
  exactly the shape a revision event needs.** A `RelationshipRecord`
  already links two claims by ID, with a typed `relationship_type` and a
  human-written `rationale` -- `ke relationship-validate` already
  enforces referential integrity against a known evidence file, and `ke
  graph-build` already projects it into `graph_claim_relationships`. The
  type set (`supports`/`contradicts`/`qualifies`/`contextualizes`) is
  the only piece missing a revision-shaped option.
- **The graph has no join from a claim back to its `research_question`
  text.** `graph_claims` stores only `evidence_record_id` (see
  `docs/history/milestones/m48_graph_report.md`'s "what is deliberately not built yet" on
  why `evidence_record_id` is not a real foreign key). Any report
  grouping claims by research question needs the same `--evidence
  <file>` join `ke relationship-report` already requires, not a new
  graph column.

## Decision: Stability -- `supersedes` as a fifth relationship type

**A revision event is a human-authored `RelationshipRecord` with
`relationship_type: "supersedes"`, linking a new claim (`source_evidence_record_id`)
to the claim it revises (`target_evidence_record_id`), with `rationale`
stating what changed and why.**

Rationale:

- Reuses 100% of existing, already-tested machinery --
  `_validate_relationship_records`, `ke relationship-validate`, `ke
  relationship-report`, `GraphRepository.get_or_create_relationship_edge`,
  `ke graph-build`, `ke graph-report`, and M49's
  `relationship_candidates` (which already excludes any pair with an
  existing edge of *any* type, `supersedes` included) -- rather than
  inventing a second file format, a second CLI command family, or a
  mutable-history table. The only change needed is widening one `CHECK`
  constraint and one Python validation set from four values to five.
- Matches "Knowledge Is Never Final" (`docs/founding_vision.md`'s First
  Principles): nothing is ever edited or deleted. A revision is a new,
  independently-provenanced `EvidenceRecord` that explicitly says which
  earlier claim it revises and why -- the old claim, and the full
  history of who asserted what and when, stays intact and queryable
  forever, exactly like `supports`/`contradicts` already do.
- Deciding whether a new claim actually *does* supersede an old one
  stays a human judgment call, the same boundary `ke relationship-validate`
  already draws for every other relationship type -- `core` never
  infers a supersession from the fact that two claims discuss the same
  concept (that's exactly what M49's `graph-relationship-candidates`
  already surfaces as an unlabeled candidate pair for a human to look
  at, `supersedes` included as one of the types they can now choose).
- **Computing an actual 0-100 Stability sub-score from a chain of
  `supersedes` edges is explicitly out of scope for `core`.** Same
  boundary `docs/roadmap/long_term_vision.md`'s Confidence Rating Design
  Guidance already draws for Evidence Quality and Consensus: "design
  guidance for the future `knowledge-engine-ai` layer, not a formula
  `core` implements." `core`'s job is only to make a revision event
  representable and queryable (`relationships_for_claim` already returns
  it, filterable by `relationship_type == "supersedes"`); weighting how
  much revision frequency should lower a confidence score is a judgment
  call for the layer that computes confidence, not the layer that stores
  evidence.

## Decision: Tracking the Unknown -- an unconfirmed-claims report, not a gap-inference engine

**A "gap" `core` can honestly report, without guessing, is a claim with
zero relationship edges of any type** -- no `supports`, `contradicts`,
`qualifies`, `contextualizes`, or `supersedes` edge touches it. That is a
real, structural fact the graph already stores (`relationships_for_claim`
returns an empty list), not an inference about what evidence "should"
exist. It means exactly one thing, stated precisely: no second claim has
been reviewed and explicitly related to this one yet -- not "this
finding is wrong," not "this area is under-researched," just "no human
judgment has connected this claim to any other yet."

Rationale for scoping it this narrowly:

- `docs/founding_vision.md`'s Addendum names "missing experiments, weak
  evidence areas, and unanswered questions" as the target -- all three
  require judgment about the *state of the science*, not just the state
  of this graph, which is explicitly out of Phase 4's scope (see
  `docs/phase4_design.md`'s Mission: "not where judgment about what a
  claim means gets added"). A claim with zero relationship edges is a
  fact about `core`'s own review coverage, a legitimate and useful
  signal on its own, without overreaching into claiming it means
  anything about the science itself.
- This is deliberately the same posture `ke graph-relationship-candidates`
  (M49) already established for a related but distinct question:
  M49 answers "which claim pairs share a concept and have no
  relationship yet" (a candidate for a human to *create* a link);
  this report answers "which claims have no relationship at all,
  regardless of whether a shared-concept candidate exists" (a
  work-queue of what has not been reviewed yet). Both are structural
  counts over the same `graph_claim_relationships` table; neither
  infers or ranks scientific importance.
- A future, richer notion of "weak evidence area" -- e.g. grouping by
  `research_question` text and reporting which questions have only one
  claim total -- needs the same `--evidence <file>` join
  `relationship-report` already requires (`graph_claims` has no
  `research_question` column, deliberately -- see Prerequisite above).
  Real, buildable, and named here as the natural next slice, not
  bundled into this milestone's schema change.

## Architecture

Two small, additive changes, no new tables:

1. **`graph_claim_relationships.relationship_type` CHECK constraint**
   widens from `('supports','contradicts','qualifies','contextualizes')`
   to `('supports','contradicts','qualifies','contextualizes','supersedes')`.
   A new schema version bump (`CURRENT_SCHEMA_VERSION` in
   `knowledge_engine/database.py`), mirroring every prior additive schema
   change in this project.
2. **`_validate_relationship_records`'s `relationship_type` allow-list**
   (`knowledge_engine/cli.py`) widens the same way, so `ke
   relationship-validate`/`ke relationship-report`/`ke graph-build` all
   accept `supersedes` records without any other code change --
   `get_or_create_relationship_edge`, `relationships_for_claim`, and `ke
   graph-report`'s claim-mode rendering already handle an arbitrary
   `relationship_type` string generically.

No change to `ke graph-relationship-candidates` (M49): it already
excludes any pair with an existing edge regardless of type, so a
`supersedes` edge is already correctly treated as "a human has already
made a call here."

## Testing Strategy

- `_validate_relationship_records` accepts a `supersedes` record and
  rejects an still-invalid type string (e.g. `"invalidates"`), mirroring
  the existing four-type test coverage in `tests/test_cli.py`.
- `GraphRepository.get_or_create_relationship_edge` accepts
  `relationship_type="supersedes"` (the `CHECK` constraint no longer
  rejects it) and continues to reject a bogus type, mirroring
  `test_get_or_create_relationship_edge_rejects_invalid_type`.
- `ke graph-build`/`ke graph-report`/`ke graph-relationship-candidates`
  CLI tests exercise a `supersedes` relationship end to end: build a
  graph from two claims linked by a `supersedes` `RelationshipRecord`,
  confirm `ke graph-report --evidence-record-id` renders it under the
  new claim's Relationships section, and confirm `ke
  graph-relationship-candidates` excludes the pair.

## Open Questions (owner decisions, not resolved here)

- **Whether `supersedes` should be directional-only or allow a
  "mutual revision" shape** (two claims each superseding parts of the
  other, e.g. a later trial confirming some findings and revising
  others). Not attempted here -- the real corpus has zero
  `RelationshipRecord`s of any type today, so there is no real case to
  design a more complex shape against yet; a single directional edge is
  the minimal correct model until a real case appears that needs more,
  matching this project's "don't build for a hypothetical" discipline.
- **The actual Stability sub-score formula** (how supersession-chain
  length, recency of the most recent supersession, and whether a
  supersession was itself later superseded should combine into a 0-100
  number). Explicitly the future `knowledge-engine-ai` layer's decision,
  per the Confidence Rating Design Guidance boundary above -- not
  `core`'s to guess.
- **Grouping claims by `research_question` for a richer "weak evidence
  area" report.** Real, buildable, named above as the natural next
  slice -- not scoped here, since it needs its own real-corpus check of
  how consistently `research_question` text actually matches across
  independently-authored `EvidenceRecord`s (free text, not a controlled
  field) before designing a grouping strategy, the same "verify before
  design" step M45's term-extraction fix already went through for a
  structurally similar problem.
- **Whether an unconfirmed-claims report should also cross-reference
  M49's `graph-relationship-candidates` output** (e.g. flagging a claim
  as "unconfirmed, but N same-concept candidates exist" vs. "unconfirmed,
  no candidates found at all"). A real, useful refinement once both
  reports have real corpus volume to combine meaningfully -- not
  attempted in this design's first slice.

## Potential Risks

- **Near-zero real data to exercise this against.** With 2
  `EvidenceRecord`s and 0 `RelationshipRecord`s in the real corpus today,
  `supersedes` and the unconfirmed-claims report will have essentially
  nothing to show on first real run -- a Phase 2 promotion-throughput
  fact, not a defect in this design, exactly as `docs/phase4_design.md`'s
  own "Claim-node sparsity" risk already named for the rest of the
  graph.
- **A `supersedes` edge is easy to author incorrectly** (pointing the
  wrong direction, or asserting supersession where `contradicts` would
  be more accurate). No new safeguard beyond what already exists for
  every other relationship type: `ke relationship-validate`'s referential
  checks and a human-written `rationale` a reviewer can read back via `ke
  relationship-report`/`ke graph-report`. Not a new risk this design
  introduces.
