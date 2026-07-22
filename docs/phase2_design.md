# Phase 2 Design: Evidence Records

Status:
This is the Phase 2 design sketch, written before any Phase 2 implementation
milestone. It plays the same role for Phase 2 that
`docs/m6_phase1_corpus_ingestion_plan.md` played for Phase 1: it turns the
four-bullet goal statement in `docs/roadmap/phase2.md` into an
implementation-ready architecture, sequencing, and open-question list. No
extraction code exists yet. See `docs/roadmap.md` for how this fits the
overall roadmap and `docs/vertical_slice.md` for the historical manual
evidence-record prototype this phase supersedes with automated extraction.

## Mission

Phase 2 turns Knowledge Engine Core from a document-ingestion system into a
system that can identify evaluable scientific statements inside imported
papers, link every statement back to the exact source text it came from, and
represent how statements from different papers agree, conflict, or qualify
each other — without ever deciding which statement is true.

## Principle

Restated from `docs/roadmap/phase2.md`: the Knowledge Engine should never
decide truth. It should organize evidence, show disagreement, expose
uncertainty, and preserve links back to sources. This principle governs every
design decision below. Concretely, it means Phase 2 extraction must be
deterministic and inspectable — the same input produces the same output, and a
reviewer can see exactly which rule or pattern produced a given claim — not a
generative or probabilistic judgment about what a paper means.

## Goals

- Extract claims, methods, results, limitations, and evidence-quality markers
  from parsed paper text.
- Preserve an exact, stable source-text span for every extracted structure, so
  any claim can be traced back to the sentence or passage it came from.
- Represent typed relationships among claims and evidence (supports,
  contradicts, qualifies, contextualizes), reusing the vocabulary already
  established in the manual evidence-record prototype.
- Track uncertainty and evidence quality as separate, explicit fields, never
  folded into a single confidence score.
- Add optional human review workflows on top of automated output, reusing the
  existing `review_status` / `review_checklist` / `review_notes` fields.

## Success Criteria

- A contributor can run automated extraction against an imported paper and get
  zero or more claim/evidence records with source-span citations.
- Every extracted record can be traced back to an exact page and text offset
  in the original parsed document.
- Automated extraction never silently overwrites a manually authored evidence
  record; the two remain visibly distinct by `extraction_method`.
- Extraction failures and low-confidence/ambiguous passages are recorded as
  explicit review-required output, not silently dropped and not silently
  accepted.
- The existing `ke evidence`, `ke evidence-validate`, `ke evidence-report`, and
  `ke answer --evidence` commands work unmodified against automatically
  extracted records, because those records satisfy the same schema as manually
  authored ones.
- Tests cover extraction happy paths, ambiguous/no-match text, and malformed
  parser input, using synthetic fixtures — no scientific claim in a test
  fixture is asserted to be true or false, only that it was correctly located
  and categorized.

## Out of Scope

- LLM-based extraction, summarization, or reasoning of any kind.
- Scientific synthesis, consensus calculation, or confidence scoring beyond
  the existing low/medium/high/unknown human-readable rationale fields.
- Embeddings, vector search, or a knowledge graph database (Phases 3 and 4).
- Automated truth determination or claim verification against external
  databases.
- A web interface or public API (Phase 5).
- Modifying the parser's PDF-extraction library or algorithm; Phase 2 only
  needs the parser to retain page/span boundaries it already computes
  internally and currently discards (see Prerequisite below).

These follow the same non-goal boundary the manual vertical-slice prototype
already established and that `docs/roadmap/phase2.md`'s principle requires.

## Prerequisite: Page/Span-Level Extraction Provenance

`docs/technical_debt.md` already identifies this gap: "Page-level extraction
provenance is not yet retained... Phase 2 evidence extraction will need
citations back to source pages or stable text spans... add page-level
extraction identity before Phase 2 claim/evidence work."

Confirmed directly in `knowledge_engine/parser.py`: `PyMuPDFParser.parse`
computes `page_texts` per page internally, then immediately collapses them
into one document-level `raw_text = "\n\n".join(page_texts)` and discards the
page boundaries. `ParsedPaper` only ever stores `page_count` (an integer) and
the two joined text blobs (`raw_text`, `body_text`) — there is currently no
way to recover which page, or what character offset within that page, any
substring of the stored text came from.

