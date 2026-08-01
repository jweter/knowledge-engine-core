# M51 Phase 4: ke graph-unconfirmed-claims

## Purpose

`docs/stability_and_tracking_design.md` (M50) resolved *what* an honest,
non-inferred "gap" means for `core` to report: a claim with zero
relationship edges of any type. That document only made the decision;
this milestone builds the read-only command that surfaces it -- the
first concrete slice of `docs/founding_vision.md`'s Addendum, "Tracking
the Unknown," to actually ship.

## What it does

`ke graph-unconfirmed-claims` lists every claim in the graph that no
`supports`/`contradicts`/`qualifies`/`contextualizes`/`supersedes` edge
touches, as source or target. Nothing else: no `--evidence` file, no
research-question grouping, no severity ranking. Purely a display layer
over `GraphRepository.unconfirmed_claims`, which itself is a plain
outer-join count over `graph_claim_relationships` -- no new judgment
logic, no heuristic about what "should" have evidence.

The report's own Scope section states precisely, and only, what a listed
claim means: no second claim has been reviewed and explicitly related to
it yet. Not "this finding is weak." Not "this area is
under-researched." Just: `core`'s own review coverage hasn't reached
this claim yet. It also points a reader at `ke
graph-relationship-candidates` (M49) -- a claim that shows up in *both*
reports (unconfirmed, and sharing a concept with another claim) is a
concrete, actionable place for a human reviewer to look first, though
this command deliberately does not compute or highlight that overlap
itself (see What is deliberately not built yet).

## What was added to GraphRepository

**`unconfirmed_claims()`** -- an outer join from `graph_claims` to
`graph_claim_relationships` (matching either `source_claim_id` or
`target_claim_id`), filtered to rows where the join found nothing.
Mirrors `relationships_for_claim`'s own source-or-target `OR` condition,
just inverted into a set-level query instead of a per-claim lookup.

## Live verification against the real corpus

Run against a copy of the real local corpus database, after `ke
graph-build --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl`
(the repo's 2 validated `EvidenceRecord`s, no relationships yet):

- `ke graph-unconfirmed-claims` correctly lists both real claims
  (`ev-glp1-step5-body-weight-week104-001`,
  `ev-glp1-gao-meta-analysis-body-weight-001`) as unconfirmed --
  matching the real, measured fact that the corpus has zero
  `RelationshipRecord`s today.
- After building one real `supports` relationship between the two
  claims (`ke graph-build --relationships <file>`), a second run of `ke
  graph-unconfirmed-claims` correctly reports zero unconfirmed claims.

## What is deliberately not built yet

- **No `--evidence`-joined `research_question` grouping.** `docs/stability_and_tracking_design.md`'s
  own Open Questions named this as the natural next slice for a richer
  "weak evidence area" report, but flagged it as needing its own
  real-corpus check of how consistently `research_question` free text
  actually matches across independently-authored `EvidenceRecord`s
  before designing a grouping strategy -- not attempted here, exactly as
  that document scoped it.
- **No cross-reference with `ke graph-relationship-candidates`'s own
  output.** A claim that is both unconfirmed *and* has a same-concept
  candidate pair available is a stronger, more actionable signal than
  either report alone -- named as a real refinement in
  `docs/stability_and_tracking_design.md`'s Open Questions, deferred
  until both reports have real corpus volume to combine meaningfully.
- **No severity or priority ranking among unconfirmed claims.** Every
  claim is listed with equal weight, in claim-ID order; deciding which
  gaps matter most is exactly the kind of judgment about the state of
  the science this milestone's Mission draws the line against.
