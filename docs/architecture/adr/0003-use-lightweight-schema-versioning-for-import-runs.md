# ADR 0003: Use Lightweight Schema Versioning for Import Runs

## Status

Accepted for M8.

## Context

M8 introduces durable import-run, import-item, validation-issue, and manifest
snapshot tables. Phase 0 and M7 databases were created directly from SQLAlchemy
metadata with `create_all()`, which is acceptable for first-run bootstrap but is
not enough as the schema begins to evolve.

The project is still pre-1.0, local-first, and SQLite-only. Adding Alembic now
would be more machinery than the current schema needs, but silently relying on
`create_all()` alone would make existing local databases harder to reason about.

## Decision

Knowledge Engine Core will use a small explicit `schema_versions` table for the
pre-1.0 SQLite application.

For M8:

- fresh databases create all SQLAlchemy tables and record schema version `1`;
- existing Phase 0/M7 databases are upgraded additively by creating the new M8
  tables and recording schema version `1`;
- unversioned databases are treated as baseline local databases and upgraded to
  schema version `1`;
- schema version `1` means the complete current relational schema, not only the
  M8 tables;
- databases with a schema version newer than the application supports fail
  clearly;
- databases marked as current but missing expected tables fail clearly rather
  than being silently accepted;
- duplicate rows for the same schema version fail clearly;
- migrations are non-destructive;
- paper, text, metadata, relationship, and FTS records are preserved during
  upgrade.

The version row is recorded only after table creation and schema verification
succeed. SQLite DDL may leave partially created tables behind after a failed
migration, so the M8 strategy is recovery-safe rather than "all DDL disappears
on rollback." Because the schema version is not advanced until verification
succeeds, a retry can complete idempotent additive table creation and record the
version. Future migrations must not claim stronger atomicity than SQLite
provides for the operations they use.

M8 also persists corpus validation attempts in SQLite:

- `manifest_snapshots` is the authoritative stored manifest input for an
  import run;
- `import_runs` stores run-level lifecycle and validation summary fields;
- `import_items` stores one row per identifiable source-manifest row;
- `import_issues` stores structural errors, import-readiness blockers, and
  warnings in deterministic order.

Manifest snapshots store authoritative raw bytes for corpus JSON and source CSV
inputs, normalized UTF-8 text for inspection, and SHA-256 hashes of the raw
bytes. The combined snapshot hash uses explicit labels, source-CSV presence, and
lengths before each byte sequence so the framing is not ambiguous. PDF contents,
extracted text, and private absolute paths are not part of the snapshot.

## Consequences

This keeps M8 small and testable while giving the project a real schema
evolution contract. It also leaves room to adopt Alembic later if migrations
become more complex or if PostgreSQL support is added.

The tradeoff is that schema changes must remain disciplined. Each future
database change needs an explicit version decision, additive migration behavior,
and tests against an existing database.

This decision should be revisited before complex data-transforming migrations,
before destructive migrations, before PostgreSQL support, or before the project
reaches a stable public database contract.

## Deferred

- Alembic or another full migration framework.
- Destructive or data-transforming migrations.
- Import retry/resume semantics.
- JSON or Markdown run reports generated from persisted state.
- Duplicate detection against stored papers.
