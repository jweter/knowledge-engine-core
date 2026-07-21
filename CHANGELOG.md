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

### Changed

- Made Ruff the authoritative formatter and linter used by both developer commands
  and GitHub Actions.
- Unexpected parser and duplicate-resolution exceptions now propagate as systemic
  failures instead of being persisted as ordinary per-paper issue codes.
- Reconciled README, roadmap, and technical-debt documentation through M13 and named
  the controlled 500-paper rehearsal as the next bounded milestone.

### Fixed

- Fixed M14 PMC OA acquisition failing on every PDF request because NCBI relocated
  its legacy PMC FTP paths ahead of removing them in August 2026; acquisition now
  retries once against NCBI's confirmed `/pub/pmc/deprecated/` relocation, and
  failures now report the HTTP status code and failing approval for diagnosability.

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
