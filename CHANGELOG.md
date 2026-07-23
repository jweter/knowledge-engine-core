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