This must be fixed before any extraction logic is written, because every
extracted claim or evidence record requires a `source_span` field (already
part of `REQUIRED_EVIDENCE_FIELDS` in `knowledge_engine/cli.py`) that names an
exact, reproducible location in the source document. Building extraction on
top of document-level text only would force `source_span` to be a page number
at best, which is not precise enough for a reviewer to find the sentence a
claim came from in a multi-page paper.

Proposed minimum fix, scoped narrowly to this prerequisite and not the
extraction logic itself:

- Extend `ParsedPaper` (or add a sibling structure) to retain per-page text
  alongside the existing document-level `raw_text`/`body_text`, so page
  boundaries survive parsing.
- Define a stable, reproducible span identity — page number plus character
  offset range within that page's text is the simplest option that needs no
  new dependency.
- Decide whether page/span text is persisted (a new table, keyed to
  `papers`) or recomputed on demand from the stored PDF at extraction time.
  Persisting avoids re-parsing but grows the database; recomputing keeps the
  schema smaller but makes extraction depend on the original PDF file
  remaining available, which is not guaranteed once local PDFs are pruned.
  This is an open question below, not decided here.

This prerequisite is Phase 2's first concrete milestone. Automated claim and
evidence extraction cannot be reviewed for correctness — reviewers cannot
check "does this span actually say what the claim says" — until it exists.

## Architecture

Phase 2 adds an Extraction Layer above the existing Parser and below the
existing Evidence Layer, reusing the vocabulary already defined by the manual
evidence-record prototype rather than inventing a parallel one:

```text
Parser (extended with page/span provenance)
  -> Extraction Layer (new)
       deterministic claim candidates + source spans
  -> Evidence Layer (schema already exists; currently manual-only)
       EvidenceRecord rows satisfying the existing REQUIRED_EVIDENCE_FIELDS
       contract, with extraction_method identifying the automated rule/pattern
       that produced them instead of "manual"
  -> Relationship Layer (new)
       typed support/contradiction/qualification links between evidence
       records, reusing the direction vocabulary already used by manual
       records (supports, contradicts, qualifies, contextualizes)
  -> existing ke evidence / ke evidence-validate / ke evidence-report /
     ke answer --evidence commands, unmodified
```

The Reasoning Layer (synthesis, consensus, confidence scoring, human-readable
answers) described in `docs/vertical_slice.md` remains explicitly out of
scope for Phase 2, exactly as it was for the manual prototype.

## Extraction Model

An extraction pass over one parsed paper should produce zero or more claim
candidates, each becoming an `EvidenceRecord`-shaped row when it passes
deterministic quality gates, or a recorded review-required outcome when it
does not.

Reusing rather than duplicating the existing schema in
`knowledge_engine/cli.py`:

- `extraction_method`: set to a specific, versioned automated-extraction
  identifier (for example `rule_based_v1`), never a bare `"automated"`, so a
  reviewer can always tell exactly which deterministic ruleset produced a
  given record — mirroring how `ADJUDICATION_RULES_VERSION` versions M14's
  license-adjudication rules.
- `extraction_status`: whether the extraction succeeded, partially matched, or
  was held for review, reusing the accepted/held/rejected vocabulary already
  established across the M14 pipeline rather than a new one.
- `source_span`: the page/offset identity from the prerequisite above.
- `population`, `intervention`, `comparator`, `outcome`, `result_summary`,
  `limitations`, `uncertainty_notes`: populated only when the deterministic
  extraction rule found explicit textual evidence for that field; left blank
  rather than guessed, matching the "never invent unsupported metadata"
  principle already enforced throughout the M14 manifest-curation pipeline.
- `review_status`: automated records default to `draft`, identical to the
  existing manual-record default, so the existing review workflow applies
  without a schema change.

## Extraction Methodology (open question, not decided here)

This is the largest undecided question in this design and should not be
settled without the project owner's input, because it is a real architectural
fork with different dependency, accuracy, and maintainability tradeoffs:

