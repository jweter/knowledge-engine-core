# M9: Small Ingestion Pilot

## Objective and Scope

M9 completes the first end-to-end local corpus ingestion path for a small pilot
set of roughly 10 to 25 papers.

The goal is to take a version 1 corpus manifest that already satisfies manifest
validation and local file readiness, persist the run state, parse approved local
PDFs, write paper records and indexed text, and preserve per-item outcomes in the
durable import-run tables.

M9 scope includes:

- validating the manifest before import begins;
- persisting the import run, import items, issues, and manifest snapshot;
- importing only eligible local PDFs from the persisted run;
- writing paper, paper-text, and FTS data for successful imports;
- recording parser, file, and persistence failures without aborting the entire
  run;
- representing full success, partial success, blocked runs, and failed runs in
  persisted state and CLI output.

M9 does not introduce parallel ingestion, large-scale throughput work, external
metadata enrichment, AI-assisted analysis, or scientific synthesis.

## Relationship to M7 Validation and M8 Persistence

M7 established the corpus manifest contract and validation behavior. It checks
manifest structure, required fields, row-level vocabulary and metadata rules, and
optional local file readiness, but it does not import papers or write database
records beyond the existing retrieval model.

M8 added durable persistence around that M7 result. Each validation attempt can
now be stored as an import run with import items, structured issues, and an
authoritative manifest snapshot.

M9 builds directly on both layers:

- M7 still defines whether a manifest is structurally valid and import-ready.
- M8 still captures the durable audit trail for the attempt.
- M9 uses the persisted M8 run state as the ingestion control surface for
  parsing PDFs and recording final item outcomes.

This keeps validation rules stable while allowing ingestion behavior to evolve
without redesigning the manifest contract.

## `ke corpus-import`

M9 provides the ingestion command:

```bash
ke corpus-import <corpus.json>
```

Behavior:

- initializes the local database if needed;
- validates the manifest with file checks enabled;
- persists the run and manifest snapshot;
- stops early with a non-zero exit code when the manifest is structurally invalid
  or import-blocked;
- imports only items that are eligible for local ingestion;
- records item-level failures such as unsafe paths, missing files, unreadable
  files, parser failures, and paper persistence failures;
- prints the final run summary, item statuses, and persisted issues after the run
  completes.

Successful items may write `papers`, `paper_texts`, and full-text search records.
Skipped or failed items remain visible through the persisted import-run data so
that operators can inspect the outcome and rerun after fixing corpus inputs.
