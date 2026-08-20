# Core Interface Contract

## Purpose

`docs/roadmap.md`'s Release Milestones name `v0.6.0` as the point where
`core`'s output becomes "a consumable interface (not new reasoning logic
in `core` itself) so the separately versioned `knowledge-engine-ai`
package can begin its own reasoning experiments on top of it." This
document is that contract, written early rather than after the fact: what
a future layer (`knowledge-engine-ai`, `knowledge-engine-graph`,
`knowledge-engine-web`, or anything else) needs to know to configure
itself against `core` and consume what `core` produces, without reading
`core`'s own source to reverse-engineer it.

It is a description of what already exists, not a new design. Every
schema, command, and config value below is implemented and tested today.
Where something is explicitly unstable or likely to change before v1.0,
that is called out rather than hidden.

## The seam: what `core` decides, what it deliberately does not

`core` locates, validates, and persists evidence. It never decides what
that evidence means for a person's *actual* question. Concretely, `core`
never sets or infers:

- A person's own real `research_question` -- inherently supplied by
  whoever is asking it, not derivable from a paper's own text.
- Any confidence *rating* beyond the existing free-text `confidence_note`
  field -- see `docs/roadmap/long_term_vision.md`'s Confidence Rating
  Design Guidance. `core`'s job is to make the per-record quality signals
  (study design, sample size, recency, limitations) available; computing
  and compounding a rating from them is explicitly the future
  `knowledge-engine-ai` layer's job.

Any consumer of `core` must supply these itself (today: a human reviewer,
via `ke extraction-review-promote`; in the future: the AI Interface
Layer). This boundary has held without exception since M19 -- see
`docs/reference_knowledge_layer_design.md`'s Addendum for the same
boundary redrawn for reference-layer content specifically.

**Revised in M52** for the Evidence Record's own `research_question`/
`evidence_direction` fields specifically: the project owner judged the
mandatory human-confirmation step for these two fields a bottleneck
disproportionate to its real accuracy benefit (every batch built by
hand through M52 read the source paper directly and classified
correctly) and explicitly authorized removing it. `ke
extraction-review-autoclassify` now provides a second, fully automated
path to a valid Evidence Record, alongside the still-available
human-authored path:

- `research_question` is generated deterministically by templating a
  draft item's own already-extracted PICO fields (M28's
  population/intervention/comparator/outcome) into a fixed sentence
  pattern -- not a person's actual research question, just a mechanical
  restatement of the paper's own PICO decomposition. A draft item is
  skipped, never guessed, when any PICO field is missing or
  implausibly long (`knowledge_engine.extraction.evidence_classification`).
- `evidence_direction` is classified deterministically, extending M18's
  self-referential framing cue patterns (`knowledge_engine.extraction.direction`)
  with additional null-result phrasing cues, and -- unlike M18 --
  defaulting to `supports` when no contrast/hedge/null cue fires. M18's
  own docstring warned that such a default would "silently assume a
  research question no one supplied"; that concern does not apply here,
  because the research question this module generates is itself
  mechanically derived from the same claim's own PICO fields, not an
  externally supplied one.
- Every automated record is honestly labeled, never hidden as if a human
  reviewed it: `extraction_method` names the automated ruleset version
  (`m52-evidence-classification-v1`, never `manual_human_review`), and
  `review_notes` states plainly that no human read or confirmed it.

This does not narrow the confidence-rating boundary above, and it does
not change what a "person's actual question" is -- an automated
record's `research_question` remains a mechanical PICO restatement, a
different and narrower thing than what a human reviewer or the future AI
Interface Layer would supply.

**Revised in M58** for the confidence-rating boundary specifically: the
project owner explicitly requested a real, live confidence-scoring
feature (`docs/evidence_intelligence_design.md`), and
`knowledge_engine/evidence_intelligence.py` now computes Evidence
Quality, Evidence Consensus, and Claim Confidence directly in `core`,
not in a separate `knowledge-engine-ai` package. This is a *location*
change, not a loosening of the seam's actual substance:

- The computation is fully deterministic (study-design tier lookup,
  relationship-edge counting, a quality x consensus product) -- no LLM,
  no statistical model, no judgment call a person did not already make
  when authoring the underlying `EvidenceRecord`/`RelationshipRecord`.
  Every number traces back to an already-stored, already-human-reviewed
  field; nothing is invented or inferred beyond what `docs/evidence_intelligence_design.md`
  specifies.
- `core` still never sets or infers `research_question`, `evidence_direction`,
  or a `RelationshipRecord` -- M58 only reads those, never writes them.
- `docs/ai_layer_architecture.md`'s own build sequence places "Evidence
  Intelligence" (Stage 3) under Phase 5 (Human Interface), "alongside
  `knowledge-engine-web`, not as a new numbered phase" -- this document's
  original "future `knowledge-engine-ai` layer's job" language predates
  that refinement, and no `knowledge-engine-ai` code exists to host the
  computation regardless, per the project owner's standing "no new
  repository yet" direction.