1. **Pure rule-based / pattern matching** (regex and sentence-structure
   heuristics, no new dependency). Fully deterministic and easiest to audit
   line-by-line, but the weakest recall — many real claims do not follow a
   fixed sentence pattern.
2. **Classical NLP pipeline** (for example spaCy, optionally with a
   scientific-text model such as scispaCy). Still fully deterministic given a
   fixed model version and fixed input — no generative or probabilistic
   "reasoning" step — but adds a real dependency with its own model-download
   and licensing footprint, which needs review against this project's offline
   -by-default and supply-chain-conscious posture (see `docs/adr` precedent
   for how the PMC Cloud Service migration was evaluated).
3. **Structured-section heuristics** (locate methods/results/limitations
   sections by heading pattern, then apply narrower rule-based extraction only
   within each section). Can be combined with either option above and may
   substantially improve precision on the well-structured papers this
   project's obesity/metabolic-disease corpus favors (randomized trials,
   systematic reviews).

No option here uses an LLM or any generative model, consistent with the
project-wide non-goal. The choice is about how much deterministic linguistic
tooling to add, not whether to add AI reasoning.

## Testing Strategy

Following the same pattern already used for M14's synthetic candidate
fixtures rather than requiring real copyrighted papers:

- Unit tests for the span-provenance extension using small generated PDFs or
  synthetic `ParsedPaper` fixtures with known page boundaries.
- Deterministic extraction-rule tests: given a fixed input sentence, assert
  the exact claim/evidence fields produced, exactly like `candidate_review.py`
  tests assert exact adjudication outcomes for fixed license strings.
- Ambiguous/no-match tests: text that should produce zero claims or an
  explicit review-required outcome, not a low-confidence guess.
- Malformed/adversarial input tests: text that could crash a naive parser
  (unusual whitespace, embedded control characters, extremely long lines).
- CLI/schema tests confirming automated records pass the existing
  `ke evidence-validate` unmodified.

No test fixture should assert that a scientific claim is true; only that
extraction located and categorized it correctly.

## Open Questions

- Should page/span text be persisted in a new table, or recomputed on demand
  from the stored local PDF at extraction time? (see Prerequisite section)
- Which extraction methodology should the first milestone implement: pure
  rule-based, a classical NLP pipeline, structured-section heuristics, or a
  combination? (see Extraction Methodology section — requires a decision
  before implementation begins)
- Should automated extraction run as part of `ke corpus-import`, or as a
  separate opt-in command analogous to `ke metadata-preview`, so extraction
  failures can never affect import success/failure semantics?
- What is the minimum viable relationship vocabulary for the Relationship
  Layer, and should it be constrained to a fixed enum from the first
  milestone (as `evidence_direction` already is) or allowed to grow?
- Should extraction be versioned and re-run against already-imported papers
  when the ruleset changes, similar to how `ADJUDICATION_RULES_VERSION`
  changes trigger a fresh M14 discovery run? If so, does this need an
  `extraction_runs`/`extraction_items` persistence pattern analogous to
  `import_runs`/`import_items`?
- How should automated and manual evidence records for the same claim be
  reconciled if both exist — treated as independent corroborating records, or
  should one supersede the other for display purposes?

## Potential Risks

- Extraction that looks confident but silently mis-locates a span, breaking
  the traceability guarantee that is this project's core safety property.
- Treating a classical NLP model's output as more authoritative than it is,
  drifting toward the "AI decides truth" outcome this phase is explicitly
  designed to avoid.
- Expanding scope into synthesis or confidence scoring before extraction and
  span provenance are proven correct, mirroring the exact risk M12's
  rehearsal design flagged for scale work ("expanding into performance
  optimization before collecting evidence").
- Adding a new NLP dependency without evaluating its maintenance and
  supply-chain posture, the same category of risk flagged for M11's metadata
  providers.
- Building the extraction schema as a parallel structure instead of extending
  `REQUIRED_EVIDENCE_FIELDS`, fragmenting the evidence model the manual
  prototype already established and breaking the existing `ke evidence*`
  command family.
