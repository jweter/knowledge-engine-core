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

### Ingestion audit trail is not connected to real imports yet

The repository can validate corpus manifests and persist import-run, item,
issue, and manifest-snapshot records. It still does not import corpus PDFs
through that run state, record parser outcomes per item, or connect duplicate
decisions to stored papers.

Why it matters: Phase 1 corpus ingestion needs reproducibility. Without import
results tied to persisted run state, large imports are difficult to audit,
resume, or debug.

Eventual fix: M9 should connect approved local PDFs to persisted import items,
write paper/search records, and preserve parser failures without aborting the
entire run.

## Medium

### Best-effort PDF metadata extraction

The parser uses PDF metadata and simple text heuristics for title, authors,
abstract, and DOI extraction.

Why it matters: Scientific PDFs vary widely. Real-world parsing failures will be
common without stronger extraction and metadata enrichment.

Eventual fix: add PubMed/Crossref enrichment, source text spans, parser fixtures,
and structured parser failure issues.

### Lightweight migrations only

M8 adds an explicit `schema_versions` table and additive migration behavior for
the pre-1.0 local SQLite application, but this is still intentionally lighter
than a full migration framework.

Why it matters: Lightweight migrations are proportionate now, but schema
evolution will become harder once users have larger local databases or once the
project supports PostgreSQL.

Eventual fix: keep future changes additive while the project is pre-1.0, and
revisit Alembic or another formal migration framework before complex schema
changes or multi-database support.

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
