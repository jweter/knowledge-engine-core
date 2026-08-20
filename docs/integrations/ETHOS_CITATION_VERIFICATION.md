# Ethos Citation Verification Integration Plan

## Purpose
Evaluate citation-verification ideas from `docushell/ethos` for a future Knowledge Engine claim-to-source validation layer.

## Boundary
Ethos is an architectural/reference candidate first. Knowledge Engine must continue to own source identity, claim/evidence records, review status, and user-facing citation semantics.

## Target capability
For every answer claim with a citation, Knowledge Engine should be able to ask:
1. Does the cited source still resolve to the same content?
2. Can the cited region be located deterministically?
3. Does that region contain evidence relevant to the claim?
4. Is the evidence strong enough to support the wording used?
5. Has parsing or source drift invalidated the citation?

## Phase 1: fingerprinting and staleness study
Compare Ethos-style document/citation fingerprints against existing Knowledge Engine content hashes and import-run identity. Define a stable citation fingerprint using Knowledge Engine-owned fields.

## Phase 2: citation-region verifier
Prototype a verifier with explicit outcomes:
- `supported`
- `partially_supported`
- `unsupported`
- `ambiguous`
- `citation_stale`
- `source_unavailable`

The verifier must return evidence and rationale metadata; a bare Boolean is insufficient.

## Phase 3: stale-citation invalidation
When document content, parser output, or canonical source identity changes, citations tied to the old representation must become stale unless a deterministic remap proves equivalence.

## Phase 4: answer gate experiment
For selected retrieval workflows, prevent a high-confidence answer from being presented as supported when the cited evidence verifier reports `unsupported`, `citation_stale`, or `source_unavailable`.

## Testing
Fixtures should include:
- exact supporting quote/region;
- source that discusses the topic but does not support the claim;
- contradictory source;
- stale parser output;
- changed PDF hash;
- same text with changed pagination;
- multiple candidate passages;
- no adequate evidence.

## Acceptance criteria
- Citation validity survives normal reruns when source content is unchanged.
- Changed source/parser authority cannot silently preserve stale citations.
- Unsupported claims are visibly downgraded or refused.
- Verification results remain separate from human scientific review.
- No external service is required for offline baseline operation unless explicitly enabled.

## Non-goals
- automatic fact truth determination from a citation alone;
- replacing expert review;
- forcing every citation through a cloud model;
- copying Ethos internals into Knowledge Engine.

## Rollback
Keep citation verification as an additive optional gate until benchmarked. Existing citations must remain readable even if the verifier is unavailable.