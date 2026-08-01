# M7 Manifest Validation Foundation

## Objective

M7 implements the first Phase 1 corpus-ingestion capability:

```text
ke corpus-validate <corpus.json> [--check-files]
```

The command validates the version 1 corpus JSON plus source CSV contract defined
in `docs/m6_phase1_corpus_ingestion_plan.md`.

M7 is validation only. It does not import papers, parse PDFs, calculate file
hashes, write to SQLite, download files, call metadata services, or perform
scientific synthesis.

## Module Structure

Corpus validation lives outside the CLI:

```text
knowledge_engine/corpus/
  __init__.py
  models.py
  validation.py
```

- `models.py` defines stable validation result structures.
- `validation.py` loads corpus JSON, loads source CSV rows, validates the
  version 1 contract, and returns a deterministic result.
- `cli.py` receives Typer arguments, calls the validation service, renders
  human-readable output, and exits according to structural validity.

## Version 1 Manifest Behavior

The corpus JSON must include:

- `manifest_version`
- `corpus_id`
- `name`
- `description`
- `scientific_domain`
- `research_question`
- `created_at`
- `updated_at`
- `license_policy`
- `source_manifest`
- `default_local_papers_directory`

`manifest_version` must be the JSON integer `1`. Boolean values are rejected
even though Python treats booleans as integers internally. Unsupported manifest
versions are blocking structural errors.

`corpus_id` and `source_id` values must match:

```text
^[a-z0-9][a-z0-9_-]*$
```

Required text fields must not be empty. Date fields must be valid ISO 8601 dates
or datetimes. `research_question` must contain `question_id` and `text`.

Malformed JSON and malformed CSV rows produce structured validation errors, not
tracebacks.

## Path Resolution

M7 implements the M6 path contract:

- `source_manifest` is relative to the directory containing `corpus.json`.
- `license_policy` is relative to the directory containing `corpus.json`.
- `default_local_papers_directory` is relative to the project root.
- Source-row `local_path` is relative to `default_local_papers_directory`.

The validator rejects:

- absolute paths, including POSIX-style rooted paths and drive-letter paths;
- `..` traversal;
- resolved paths escaping their allowed base;
- symlink or canonical-resolution escapes where the target exists;
- local paths that repeat the configured papers directory;
- non-file local paths when `--check-files` is used.

User-facing output uses committed relative paths or source-row values rather
than private absolute paths.

## Project Root Discovery

The CLI discovers the project root by walking upward from the current working
directory. It prefers a directory containing both `pyproject.toml` and
`knowledge_engine/`, then falls back to a `.git` directory. If no project marker
is found, validation uses the current working directory as the project root.

The validation service also accepts an explicit project root for tests and
future callers. Manifests outside the repository are allowed, but
`default_local_papers_directory` is still resolved relative to the selected
project root.

## Legacy Year Compatibility

`publication_year` is canonical for manifest version 1.

For M7 only, the legacy `year` column is accepted:

- If only `publication_year` exists, it is used normally.
- If only `year` exists, validation emits `deprecated_year_column`.
- If both exist with the same non-empty value, validation emits
  `redundant_year_column`.
- If both exist and one is empty, validation emits
  `year_column_partial_compatibility`.
- If both exist with conflicting non-empty values, validation emits
  `conflicting_year_columns` as a blocking structural error.

The validator never rewrites the CSV.

## Controlled Vocabularies

Supported `usage_status` values:

- `approved_open_access`
- `approved_public_domain`
- `approved_author_manuscript`
- `approved_local_only`
- `metadata_only`
- `needs_legal_review`
- `excluded_legal`

Supported `inclusion_status` values:

- `included`
- `candidate`
- `excluded`
- `deferred`

Validation checks whether the declared metadata conforms to the project policy.
It does not decide whether a source is legally usable.

## Manifest Validity Versus Import Readiness

M7 reports two separate states.

Manifest validity:

- `valid`
- `invalid`

Import readiness:

- `ready`
- `blocked`
- `not evaluated`

