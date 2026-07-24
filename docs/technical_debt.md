# Technical Debt

This document tracks known technical debt for the current Phase 1 prerelease.
Debt is not automatically bad. Some debt is the correct tradeoff while the project
is pre-1.0, provided it remains visible and is revisited when evidence justifies it.
This is the single authoritative debt register; the former `docs/pain_points.txt`
register has been retired to prevent duplicate or contradictory status.

## Critical

No critical technical debt is currently known.

## High

### Poetry certificate failure on the current Windows machine

Poetry 2.4.1 launches, but dependency resolution fails with certificate
verification errors against PyPI. Pip-based installation works under Python
3.14.6.

Why it matters: Poetry is the documented contributor workflow. If contributors
hit certificate failures during setup, the project feels unreliable before they
ever run the code.

Eventual fix: diagnose Poetry certificate/proxy behavior on Windows, document
the resolution, and keep CI as an independent confirmation that Poetry works in a
clean environment.

### Parser failure taxonomy remains intentionally narrow

M9 added recoverable item-level parser issues, and the pre-M14 hardening milestone
separates declared `DocumentParseError` failures from unexpected programming defects.
The current parser still has only a small expected-failure hierarchy.

Why it matters: real scientific PDFs may expose additional stable failure categories,
but classifying every dependency exception as recoverable would conceal broken code.

Eventual fix: add parser categories only from observed corpus evidence, keeping raw
exception details out of persistent issues and allowing unexpected defects to remain
systemic.

### Duplicate-resolution failure taxonomy remains intentionally narrow

M10 added pre-persistence duplicate decisions and linked resume/retry behavior. The
pre-M14 hardening milestone defines `DuplicateResolutionError` as the only recoverable
item-specific duplicate-resolution failure contract.

Why it matters: database, ORM, type, assertion, and programming failures affecting
duplicate resolution must not appear as independent bad-paper outcomes.

Eventual fix: add narrower subtypes only when a genuine expected evidence failure is
observed and has a stable recovery policy.

## Resolved

### Ingestion audit trail connected to real imports

Resolved by M9 and extended by M10–M13. Validated local PDFs now import through
persisted run/item state, parser and persistence outcomes are recorded, duplicate
decisions occur before persistence, and linked resume/retry and bounded rehearsal
reporting are available.

### Architecture documentation lagged current Phase 1 modules

Resolved by the audit documentation reconciliation. `docs/architecture.md` now
records corpus validation, import-run persistence, duplicate resolution, PubMed/PMC
discovery and acquisition boundaries, and optional Drive-backup infrastructure.

### Drive-backup work lacked roadmap traceability

Resolved at the documentation level by identifying the subsystem as optional
operator durability support for local SQLite backup bundles. It does not alter
scientific-ingestion semantics. Any expansion beyond backup transport and recovery
support still requires a dedicated roadmap decision or ADR.

### Page-level extraction provenance was not retained

Resolved by the M15 Phase 2 foundation milestone. `PyMuPDFParser` now normalizes
each page individually and `ParsedPaper.pages` preserves page boundaries; a new
`paper_pages` table (`PaperPage` model) persists per-page text keyed to `papers`.
Every extracted claim can now cite an exact `(page_number, offset)` span instead of
only a page count. See `docs/phase2_design.md`'s Prerequisite section.

### One-off GitHub Actions workflows are not classified

Was flagged as needing an inventory "after M14 is stable" to distinguish
load-bearing automation from retained implementation history. M14 has been
stable since the corpus reached 605 papers and the project owner stopped
further growth; inventoried now. `.github/workflows/` contains exactly two
files: `quality.yml` (the recurring CI quality gate) and
`m14-mass-discovery.yml` (the M14 discovery pipeline, dispatchable on demand
for future corpus growth and also run as a bounded smoke test on pull
requests touching M14 pipeline code). Both are load-bearing; no historical
one-off diagnostic or patch workflow remains -- `git log` confirms these were
already removed earlier in the project's history (for example, "chore:
remove temporary pytest diagnostic workflow"). No cleanup PR was needed.

## Medium

### Best-effort PDF metadata extraction

The parser uses PDF metadata and simple text heuristics for title, authors,
abstract, and DOI extraction. M11 added provenance-preserving metadata preview and
Crossref enrichment boundaries, but parser extraction remains heuristic.

Why it matters: Scientific PDFs vary widely. Real-world parsing and metadata quality
will remain uneven without measured corpus hardening.

Eventual fix: use rehearsal evidence to prioritize fixtures and evaluate established
scientific parsers or additional providers. Preserve provider assertions and
selection rationale rather than silently overwriting canonical values.

### Persistence failures use a broad sanitized category

Non-duplicate failures inside atomic paper/FTS persistence currently use the stable
`paper_persistence_failed` issue code.

Why it matters: relational writes, FTS writes, locks, disk failures, and unexpected
repository defects are operationally different even when the user-facing message
must remain sanitized.

Eventual fix: introduce stable repository exception categories after observed
failures justify their semantics. Preserve per-item savepoint rollback.

### Lightweight migrations only

M8 added an explicit `schema_versions` table and additive migration behavior for
the pre-1.0 local SQLite application, but this remains intentionally lighter than a
full migration framework.

Why it matters: Lightweight migrations are proportionate now, but schema evolution
will become harder once users have larger databases or multiple supported backends.

Eventual fix: keep future changes additive while pre-1.0 and revisit Alembic or
another formal framework before complex transformations or multi-database support.

### FTS index synchronization is write-only

The repository inserts imported papers into the FTS table, but there are no
update/delete workflows yet.

Why it matters: Future edit, reparse, or delete behavior must keep relational
metadata and FTS rows consistent.

Eventual fix: add explicit update/delete repository methods and tests, or use SQLite
triggers if that becomes the preferred design.

### Scientific work, version, file, and assertion identity are not separated

Current Phase 1 models are sufficient for document-level ingestion and bounded
rehearsals, but do not yet represent scholarly works, alternate versions, local
files, extraction runs, provider assertions, and canonical selections separately.

Why it matters: preprints, versions of record, corrections, supplements, and
provider conflicts will eventually require explicit provenance-aware identity.

Eventual fix: design this model when multiple-provider/version conflicts become an
operational requirement. Do not introduce it solely for the 500-paper rehearsal.

## Low

### Search snippets rely on SQLite FTS behavior

Search snippets are produced by SQLite's `snippet` function.

Why it matters: Snippet quality may vary by query and document structure.

Eventual fix: add deterministic snippet generation around matched terms if user
testing shows the built-in snippets are not sufficient.

### No committed realistic sample corpus

Tests generate a tiny PDF fixture, but the repository does not include a realistic
legally redistributable paper sample.

Why it matters: New contributors cannot immediately see realistic parsing and
search behavior.

Eventual fix: add a legal sample PDF or fixture-generation command.

### Stale machine PATH entries on the current Windows machine

The broken Python 3.12 install was removed, but machine-level PATH entries still
reference Python312 and require administrator rights to remove.

Why it matters: This is local environment debt, not project code debt. It could
confuse future command resolution on that machine.

Eventual fix: remove stale entries from an elevated shell or the Windows
Environment Variables UI.

### Typer and Click compatibility pin

Typer 0.12.x previously failed with newer Click versions, so Click remains bounded
to the verified compatible range.

Why it matters: dependency pins can conceal future compatibility improvements or
security updates if they are never revisited.

Eventual fix: retest the CLI after a deliberate Typer upgrade and loosen the Click
constraint only when the full Quality workflow remains green.
