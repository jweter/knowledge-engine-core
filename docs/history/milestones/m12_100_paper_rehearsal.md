# M12 Controlled 100-Paper Rehearsal

## Purpose

M12 validates the existing Phase 1 ingestion workflow against a real, bounded corpus of exactly 100 legally usable local scientific PDFs. It is an operational rehearsal and evidence-collection milestone, not a new ingestion architecture.

The rehearsal must measure what the current system actually records and must identify gaps explicitly. It must not invent timing, conflict, quality, or scientific conclusions that are absent from persisted state or manual operator measurements.

## Required repository state

Before the real rehearsal:

- the exact M12 PR head passes Ruff formatting, Ruff lint, strict mypy, pytest, diff hygiene, and temporary-artifact rejection;
- the source manifest is structurally valid;
- exactly 100 included rows have importable usage status;
- every included row has source URL, access date, inclusion reason, local path, and legal basis;
- all local paths are relative and remain inside the configured corpus paper directory;
- all 100 local files are present and readable;
- local PDFs, databases, generated full-text output, and unsanitized reports remain untracked.

## Corpus acceptance rules

The real rehearsal corpus must contain exactly 100 included rows that satisfy all of the following:

1. `inclusion_status` is `included`.
2. `usage_status` permits local full-text import.
3. The source has a curated legal basis and provenance.
4. `local_path` resolves inside the configured local papers directory.
5. The source is a PDF supported by the current parser.
6. The row is not knowingly duplicated solely to inflate the corpus size.
7. Any expected duplicate document is identified in notes so the observed duplicate outcome can be reviewed.

Candidate, deferred, excluded, metadata-only, or unresolved legal rows do not count toward the 100 imported rehearsal inputs.

## Prohibited committed artifacts

Do not commit:

- source PDFs;
- SQLite databases or journal files;
- extracted full text;
- raw provider responses;
- private absolute paths;
- unsanitized generated run reports;
- cache, temporary, or editor files.

Only the rehearsal procedure, sanitized templates, synthetic fixtures, and reviewed aggregate findings may be committed.

## Preflight sequence

1. Confirm the M12 branch and current commit.
2. Confirm the working tree contains no source PDFs or database files staged for commit.
3. Run `ke corpus-validate <corpus.json> --check-files`.
4. Confirm manifest validity is `valid` and import readiness is `ready`.
5. Confirm the source summary contains exactly 100 included and importable rows.
6. Confirm all local files are present.
7. Record the local Python, Poetry, PyMuPDF, SQLite, operating-system, CPU, and memory environment in the local operator worksheet.
8. Record the start wall-clock timestamp immediately before import.

## Rehearsal execution sequence

### Fresh run

1. Run `ke corpus-import <corpus.json>`.
2. Record the returned import run ID.
3. Record the end wall-clock timestamp and calculate elapsed time externally.
4. Generate the M12 run report from the persisted import run.
5. Reconcile the report item total with the 100 manifest rows.

### Idempotent rerun

1. Run the same manifest again using the supported resume path.
2. Confirm previously successful items are not imported as new papers.
3. Confirm duplicate and skip outcomes remain explicit.
4. Generate a report for the linked run and verify parent-run lineage.

### Failed-item retry

When retryable failures exist:

1. Correct only the local input or environmental cause.
2. Run the failed-item retry mode against the original run.
3. Confirm only eligible failed items are retried.
4. Confirm successful items remain linked rather than re-imported.
5. Generate a report for the retry run.

Do not manufacture failures in the real corpus merely to satisfy this section. Synthetic automated tests cover deterministic failure and retry cases.

## Required measurements

### Persisted measurements

The generated run report must include values derived from database state:

- run ID, mode, status, review status, and parent run ID;
- corpus identity and manifest version;
- manifest snapshot ID and combined SHA-256;
- created and completed timestamps;
- total source rows and persisted import-item count;
- item counts by status;
- duplicate outcome counts;
- matched paper and matched import-item counts;
- retry-link count;
- issue counts by code, severity, category, blocking state, and affected item;
- warning, structural-error, and import-blocker reconciliation;
- per-item source ID, status, duplicate outcome, match lineage, and retry lineage.

### Manual operator measurements

The current schema does not provide a dedicated high-resolution execution duration or resource-usage series. The operator worksheet must therefore record:

- wall-clock start and end timestamps;
- elapsed duration;
- peak memory when measured with an external tool;
- approximate database size before and after;
- notable CPU, disk, or environment observations;
- any manual interventions.

Manual measurements must be labeled as operator-recorded and must not be presented as database-derived.

## Explicit current-schema gaps

The M12 report must state when the following are unavailable:

- high-resolution per-stage timings;
- CPU, memory, and disk telemetry;
- durable M11 external metadata candidates or metadata-conflict counts;
- parser warning categories not persisted as import issues;
- scientific quality or evidence assessment.

A missing measurement is a technical-debt finding, not permission to estimate it.

## Required outcome reconciliation

For every report:

- persisted item count must equal the sum of item-status counts;
- duplicate-outcome counts must not exceed item count;
- issue summary counts must equal the persisted issue records;
- run warning, structural-error, and import-blocker totals must reconcile with issues;
- imported, failed, skipped, duplicate, and review-required categories must map to documented item statuses rather than inferred prose;
- any reconciliation failure blocks M12 completion and must be fixed at its root cause.

## Technical-debt findings template

Each finding must contain:

- identifier;
- category;
- observed evidence;
- affected run and item IDs when safe;
- operational impact;
- reproducibility steps;
- proposed smallest fix;
- M12 blocker: yes or no;
- recommended milestone owner: M12, M13, or later.

Required categories:

- parser failure;
- empty or malformed document;
- duplicate ambiguity;
- legal or provenance gap;
- metadata conflict/reporting gap;
- performance bottleneck;
- resume or retry defect;
- reporting or schema gap.

## M12 acceptance criteria

M12 is complete only when:

1. The deterministic run-report implementation and synthetic 100-item tests pass.
2. The operator checklist and sanitized report contract are committed.
3. A real legally usable 100-paper corpus passes preflight.
4. The real fresh run completes with understandable partial-success behavior.
5. A resume or rerun demonstrates idempotent handling.
6. Retry behavior is verified when real retryable failures exist, or is explicitly limited to synthetic proof when none occur.
7. The real run results and technical-debt findings are reviewed without committing restricted artifacts.
8. Architecture, security, privacy, dependency, and full-diff review is complete.
9. The exact final PR head passes the complete Quality gate.

A synthetic 100-item test alone does not satisfy the real rehearsal requirement.

## Non-goals

- PDF downloading;
- parallel or distributed workers;
- parser redesign without a verified blocker;
- claim extraction;
- scientific synthesis;
- confidence scoring;
- M13 scale-readiness approval.