Structural errors make manifest validity `invalid` and produce exit code `1`.
Examples include malformed JSON, unsupported manifest version, missing required
fields or headers, invalid identifiers, invalid paths, duplicate source IDs,
conflicting year columns, malformed hashes, and missing referenced metadata
files.

Import-readiness blockers do not necessarily make the manifest structurally
invalid. Examples include unresolved legal/provenance status, included rows
without required provenance fields, missing local files when `--check-files` is
used, unsupported local file extensions, or local paths that point to
directories.

A structurally valid but import-blocked manifest exits with code `0`. M7 keeps
the exit-code contract simple: nonzero means the manifest contract is
structurally invalid.

## Check-Files Behavior

Without `--check-files`, M7 validates path syntax and containment rules but does
not require local files to exist. Local-file readiness is reported as
`not evaluated`.

With `--check-files`, included rows with approved full-text usage statuses must
have usable `.pdf` files under `default_local_papers_directory`. The validator
checks existence, regular-file status, extension, and containment.

M7 does not open PDFs, parse PDFs, calculate hashes, or compare expected hashes
to file contents.

Rows with `metadata_only`, `excluded_legal`, `candidate`, `excluded`, or
`deferred` status do not require local PDFs for M7 file-readiness checks unless
future milestones define a stricter import policy.

## Issue and Result Model

Every issue includes:

- code
- severity
- category
- message
- source ID when applicable
- field when applicable
- CSV line number when applicable
- whether it blocks manifest validity
- whether it blocks import readiness

The service result exposes:

- corpus identity when loadable
- source-row counts
- warning count
- structural error count
- import blocker count
- manifest validity
- import readiness
- usage-status counts
- inclusion-status counts
- local-file counts
- ordered issues

Issues are ordered deterministically for review and tests.

## CLI Output

The command prints:

- corpus name and ID when available;
- manifest version when available;
- source manifest path;
- source-row counts;
- manifest validity;
- import readiness;
- structural errors;
- import blockers;
- warnings;
- legal-use status counts;
- inclusion-status counts;
- local-file counts.

Every run ends with:

```text
No papers were imported.
No database writes were performed.
Validation does not constitute legal approval or scientific review.
```

M7 intentionally does not add `--json`. Machine-readable validation output is
deferred until import-run reporting or persistence begins.

## Security Considerations

Corpus manifests are treated as untrusted input.

M7 rejects path traversal and absolute paths, resolves paths canonically before
containment checks, avoids printing private absolute paths, and never follows
remote URLs. It also avoids PDF parsing and file hashing, which keeps the
validation surface small.

## Testing

M7 adds unit coverage for:

- corpus JSON validity;
- malformed JSON;
- missing files;
- manifest version handling;
- path rules;
- CSV header and row validation;
- controlled vocabularies;
- year-column compatibility;
- duplicate source IDs;
- duplicate normalized DOI warnings;
- conditional provenance checks;
- optional local-file checks;
- manifest validity versus import readiness;
- CLI output, exit codes, and disclaimers.

The tests use temporary synthetic manifests and do not depend on committed PDFs.

## Explicit Non-Goals

M7 does not:

- import PDFs;
- parse PDFs;
- hash PDF contents;
- write to SQLite;
- add database tables or migrations;
- create import-run or import-item persistence;
- download files;
- call external metadata services;
- add JSON output;
- add AI, embeddings, evidence extraction, synthesis, consensus, confidence
  scoring, graph databases, APIs, or web interfaces.

## Known Limitations

- Validation does not prove legal usability.
- Validation does not perform scientific review.
- Duplicate DOI warnings are manifest-local only and do not query the database.
- File checks require local PDFs but do not inspect PDF content.
- The version 1 manifest contract is intentionally small and may need a future
  version when import-run persistence begins.

## M8 Handoff

M8 should add import-run and import-item persistence without changing the M7
contract unnecessarily. The M7 result model is the natural input to future run
records, manifest snapshots, structured warnings, and resumable import planning.
