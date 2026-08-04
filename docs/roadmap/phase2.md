# Phase 2: Evidence Records

Phase 2 converts source documents into traceable Evidence Records. Its
deterministic extraction foundation, page/span provenance, review tooling, and
grounding-verified automated PICO follow-up are implemented.

The detailed design and historical implementation record are maintained in
`docs/phase2_design.md` and `docs/roadmap.md`. M15 added page/span provenance;
M16-M28 built the deterministic extraction pipeline; later milestones exercised
it at corpus scale; M69 and its bounded cross-page follow-up grounded 108 of the
118-record automated-review backlog and deliberately left 10 unsupported
records untouched.

## Delivered Foundation

- Extract claims, methods, results, limitations, and evidence markers.
- Preserve source text spans for every extracted structure.
- Add review, validation, and provenance workflows without making mandatory
  human reading the only scaling mechanism.
- Track uncertainty and evidence quality separately from source metadata.

## Current Direction

- Independently review the implemented
  [provisional GLP-1/body-weight evidence map](../glp1_body_weight_golden_evidence_map.md),
  then address its explicit post-discontinuation, safety, population, agent,
  and contradictory-evidence gaps before marking it reviewed.
- Evaluate retrieval and cross-study behavior against golden questions.
- Preserve the no-synthesis boundary in core while exposing deterministic,
  inspectable inputs to the web and AI layers.

## Principle

The Knowledge Engine should never decide truth. It should organize evidence,
show disagreement, expose uncertainty, and preserve links back to sources.
