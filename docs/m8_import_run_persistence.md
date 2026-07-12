# M8: Import-Run and Import-Item Persistence

## Objective

M8 persists corpus validation attempts as durable import-run state.

It allows a user to validate a version 1 corpus manifest, record that validation
attempt, preserve the exact manifest inputs, create one import item per source
row, preserve structural errors, import-readiness blockers, and warnings, and
inspect the persisted result later.

M8 does not import papers. It is the audit trail foundation that later ingestion
will use.

## Migration Strategy

M8 uses the lightweight schema-version strategy documented in
`docs/architecture/adr/0003-use-lightweight-schema-versioning-for-import-runs.md`.

The application now maintains a `schema_versions` table for the local SQLite
database:

- fresh databases create the current schema and record schema version `1`;
- existing Phase 0/M7 databases are upgraded additively;
- unversioned existing databases are treated as baseline local databases and
  upgraded to schema version `1`;
- schema version `1` represents the complete current relational schema;
- databases marked current but missing expected tables fail clearly;
- existing paper, paper-text, and FTS records are preserved;
- databases with a future unsupported schema version fail clearly;
- migrations are non-destructive.

This is intentionally smaller than Alembic while the project is pre-1.0 and
SQLite-only. If schema evolution becomes more complex, the project can revisit a
full migration framework.

## Schema and Table Responsibilities

M8 adds four durable tables plus schema version tracking.

`schema_versions`

- records the highest applied local SQLite schema version;
- prevents the application from silently opening a newer unsupported database.

`manifest_snapshots`

- stores the manifest inputs used for a validation run;
- preserves raw corpus JSON and source CSV bytes as authoritative snapshot
  inputs;
- preserves normalized UTF-8 text for human inspection;
- stores SHA-256 hashes of raw corpus JSON and source CSV bytes;
- stores a deterministic combined snapshot hash;
- does not store PDFs, extracted text, or private absolute paths.

`import_runs`

- stores one persisted validation attempt;
- records corpus identity when loadable;
- records validation mode, run status, manifest validity, import readiness, and
  summary counts;
- references the manifest snapshot used for the run.

`import_items`

- stores one row per identifiable source-manifest row;
- preserves source ID, CSV line number, title, normalized DOI, inclusion status,
  usage status, local relative path, and item-level issue counts;
- does not link to paper records yet.

`import_issues`

- stores validation issues in deterministic order;
- supports run-scoped and item-scoped issues;
- preserves issue code, severity, category, message, field, source ID, CSV line
  number, and blocking flags.

## Identifiers

M8 uses application-generated UUID version 4 values stored as lowercase
canonical text for public durable identifiers:

- `import_run_id`
- `import_item_id`
- `issue_id`
- `snapshot_id`

Integer primary keys remain internal database implementation details. Source IDs
are not import-item identifiers because the same source row can appear in more
than one run.

## Run Lifecycle

M8 supports these run statuses:

- `created`
- `validating`
- `validation_failed`
- `validated`
- `import_blocked`

The service records the final status after a validation attempt is persisted:

- structurally invalid manifest: `validation_failed`;
- structurally valid but import-blocked manifest: `import_blocked`;
- structurally valid manifest with readiness ready or not evaluated:
  `validated`.

M8 does not use later ingestion statuses such as `running`, `succeeded`, or
`partially_succeeded`.

## Item Lifecycle

M8 supports these item statuses:

- `pending`
- `valid`
- `invalid`
- `import_blocked`

The persisted item status is derived from row-scoped issues:

- structural row errors produce `invalid`;
- structurally valid rows with import blockers produce `import_blocked`;
- structurally valid rows without import blockers produce `valid`.

Malformed CSV rows that cannot be represented as a source row are preserved as
run-scoped issues rather than papering over missing source identity.

## Issue Persistence

M8 persists M7 validation issues in a single `import_issues` table.

Each issue records:

- stable issue UUID;
- parent run;
- optional parent item;
- issue code;
- severity;
- category;
- user-facing message;
- source ID when available;
- field when available;
- CSV line number when available;
- manifest-validity blocking flag;
- import-readiness blocking flag;
- deterministic sequence number.

Expected validation failures are stored as structured issues, not Python
tracebacks.

Duplicate DOI warnings are stored as run-scoped issues because one duplicate DOI
message can describe multiple affected rows. Row-specific issues keep their CSV
line number and attach to the corresponding import item.

## Manifest Snapshot Representation

`manifest_snapshots` is the authoritative stored representation of the manifest
input used for an import run.

The snapshot stores:

- project-safe corpus path;
- safe source manifest path when available;
- raw corpus JSON bytes;
- raw source CSV bytes when available;
- normalized corpus JSON text;
- normalized source CSV text when available;
- SHA-256 hash of the raw corpus JSON bytes;
- SHA-256 hash of the raw source CSV bytes when available;
- combined SHA-256 hash with explicit labels and byte lengths;
- capture timestamp.

The raw-byte hashes preserve change detection even when UTF-8 BOM bytes are
normalized in the stored inspection text. The combined hash frames every input
with a label, source-CSV presence marker, and length so two different input
sequences cannot collide through simple concatenation ambiguity.

Unsafe `source_manifest` paths and non-CSV source-manifest targets are not
followed during snapshot capture. This prevents a malformed manifest from
causing M8 to read files outside the corpus metadata directory or snapshot a
misleading PDF before validation reports the structural error.

