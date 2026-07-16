# M10 Schema Contract

## Purpose

This document defines the additive schema changes required for M10 duplicate
detection and resumability. It is subordinate to Issue #7 and the reviewed M10
implementation-contract comment, but it is the exact coding contract for the
first implementation work package.

## Existing Schema Facts

The current schema is version 1.

The following fields already exist and must not be added again:

- `import_runs.parent_import_run_id`
- `import_items.normalized_doi`
- `papers.content_hash`
- `papers.doi`
- `papers.publication_year`

`parent_import_run_id` currently has no foreign-key constraint. M10 may retain it
as a stable external run identifier while adding explicit run-mode semantics.

## Schema Version

M10 increments `CURRENT_SCHEMA_VERSION` from `1` to `2`.

Migration version 2 must be additive and must preserve all version-1 data.
The version row must be inserted only after migration verification succeeds.

## `import_runs` Additions

Add:

- `run_mode VARCHAR(32) NOT NULL DEFAULT 'fresh'`

Allowed values:

- `fresh`
- `resume`
- `retry_failed`

Add an index on `parent_import_run_id` if one does not already exist.

Validation rules:

- `fresh` runs must normally have `parent_import_run_id IS NULL`.
- `resume` and `retry_failed` runs must have `parent_import_run_id IS NOT NULL`.
- Existing version-1 rows migrate as `run_mode='fresh'`.

The migration must not rewrite prior run identifiers or timestamps.

## `import_items` Additions

Add nullable columns:

- `duplicate_outcome VARCHAR(64)`
- `matched_paper_id INTEGER REFERENCES papers(id)`
- `matched_import_item_id VARCHAR(36) REFERENCES import_items(import_item_id)`
- `computed_content_hash VARCHAR(64)`
- `duplicate_evidence_json TEXT`
- `retry_of_import_item_id VARCHAR(36) REFERENCES import_items(import_item_id)`

Add indexes on:

- `duplicate_outcome`
- `matched_paper_id`
- `matched_import_item_id`
- `computed_content_hash`
- `retry_of_import_item_id`

Allowed `duplicate_outcome` values:

- `none`
- `exact_hash_duplicate`
- `doi_duplicate`
- `doi_hash_conflict`
- `possible_title_year_duplicate`

For newly created M10 items, use `none` rather than `NULL` once duplicate
evaluation has completed with no signal. `NULL` remains valid for migrated
version-1 rows and for items that never reached duplicate evaluation.

## Status and Write Invariants

The existing `item_status` column remains the lifecycle status source.
M10 uses these terminal values:

- `imported`
- `skipped`
- `failed`
- `needs_review`

Required combinations:

- `exact_hash_duplicate` -> `skipped`
- `doi_duplicate` -> `skipped`
- `doi_hash_conflict` -> `needs_review`
- `possible_title_year_duplicate` -> `needs_review`

A `needs_review` item must not create or modify:

- `papers`
- `paper_texts`
- `paper_search`

A safely skipped duplicate must not create a second paper, paper-text, or FTS
row.

## Duplicate Evidence JSON

`duplicate_evidence_json` stores a deterministic JSON object. It must not store:

- private absolute paths;
- raw exception strings;
- file contents;
- parser text;
- secrets or environment values.

Permitted keys include:

- `matching_method`
- `candidate_content_hash`
- `matched_content_hash`
- `candidate_normalized_doi`
- `matched_normalized_doi`
- `candidate_normalized_title`
- `matched_normalized_title`
- `candidate_publication_year`
- `matched_publication_year`
- `action`
- `reason_code`

Serialization must be deterministic: sorted keys, UTF-8, and no incidental
whitespace dependence in tests.

## Migration Mechanics

SQLite version-2 migration should:

1. Detect current version.
2. Create all missing version-1 tables when initializing a fresh database.
3. For an existing version-1 database, add each missing column with `ALTER TABLE`.
4. Create required indexes with `CREATE INDEX IF NOT EXISTS`.
5. Verify columns, indexes, and foreign-key declarations where SQLite exposes
   them.
6. Verify all existing rows remain readable.
7. Insert schema version 2 only after verification passes.

Because SQLite cannot add all constraints through `ALTER TABLE`, application
validation remains authoritative for run-mode and duplicate-outcome vocabulary.
Foreign-key columns should still use SQLAlchemy model declarations so fresh
version-2 databases receive the intended constraints.

Migration must be retry-safe. A partially applied migration must be able to run
again without duplicate-column or duplicate-index failure.

## Repository and Query Requirements

M10 needs lookup helpers that return explicit candidate records rather than
raising uniqueness errors as normal control flow.

Required queries:

- paper by exact `content_hash`;
- paper by normalized DOI;
- papers by normalized title and publication year;
- prior import item by stable `source_id` within a parent run;
- prior imported/skipped/failed/review item outcomes;
- same-run earlier item by computed hash or normalized DOI.

Database uniqueness errors remain the last integrity backstop.

## Upgrade Tests

Required migration tests:

- fresh database initializes directly at version 2;
- populated version-1 database upgrades to version 2;
- every version-1 paper, paper-text, FTS row, run, item, issue, and snapshot is
  preserved;
- existing import runs receive `run_mode='fresh'`;
- new nullable duplicate columns are `NULL` on migrated items;
- required indexes exist;
- foreign-key enforcement remains enabled;
- rerunning initialization after upgrade is idempotent;
- a simulated incomplete version-2 migration is safely repairable;
- a schema version newer than 2 still fails clearly.

## Non-Goals

This schema work package does not implement:

- duplicate decision logic;
- CLI resume/retry options;
- metadata enrichment;
- fuzzy matching or merging;
- replacement or supersession workflows;
- network access;
- AI, embeddings, synthesis, or evidence extraction.

## Completion Gate

The schema work package is complete only when:

- models and migration code match this contract;
- fresh and upgrade tests pass;
- existing M9 tests remain green;
- Black, Ruff, mypy, pytest, and `git diff --check` pass;
- no PDFs, databases, generated reports, or unrelated artifacts are committed.
