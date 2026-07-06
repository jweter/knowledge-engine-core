# Technical Debt

This document tracks known technical debt at the initial release candidate. Debt
is not automatically bad. Some debt is the correct tradeoff for Phase 0, as long
as it is visible and intentionally revisited.

## Critical

No critical technical debt is known for the initial Phase 0 release candidate.

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

### No import manifest or ingestion audit trail

The repository can import individual PDFs, but it does not yet record import
runs, skipped files, failures, duplicates, or source provenance beyond stored
paper fields.

Why it matters: Phase 1 corpus ingestion needs reproducibility. Without import
manifests, large imports are difficult to audit, resume, or debug.

Eventual fix: add import run models, manifest files, duplicate reports, and
structured failure logs.

## Medium

### Best-effort PDF metadata extraction

The parser uses PDF metadata and simple text heuristics for title, authors,
abstract, and DOI extraction.

Why it matters: Scientific PDFs vary widely. Real-world parsing failures will be
common without stronger extraction and metadata enrichment.

Eventual fix: add PubMed/Crossref enrichment, source text spans, parser fixtures,
and structured parser failure issues.

### No database migrations

Phase 0 creates tables directly from SQLAlchemy metadata.

Why it matters: Direct schema creation is fine before a public release, but
schema evolution will become risky once users have local databases.

Eventual fix: introduce Alembic or a lightweight migration strategy before
making incompatible schema changes.

### FTS index synchronization is write-only

The repository inserts imported papers into the FTS table, but there are no
update/delete workflows yet.

Why it matters: Future edit, reparse, or delete behavior must keep relational
metadata and FTS rows consistent.

Eventual fix: add explicit update/delete repository methods and tests, or use
SQLite triggers if that becomes the preferred design.

## Low

### Search snippets rely on SQLite FTS behavior

Search snippets are produced by SQLite's `snippet` function.

Why it matters: Snippet quality may vary by query and document structure.

Eventual fix: add deterministic snippet generation around matched terms if user
testing shows the built-in snippets are not sufficient.

### No committed realistic sample corpus

Tests generate a tiny PDF fixture, but the repository does not include a
realistic legally redistributable paper sample.

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
