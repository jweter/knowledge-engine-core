# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added the `ke corpus-import` CLI command for persisted, local-only corpus imports.
- Added pre-persistence duplicate evidence decisions with exact-duplicate skipping and
  probable-match review outcomes.
- Added linked resume and retry behavior with explicit execution and review statuses.
- Added provenance-preserving metadata preview and Crossref enrichment boundaries.
- Added a controlled 100-paper rehearsal report and deterministic scale-readiness
  assessment for the next bounded corpus rehearsal.
- Added typed expected parser and duplicate-resolution failure contracts.
- Added the controlled 500-paper rehearsal report (M14, issue #21): a fresh
  import and a linked resume against the same manifest snapshot both reconciled
  exactly with zero failures, zero issues, and a fully idempotent resume,
  yielding a `PROCEED` decision.
- Added `docs/phase2_design.md`, the implementation-ready Phase 2 design
  (mirroring `docs/phase1_design.md`'s role for Phase 1): architecture,
  extraction-record schema reuse, testing strategy, and open questions for
  automated claim/evidence extraction.
- Added the M15 Phase 2 foundation (issue #89): page/span-level extraction
  provenance. `PyMuPDFParser` now normalizes text per page and
  `ParsedPaper.pages` preserves page boundaries a document-level join used to
  discard; a new `paper_pages` table persists this so a future extracted claim
  can cite an exact `(page_number, offset)` span instead of only a page count.
  `ke evidence-validate` now validates `source_span`'s shape and requires a
  non-empty `extraction_status`, and `ke evidence`/`ke answer --evidence`/
  `ke evidence-report` display each record's real `extraction_method` instead
  of a hardcoded manual label.
- Added the M16 deterministic structured-section detection (issue #91):
  `knowledge_engine.extraction.detect_sections` locates methods/results/
  limitations-style IMRAD sections within a paper's parsed pages by
  conservative heading-pattern matching (no new dependency, no statistical
  model), returning page/offset-bounded `SectionSpan` records. Sections may
  span multiple pages. A paper with no recognizable headings simply produces
  zero sections rather than a guessed default. Not yet wired into any CLI
  command or evidence-record generation -- claim extraction against these
  spans is a later milestone.
- Added the M17 deterministic claim-candidate sentence detection (issue #94):
  `knowledge_engine.extraction.detect_claim_candidates` locates candidate
  claim sentences within a paper's `results`/`conclusion` sections (from M16)
  by conservative signal matching -- a percentage, p-value, confidence
  interval, or explicit comparative phrase -- using a deterministic,
  abbreviation-aware sentence splitter (no new dependency, no statistical
  model). A sentence with no such signal is never treated as a candidate.
  Stops short of PICO extraction, evidence-direction classification, and
  `EvidenceRecord` generation, which remain later milestones.
- Added the M18 deterministic claim framing-cue classification (issue #98):
  `knowledge_engine.extraction.classify_claim_framing` classifies each M17
  claim candidate by how its sentence frames itself relative to prior work
  the text itself references -- `contextualizes`, `contradicts`, `qualifies`,
  or `unclassified` when no such cue is present. This is deliberately not the
  evidence-record schema's `evidence_direction` field, which is defined
  relative to a `research_question` a claim candidate does not have; a
  candidate is never defaulted to a supports-equivalent label absent an
  explicit cue.
- Added the M19 draft extraction review-item generation (issue #101):
  `knowledge_engine.extraction.build_draft_evidence_items` combines a claim
  candidate, its M18 framing classification, and a paper's own `paper_id`/
  `doi`/`title` into a `DraftEvidenceItem` -- the first piece of the Evidence
  Layer. Every field with an honest deterministic source (`claim_text`,
  `result_summary`, `source_span` including the paper's `paper_id` so a
  DOI-less paper's offsets are still traceable, `source_doi`, `source_title`,
  `source_type`, `extraction_method`, `extraction_status`) is populated;
  every field requiring real judgment or external input
  (`research_question`, `evidence_direction`, PICO fields, `study_type`,
  `limitations`, `uncertainty_notes`, `confidence_note`, `provenance`) is
  explicitly `None`, never a guessed placeholder. A draft item is not a
  valid `EvidenceRecord` and is confirmed to fail
  `_validate_evidence_record`'s existing checks until a reviewer completes
  it. No CLI command, JSONL writer, or schema change.
- Added the `ke extraction-review-generate` CLI command (M20, issue #104):
  runs the full deterministic Extraction Layer pipeline (M16 section
  detection, M17 claim candidates, M18 framing classification, M19 draft
  evidence items) against one persisted paper, identified by `--paper-id`
  since a paper's `doi` is nullable and `title` is not a unique identity in
  this repository, and writes the resulting draft items to a JSONL review
  queue at `--output`. A separate, opt-in command -- never invoked by
  `corpus-import` -- so an extraction issue can never affect import
  success/failure semantics, resolving an explicitly open question in
  `docs/phase2_design.md`. A paper with zero persisted pages (pre-M15, or
  the documented `paper_pages` backfill gap) produces an explicit
  diagnostic rather than a silently empty result; zero draft items from a
  paper that does have pages is a valid, clearly reported outcome.
- Added the `ke extraction-review-promote` CLI command (M21, issue #107):
  promotes reviewer-completed draft extraction items (M20's JSONL output,
  after a human has filled in `research_question`/`evidence_direction`/etc.)
  into real `EvidenceRecord` rows, closing the extraction-to-evidence loop
  for the first time. Adds zero new judgment logic -- it validates and
  persists only what a reviewer already supplied, reusing
  `_validate_evidence_record` (the same validator `ke evidence-validate`
  uses) unchanged. Administrative fields a promotion tool -- not a
  reviewer -- owns (`schema_version`, a deterministic `evidence_record_id`,
  and default `review_status`/`review_checklist`/`review_notes`) are
  filled in automatically, never overwriting a value already supplied.
  Promotion is idempotent (re-running on the same completed input does not
  create duplicate rows) and append-only (an existing `evidence_records.jsonl`
  is never overwritten or truncated). An incomplete record is never
  promoted; it is reported with the exact validation errors and the command
  exits non-zero, while any other valid records in the same input are still
  promoted.
- Added the `ke paper-pages-backfill` CLI command (M22, issue #110):
  backfills `paper_pages` rows for papers imported before M15, exactly as
  scoped in that milestone's tracked follow-up (issue #89). Re-parses a
  paper's original local PDF using the same deterministic `PyMuPDFParser`
  normalization already trusted at import time, but only persists the
  result once the freshly computed `content_hash` matches the paper's
  already-persisted one -- a mismatch (the file at `source_path` may have
  changed since import) is reported, never silently backfilled. A missing
  source file is reported with a clear reason rather than silently
  skipped, and one paper's parse failure never aborts the rest of the
  batch. Supports `--dry-run`. Idempotent: a paper that already has pages
  is never reprocessed by a repeated run.
- Constrained `extraction_status` to a closed vocabulary (M23, issue #117):
  `ke evidence-validate` now rejects any `extraction_status` value outside
  `ALLOWED_EXTRACTION_STATUSES = {"draft_review_required",
  "draft_manual_prototype"}` -- the only two values anything in this
  codebase actually produces -- instead of accepting any non-empty string.
  Also validates `source_span.start_offset`/`end_offset` when present: both
  must be given together, as non-negative integers, with
  `start_offset < end_offset`, matching how the M19 extraction pipeline
  already populates them.
- Added the Relationship Layer's first slice (M24, issue #120): a
  human-authored evidence-relationship schema and the `ke
  relationship-validate` CLI command. Reuses `evidence_direction`'s exact
  vocabulary (`ALLOWED_RELATIONSHIP_TYPES = {"supports", "contradicts",
  "qualifies", "contextualizes"}`). Validates structurally always (required
  fields, unique `relationship_id`, allowed `relationship_type`, no
  self-referential links, non-empty `provenance`) and, when an `--evidence`
  file is given, validates referentially (both endpoints of a relationship
  must actually exist in that evidence file; a dangling reference is
  reported, never silently accepted). Automated relationship detection is
  explicitly not implemented -- `core` validates a human-supplied
  relationship's shape, never decides or suggests one itself.
- Added `extraction_runs` persistence (M25, issue #123): `ke
  extraction-review-generate` now records a durable row per invocation
  (`paper_id`, `output_path`, page/section/candidate/draft-item counts, and
  all four extraction-stage rules versions) in a new schema-version-5
  `extraction_runs` table, so a paper's extraction history can be found
  without re-reading every JSONL file the command has ever produced. `core`
  never automatically re-runs extraction on a ruleset-version change -- a
  human decides when to re-invoke the command for a given paper. No new
  `extraction_items` table: each draft item's own JSONL row already carries
  its full rules-version context, so a second database copy of the same
  data would only duplicate it.
- Added the M26 deterministic study-type classification and limitations
  extraction (issue #129): `knowledge_engine.extraction.study_design`
  classifies a paper's own stated study design (randomized controlled
  trial, meta-analysis, systematic review, cohort/case-control/
  cross-sectional/pilot/observational study) from an explicit cue in its
  Abstract or Methods section, and extracts a paper's own stated
  limitations from an explicit "Limitations" heading. Both are the first
  slice of deterministic, non-human-typed PICO-adjacent extraction (see
  `docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed Fields
  section) -- paper-intrinsic facts, not judgment relative to a research
  question, extracted the same conservative way M17/M18 extract claims: a
  missing signal produces `None`, never a guess. Wired into `ke
  extraction-review-generate`, which now populates `study_type` and
  `limitations` on every generated draft item when detected. Bumps the
  database to schema version 6: `extraction_runs` gains a fifth rules-version
  column, `study_design_rules_version`, alongside the four M25 added, and
  each draft item's own `extraction_context` gains the same field, so a
  future study-design ruleset revision doesn't leave `study_type`/
  `limitations` provenance unrecorded at either the run or item level.
- Added the M27 corpus-library snapshot (issue #133): `ke
  corpus-library-export --output <path>` copies a local database's
  paper-intrinsic content -- `papers`, their `paper_pages`/`paper_texts`,
  and the `journals`/`authors`/`keywords` they reference -- into a fresh,
  standalone SQLite file, deliberately excluding operational tables
  (`import_runs`, `extraction_runs`) that describe one machine's own
  history rather than the corpus itself. `ke corpus-library-import --input
  <path>` hydrates a local database from a snapshot; a paper whose
  `content_hash` already exists locally is skipped, so importing the same
  or an overlapping snapshot twice is idempotent, and
  journals/authors/keywords are matched by their existing natural unique
  key rather than duplicated. This exists because the working SQLite
  database is gitignored (large, environment-specific, and every session
  in this project's remote execution environment starts from a fresh
  clone), so nothing downloaded and parsed today would otherwise survive
  past the current session -- see `docs/roadmap.md`'s "Scaling beyond 500
  papers for Phase 2 tuning" section.
- Added the `ke-corpus-pdf-backup` CLI command and `docs/corpus_pdf_backup.md`:
  a skip-existing bulk backup of local corpus PDFs to the allowlisted
  `source_documents.pdf` Google Drive folder, addressing the same
  gitignored-PDFs-don't-survive-the-session gap as the corpus-library
  snapshot above, for the raw PDFs themselves. Authorizes with a
  service-account JSON key (never committed, kept outside the repository)
  exchanged for a short-lived `drive.file`-scoped OAuth token via a
  hand-rolled JWT-bearer flow (`knowledge_engine.google_drive_service_account`,
  using `cryptography` for RS256 signing) rather than the full
  `google-api-python-client`/`google-auth` SDKs, matching
  `google_drive_http.py`'s existing minimal-dependency Drive transport.
  Reuses the existing `ConstrainedDriveAdapter` for destination-ancestry and
  upload-readback verification and adds a new paginated
  `GoogleDriveHttpTransport.list_files` method; a local PDF is skipped only
  when its filename and SHA-256 both already match a Drive file, so a
  changed file with the same name is re-uploaded rather than silently
  skipped. One file's upload failure does not abort the run; the command
  uploads everything it can and reports failures in its summary.
- Grew `data/corpora/glp1_weight_loss/sources.csv` by 81 records (the first
  small automated discovery batch, `retstart=0`, toward the project owner's
  "at least a couple thousand papers" target -- 84 initially accepted, 3
  later held once a v7 adjudication-ruleset fix corrected a pediatric-scope
  gap) and committed the first
  `data/corpus_library/obesity_metabolic_disease_library.sqlite3` snapshot
  (84 papers total, including the pre-existing prototype rows) produced by
  `ke corpus-library-export`.
- Grew `sources.csv` by another 72 records (the second discovery batch,
  `retstart=250`, under the v7 pediatric-scope ruleset from the start; the
  v8/v9 correction-notice and co-occurrence rules landed afterward and this
  batch was re-adjudicated under v9, holding 1 further correction-notice
  record; a further single record, a persistent-hiccups case report whose
  abstract named type 2 diabetes only as an incidental unrelated
  comorbidity, was manually excluded after Codex review flagged it, since
  v9 deliberately reverted the automated same-sentence co-occurrence rule
  that would otherwise have caught it) and refreshed the corpus-library
  snapshot (156 papers total; a follow-up correction PR then manually
  excluded a second incidental-comorbidity false positive found by
  applying the same review to the already-merged `retstart=0` batch,
  leaving 155 papers -- see the `### Fixed` entry below).
- Grew `sources.csv` by another 86 records (the third discovery batch,
  `retstart=500`, fully under the v9 ruleset). Proactively screened all 90
  automatically accepted records for the incidental-comorbidity
  false-positive pattern (a single-patient case report whose abstract
  names a target disease term only as unrelated patient background) before
  acquisition, since v9 has no automated rule for it; found and manually
  excluded 3 further matches (TB peritonitis in a dialysis patient with
  diabetes, S. hominis endophthalmitis in a diabetic patient, and
  immune-checkpoint-inhibitor toxicity in a bladder-cancer patient with
  chronic kidney disease and diabetes -- in each case the disease term was
  purely background, unrelated to the paper's actual intervention). A
  Codex review then caught a fourth, differently-shaped false positive: a
  basic cervical-cancer biology paper whose abstract matched only because
  it used a xenograft mouse strain literally named "non-obese diabetic
  (NOD)-SCID," unrelated to metabolic disease -- excluded, and the rest of
  the batch was re-checked for the same mouse-strain-name term collision
  (one further hit, "Experimental models in diabetes research," was
  confirmed genuinely on-topic and kept). Refreshed the corpus-library
  snapshot (241 papers total, 493 authors).
- Grew `sources.csv` by another 76 records (the fourth discovery batch,
  `retstart=750`). Applied both known false-positive screens proactively
  before acquisition (incidental-comorbidity case reports and
  NOD-SCID/mouse-strain-name term collisions); found and manually excluded
  1 incidental-comorbidity match pre-acquisition, a BCGitis case report (a
  granulomatous cystitis complication of intravesical BCG therapy for
  bladder cancer) in which type 2 diabetes was purely patient background.
  No mouse-strain-name collisions found. A Codex review then caught a
  second incidental-comorbidity record the pre-acquisition screen had
  missed because its title didn't literally say "case report" (only its
  venue, "JCEM case reports," did): an adrenal-insufficiency case report
  in which obesity was one of several incidental presenting signs,
  unrelated to the paper's actual topic (long-term high-dose
  ethinylestradiol use). Excluded it and broadened the screen to also
  check venue names. Individually re-reading every case-report-style
  accepted record in the batch (rather than relying on the title-keyword
  filter alone) found one further miss: a title that names the disease
  term directly ("Case Report: Uremia secondary to acute pyelonephritis in
  a patient with type 2 diabetes mellitus") does not guarantee the mention
  is central rather than incidental -- the patient's diabetes was
  well-controlled background, unrelated to the paper's actual topic
  (glucocorticoid-treated tubulointerstitial nephritis). Excluded it; the
  remaining two "JCEM case reports" records were confirmed genuinely
  on-topic (their titles directly name tirzepatide and semaglutide as the
  intervention) and kept. Refreshed the corpus-library snapshot (317
  papers total, 718 authors).
- Grew `sources.csv` by another 70 records (the fifth discovery batch,
  `retstart=1000`). Individually read every case-report-style accepted
  record (by title or venue) and every NOD-SCID/mouse-strain-name
  collision before acquisition, per the process established in the
  `retstart=750` batch. Found and excluded 1 incidental-comorbidity match:
  a case report on apremilast treatment for a rare skin disorder (acquired
  reactive perforating collagenosis) in which type 2 diabetes was one of
  several stable, unrelated patient comorbidities. Initially judged a type
  1 diabetes multi-omics paper (referencing "non-obese diabetic (NOD)"
  mice as a real T1D research model, not an incidental term collision) as
  on-topic and kept it -- Codex reviews on the PR then caught three
  further problems this narrower check had missed: that same T1D paper
  should have been held under `exclusion_criteria.md`'s explicit "type 1
  diabetes-specific without evidence applicable to the committed Phase 1
  scope" rule regardless of the NOD-mice question; a lymphoma
  drug-resistance study matched only because "FTO" expands to "fat mass
  and obesity-associated," a gene name unrelated to metabolic disease; and
  a rare-genetic-disease EHR mapping study whose only type-2-diabetes
  mention was one incidental example finding about an unrelated disease
  (myotonic dystrophy). Excluded all three. Net: 70 of 74 automatically
  accepted records remain. Refreshed the corpus-library snapshot (387
  papers total, 871 authors).
- Grew `sources.csv` by another 106 records (the sixth discovery batch,
  `retstart=1250`, the largest yet at 111 automatically accepted). Applied
  the full false-positive screen (case-report-style rows by title or
  venue, gene/mouse-strain-name lexical collisions, type 1
  diabetes-specific titles) before acquisition, excluding 1 case report
  whose reported intervention (vagus nerve stimulation) treated a
  coexisting condition (epilepsy) rather than the diabetes named in the
  title. A Codex review on the growth PR then flagged 3 further records as
  failing basic title-scope criteria (a quality-of-life survey with no
  treatment findings, an osteoarthritis mechanism review, and a
  contrast-media safety study with obesity as an incidental risk-factor
  mention); a full manual review of the batch prompted by that finding
  identified roughly a dozen more candidates in the same shape (drugs
  studied for unrelated diseases, analytical-chemistry method papers,
  broad mechanism-only reviews, and further incidental disease mentions).
  Per the project owner's explicit direction that this corpus-building
  phase should prioritize breadth over precision for now, only the
  clear-cut cases (the Codex-flagged 3 plus one further unambiguous
  wrong-disease match, a cancer-cachexia genetics paper matching only the
  generic English phrase "a complex metabolic syndrome" rather than the
  corpus's named disease entity) were held; the remaining borderline
  mechanism/chemistry-adjacent papers were kept. Net: 106 of 111
  automatically accepted records remain. Refreshed the corpus-library
  snapshot (493 papers total, 1117 authors).
- Grew `sources.csv` by another 112 records (the seventh discovery batch,
  `retstart=1500`; 120 automatically accepted, 1 excluded as a cross-batch
  duplicate already present from `retstart=1250`). Screened only the
  clear-cut patterns going forward (per the volume-priority direction
  above), not exhaustive gray-area sweeps: excluded 5 further records --
  4 single-patient case reports where type 2 diabetes or obesity was
  purely incidental patient background unrelated to the reported condition
  (a fungal prostatitis infection, a ciliopathy genetics case, an
  incidental angiographic finding, and uremic pericarditis/cardiac
  tamponade), and 1 type 1 diabetes-specific mechanistic study held under
  `exclusion_criteria.md`'s explicit rule. A Codex review on the growth PR
  then flagged 2 further records as failing the same clear-cut patterns: a
  COVID-19-booster/influenza mortality study where obesity and diabetes
  were only incidental comorbidities in the prediction model rather than
  the studied condition, and a childhood-obesity narrative review whose
  title's "Adult" referred to a future disease burden being projected for
  a pediatric study population, not the actual (adult) subjects. Both were
  held. Net: 112 of 120 automatically accepted records remain. Refreshed
  the corpus-library snapshot (605 papers total, 1388 authors).
- Added M28 deterministic PICO extraction
  (`knowledge_engine.extraction.pico.extract_pico`): population,
  intervention, comparator, and outcome, each the first sentence matching
  an explicit cue (a numeric cohort-size clause for population;
  received/administered/randomized to/etc. for intervention;
  versus/compared with/placebo/etc. for comparator; primary outcome/
  endpoint/etc. for outcome) within Abstract/Methods (and also Results for
  comparator/outcome). Patterns were tuned by reading a real sample of the
  605-paper `glp1_weight_loss` corpus's actual abstracts rather than
  guessed speculatively -- the corpus only reached a size the project
  owner judged sufficient for this once M14's growth loop was
  deliberately stopped. No new dependency, no LLM, and the same
  absence-over-guessing discipline as M17's claim candidates and M26's
  `study_type`/`limitations`. Wired into `ke extraction-review-generate`
  alongside M16-M26's pipeline; adds
  `extraction_runs.pico_extraction_rules_version` (schema version 7).
  Promoted M26's private, unshared section-text and heading-stripping
  helpers to `knowledge_engine.extraction.sections.section_text`/
  `section_content` so this module could reuse them exactly rather than
  risk a third divergent copy -- the same lesson the
  `ClassifiedPaperRepository` bug below had just taught.
- Added M29 `ke relationship-report`, expanding the Relationship Layer
  past M24's validate-only first slice with a pure Markdown display
  layer -- not automated detection, which remains a human judgment call
  per M24's "never decide truth" boundary. A reviewer could previously
  validate a `relationships.jsonl` file but had no way to actually read
  one, since it only stores two `evidence_record_id` strings, a type, and
  a rationale. `ke relationship-report <path> --evidence
  <evidence_records.jsonl> [--output report.md]` reuses
  `relationship-validate`'s and `evidence-validate`'s checks completely
  unchanged as the sole correctness gate, refuses to render anything if
  either file is invalid or a reference is dangling, and renders each
  relationship's type and rationale next to the `claim_text`/
  `source_title`/`source_doi`/`evidence_direction` of the two evidence
  records it links. No database change -- relationships remain
  file-only, matching how evidence records themselves have always
  worked.
- Added M30, Phase 3's first milestone: a pluggable
  `knowledge_engine.vector_search` package (`VectorIndex` interface,
  `FaissVectorIndex` local implementation, `EmbeddingGenerator` interface
  with no implementation yet) and two CLI commands,
  `ke embedding-index-build --vectors <jsonl> --index-path <path>` and
  `ke vector-search --index-path <path> --query-vector <json>`. Per
  `docs/phase3_design.md`'s option 3, no embedding-generation code exists
  yet, so these commands operate on externally-supplied vectors only --
  `embedding-index-build` parses and validates a JSONL file any external
  tool produced, referentially checks every `paper_id` against the local
  database, builds/updates the FAISS index, and persists
  `Paper.embedding_model`/`embedding_id`; `vector-search` takes an
  already-embedded query vector (not free text) and returns ranked papers
  with their real metadata, explicitly labeled "vector similarity only,
  not lexical search." Added `faiss-cpu` as a new dependency (no
  PyTorch or other heavy transitive dependency); already anticipated by
  the roadmap's "local FAISS" goal, unlike the still-open
  embedding-generation dependency decision. Free-text semantic search
  remains blocked on that decision.
- Added M31: resolved `docs/phase3_design.md`'s embedding-generation
  decision as "both". Added `SentenceTransformerEmbeddingGenerator`
  (`knowledge_engine.vector_search.local_generator`, local
  `sentence-transformers` model, default `all-MiniLM-L6-v2`, fully
  offline once weights are cached) and `OpenAiEmbeddingGenerator`
  (`knowledge_engine.vector_search.openai_generator`, OpenAI's
  `/v1/embeddings` endpoint over stdlib `urllib` -- no SDK, matching
  every other outbound HTTP client in this project -- requires
  `KE_OPENAI_API_KEY`), both implementing `EmbeddingGenerator`. Added
  `ke embedding-generate --generator local|openai --output <jsonl>`,
  which embeds each paper's title/abstract (one vector per paper) and
  writes the same vectors-file format `ke embedding-index-build` already
  consumes; M30's ingestion/build/search commands are unchanged. Added
  `sentence-transformers` as a new dependency, with PyTorch pinned to the
  CPU-only wheel index (`https://download.pytorch.org/whl/cpu`) on
  Linux/Windows rather than the default GPU/CUDA build, since this
  project runs single-machine and offline and the default build pulls in
  an unused multi-gigabyte NVIDIA CUDA toolkit; macOS resolves `torch`
  from the default PyPI index instead, since the CPU-only wheel index
  publishes no macOS wheels at all (found by a Codex review on PR #155,
  which would otherwise have blocked `poetry install` on macOS entirely).
- Added M32: `ke vector-search` now accepts `--query-text <text>
  --generator local|openai [--model <name>]` as an alternative to
  `--query-vector <json>` -- embedding a free-text query live with either
  M31 generator before searching, instead of requiring every query to be
  pre-embedded out-of-band first. Exactly one of `--query-vector`/
  `--query-text` must be given; either way the query's embedding_model is
  checked against the index's recorded embedding_model before searching.
  `ke search`/`ke answer` remain lexical-only (FTS5); combining lexical
  and semantic results into one ranked list is still a separate,
  undesigned question.
- Added M33: `QdrantVectorIndex` (`knowledge_engine.vector_search.qdrant_index`),
  the second `VectorIndex` implementation, targeting a collection on an
  operator-run Qdrant server (this project does not stand one up). The
  collection is created on first use and validated against the expected
  dimension on reuse, mirroring `FaissVectorIndex.load`'s dimension check.
  Score is squared Euclidean distance, matching `FaissVectorIndex`'s
  convention exactly -- Qdrant's own Euclidean-distance score is *not*
  squared, verified empirically against `qdrant-client`'s embedded
  local-mode client since Qdrant's own docs do not state this precisely.
  Requires an `embedding_model` identifier: every point's payload records
  it, and reusing an existing *non-empty* collection is rejected unless
  its recorded model matches -- the same embedding-model-mixing bug class
  a Codex review found in the FAISS path on PR #154, found again by a
  Codex review on PR #157 before this backend ever shipped (see Fixed
  below). Added `qdrant-client` as a new dependency (small transitive footprint:
  `grpcio`, `httpx`, `numpy`, `pydantic`, `protobuf`, `portalocker`,
  `urllib3` -- no heavy ML runtime). Tests
  (`tests/test_qdrant_index.py`) inject `qdrant_client.QdrantClient(":memory:")`
  -- the client's own embedded local mode -- so the suite exercises real
  `qdrant-client` code paths deterministically without a live server.
  Scoped to the class and its tests only; CLI wiring
  (`ke embedding-index-build`/`ke vector-search` targeting a Qdrant
  collection instead of a local FAISS file) is deliberately deferred
  until a real operator need for it appears, matching how
  `docs/phase3_design.md` already framed Qdrant support before this
  milestone.

### Changed

- Made Ruff the authoritative formatter and linter used by both developer commands
  and GitHub Actions.
- Unexpected parser and duplicate-resolution exceptions now propagate as systemic
  failures instead of being persisted as ordinary per-paper issue codes.
- Reconciled README, roadmap, and technical-debt documentation through M13 and named
  the controlled 500-paper rehearsal as the next bounded milestone.
- Migrated M14 PMC OA discovery and acquisition off the PMC OA Web Service API
  (`oa.fcgi`) and the PMC FTP Service, both of which NCBI is removing entirely in
  August 2026, onto NCBI's documented PMC Article Datasets Cloud Service (a public,
  world-readable S3 bucket reachable via ordinary unsigned HTTPS — no new
  dependency). This is a durable replacement, done ahead of the removal date,
  superseding the temporary `/pub/pmc/deprecated/` bridge added previously. See
  `docs/architecture/adr/0004-migrate-pmc-oa-acquisition-to-cloud-service.md`.
  Bumped the M14 adjudication ruleset to `m14-candidate-adjudication-v4` since the
  accepted PDF-URL host changed.
- Reconciled README documentation through M17: current phase, milestone history,
  and known issues now reflect Phase 2 progress (page/span provenance, structured-
  section detection, claim-candidate detection) instead of stopping at M14.

### Fixed

- Fixed M30's `embedding-index-build`/`vector-search` silently permitting
  vectors from different `embedding_model`s into the same FAISS index --
  L2 distance between vectors from incompatible embedding spaces is
  meaningless even at the same dimension, so this could rank unrelated
  vector spaces together and produce meaningless results. Found by a
  Codex review on PR #154. Fixed by adding a JSON metadata sidecar
  (`knowledge_engine.vector_search.index_metadata`) recording exactly
  which model built an index: `embedding-index-build` now rejects a
  vectors file mixing models, rejects updating an index with a different
  model than it was built with, and refuses to update an index missing
  its metadata sidecar entirely; `vector-search` refuses to search such
  an index and validates an optional `embedding_model` in the query file
  against it.
- Fixed M33's `QdrantVectorIndex` accepting any existing Qdrant collection
  with a matching dimension and Euclidean distance for reuse, even if it
  was populated with vectors from a different embedding model -- the same
  bug class as above, since same-dimension embeddings from unrelated
  models are common and L2 distance across them is meaningless. Found by
  a Codex review on PR #157, before this backend ever merged. Fixed by
  requiring an `embedding_model` identifier, recording it on every
  point's payload, and rejecting reuse of a *non-empty* collection whose
  recorded model (or unverifiable absence of one, for points inserted
  outside `add`) does not match. A genuinely empty existing collection
  has nothing to conflict with yet, so it may still be claimed by any
  model.
- Fixed `ke corpus-library-import` (M27) copying `embedding_model`/
  `embedding_id` verbatim onto an imported paper. `embedding_id` is the
  source database's own `Paper.id`, which is only unique within that one
  database -- copying it into a target database (where the imported paper
  gets a different, fresh primary key) let the imported paper silently
  claim another, unrelated paper's embedding identity, or a stale one
  nothing indexes. Found by a Codex review on PR #154. Fixed by clearing
  both fields on import; an operator must re-run `ke embedding-index-build`
  for papers after importing a snapshot, since the FAISS index file was
  never part of the snapshot's portable paper-intrinsic content anyway.
- Fixed `_build_embedding_generator` constructing
  `SentenceTransformerEmbeddingGenerator`/`OpenAiEmbeddingGenerator`
  outside any try/except, so a constructor-time `LocalEmbeddingError`/
  `OpenAiEmbeddingError` (an invalid `--model`, an empty local model name)
  propagated as an unhandled exception instead of the sanitized red-text
  + exit(1) error every other failure path in `embedding-generate`/
  `vector-search` uses. Found by a Codex review on PR #156. Fixed by
  wrapping both constructor calls in the shared helper itself, so both
  call sites get the fix.
- Fixed `_report_text` (shared by every Markdown report renderer --
  `evidence-report` and M29's `relationship-report`) only ASCII-normalizing
  free-text fields without escaping Markdown structure or collapsing
  embedded newlines. A rationale, claim text, or other reviewer-authored/
  extracted field containing an embedded `\n\n## Final Disclaimer` line
  could forge a fake report section, and ordinary text containing
  `*`/`_`/`` ` ``/`[`/`]`/`<` rendered as live Markdown formatting instead
  of the literal stored text. Found by a Codex review on PR #150. Fixed
  by collapsing embedded whitespace/newlines and escaping
  Markdown-significant characters centrally in `_report_text`, so every
  report renderer is protected at once rather than only the one Codex
  reviewed.
- Fixed the M14 candidate-adjudication ruleset (`ADJUDICATION_RULES_VERSION`)
  accepting three kinds of out-of-scope or non-primary-content sources into
  the corpus: pediatric-titled papers (v7), correction/erratum/retraction
  notices (v8), and a case report whose abstract mentioned a disease term
  only as an incidental, unrelated patient comorbidity (v8, via a
  same-sentence disease/intervention co-occurrence requirement). Re-running
  the v8 co-occurrence rule against a real 250-candidate batch showed it was
  too strict for ordinary structured/narrative scientific writing -- it
  dropped 44% of previously accepted, legitimately on-topic records -- so
  v9 reverts that specific rule while keeping the pediatric and
  correction-notice exclusions, which showed no such false-positive cost.
- Manually excluded a second incidental-comorbidity false positive from the
  already-merged `retstart=0` batch: a kidney-stone-treatment case report
  (`pmc-13262153`) whose abstract named obesity only as an unrelated patient
  comorbidity, found by applying the same review pattern that caught a
  near-identical case (a persistent-hiccups case report naming type 2
  diabetes as an incidental comorbidity) in the `retstart=250` batch. Since
  v9 deliberately has no automated rule for this pattern, both records were
  excluded by direct manual review rather than by another ruleset change.
  `sources.csv` now holds 83 sources (80 from `retstart=0`, down from 81);
  refreshed the corpus-library snapshot (83 papers, 136 authors).
- Fixed M14 bounded PubMed/PMC discovery retrying NCBI failures (including PMC
  identifier conversion) with only the steady-state request pacing interval instead
  of a real backoff; retries now use exponential backoff and failure messages
  include the HTTP status code for diagnosability.
- Fixed M14 PMC OA acquisition failing on every PDF request because NCBI relocated
  its legacy PMC FTP paths ahead of removing them in August 2026; acquisition now
  retries once against NCBI's confirmed `/pub/pmc/deprecated/` relocation, and
  failures now report the HTTP status code and failing approval for diagnosability.
- Fixed the `Quality` GitHub Actions gate silently reporting success even when lint,
  type-check, or tests failed, because piping through `tee` without `set -o
  pipefail` swallowed the real tool exit code. Also fixed every pre-existing lint
  finding, mypy error, and test failure the corrected gate now enforces, including
  a third and fourth occurrence of the single-command Typer CLI collapse bug
  (`pdf_calibration_cli.py`, `candidate_review_cli.py`) and a real SQLite backup
  bug where a naive (non-timezone-aware) timestamp left a partial, unverified
  snapshot file on disk instead of being cleaned up.
- Fixed M14 candidate adjudication accepting restricted `CC BY-NC`, `CC BY-NC-ND`,
  and `CC BY-NC-SA` licenses as if they were the fully-reusable `CC BY` license,
  because the license check used a string-prefix match instead of an exact match.
  Restricted licenses are now correctly held instead of accepted.
- Fixed M14 manifest curation leaving `license_url` and `access_date` blank and
  `expected_content_hash` unprefixed, which caused every exported row to fail
  corpus-import validation. `license_url` is now derived deterministically from
  `license_type`, `access_date` from the adjudication timestamp, and the hash is
  now written with its required `sha256:` prefix.
- Fixed the allowed-license version pattern matching any digits-and-dots string
  (e.g. `CC0 2.0`, a version that was never published) instead of a real
  Creative Commons version, which could let malformed license evidence pass
  adjudication and produce a license URL with no real deed behind it.
- Fixed `migrate_schema` verifying that every table registered in the ORM
  metadata already exists *before* creating newly-registered tables, for any
  database past schema version 0 — a table introduced by a new schema version
  (like this release's `paper_pages`) could never actually migrate onto an
  existing database; it would always raise instead. Fixed by only exempting
  tables introduced at a version newer than the database's own recorded
  version from the pre-creation check, so a genuinely new table is created
  silently while a table that was actually dropped or corrupted from an
  already-reached version still raises rather than being silently recreated
  empty.
- Fixed `ClassifiedPaperRepository` (used by `ke corpus-import`, the only
  path that has ever populated the real committed corpus) silently dropping
  M15's per-page extraction provenance: it fully overrode
  `PaperRepository.add_parsed_paper` with its own independent copy for
  exception classification, and that copy never picked up the
  `paper.pages = [...]` line M15 added to the base class. Every paper
  imported through `corpus-import` since M15 persisted zero `PaperPage`
  rows despite a correctly recorded `page_count`, silently blocking Phase 2
  extraction for the entire corpus -- found by running
  `ke extraction-review-generate` against all 605 real papers for the first
  time, which failed on every single one with "no persisted pages." Fixed
  by extracting the shared paper-construction logic into
  `PaperRepository._build_paper`, used by both overrides, so this class of
  copy-paste divergence cannot recur. Backfilled the existing local
  database with `ke paper-pages-backfill`.

## [0.2.0-alpha.1] - 2026-07-11

### Added

- Added natural-language scientific-question retrieval with `ke answer`.
- Added curated `sources.csv` metadata overlays for retrieval results.
- Added manual JSONL evidence records with review status and checklists.
- Added structural evidence validation with `ke evidence-validate` and shared
  validation across evidence-consuming commands.
- Added DOI-matched evidence previews, evidence review status summaries, and
  local Markdown evidence reports.
- Added the GLP-1 demo corpus metadata and reproducible demo checklist.
- Documented explicit retrieval, manual-evidence, and no-synthesis boundaries.

## [0.1.0] - 2026-07-06

Initial public Phase 0 release.
