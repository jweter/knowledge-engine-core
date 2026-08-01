# M14 Controlled 500-Paper Rehearsal Report

## Decision

`PROCEED`

## Execution State

`completed`

## Immutable Input Identity

- Repository commit SHA: `4109f8902021fa0be96617e61c3c5a95addd182c`
- Corpus ID: `m14_rehearsal`
- Manifest version: `1`
- `corpus.json` SHA-256: `327ddf49ea4cc21ae420160d620f0c3412dddbc5715ff9204c83a4b346fdf74c`
- `sources.csv` SHA-256: `92ca93b77c274e8559ea81c033d09f7ad6631aa352d9eb48106c6562aec069d5`
- Accepted source rows: `500`
- Unique source IDs: `500`
- Included full-text rows: `500`
- Present declared local files: `500`
- Rows with explicit licensing or authorization basis: `500` (all `usage_status = approved_open_access`, `license_type = CC BY`)

## Privacy-Safe Environment

- Operating-system family and major version: Linux (Ubuntu 24.04 LTS)
- Architecture: x86_64
- Python version: 3.12.3 (project virtualenv)
- Storage class: unknown (managed remote execution environment; underlying physical storage medium not independently verifiable from inside the container)
- Logical CPU count: 4
- Memory band: 8-16 GB

No hostname, username, home directory, IP address, machine serial number, cloud account, or absolute private path appears above or elsewhere in this report.

## Preflight

- Exact-head quality suite passed: true (`ruff check .`, `ruff format --check .`, `mypy knowledge_engine tests`, `pytest` — 494 passed)
- Manifest validation passed: true (`ke corpus-validate work/m14_rehearsal/corpus.json --check-files` — manifest validity `valid`, import readiness `ready`, 0 blocking structural errors, 0 import-blocking issues, 0 warnings)
- Local-file readiness passed: true (500 present, 0 missing, 0 invalid)
- Duplicate source IDs: 0
- Unsafe or absolute paths: 0
- Database bytes before import: `253952`

## Fresh Import

- Import-run ID: `6cff8536-78c0-47b3-9411-dfef61ba4222`
- Run mode: `fresh`
- Run status: `succeeded`
- Review status: `clear`
- Elapsed seconds: `~117.3` (created `2026-07-22T08:07:36Z`, completed `2026-07-22T08:09:33Z`)
- Source rows: `500`
- Persisted items: `500`
- Imported: `500`
- Failed: `0`
- Skipped: `0`
- Needs review: `0`
- Warning count: `0`
- Issue count: `0`
- Issue-code counts: none
- Database bytes after: `155643904`
- Database growth bytes: `155389952` (~148.2 MiB)
- Count reconciliation passed: true

Required reconciliation:

```text
source_rows = persisted_items = imported + failed + skipped + needs_review
500 = 500 = 500 + 0 + 0 + 0
```

Independently re-derived from the database directly (not solely CLI output): `papers = 500`, `paper_texts = 500`, `paper_search (FTS) = 500`, `import_items = 500`, `import_runs = 1`, `import_issues = 0`.

## Linked Resume

- Resume import-run ID: `cefa00fe-87b7-4f71-a2e5-762a74eb6c65`
- Parent import-run ID: `6cff8536-78c0-47b3-9411-dfef61ba4222`
- Run status: `succeeded`
- Review status: `clear`
- Elapsed seconds: `~1.76` (created `2026-07-22T08:10:23Z`, completed `2026-07-22T08:10:23Z`)
- Imported: `0`
- Failed: `0`
- Skipped: `500`
- Needs review: `0`
- Paper rows before/after: `500` / `500`
- Paper-text rows before/after: `500` / `500`
- FTS rows before/after: `500` / `500`
- Lineage-reconciled items: `500` / `500` (every resumed item carries a non-null `matched_paper_id` and `matched_import_item_id` pointing to the fresh run's records; independently counted directly from the resume run's item log, not solely the summary line)
- Idempotency passed: true

