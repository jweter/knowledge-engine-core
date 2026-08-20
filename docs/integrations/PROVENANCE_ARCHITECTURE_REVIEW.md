# Provenance Architecture Review

## Purpose
Evaluate external provenance-first RAG architecture patterns for Knowledge Engine without importing another system's domain model or weakening Knowledge Engine's existing evidence, legal-use, and review boundaries.

Primary reference: `kamuma03/Provenance`.

## Why this matters
Knowledge Engine already treats provenance as a first-class requirement. The next maturity step is to make every generated claim traceable to stable source identity and, where technically available, to a precise page/span/region rather than only a document-level citation.

## Integration posture
**Reference architecture first.** Do not add Provenance as a runtime dependency by default.

Knowledge Engine should own:
- source/document identity;
- canonical claim/evidence models;
- legal-use status;
- review state;
- citation rendering;
- scientific confidence semantics;
- persistence schema.

Reusable ideas to evaluate:
- page/span/bounding-box evidence identity;
- retrieval traces that survive reruns;
- critic/verifier stages after answer generation;
- refusal when available evidence is insufficient;
- graph + vector retrieval as independent evidence channels;
- explicit trace metadata for every answer.

## Proposed target model
```text
source document
  -> stable document identity
  -> parsed blocks/spans
  -> retrieval candidates
  -> claim candidate
  -> supporting evidence spans
  -> verifier/critic result
  -> final answer or refusal
```

## Phase 1: architecture comparison
1. Inspect Provenance's citation, evidence-span, and verifier data flow.
2. Map those concepts to current Knowledge Engine source, parser, retrieval, and evidence structures.
3. Identify concepts that are missing versus concepts already solved internally.
4. Record only conceptual gaps; do not copy source code.

## Phase 2: canonical evidence-span contract
Define a Knowledge Engine-owned evidence locator capable of representing, where available:
- document/source ID;
- page number;
- normalized text span offsets;
- bounding box/region;
- parser/provider and version;
- content hash;
- extraction timestamp/run ID;
- confidence/quality warnings.

The contract must degrade gracefully when a parser cannot provide coordinates.

## Phase 3: retrieval trace
Add or extend a machine-readable trace that records:
- query;
- retrieval candidates;
- ranking scores;
- selected evidence;
- rejected evidence where useful;
- generated claims;
- final cited spans.

Trace data must be diagnostic/provenance data, not a substitute for scientific review.

## Phase 4: verifier experiment
Prototype a verifier that answers a narrow question: **does the selected evidence materially support the generated claim?**

The verifier must be allowed to return `unsupported`, `ambiguous`, or `insufficient_evidence`. It must never manufacture supporting evidence.

## Acceptance criteria
- A generated claim can be traced to stable source identity and precise evidence locations where available.
- Re-parsing or parser replacement cannot silently relink citations to different text.
- Missing coordinate support degrades capability explicitly rather than fabricating locations.
- The verifier can refuse unsupported claims.
- No external project's object model becomes a persisted Knowledge Engine contract.

## Non-goals
- importing another complete RAG stack;
- replacing Knowledge Engine retrieval wholesale;
- making LLM verifier output equivalent to human scientific review;
- bypassing legal-use or provenance gates.

## Rollback
All provenance enhancements must be additive behind Knowledge Engine-owned interfaces. Existing document-level citations remain available until the span-level path is proven reliable.