- What remains the future AI layer's job, unchanged: synthesizing or
  narrating what a confidence number *means* for a person's actual
  question, cross-domain profiles beyond Clinical Medicine, the
  Statistics Auditor, and Discovery Intelligence -- see
  `docs/evidence_intelligence_design.md`'s own "Explicitly out of scope"
  section.

**Revised in M69** for the "a human reviewer" clause in this section's
own opening paragraph (line 35-36): the project owner has decided that
manual human review does not scale to this project's real corpus-growth
plans and will not be relied on as the review mechanism going forward
-- see `docs/roadmap/long_term_vision.md`'s "Decision: automated
evidence review at scale (M69)" for the full reasoning. Concretely:

- "Today: a human reviewer, via `ke extraction-review-promote`" widens
  to also include a grounding-verified LLM extraction path, honestly
  labeled with its own `extraction_method` value (never
  `manual_human_review`) and never claiming a human read it.
- Line 90's "already-human-reviewed field" claim, true when M58 was
  written, no longer describes every record a caller might read --
  `manually_reviewed` in `compute_evidence_quality` narrows to mean
  "human-reviewed" specifically; a grounding-verified LLM record is a
  separate, honestly-labeled tier, not folded into that flag.
- `core`'s "never decide truth" seam is unchanged: grounding
  verification checks that extracted text traces to the source, the
  same kind of check `source_span` already enforces -- it does not
  judge whether the source itself is correct, and still never sets
  `research_question` or a confidence *rating*.

## Configuration

`core` reads settings via `knowledge_engine.config.Settings`
(`pydantic-settings`, prefix `KE_`, also reads a `.env` file in the
working directory). All fields are optional with sane defaults:

