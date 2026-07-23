# Phase 2 Design: Evidence Records

Status:
This is the Phase 2 design sketch, written before any Phase 2 implementation
milestone. It plays the same role for Phase 2 that
`docs/m6_phase1_corpus_ingestion_plan.md` played for Phase 1: it turns the
four-bullet goal statement in `docs/roadmap/phase2.md` into an
implementation-ready architecture, sequencing, and open-question list. See
`docs/roadmap.md` for how this fits the overall roadmap and
`docs/vertical_slice.md` for the historical manual evidence-record prototype
this phase supersedes with automated extraction.

M15 (issue #89, PR #90, merged) implemented this design's foundation
prerequisite: page/span-level extraction provenance (`ParsedPaper.pages`, the
`paper_pages` table), plus the evidence-record validator and renderer fixes
described below. M16 (issue #91, PR #92, merged) implemented deterministic
structured-section detection (`knowledge_engine.extraction.detect_sections`)
— the first piece of the Extraction Layer. M17 (issue #94, PR #95, merged)
implemented deterministic claim-candidate sentence detection
(`knowledge_engine.extraction.detect_claim_candidates`) within `results`/
`conclusion` sections, using a conservative quantitative/comparative signal
match — the second piece of the Extraction Layer. M18 (issue #98, PR #99,
merged) implemented deterministic claim framing-cue classification
(`knowledge_engine.extraction.classify_claim_framing`) — the third piece of
the Extraction Layer. M18 deliberately does not implement the schema's
`evidence_direction` field: that field is defined relative to a
`research_question` (see `docs/vs7_manual_evidence_record.md`'s worked
example), which a claim candidate does not have. M18 instead classifies only
how a candidate's sentence frames itself relative to prior work the text
itself references (`contextualizes`/`contradicts`/`qualifies`), leaving most
candidates `unclassified` rather than guessing a supports-equivalent label.
M19 (issue #101, PR #102, merged) implemented draft extraction review-item
generation (`knowledge_engine.extraction.build_draft_evidence_items`) — the
first piece of the Evidence Layer. A `DraftEvidenceItem` populates every
field with an honest deterministic source (`claim_text`, `result_summary`,
`source_span` — including the paper's `paper_id`, so a DOI-less paper's
offsets stay traceable, since title alone is not a unique identity in this
repository — `source_doi`/`source_title` from the paper, `source_type`,
`extraction_method`, `extraction_status`) and leaves every field requiring
real judgment or external input (`research_question`, `evidence_direction`,
PICO fields, `study_type`, `limitations`, `uncertainty_notes`,
`confidence_note`, `provenance`) explicitly `None`. It is not a valid
`EvidenceRecord` and is confirmed to fail the existing validator's checks
until a reviewer completes it.
M20 (issue #104, PR #105, merged) added the `ke extraction-review-generate` CLI
command, wiring M16-M19 into an actually runnable pipeline for the first
time: given a persisted paper's `--paper-id`, it runs section detection,
claim-candidate detection, framing classification, and draft-item
generation, then writes the results to a JSONL review queue at `--output`.
A separate, opt-in command — never invoked by `corpus-import` — resolving
this design's open question about how extraction should be triggered. A
paper with zero persisted pages produces an explicit diagnostic, never a
silently empty result.
M21 (issue #107, PR #108, merged) added the `ke extraction-review-promote` CLI
command, closing the extraction-to-evidence loop for the first time: it
promotes reviewer-completed draft items (M20's JSONL output, after a human
has filled in `research_question`/`evidence_direction`/etc.) into real
`EvidenceRecord` rows, reusing `_validate_evidence_record` unchanged as the
sole correctness gate and adding zero new judgment logic. Administrative
fields a promotion tool owns (`schema_version`, a deterministic
`evidence_record_id`, default `review_status`/`review_checklist`/
`review_notes`) are filled in automatically; an incomplete record is never
promoted. Promotion is idempotent and append-only.
M22 (issue #110, PR #111, merged) added the `ke paper-pages-backfill` CLI
command, closing the M15 "Known gap" below exactly as originally scoped in
issue #89: papers imported before M15 have zero `paper_pages` rows and
cannot be extracted at all. Backfill re-parses a paper's still-present
original local PDF and persists the result only once its freshly computed
`content_hash` matches the paper's already-persisted one -- a mismatch or
a missing source file is reported, never silently skipped or trusted.
`research_question` acquisition, real research-question-relative
`evidence_direction` classification, PICO extraction, a synthesized
confidence rating, and the Relationship Layer are explicitly out of scope
for `core` -- they belong to the future `knowledge-engine-ai` layer; see
`docs/roadmap/long_term_vision.md`'s AI Interface Layer section.

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
- `ke evidence-validate`, `ke evidence`, `ke answer --evidence`, and
  `ke evidence-report` accept automatically extracted records without a schema
  migration, because those records satisfy the same field contract as manually
  authored ones. Their *rendering* must change (see Renderer Changes below) —
  confirmed by inspection, every current renderer hardcodes a "manual" label
  regardless of `extraction_method`'s actual value (for example
  `ke answer --evidence` prints the literal string `"Extraction method:
  manual"` rather than reading the field), which would misrepresent automated
  records as manual if left as-is.
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

## Prerequisite: Page/Span-Level Extraction Provenance (implemented)

`docs/technical_debt.md` already identified this gap: "Page-level extraction
provenance is not yet retained... Phase 2 evidence extraction will need
citations back to source pages or stable text spans... add page-level
extraction identity before Phase 2 claim/evidence work."

Confirmed directly in `knowledge_engine/parser.py`: `PyMuPDFParser.parse`
computed `page_texts` per page internally, then immediately collapsed them
into one document-level `raw_text = "\n\n".join(page_texts)` and discarded the
page boundaries. `ParsedPaper` only ever stored `page_count` (an integer) and
the two joined text blobs (`raw_text`, `body_text`) — there was no way to
recover which page, or what character offset within that page, any substring
of the stored text came from.

This was fixed before any extraction logic was written, because every
extracted claim or evidence record requires a `source_span` field (already
part of `REQUIRED_EVIDENCE_FIELDS` in `knowledge_engine/cli.py`) that names an
exact, reproducible location in the source document. Building extraction on
top of document-level text only would have forced `source_span` to be a page
number at best, which is not precise enough for a reviewer to find the
sentence a claim came from in a multi-page paper.

Implemented:

- `ParsedPaper` gained a `pages: list[ParsedPage]` field (`ParsedPage` =
  `page_number` + normalized per-page `text`). `PyMuPDFParser` now normalizes
  each page individually instead of normalizing the whole joined document at
  once; `raw_text` is the join of each page's own normalized text (skipping
  pages that normalize to empty), which is mathematically equivalent to the
  prior single-pass normalization — verified by a dedicated regression test
  reproducing the old formula against a real multi-page fixture including a
  blank page.
- Span identity: page number plus character offset range within that page's
  own `text`. Because a page's `text` is exactly its contribution to the
  joined `raw_text`, an offset computed against one page's text needs no
  separate global-to-page offset mapping.
- Persistence decided: page text is **persisted**, in a new `paper_pages`
  table (`PaperPage` model, keyed by `(paper_id, page_number)`), not
  recomputed on demand. Recomputing would make extraction depend on the
  original local PDF still being present, which is not guaranteed — PDFs are
  gitignored, kept outside the repository, and (per the M14 rehearsal
  runbook's own artifact-hygiene rules) are treated as ephemeral working
  files, not permanent storage. Persisting evidence rather than re-deriving
  it on demand also matches this project's established pattern for import
  runs, manifest snapshots, and acquisition receipts.
- Adding a new table exposed a real, previously-latent bug in
  `knowledge_engine/database.py`'s `migrate_schema`: it called
  `_verify_expected_tables` (which raises if any table registered in the ORM
  metadata is absent) *before* `Base.metadata.create_all`, for any database
  already past schema version 0. Every prior schema change only added
  columns (which `create_all` cannot do, hence the existing
  `_migrate_schema_v2`/`_v3` `ALTER TABLE` functions), so this ordering had
  never been exercised against a brand-new table before. Fixed by tracking
  which schema version introduces each new table
  (`_TABLES_INTRODUCED_AT_VERSION`) and exempting only those tables — not
  every table — from the pre-creation check, so a table that is missing
  because it is legitimately new is still created silently, while a table
  missing because it was actually dropped or corrupted still raises rather
  than being silently recreated as empty. Confirmed with dedicated tests for
  both cases.

**Known gap, found by Codex automated review, deliberately not fixed in this
milestone (resolved by M22, see Status above)**: `paper_pages` is only
populated going forward, by `PaperRepository.add_parsed_paper`. A paper
imported before this migration has zero page rows after upgrading, and
cannot simply be re-imported to backfill them — `papers.source_path`/`doi`/
`content_hash` uniqueness rejects a repeat import of the same file. This
matches how every prior additive schema change in this codebase works
(v2/v3 added columns that start empty for pre-existing rows and are
populated only by new operations going forward), but with one real
difference: a genuine backfill *is* possible for `paper_pages` specifically
(re-parse the paper's original local PDF, since the same per-page normalization
logic in `PyMuPDFParser` is deterministic), but only as long as that PDF file
is still present — and it may not be, since local PDFs are treated as
ephemeral working files throughout this project, not permanent storage.
M22's `ke paper-pages-backfill` command implements exactly this: locating
papers with a still-present source file, re-parsing, upserting page rows,
and reporting which papers could not be backfilled. `PaperPage`'s docstring
documents that extraction logic must treat an empty `pages` list as "no
page provenance available," not assume every paper has one -- true for any
paper whose source file is no longer present, even after backfill runs.

This prerequisite was Phase 2's first concrete milestone. Automated claim and
evidence extraction cannot be reviewed for correctness — reviewers cannot
check "does this span actually say what the claim says" — without it.

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
  -> ke evidence / ke evidence-validate / ke evidence-report /
     ke answer --evidence commands (validator and renderer changes above
     already applied; no further schema change needed for extraction output)
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
  was held for review. **Correction**: no fixed vocabulary for this field is
  established anywhere in the codebase yet (see Validator Changes below) — a
  closed enum should be defined once real extraction logic determines what
  states it actually needs, not invented speculatively here.
- `source_span`: an object compatible with the existing manual-record shape
  (`local_pdf_path`, `page_number`, `section`, `table_or_figure`,
  `locator_note`), with `page_number` set from the `PaperPage` provenance
  added by this milestone's prerequisite. A future milestone may add a
  precise offset range within that page once extraction logic needs one.
- `population`, `intervention`, `comparator`, `outcome`, `result_summary`,
  `limitations`, `uncertainty_notes`: populated only when the deterministic
  extraction rule found explicit textual evidence for that field; left blank
  rather than guessed, matching the "never invent unsupported metadata"
  principle already enforced throughout the M14 manifest-curation pipeline.
- `review_status`: automated records default to `draft`, identical to the
  existing manual-record default, so the existing review workflow applies
  without a schema change.

## Validator Changes (implemented)

Confirmed by inspection of `_validate_evidence_record` in
`knowledge_engine/cli.py`: `REQUIRED_EVIDENCE_FIELDS` only required that
`source_span` and `extraction_status` be *present* (`missing_fields = sorted(
required_fields - record.keys())`); neither field's content was validated.
`source_span` was never checked for type or shape, so a record with
`source_span: null` or an arbitrary string passed `ke evidence-validate`.
`extraction_status` had no content check at all, not even the non-empty-string
check every sibling field (`extraction_method`, `claim_text`, etc.) already
had.

Fixed directly (not deferred to a later milestone, since both were needed to
make the Success Criteria above true rather than aspirational):

- `extraction_status` was added to the existing non-empty-string validation
  loop, matching `extraction_method`'s existing check. **Correction to an
  earlier draft of this design**: that earlier draft proposed validating
  `extraction_status` against an "accepted/held/rejected" vocabulary by
  analogy to M14's adjudication `decision` field. Direct inspection of the
  real evidence-record data (`data/corpora/glp1_weight_loss/evidence_records.jsonl`)
  showed this was unfounded — the only value ever used is the literal string
  `draft_manual_prototype`, and no accepted/held/rejected vocabulary exists
  anywhere for evidence records. Inventing a speculative enum before real
  extraction logic defines meaningful states would risk exactly the kind of
  unsupported-metadata invention this project holds itself against elsewhere;
  a plain required-non-empty-string check is the honestly-scoped fix for this
  foundation milestone. A closed vocabulary (mirroring `ALLOWED_REVIEW_STATUSES`)
  can be added once real extraction status values are defined.
- `source_span` must now be a non-empty JSON object (catches the `null` case
  directly), and if it contains a `page_number` key, that value must be a
  positive integer. This was also more grounded than originally drafted: real
  evidence records (again confirmed against `evidence_records.jsonl`) already
  store `source_span` as an object with `page_number`, `section`,
  `table_or_figure`, and `locator_note` keys — not the bare page/offset shape
  first sketched above. The `page_number` check is compatible with both the
  existing manual shape and the `PaperPage.page_number` provenance added by
  this milestone; a stricter offset-range check can be added once extraction
  logic defines how it populates that value.

## Renderer Changes (implemented)

Confirmed by inspection: every evidence renderer in `knowledge_engine/cli.py`
hardcoded a manual-only label rather than reading `extraction_method`.
`ke evidence` appended the literal suffix `" (manual)"` after the field value
and ended with "This is manually extracted evidence."; `ke answer --evidence`
printed the unconditional literal string `"Extraction method: manual"` — not
even interpolating the field; and `ke evidence-report` labeled every row
`"#### Manual Evidence Record"` and appended `" (manual)"` to the
extraction-method line. Left unmodified, this would have directly violated
this design's own requirement that automated and manual records "remain
visibly distinct by `extraction_method`" — every automated record would have
displayed as manual.

All three renderers (and the shared evidence-preview helper `ke answer
--evidence` uses) now display the record's actual `extraction_method` and
`extraction_status` values instead of a hardcoded label, and the fixed
disclaimer text no longer asserts every record was manually extracted
(`ke evidence`'s closing line now reads "Extraction method and status are
recorded per record above."; `ke evidence-report`'s header is `"#### Evidence
Record"`, not `"#### Manual Evidence Record"`). Renderer-only change — no
schema or validator change was required for this part.

## Extraction Methodology (decided)

**Decision: option 3 combined with option 1** — structured-section heuristics
(locate methods/results/limitations sections by heading pattern) narrowing
input to option 1's rule-based/pattern-matching extraction within each
section. No new dependency. Decided by the project owner after weighing this
design against `docs/roadmap/long_term_vision.md`, which separates
`knowledge-engine-core` (document ingestion and local source vault) from a
distinct future `knowledge-engine-ai` package (reasoning, synthesis, and
evidence summaries) in the wider ecosystem plan. Extraction that stays fully
rule-based and auditable line-by-line — the same standard this project already
holds itself to for adjudication rules such as `ADJUDICATION_RULES_VERSION` —
belongs in `core`; anything that would blur into statistical or model-based
"reasoning" is deliberately deferred to that separate future package rather
than adopted here as a starting assumption.

The accepted tradeoff is weaker recall than a classical NLP pipeline would
give: real papers do not always phrase results in a fixed pattern, so this
approach will miss claims a statistical model would catch. This mirrors how
Phase 1 started with one bounded 500-paper rehearsal rather than the full
literature — start narrow and prove correctness before considering a richer
approach as a separately authorized enhancement, not a starting requirement.

All three options originally considered, for reference:

1. **Pure rule-based / pattern matching** (regex and sentence-structure
   heuristics, no new dependency). Fully deterministic and easiest to audit
   line-by-line, but the weakest recall — many real claims do not follow a
   fixed sentence pattern. **Adopted**, narrowed by option 3 below.
2. **Classical NLP pipeline** (for example spaCy, optionally with a
   scientific-text model such as scispaCy). Still fully deterministic given a
   fixed model version and fixed input — no generative or probabilistic
   "reasoning" step — but adds a real dependency with its own model-download
   and licensing footprint, which needs review against this project's offline
   -by-default and supply-chain-conscious posture (see `docs/adr` precedent
   for how the PMC Cloud Service migration was evaluated). **Deferred**; not
   ruled out permanently, but requires separate authorization later.
3. **Structured-section heuristics** (locate methods/results/limitations
   sections by heading pattern, then apply narrower rule-based extraction only
   within each section). May substantially improve precision on the
   well-structured papers this project's obesity/metabolic-disease corpus
   favors (randomized trials, systematic reviews). **Adopted**, combined with
   option 1.

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
- Validator tests confirming the new `source_span`/`extraction_status` checks
  correctly accept well-formed automated records and reject malformed ones
  (see Validator Changes).
- Renderer tests confirming `ke evidence`, `ke answer --evidence`, and
  `ke evidence-report` display an automated record's real `extraction_method`
  and do not print a manual-only disclaimer for it (see Renderer Changes).

No test fixture should assert that a scientific claim is true; only that
extraction located and categorized it correctly.

## Open Questions

Resolved during the foundation milestone: whether page/span text is persisted
or recomputed (persisted, see Prerequisite section), and which extraction
methodology to use (rule-based combined with structured-section heuristics,
see Extraction Methodology section). Resolved in M20: automated extraction
runs as a separate, opt-in command (`ke extraction-review-generate`),
analogous to `ke metadata-preview`, never as part of `ke corpus-import` — so
an extraction issue can never affect import success/failure semantics.
Remaining:

- What allowed-value vocabulary should `extraction_status` use once real
  extraction logic defines meaningful states, and should it be enforced with
  an `ALLOWED_...` set the same way `review_status` is? (see Validator
  Changes — deliberately left unconstrained for now, beyond non-empty-string)
- Should a stricter `source_span` check requiring a character-offset range
  (not just `page_number`) be added once extraction logic defines how it
  populates one?
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
