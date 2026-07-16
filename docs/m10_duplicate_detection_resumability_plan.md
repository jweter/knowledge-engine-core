# M10 Duplicate Detection and Resumability Plan

## Status

Active implementation document for Issue #7.

Branch: `feature/m10-duplicate-detection-resumability`

Baseline: `9fa26dd7107f331ab1560e801f08144804c7f4af`

Implemented so far:

- schema version increased from 1 to 2;
- retry-safe additive SQLite migration for M10 columns;
- required version-2 indexes;
- schema verification for required version-2 columns and indexes;
- focused fresh-database and retry-safety tests.

Still pending:

- SQLAlchemy model mappings for the new fields;
- populated version-1 upgrade-preservation tests;
- duplicate query and decision services;
- ingestion integration before persistence;
- immutable resume/retry planning;
- CLI options and reporting;
- final regression validation and release documentation.

No production slice is complete until its GitHub Actions quality run passes.

## Objective

Make corpus reruns safe, preserve immutable run history, and make duplicate outcomes explicit and auditable before any paper, paper-text, or FTS persistence occurs.

## Authoritative Scope

The Issue #7 body and the reviewed implementation-contract comment define M10. This document translates that contract into repository work packages. `docs/m10_schema_contract.md` is the exact contract for the schema work package.

## Work Package 1 — Schema and Domain Vocabulary

- Add one additive schema migration through `schema_versions`.
- Retain the existing `import_runs.parent_import_run_id` field.
- Add `import_runs.run_mode`.
- Retain the existing `import_items.normalized_doi` field.
- Add import-item duplicate/retry fields:
  - `duplicate_outcome`
  - `matched_paper_id`
  - `matched_import_item_id`
  - `computed_content_hash`
  - structured duplicate evidence
  - `retry_of_import_item_id`
- Preserve all existing M8/M9 records.
- Add fresh-schema, populated-upgrade, and partial-migration retry tests.

Exit criteria:

- Existing databases upgrade without data loss.
- New schema state is recorded only after verification succeeds.
- Required columns and indexes are verified.
- ORM models expose every new field.

## Work Package 2 — Duplicate Query Layer

Add focused repository/query helpers for:

- exact content hash lookup;
- normalized DOI lookup;
- normalized title/year candidate lookup;
- same-run imported-item lookup;
- prior-run lineage and source-ID reconciliation.

Exit criteria:

- Query helpers are deterministic and independently tested.
- No CLI formatting or policy logic is embedded in repository methods.

## Work Package 3 — Duplicate Decision Service

Introduce a pure, deterministic service that accepts identity evidence and returns a structured decision.

Decision outcomes:

- importable;
- exact hash duplicate skip;
- DOI duplicate skip;
- DOI/hash conflict requiring review;
- title/year candidate requiring review.

Exit criteria:

- Stronger identity evidence always dominates weaker evidence.
- Missing or contradictory evidence cannot produce a silent merge.
- Decision tests cover every hierarchy branch.

## Work Package 4 — Ingestion Integration

Integrate duplicate evaluation before `PaperRepository.add_parsed_paper`.

Pipeline:

```text
validation/legal gate
→ resolve local file
→ compute SHA-256
→ parse required metadata
→ duplicate decision
→ persist only when importable
```

Exit criteria:

- `needs_review` writes no paper, paper-text, or FTS rows.
- Exact duplicates are explicit persisted skips.
- Database uniqueness constraints remain backstops only.
- Same-run duplicates are detected.

## Work Package 5 — Resume and Retry Planning

Implement immutable new-run planning:

- `fresh`;
- `resume`;
- `retry_failed`.

Rules:

- Reconcile by stable `source_id`, never row position.
- Require matching `corpus_id` for parent-run operations.
- Compare current rows to the prior authoritative manifest snapshot.
- Material identity changes prevent automatic reuse.
- Resume may process new sources.
- Retry-failed excludes new sources and selects only prior failed items.

Exit criteria:

- Prior runs and items remain unchanged.
- Added, removed, reordered, and materially changed rows behave deterministically.

## Work Package 6 — CLI and Reporting

Add mutually exclusive options:

```text
--resume-from <run-id>
--retry-failed-from <run-id>
```

Reporting requirements:

- display run mode and parent run;
- show duplicate outcome and matched identity where safe;
- report `needs_review` separately from failures;
- preserve no-download and scientific-review disclaimers;
- derive summaries only from persisted item outcomes.

Exit criteria:

- CLI output is deterministic.
- Fresh, resume, retry, all-skipped, partial-success, and needs-review runs are represented accurately.

## Work Package 7 — Integrity and Regression Tests

Required integration coverage:

- exact hash duplicate against existing paper;
- exact duplicate within one run;
- normalized DOI duplicate with reconcilable hash evidence;
- DOI match with different hash;
- DOI match with unavailable hash evidence;
- same hash with conflicting metadata;
- title/year candidate held for review;
- rerun produces no duplicate paper, paper-text, or FTS rows;
- resume by source ID despite row reordering;
- added, removed, and changed source rows;
- retry selects only failed items;
- prior history remains immutable;
- migration from current schema;
- accurate summaries for partial success, all skipped, and needs review.

## Non-Goals

- fuzzy merge automation;
- automatic replacement or supersession;
- review-resolution UI;
- metadata enrichment adapters;
- downloads or network access;
- parallel ingestion;
- AI, embeddings, automated evidence extraction, synthesis, consensus, confidence scoring, graph databases, APIs, or web interfaces.

## Validation Gate

Before M10 can be merged:

- full pytest suite passes;
- Black passes;
- Ruff passes;
- mypy passes;
- `git diff --check` passes;
- final PR diff contains no local PDFs, SQLite databases, generated reports, caches, secrets, or unrelated lockfile changes.

## Recommended Commit Sequence

1. `db: add M10 duplicate and lineage schema`
2. `ingestion: add duplicate lookup and decision services`
3. `ingestion: enforce duplicate outcomes before persistence`
4. `ingestion: add immutable resume and retry planning`
5. `cli: expose M10 resume retry and review reporting`
6. `tests: cover M10 duplicate and resumability integrity`
7. `docs: finalize M10 operational guidance`