| Env var | Default | Purpose |
|---|---|---|
| `KE_PROJECT_ROOT` | current working directory | Base path other defaults resolve under. |
| `KE_DATA_DIR` | `{project_root}/data` | Where the SQLite database and corpus artifacts live. |
| `KE_DATABASE_URL` | `sqlite:///{data_dir}/knowledge_engine.sqlite3` | Full SQLAlchemy URL; set this to point `core` at a specific database file without touching the default one (e.g. a scratch DB for verification, matching this project's own established pattern for getting a clean database without deleting the default file). |
| `KE_OPENAI_API_KEY` | none | Only read by `ke embedding-generate --generator openai`. |
| `KE_CORE_API_KEY` | none | Only read by the CORE discovery source (`ke core-candidate-discover`), a third-party literature API, not related to this project's own "core" package. |
| `KE_UNPAYWALL_EMAIL` | none | Required by Unpaywall's terms of service for `ke unpaywall-doi-lookup`/`ke unpaywall-batch-lookup`. |

No other configuration surface exists. There is no config *file* format
of `core`'s own (beyond `.env`) -- the CLI and the SQLite database are the
entire interface.

## Data access: two supported paths

**1. The SQLite database directly**, at `resolved_database_url` above.
Read access via SQLAlchemy or any SQLite client is safe for read-only
consumption. `core` uses a lightweight, additive migration model (a
`schema_versions` table; see `docs/technical_debt.md`'s "Lightweight
migrations only" entry) -- schema changes are additive pre-1.0, but the
table layout itself is not yet a versioned, published contract. A
consumer reading the database directly should expect to track `core`
schema changes by watching `CHANGELOG.md`, not assume long-term column
stability before v1.0.

**2. The portable corpus-library snapshot** (`ke corpus-library-export`/
`ke corpus-library-import`, M27) -- a single `.sqlite3` (or `.gz`-
compressed) file containing paper-intrinsic content (title, authors,
abstract, full text, pages, keywords) but deliberately *not* raw PDFs
(archived separately) or embedding vectors (cleared on import, since
`Paper.id` is only unique within one database -- see `docs/phase3_design.md`'s
Open Questions). This is the actual portable artifact: import it into a
fresh database with `ke corpus-library-import --input <file>` rather than
copying the live working database.

## The CLI is the primary API

There is no HTTP API, no RPC layer, no Python package published for
import today -- `ke <command>` is the interface. Full command list is in
`pyproject.toml`'s `[tool.poetry.scripts]` entry point
(`knowledge_engine.entrypoint:app`); the commands a consuming layer is
most likely to actually call:

**Reading what `core` has already validated:**
- `ke search <query>` / `ke answer <question>` -- lexical (FTS5) retrieval.
  Console-table output only; no `--output` option today.
- `ke vector-search --query-text <text>` -- semantic retrieval. **FAISS
  only via this command** -- `entrypoint.vector_search`/`fused_search`
  hardcode `FaissVectorIndex.load`. M33's `QdrantVectorIndex` exists and
  is tested, but is Python-only: there is no CLI backend selector wiring
  it up (`docs/phase3_design.md`'s Open Questions records this as
  deliberately not built, not an oversight). Console-table output only.
- `ke fused-search <query-text>` -- Reciprocal Rank Fusion of the two
  above. Same FAISS-only, console-only caveats apply.
- `ke evidence <records.jsonl>` / `ke evidence-report` -- read/report on
  persisted manual Evidence Records. `evidence-report` supports
  `--output <path>` and `--format markdown` (default) or `--format json`
  -- the JSON form is a structured, machine-readable sibling for a
  consumer (e.g. a future `knowledge-engine-ai` layer) that needs to
  parse retrieval + matched-evidence results programmatically instead of
  scraping Markdown or Rich console text; see
  `docs/ai_layer_architecture.md`.
- `ke evidence-map-report <map.json> --evidence <records.jsonl> --relationships
  <relationships.jsonl> --sources <sources.csv> [--output <path.md>]` -- render
  the reviewed map's stored PICO, results, limitations, citations, and
  relationships in deterministic map order. It does not parse numerical prose
  or perform synthesis.
- `ke evidence-map-grounding-verify <map.json> --evidence <records.jsonl>
  [--output <path.md>] [--force]` -- deterministic, non-LLM, non-human check
  that every numeric token in each golden-map record's `result_summary`
  (hazard ratios, confidence intervals, p-values, sample sizes) is genuinely
  present in the extracted source-PDF page text at that record's own
  `source_span.local_pdf_path`/`page_number` (resolved via the local
  database's `paper_pages`, so this command requires `ke init` to have
  populated the papers referenced by the map). Exit `1` if any record is not
  fully grounded or its source page could not be resolved, `0` otherwise. This
  is the automated review mechanism `map_status: "reviewed"` relies on (the
  project owner's 2026-08-10 decision extended M69's existing "human reading
  is not a required review gate" precedent to golden-map review) -- narrower
  than full semantic review, since it confirms a number is present in the
  source page, not that it is attached to the correct claim, and it does not
  re-derive population/comparator groupings or the contradiction assessment.
  See `knowledge_engine/golden_map_grounding.py`'s module docstring for why it
  checks numeric presence rather than reusing `verify_grounding`'s
  sentence-level near-match.
- `ke statistical-verify <statistical_inputs.jsonl> --evidence
  <records.jsonl> [--binary-inputs <binary_inputs.jsonl>] [--output <path.md>]`
  -- validate version 1 or 2 source-linked
  statistical inputs and verify the supported intervention-minus-comparator
  mean-change identity with Decimal arithmetic. Version 2 may additionally
  approximate a two-sided 95% interval from explicit arm standard errors using
  the declared independent-arm normal method, critical value, sample sizes,
  and endpoint tolerance. Exit `1` on invalid inputs or an arithmetic/interval
  discrepancy. It opens no PDF or database, does not reconstruct a source
  statistical model, and does not pool effects or assess scientific validity.
  A typed numerical locator is independently reviewed and may differ from the
  Evidence Record's claim locator; normalized DOI, reviewed Evidence Record
  identity, outcome, and both source spans remain enforced.
  `--binary-inputs` adds a separate version 1 count contract: it verifies
  source-reported arm percentages, then derives a crude risk ratio and
  log-Wald interval only under an explicit correction policy. A
  source-reported adjusted measure is retained as display-only context and is
  never treated as equivalent to the crude result. Omitting the option
  preserves the continuous-only contract and output.
- `ke statistical-readiness-report <readiness_map.json> --evidence-map
  <golden_map.json> --evidence <records.jsonl> --inputs
  <statistical_inputs.jsonl> [--binary-inputs <binary_inputs.jsonl>]
  [--output <path.md>]` -- validate a curated readiness-map classification
  (`knowledge_engine/statistical_readiness.py`) against the reviewed golden
  evidence map's actual evidence-node coverage and the already-validated
  typed statistical inputs, then render a deterministic Markdown report:
  per-record readiness category and verification facets, declared
  pooling-compatibility groups and their computed `candidate`/`no`/
  `undetermined` status, and an overall
  `ready_for_pooling_design_review`/`not_ready_for_pooling_design` verdict
  with blockers. Exit `1` on any validation failure, including a golden-map
  Evidence Record with no readiness classification or a classification
  referencing an unknown/unreviewed record or input id. It never pools
  studies, performs meta-analysis, infers a missing classification, or
  determines scientific truth.
- `ke relationship-report` -- read Relationship Records. Console output
  only.
- `ke graph-report [--evidence-record-id <id> | --paper-id <id>] [--output <path.md>]`
  -- read the Phase 4 knowledge graph (M46-M51). No filter: corpus-wide
  population counts. `--evidence-record-id`: one claim's concepts and
  relationship edges. `--paper-id`: one paper's citation edges. Supports
  `--output <path.md>` (Markdown, not JSON), matching
  `evidence-report`/`relationship-report`'s own precedent.
- `ke graph-relationship-candidates [--min-shared-concepts <n>] [--output <path.md>] [--corpus <id>]`
  -- surfaces claim pairs sharing a PICO-resolved concept, for a human to
  review before authoring a `RelationshipRecord`. Structural overlap
  only: never infers, detects, or suggests a relationship type or
  rationale, the same boundary `ke relationship-validate` already draws.
  Supports `--output <path.md>` (Markdown, not JSON). Optional `--corpus
  <id>` (schema v12) restricts candidates to claim pairs where *both*
  claims carry that `graph_claims.corpus_id`; omitting it preserves the
  original cross-corpus behavior, since the graph is corpus-agnostic by
  design (see `ke graph-build`'s `--corpus` entry below). See
  `docs/history/milestones/m49_graph_relationship_candidates.md`.
- `ke relationship-review-worksheet --evidence <records.jsonl> [--min-shared-concepts <n>] [--limit <n>] [--offset <n>] [--rank-by-similarity] [--output <path.md>] [--corpus <id>]`
  (M60, `--rank-by-similarity` added M61, `--corpus` added schema v12) --
  assembles a batch of `ke graph-relationship-candidates`'s exact
  candidate pairs into one worksheet with both claims' full PICO fields
  side by side, plus a fill-in-the-blank `RelationshipRecord` JSON
  template per pair. Adds no candidate-selection logic of its own; never
  infers, scores, or suggests a relationship. `--limit` (default 10) and
  `--offset` page through a large candidate list across review sessions.
  `--rank-by-similarity` re-sorts candidates by cosine similarity of
  each pair's `outcome`/`result_summary` text, using a local, offline
  `sentence-transformers` model (M31's `SentenceTransformerEmbeddingGenerator`,
  no network access, no API key) -- ranking only, never a relationship
  judgment. `--corpus <id>` restricts to that corpus, identically to `ke
  graph-relationship-candidates --corpus`. Supports `--output <path.md>`
  (Markdown, not JSON).
- `ke graph-unconfirmed-claims [--output <path.md>]` -- lists claims with
  zero relationship edges of any type, M50's Tracking the Unknown
  decision (`docs/stability_and_tracking_design.md`). No filtering, no
  `research_question` grouping. Supports `--output <path.md>` (Markdown,
  not JSON). See `docs/history/milestones/m51_graph_unconfirmed_claims.md`.
- `ke evidence-intelligence --evidence <records.jsonl> --evidence-record-id <id> [--output <path>] [--format markdown|json]`
  (M58, `--format json` added M63) -- computes deterministic Evidence
  Quality, Evidence Consensus, and Claim Confidence for one claim, plus
  corpus-relative Evidence Coverage and a templated (non-LLM) synthesis.
  Reads the `--evidence` file for the record's own fields and the
  already-built graph for its relationship edges; never infers a
  relationship, never calls an LLM. The three confidence numbers always
  render as three separate fields, never one collapsed score. `--format
  json` is the structured, machine-readable sibling of the default
  Markdown report -- the same numbers as a JSON object (`schema_version:
  1`) instead of prose, for a consumer that needs to parse results
  programmatically (e.g. `knowledge-engine-ai`) rather than scrape text,
  the same reasoning `ke evidence-report --format json` was added for.
  `evidence_quality` includes both the backward-compatible
  `manually_reviewed` boolean and the canonical three-way
  `extraction_tier` (`manual`, `llm_grounded`, or `automated`).
  See `docs/evidence_intelligence_design.md`.
- `ke evidence-review-queue --evidence <records.jsonl> [--limit <n>] [--output <path.md>]`
  (M62) -- prioritizes automated (`m52-evidence-classification-v1`)
  evidence records for manual review by real structural signal only: a
  record already touching a relationship edge ranks above one merely
  appearing in a relationship candidate pair, which ranks above
  everything else. Never a judgment about a record's own content or
  accuracy. `--limit` (default 20). Supports `--output <path.md>`
  (Markdown, not JSON).

**Corpus-building (the pipeline a consumer generally does not re-run
itself, but may need to trigger for a specific paper):**
- `ke discovery-cycle-run` (M55, `docs/history/milestones/m55_discovery_cycle.md`): one
  schedulable cycle of discovery + deterministic adjudication + M53
  ledger cross-check, stopping before acquisition (writes a JSON
  worksheet, not an evidence artifact -- see the design doc for why).
- `ke federated-discover --query <text> --ledger-root <dir>` (FRD-1 through FRD-4/FRD-6,
  `docs/roadmap/federated_research_discovery_adoption.md`): fans one query out
  across configured discovery providers (PubMed, Crossref, OpenAlex via
  `--openalex-api-key`/`KE_OPENALEX_API_KEY`, Semantic Scholar --
  key-optional by design, `--semantic-scholar-api-key`/
  `KE_SEMANTIC_SCHOLAR_API_KEY` only raises its rate limit -- and arXiv,
  fully public and keyless), deduplicates candidates by exact DOI, and
  persists the run to `--ledger-root` before returning it. Optional
  `--output <path.json>` also saves the full result as JSON, for a
  programmatic caller (e.g. `knowledge-engine-web`) to parse instead of the
  console table -- the same "structured, machine-readable sibling" pattern
  `ke evidence-report --format json` already established. The payload is
  `federated_result_snapshot.py`'s provenance-safe composition: the query,
  deduplicated candidates with per-provider observations, the persisted
  `search_run_id`, a deterministic `coverage` block (search timestamp,
  normalized query, year bounds, per-provider limit, which providers
  completed/failed -- FRD-5/FRD-6), and a `provider_disagreements` block
  (conflicting provider-observed metadata for the same candidate, with no
  provider treated as authoritative -- FRD-5). No credentials, internal
  ledger context, or provider-native raw responses are included. A separate discovery mode from
  `discovery-cycle-run` above --
  provider-neutral and not scoped to a single corpus's adjudication rules;
  also writes no `ready_for_scope_review` worksheet and performs no
  acquisition. `ke federated-coverage-report <search_run_id> --ledger-root
  <dir>` re-fetches one persisted run's deterministic coverage facts (which
  providers completed/failed/were disabled, and why) by ID -- the reachable
  form of the "downstream AI/Web can render coverage without guessing"
  contract that document's FRD-6 exit criterion names.
- `ke citation-snowball --seeds <ids> --ledger-root <dir>` (FRD-7,
  `docs/roadmap/federated_research_discovery_adoption.md`): breadth-first
  expands `--seeds` (comma-separated provider paper/work IDs, DOIs, arXiv
  IDs, or PMIDs) through `--provider`'s public references/citations
  graph up to `--max-depth` hops (default 1, max 3), bounded by
  `--limit-per-traversal` (default 25) and `--max-candidates` (default
  100), and persists a deterministic, replayable record of the plan, every
  traversal's provider outcome, discovered candidate IDs, and citation-edge
  provenance to `--ledger-root` before returning it -- the same
  persist-before-return discipline as `federated-discover`. This is the
  first CLI surface for `citation_snowball.py`/`citation_snowball_ledger.py`;
  Semantic Scholar's own `references`/`citations`/`traverse` methods were
  already implemented and unit-tested but reachable only from a test file
  until now. Optional `--directions` (default `references,citations`) and
  `--output <path.json>` (full result: plan, traversal outcomes, discovered
  candidates with observations, and edge provenance) follow the same
  pattern as `federated-discover`. `--provider` selects the traversal
  provider: `semantic_scholar` (default, no credential required) or
  `openalex` (via `OpenAlexCitationAdapter`, requires
  `--openalex-api-key`/`KE_OPENALEX_API_KEY` -- reports itself `disabled`,
  not an error, without one, matching `OpenAlexProvider`'s existing
  federated-discover behavior). Each run traverses exactly one provider;
  `CitationSnowballDiscovery` validates every traversal's reported provider
  identity stays constant for the run.
  `ke citation-snowball-report <snowball_run_id> --ledger-root <dir>`
  re-fetches one persisted run's plan and traversal outcomes by ID,
  mirroring `federated-coverage-report`'s role for `federated-discover` and
  satisfying FRD-7's "expansion can be replayed and compared later" exit
  criterion.
- `ke federated-discover --research-question-id <id> --project-id <id>`
  (FRD-6 follow-up): `federated-discover` now also accepts optional
  `--project-id`/`--research-question-id` flags, threaded straight through
  to `FederatedDiscoveryService.search(...)` and persisted on the ledger
  record -- both were already accepted by every layer beneath the CLI
  (`FederatedSearchLedger.record`, `federated_discovery_service.py`) but,
  like `research_question_id` before this change, unreachable from the CLI.
  Neither value enters the public coverage payload
  (`SearchCoverageReport`/`--output`'s `coverage` field) -- see that type's
  own docstring. Purely additive: both flags default to `None`, so every
  existing invocation and consumer keeps its current behavior.
  `ke federated-discover-history <research_question_id> --ledger-root <dir>
  [--output <path.json>]` is a new read command: it lists every persisted
  run tagged with that `research_question_id` via
  `FederatedSearchLedger.list_by_research_question_id`, newest first, each
  rendered through the same `SearchCoverageReport` shape
  `federated-coverage-report` already exposes.
  `federated-coverage-report`/`load` are point lookups by exact
  `search_run_id`; this is the first ledger read that discovers which runs
  exist for a tracked question at all, without the caller already knowing
  their UUIDs -- the capability `knowledge-engine-web`'s WEB-FRD-5
  freshness-history design depends on. No matching runs is reported
  plainly (exit `0`), never as an error: a tracked question with no prior
  recorded search is an expected, honest state.
- `ke federated-coverage-report <search_run_id> --ledger-root <dir>
  [--output <path.json>]` (FRD-6 candidate-snapshot follow-up):
  `federated-coverage-report` now also accepts `--output`, which writes
  `{"search_run_id", "coverage": SearchCoverageReport.to_dict(), "candidates":
  [...]}` -- that run's own deduplicated candidate list (canonical ID,
  title, DOI, publication year, and every provider's full observation, the
  same shape `federated-discover --output`'s `candidates` field already
  serializes at request time), now durable in `FederatedSearchLedger` and
  re-fetchable for one specific past run by ID. This closes the point-lookup
  gap `knowledge-engine-web`'s WEB-FRD-5 freshness-history design identified
  (its design doc section 9): `federated-discover-history` above returns
  only each matched run's aggregate `SearchCoverageReport`, not any run's
  candidate list, because until now the ledger never persisted candidates at
  all -- only their count. `FederatedSearchLedger.record` now also captures
  `result.candidates` on every new run; runs persisted before this change
  have no candidate snapshot, and load with an honest empty `candidates`
  list rather than a fabricated or reconstructed one. Purely additive: the
  new `--output` flag defaults to `None` and the ledger's on-disk
  `schema_version` is unchanged (candidates is an optional field older
  records simply omit), so every existing invocation, consumer, and
  previously persisted run keeps working exactly as before.
- **`ProviderObservation` publication-status fields (FRD-5 follow-up):**
  `knowledge_engine.federated_discovery.ProviderObservation` -- and its
  ledger mirror, `federated_search_ledger.CandidateObservationRecord` --
  gained three new optional fields alongside the existing `retracted: bool
  | None`: `corrected: bool | None`, `expression_of_concern: bool | None`,
  `withdrawn: bool | None`. Each is an independent, non-exclusive flag (the
  same per-flag pattern `open_access`/`retracted`/`preprint` already
  established, not one combined status enum), following this project's
  adopted "correction, expression-of-concern, withdrawal, and retraction
  states should be modeled distinctly where provider data permits"
  direction (`docs/roadmap/federated_research_discovery_adoption.md`'s
  idea 5). `None` means "this provider did not report this flag," never an
  affirmative "false" -- the same distinction `retracted` already required
  a caller to preserve, and the reason `knowledge-engine-web`'s WEB-FRD-4
  renders a candidate's status as `"not_checked"` (zero providers reported
  it) separately from `"clear"` (at least one provider explicitly reported
  `false`), rather than defaulting a missing value to `false`. **No
  provider adapter populates these three new fields yet** -- unlike
  `retracted` (populated from OpenAlex's `is_retracted`), no currently
  configured provider transport in this repository parses a
  correction/expression-of-concern/withdrawal signal; wiring a real
  provider (e.g. Crossref's `update-to` relation types) to actually set
  them is separate, not-yet-scoped follow-up work. This change unblocks
  only the Core-side schema gap `knowledge-engine-web`'s WEB-FRD-4 and
  WEB-FRD-5 sections named explicitly ("Core's `ProviderObservation` does
  not yet carry those fields") -- it does not itself make any provider
  report a real correction/expression-of-concern/withdrawal, and
  `knowledge-engine-ai`/`knowledge-engine-web` still need their own
  changes to parse and render these fields once a provider populates them.
  Purely additive: three new fields default to `None` on both dataclasses,
  `provider_disagreement.py`'s field-order tuple gained the same three
  entries (so disagreement inspection extends to them without new code),
  the ledger's `schema_version` is unchanged, and a candidate observation
  persisted before this change loads with an honest `None` for all three
  (`_optional_bool` already returns `None` for an absent key) rather than
  a fabricated value. Every existing caller, CLI invocation, and
  previously persisted ledger record keeps working exactly as before.
- `ke corpus-import`, `ke extraction-review-generate`/`-batch-generate`,
  `ke extraction-review-annotate` (M45), `ke extraction-review-autoclassify`
  (M52, see "The seam" above), `ke extraction-review-promote`.
  These write JSONL to `--output` by design (they are pipeline steps
  producing an artifact for the next step to consume).

**Reference-layer live lookups (M41-M45, M71, M73, always background
context, see "the seam" above):**
- `ke reference-lookup` (Wikipedia), `ke rxnorm-lookup`, `ke mesh-lookup`,
  `ke pubchem-lookup`, `ke clinicaltrials-lookup <NCT_ID>` (M71,
  ClinicalTrials.gov API v2 -- trial phase, arms/interventions,
  enrollment, sponsor, and status for an NCT ID a paper cites; a
  malformed or unregistered ID reports `found: false`, never a guess),
  `ke uniprot-lookup <term>` (M73, UniProt REST API -- protein/gene
  identity, function summary, and sequence length for a term like "PD-1"
  or "GLP-1 receptor" a paper assumes its reader already knows; restricted
  to reviewed human entries, an unmatched term reports `found: false`)
  each support an optional `--output <path.json>`. `ke
  extraction-review-annotate` requires `--output` (it always writes a
  file).

**Phase 4 knowledge graph (M46-M51, see "the seam" above):**
- `ke graph-build --evidence <records.jsonl> [--relationships <records.jsonl>] [--output <path.json>] [--corpus <id>]`
  -- populates `graph_concepts`/`graph_claims`/`graph_claim_concepts`/
  `graph_claim_relationships` in the SQLite database from an already-
  validated Evidence Record file (and optional Relationship Record
  file), reusing M45's `annotate_draft_items` to resolve PICO fields into
  concept nodes. Writes to the database always; `--output` is an
  optional JSON summary of total graph row counts, not the graph data
  itself. See `docs/history/milestones/m46_graph_repository.md`. Optional
  `--corpus <id>` (schema v12, `graph_claims.corpus_id`) records which
  corpus every claim referenced by `--evidence` belongs to -- applied to
  *every* referenced claim, not just newly-created ones (an
  already-existing claim with no `corpus_id` yet is backfilled; one that
  already has a `corpus_id` is never overwritten). Omitting it leaves
  every claim's `corpus_id` exactly as it was: the graph remains
  corpus-agnostic by default, and `--corpus` is required on the same run
  for `ke graph-relationship-candidates`/`relationship-review-worksheet`
  to later scope to that corpus.
- `ke graph-citations-build [--output <path.json>]` -- populates
  `graph_citations` from every persisted paper's own reference list,
  matching cited DOIs against other papers already in this database. No
  input file and no network access (unlike `ke graph-build`). Only
  DOI-identity matches; no structured per-entry parsing -- see
  `docs/history/milestones/m47_graph_citations.md` for the real-corpus measurement that
  scoped this decision.
- `ke graph-relationship-candidates` -- read-only, no input file and no
  network access. See `docs/history/milestones/m49_graph_relationship_candidates.md`.

**Do not assume `--output` (or any machine-readable output) exists on a
command not listed above as having it.** `search`/`answer`/
`vector-search`/`fused-search` -- the four primary retrieval commands --
currently have no such option; prefer the JSONL-producing pipeline
commands above, or read the SQLite database directly, over parsing
Rich-formatted console tables, which are for humans and may reflow.

## Data schemas

### Evidence Record

The unit of validated evidence. Schema version `"0.1"`
(`EVIDENCE_SCHEMA_VERSION` in `knowledge_engine/cli.py`). Required fields
(`REQUIRED_EVIDENCE_FIELDS`):

```
schema_version, evidence_record_id, extraction_method, extraction_status,
source_doi, source_title, source_type, study_type, research_question,
claim_text, evidence_direction, population, intervention, comparator,
outcome, result_summary, source_span, limitations, uncertainty_notes,
confidence_note, provenance, created_for_milestone
```

Optional review fields (`REVIEW_EVIDENCE_FIELDS`): `review_status`
(`draft`/`reviewed`/`needs_revision`/`rejected`), `review_checklist`,
`review_notes`.

`extraction_status` is constrained to exactly two values
(`ALLOWED_EXTRACTION_STATUSES`): `draft_review_required` (every
M19-generated draft, including after promotion -- promotion never
overwrites this) or `draft_manual_prototype` (pre-M19 hand-authored
records). `source_span` is required to be a non-empty object;
`start_offset`/`end_offset` are validated together as non-negative
integers with `start_offset < end_offset` when present, and
`page_number` as a positive integer when present -- but `paper_id`
inside `source_span` is **not** enforced by the promotion validator,
only populated by convention: M19's `build_draft_evidence_item` always
sets it, but a hand-authored or externally-supplied Evidence Record can
pass validation without it. Do not assume `source_span.paper_id` is
present; check for it.

A record only becomes real evidence via `ke extraction-review-promote`,
which validates with `_validate_evidence_record` (the same validator `ke
evidence-validate` runs) and refuses any record missing
`research_question`/`evidence_direction` -- see "the seam" above. There
is no way to bypass this validation from the CLI. Note that `promote`
itself has never checked *who or what* filled those two fields, only
that they are present and well-formed -- it accepts a record from `ke
extraction-review-autoclassify` (M52's automated path) exactly as
readily as one a human reviewer typed by hand.

### Relationship Record

Typed links between two Evidence Records. Required fields
(`REQUIRED_RELATIONSHIP_FIELDS`):

```
schema_version, relationship_id, source_evidence_record_id,
target_evidence_record_id, relationship_type, rationale, provenance,
created_for_milestone
```

`relationship_type` is constrained to five values
(`ALLOWED_RELATIONSHIP_TYPES`): `supports`, `contradicts`, `qualifies`,
`contextualizes` -- reusing `evidence_direction`'s own vocabulary rather
than a separate one (M24) -- plus `supersedes` (M50: a newer claim
explicitly revising an older one, the Stability Score revision-event
mechanism; see `docs/stability_and_tracking_design.md`). Validated with
`ke relationship-validate`, which also checks referenced
`evidence_record_id`s exist when an `--evidence` file is supplied.

### Draft evidence item (pre-validation)

`ke extraction-review-generate`/`-batch-generate`'s output --
*intentionally incomplete*, never itself a valid Evidence Record. Same
field set as an Evidence Record's `to_dict()` output
(`knowledge_engine/extraction/evidence_items.py`), plus an
`extraction_context` object carrying the M17/M18 audit trail (matched
signal, framing, matched cue, rules versions) a reviewer needs to judge
the extraction without re-deriving it. `research_question`/
`evidence_direction`/`uncertainty_notes`/`confidence_note`/`provenance`
are always `null`; `study_type`/`limitations`/PICO fields are populated
when M26/M28's deterministic extraction detects them, `null` otherwise --
never guessed.

If M45's `ke extraction-review-annotate` has run, each item additionally
carries `reference_context` -- see below.

### Reference-layer lookup results (M41-M44)

Every lookup source returns a JSON object with the same shape family:
`term`, `found` (bool), source-specific identity/definition fields (all
`null` when `found: false`), `source_url`, `license`, `retrieved_at`.
Source-specific fields:

- **Wikipedia** (`ReferenceLookupResult`, M41): `title`, `description`
  (short), `extract` (longer summary paragraph), `page_type` (including
  `"disambiguation"`), `revision`, `permanent_url`,
  `page_last_modified`.
- **RxNorm** (`RxNormLookupResult`, M42): `rxcui`, `name`, `term_type`,
  `synonym`, `ingredients` (list of `{rxcui, name}` -- compare this, not
  `rxcui`, to recognize a brand name and its generic as the same drug).
- **MeSH** (`MeshLookupResult`, M43): `mesh_id`, `heading`, `scope_note`,
  `synonyms` (list).
- **PubChem** (`PubchemLookupResult`, M44): `cid`, `title`, `iupac_name`,
  `molecular_formula`, `molecular_weight`, `smiles`.

All four: never evidence, never routed through Evidence Record promotion,
never merged into `core`'s own search commands. `license` is a
human-readable string describing real, verified provenance (see each
milestone's own doc for the exact basis) -- not machine-parseable, and
deliberately not run through `license_rules.py`'s CC-family pattern
(which governs the separate paper corpus only).

### `reference_context` (M45)

Added to a draft evidence item by `ke extraction-review-annotate`. An
object with keys `intervention`/`comparator`/`population`/`outcome`,
each either `null` (nothing to look up) or one of the RxNorm/MeSH shapes
above plus a `source` key (`"rxnorm"` or `"mesh"`). See
`docs/history/milestones/m45_extraction_review_annotate.md` for what "found" actually means
here (a single matched candidate word, not the whole raw field) and its
real cost profile (roughly a minute or more of network calls per real
paper).

### Corpus source metadata (`sources.csv`)

The curated overlay a corpus directory (e.g.
`data/corpora/glp1_weight_loss/`) carries alongside the database, one row
per included/excluded paper:

```
source_id, title, authors, publication_year, venue, doi, pmid, arxiv_id,
other_identifier, source_url, pdf_url, local_path, access_date,
license_type, license_url, usage_status, inclusion_status,
inclusion_reason, exclusion_reason, expected_content_hash, source_type,
study_type, population, intervention, comparator, outcome_notes, notes
```

`inclusion_status`/`inclusion_reason`/`exclusion_reason` are the human
audit trail for why a paper is or is not in the corpus.
`license_type`/`license_url` record the CC BY/CC0 basis
`license_rules.py`'s `ALLOWED_LICENSE_PATTERN` requires for inclusion.
**Known gap, not yet built** (see `docs/roadmap.md`'s M14 corpus-growth
section): this file records only current inclusions, not a durable
ledger of previously-rejected records, so a consumer building its own
duplicate/exclusion tracking should not assume absence from this file
means "never considered."

## Versioning and stability

Nothing here is published under semantic versioning yet (`core` is
`0.2.0a1`). Treat as stable now: the Evidence/Relationship Record field
sets and their `ALLOWED_*` enums (changing these is a breaking schema
change and would be called out loudly in `CHANGELOG.md`); the CLI command
names and their `--output` JSON shapes for the commands listed above.
Treat as likely to evolve before v1.0: the raw SQLite table layout (no
long-term column-stability guarantee pre-1.0, per
`docs/technical_debt.md`); exact wording of `license`/error-message
strings (never parse these; use the structured fields).

Each extraction stage's own rules version is stamped into its output for
traceability, not for consumers to branch on:
`SECTION_DETECTION_RULES_VERSION` (`m16-section-detection-v2`),
`CLAIM_CANDIDATE_RULES_VERSION` (`m17-claim-candidate-v1`),
`CLAIM_FRAMING_RULES_VERSION` (`m18-claim-framing-v1`),
`DRAFT_EVIDENCE_ITEM_RULES_VERSION` (`m19-draft-evidence-item-v1`),
`STUDY_DESIGN_RULES_VERSION` (`m26-study-design-v3`),
`PICO_EXTRACTION_RULES_VERSION` (`m28-pico-v5`),
`EXTRACTION_REVIEW_ANNOTATE_RULES_VERSION` (`m45-extraction-review-annotate-v2`).
A future re-run with a bumped ruleset is never automatic (M25) -- a human
decides when to re-invoke extraction for a given paper.

## What does not exist yet

- No structured per-entry citation parsing (author/title/journal/year) --
  `graph_citations` (M47, `ke graph-citations-build`) exists and is
  populated, but only via DOI-identity matching against papers already in
  the corpus, not full reference-entry extraction; see
  `docs/history/milestones/m47_graph_citations.md` for the real-corpus measurement that
  scoped this decision (three real citation styles found, but only 5
  intra-corpus edges exist, which does not justify the larger build).
- No Neo4j or other dedicated graph backend -- the graph lives in the
  same SQLite database as everything else, behind `GraphRepository`,
  mirroring Phase 3's FAISS-before-Qdrant sequencing.
- No HTTP/RPC API -- the CLI and direct SQLite/corpus-library access are
  the only interfaces.
- No published Python package -- importing `knowledge_engine` modules
  directly from another repository is possible today (it is plain
  Python) but not a supported, versioned interface; go through the CLI.
- No formal confidence rating of any kind -- see "the seam" above.