Manifest JSON and source CSV snapshot inputs are each limited to 5 MiB in M8.
Oversized inputs fail before persistence and are not recorded as import runs.

## Transaction Behavior

An import-run creation attempt is persisted in one transaction:

1. read corpus JSON bytes;
2. safely read source CSV bytes when the manifest path is safe and available;
3. run M7 validation;
4. create snapshot, run, item, and issue records;
5. verify the records can be read back consistently;
6. commit.

If database persistence fails, the transaction rolls back and the CLI reports
that the import run was not recorded. M8 does not write paper records or FTS
records.

SQLite DDL may leave partially created tables behind after a failed migration.
M8 therefore relies on a recovery-safe sequence: schema version `1` is not
recorded until table creation and schema verification succeed, and additive
`create_all()` behavior allows a retry to complete the schema. Future migrations
must document actual SQLite behavior if they use operations that are not
idempotent or rollback-safe.

## CLI Commands

M8 adds two commands.

```bash
ke corpus-run-create <corpus.json> [--check-files]
```

Behavior:

- runs M7 validation;
- persists one import run;
- persists one import item per identifiable source row;
- persists validation issues;
- persists the manifest snapshot;
- prints the run UUID, status, validity, readiness, counts, and issues;
- states that no papers were imported;
- states that no PDFs were parsed or hashed;
- states that validation is not legal approval or scientific review.

```bash
ke corpus-run-show <run-id>
```

Behavior:

- reads a persisted run;
- shows run metadata, snapshot hash, counts, issues, and item summaries;
- reports unknown run IDs clearly;
- performs no validation and no import.

## Exit Codes

`ke corpus-run-create`:

- persistence failure: nonzero;
- structurally invalid manifest successfully recorded: nonzero;
- structurally valid but import-blocked manifest successfully recorded: `0`;
- structurally valid manifest with readiness not evaluated: `0`;
- structurally valid and ready manifest: `0`.

`ke corpus-run-show`:

- known run: `0`;
- unknown run ID: nonzero;
- database failure: nonzero.

Exit status is based on structural validity and persistence success, not on
scientific meaning.

## Read-Back Behavior

After creating a run, the service reads the persisted state back before the
transaction commits.

It verifies:

- warning, structural-error, and import-blocker counts match persisted issues;
- item count matches the validation source rows;
- issue sequence order is stable;
- item UUIDs are unique.

Tests also verify snapshot hashes, timestamp policy, and round-tripped validity
and readiness values.

The CLI performs an additional read after the transaction commits and renders
that durable state for `ke corpus-run-create`.

## Invalid-Manifest Persistence

Structurally invalid manifests are still persisted when the corpus JSON file can
be read.

Malformed JSON behavior:

- corpus JSON bytes are snapshotted;
- no source CSV snapshot is captured because the reference cannot be trusted;
- the run is stored with `validation_failed`;
- the malformed JSON issue is stored at run scope;
- no import items are created.

Missing source CSV and missing license policy files are also recorded as
validation-failed runs with structural issues.

## Backward Compatibility

M8 preserves existing commands and data:

- `ke import`
- `ke search`
- `ke answer`
- `ke corpus-validate`
- evidence commands
- `ke stats`

The M7 `corpus-validate` command remains non-persisting. M8 adds separate
commands for persistence instead of changing validation behavior.

Existing paper and FTS records survive the additive schema upgrade.

## Security and Privacy Constraints

M8 treats manifest inputs as untrusted.

Security rules:

- no private absolute paths are stored or printed;
- unsafe source CSV paths are not followed during snapshot capture;
- non-CSV source manifest targets are not snapshotted;
- manifest JSON and source CSV snapshots are size-limited;
- SQLAlchemy parameters are used for database writes;
- no dynamic SQL is built from manifest values;
- PDF contents are not opened, parsed, hashed, or stored;
- extracted text is not stored by import-run persistence;
- URLs are not followed;
- user-controlled text is escaped before Rich output;
- validation and persistence do not constitute legal approval or scientific
  review.

## Explicit Non-Goals

M8 does not:

- import PDFs;
- parse PDFs;
- open PDF contents;
- calculate PDF content hashes;
- write paper or paper-text records;
- populate FTS;
- detect duplicates against stored papers;
- download documents;
- call metadata services;
- retry or resume imports;
- implement M9 ingestion;
- add AI, embeddings, evidence extraction, synthesis, consensus, confidence
  scoring, graphs, APIs, or web interfaces.

## Known Limitations

- The schema-version mechanism is intentionally lightweight and pre-1.0.
- M8 stores final run status, not a full transition event log.
- Malformed CSV rows without usable row identity are represented through
  run-scoped issues.
- Snapshot text is normalized for inspection while raw-byte hashes preserve
  input identity.
- Oversized manifest inputs are rejected before persistence rather than being
  recorded as failed validation runs.
- Import-run reports are displayed in the terminal only; JSON and Markdown
  reports remain future work.
- Duplicate detection is limited to M7 manifest warnings and does not inspect
  stored papers.

## M9 Handoff

M9 should use this persisted state to run a small 10-25 paper ingestion pilot.

Recommended M9 scope:

- load a validated manifest run;
- parse approved local PDFs only after validation;
- write paper and paper-text records;
- update FTS;
- update item statuses for import success or parser failure;
- preserve parser errors without aborting the full run;
- continue to avoid AI, synthesis, and confidence scoring.
