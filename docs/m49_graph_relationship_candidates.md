# M49 Phase 4: ke graph-relationship-candidates

## Purpose

`docs/phase4_design.md`'s Open Questions named **automated relationship
candidate-surfacing** as real, worthwhile future work: PICO-overlap or
citation-based candidate pairs a human confirms, rather than composes
from scratch when authoring a `RelationshipRecord`. It was explicitly
not attempted in the first Phase 4 slice, since it needs
`graph_claims`/`graph_claim_concepts` to exist to compute overlap
against -- M46 built those. M49 builds the deferred feature: `ke
graph-relationship-candidates`.

## What it does

Reads the graph's existing `graph_claim_concepts` edges and surfaces
every pair of claims that share at least one concept (by default),
along with the concepts they share. A pair already linked by a
validated `graph_claim_relationships` edge, in either direction, is
excluded -- a human has already made that call for it.

**This command never infers, detects, or suggests a relationship.** It
reports structural overlap only -- which claims share a PICO-resolved
concept -- exactly the same boundary `ke relationship-validate`'s own
docstring already draws ("Never infers or detects a relationship...
Deciding whether a relationship actually holds remains a human judgment
call"). Whether two claims actually support, contradict, qualify, or
contextualize each other, and why, stays entirely a human decision,
authored as a `RelationshipRecord` and checked with `ke
relationship-validate` exactly as before. The report's own "Scope"
section states this explicitly, mirroring `ke graph-report`'s existing
practice of stating what a report is and is not.

`--min-shared-concepts <n>` (default 1) raises the bar for what counts
as a candidate pair -- useful once a corpus has enough claims that
single-concept overlap (e.g. two claims that both merely mention
"obesity" as a population) produces too many low-signal pairs to be
useful. `--output <path.md>` writes the report to a file instead of the
console, through the same `_validate_output`/`_write_output` helpers
every other output-producing command uses (symlink-safe by
construction, not a hand-rolled check).

## What was added to GraphRepository

**`relationship_candidates(minimum_shared_concepts=1)`** -- for every
pair of claims sharing at least `minimum_shared_concepts` concepts (via
any edge role), returns `(claim_a, claim_b, shared_concepts)`, sorted by
shared-concept count descending, then claim ID. Implemented in Python
over two small in-memory maps (`concept -> claim ids`, `pair -> shared
concept ids`) built from one `graph_claim_concepts` query, rather than a
SQL self-join -- the real corpus's claim/concept counts are small (M46:
2 claims from today's 2 validated `EvidenceRecord`s) and the Python
approach is easier to verify shares no relationship-inference logic.
Pairs already present in `graph_claim_relationships` (checked via a
`frozenset({source_claim_id, target_claim_id})` set, so either edge
direction excludes the pair) are filtered out before returning.

## Markdown-escaping discipline

Concept labels and evidence record IDs are escaped through the same
local `_graph_report_text` helper `ke graph-report` already uses --
collapses whitespace and escapes Markdown-structural characters so a
concept label can never forge a report heading. No new escaping logic
was written; this reuses the existing helper unchanged.

## Live verification against the real corpus

Run against a copy of the real local corpus database, after `ke
graph-build --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl`
(the repo's 2 validated `EvidenceRecord`s):

- `ke graph-relationship-candidates` (default `--min-shared-concepts 1`)
  correctly surfaces exactly one candidate pair --
  `ev-glp1-step5-body-weight-week104-001` and
  `ev-glp1-gao-meta-analysis-body-weight-001` -- sharing 2 concepts
  (`semaglutide`, `placebo`), matching `ke graph-report
  --evidence-record-id`'s own per-claim concept detail for both records.
- `ke graph-relationship-candidates --min-shared-concepts 3` correctly
  reports 0 candidate pairs, since the real pair shares only 2 concepts
  -- confirming the threshold filter is applied, not merely accepted and
  ignored.
- `--output <path.md>` writes the same content to a file.

## What is deliberately not built yet

- **No PICO-role-aware scoring.** A pair sharing a concept via matching
  `intervention` edges is treated identically to a pair sharing it via
  one `population` edge and one `outcome` edge -- both count as "1
  shared concept." Distinguishing "same drug studied" from "the outcome
  concept in claim A happens to equal the population concept in claim
  B" would be a real, worthwhile refinement, but needs real corpus data
  with more than 2 claims to design against meaningfully, matching this
  project's established "verify against real data before writing new
  logic" discipline.
- **No citation-based candidate pairs.** `docs/phase4_design.md`'s Open
  Question also named citation-based candidates (two claims whose
  papers cite each other) alongside PICO-overlap ones. Not attempted
  here -- a claim is evidence-record-scoped and a citation edge is
  paper-scoped, and the two don't share a join key in the schema today
  (the same `graph_claims` has no `paper_id` column limitation `ke
  graph-report`'s own "what is deliberately not built yet" section
  already named). Left for a dedicated follow-up once that join is
  scoped.
- **No entity-resolution/deduplication awareness.** `docs/phase4_design.md`'s
  "Concept-node duplication across sources" risk (the same real-world
  concept appearing as two distinct `graph_concepts` rows) means a real
  candidate pair could be missed if two claims' matching concepts were
  never deduplicated into one row. Not addressed here -- this command
  reports what the graph's existing rows say, the same posture `ke
  graph-report` already takes.