The parent run (`6cff8536-78c0-47b3-9411-dfef61ba4222`) was re-read via `ke corpus-run-show` after the resume completed and is byte-for-byte unchanged from its state immediately after the fresh import: same `run_status`, `run_mode`, `created`/`completed` timestamps, manifest snapshot ID, and combined snapshot hash.

## Rates

Denominator: 500 accepted rows.

- Failure numerator and rate: `0` / `0.000`
- Blocking-issue numerator and rate: `0` / `0.000`
- Warning numerator and rate: `0` / `0.000`
- Review-required numerator and rate: `0` / `0.000`

## Stop Condition

- Code: none
- Sanitized summary: No stop condition occurred. No unexpected exception was raised in either run. No count failed to reconcile. The linked resume created zero unexpected papers, paper-text rows, or FTS rows, and every item retained complete lineage. Elapsed time and database growth were both measured directly (wall-clock timestamps and `stat`-reported byte counts). Neither manifest file's SHA-256 changed between the value recorded before initialization and the value re-checked after the resume completed.

## Artifact Hygiene

- PDFs committed: false (`papers/corpora/m14_rehearsal/` is excluded by `.gitignore`'s `papers/**/*.pdf` pattern; confirmed via `git status --porcelain --ignored`)
- Databases committed: false (rehearsal database was initialized entirely outside the repository, under a scratch directory via `KE_DATA_DIR`, and is not tracked by Git at any path)
- Private paths present: false (this report and the working manifest use only repository-relative paths; the absolute scratch path used for the external database is not repeated in this document)
- Raw exception text present: false (both runs completed with exit code 0; no exception was raised or caught)
- Temporary artifacts present: false (the working `corpus.json`, `sources.csv`, and `license_policy.md` live under `work/`, which is excluded by `.gitignore`; confirmed via `git status --porcelain --ignored`)
- Complete Git diff reviewed: true (`git status --porcelain` shows only this report as a new file prior to commit)
- Exact-head quality suite passed after report generation: true (re-run after writing this report; see commit history for the exact run)

## Unknowns

- The physical storage medium backing this managed remote execution environment's filesystem (local SSD vs. network-backed volume) could not be independently verified from inside the container, so "Storage class" above is recorded as `unknown` rather than guessed.
- This rehearsal exercises only the `fresh` and `resume` (`--resume-from`) run modes. The `--retry-failed-from` mode was not exercised, because zero items failed in the fresh run and there was therefore nothing to retry. This is expected given a batch that was already adjudicated and acquisition-verified before import, not a gap in the rehearsal.
- No `needs_review` items occurred, so the needs-review resolution path (beyond the CLI reporting a zero count) was not exercised end-to-end by this rehearsal.

## Final Rationale

Every entry-gate condition held: exactly 500 accepted rows, unique stable `source_id`s, an explicit usage status and licensing basis on every included row, every declared local file present and readable, no PDF or database artifact tracked by Git, and a rehearsal database initialized outside the repository with its byte size measured both before and after.

The fresh import reconciled exactly (`500 = 500 = 500 + 0 + 0 + 0`) with zero failures, zero issues, and zero warnings, both from the CLI's own summary and from an independent direct query of the underlying SQLite tables. The linked resume against the identical manifest snapshot (confirmed by an unchanged combined snapshot hash) was fully idempotent: it created no new paper, paper-text, or FTS row, skipped all 500 items with complete parent lineage, and left the parent run's own record byte-for-byte unchanged. No stop condition in the runbook was triggered at any point.

The only gaps are the two explicitly listed unknowns above, neither of which reflects an ingestion defect: the storage-class field could not be verified in this environment, and the retry-failed-from resume path had no failed items to exercise because the batch was already fully clean going into the import. Given a completed, fully reconciled, idempotent rehearsal with no stop condition and no unresolved count mismatch, the evidence supports `PROCEED`. The continuation point is the next roadmap milestone that builds on a proven ingestion pipeline (see `docs/roadmap.md`), not a repeat of this rehearsal.
