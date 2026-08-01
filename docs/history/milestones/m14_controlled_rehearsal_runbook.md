# M14 Controlled 500-Paper Rehearsal Runbook

## Status

This runbook prepares Issue #21 for execution. It does not assert that the 500-paper rehearsal has run.

The rehearsal must remain blocked until the operator can prove all entry conditions against one local, legally curated corpus. Source PDFs and the local database must remain outside Git.

## Immutable Inputs

Record these values before initialization or import:

- Git commit SHA used for the rehearsal;
- corpus ID and manifest version;
- SHA-256 of `corpus.json`;
- SHA-256 of `sources.csv`;
- accepted source-row count;
- count of included full-text rows;
- count of locally present declared files;
- count of distinct stable `source_id` values;
- count of rows with an explicit usage status and licensing basis.

Do not record usernames, home-directory names, absolute local paths, provider payloads, tokens, source PDF contents, or database contents.

## Entry Gate

Proceed only when every statement is true:

1. The checked-out commit contains the merged persistence-failure taxonomy from PR #24.
2. Exactly 500 accepted manifest rows are present.
3. Every accepted row has a unique, non-empty stable `source_id`.
4. Every included full-text row has an allowed usage status, an explicit licensing basis, and a safe relative `local_path`.
5. Every declared local file exists and is readable.
6. No local PDF, SQLite database, cache, generated diagnostic archive, or private environment file is tracked by Git.
7. A new rehearsal database location has been selected outside the repository.
8. Database byte size can be measured before and after execution.

Any failed statement is a stop condition. Do not reduce the row count, synthesize documents, or silently exclude failures to reach 500.

## Privacy-Safe Environment Identity

Record only:

- operating-system family and major version;
- architecture;
- Python version;
- Knowledge Engine commit SHA;
- storage class such as local SSD, network filesystem, or unknown;
- logical CPU count when available;
- memory tier rounded to a broad band, such as `<8 GB`, `8-16 GB`, `16-32 GB`, or `>32 GB`.

Do not record hostname, username, machine serial number, home directory, IP address, cloud account, or exact private path.

## Preflight Sequence

Run from the repository root using the exact commit intended for the rehearsal.

1. Confirm the working tree is clean.
2. Run the complete quality suite required by the repository.
3. Validate the corpus with local-file checks enabled.
4. Independently reconcile:
   - source rows = 500;
   - unique source IDs = 500;
   - accepted rows = 500;
   - declared included files = present included files;
   - duplicate source IDs = 0;
   - unsafe or absolute paths = 0.
5. Initialize a new local database outside the repository.
6. Measure database bytes before import.
7. Capture the sanitized environment identity.

Do not continue if validation reports an import blocker or if any count cannot be independently reproduced.

## Fresh Import

Execute a fresh `corpus-import` against the immutable `corpus.json` without a resume or retry option.

Record:

- UTC start and completion timestamps;
- monotonic elapsed seconds;
- fresh import-run ID;
- run mode and terminal run status;
- source-row count;
- persisted import-item count;
- imported, failed, skipped, and needs-review counts;
- warning and issue counts;
- database bytes after import;
- database growth in bytes;
- every stable issue code and its count.

The following equality must hold:

```text
source_rows = persisted_items = imported + failed + skipped + needs_review
```

A mismatch is a stop condition and requires a separate defect issue and PR.

## Linked Resume

Run a linked resume against the same immutable corpus snapshot using:

```text
--resume-from <fresh-import-run-id>
```

Record:

- linked resume run ID;
- parent run ID;
- terminal run and review statuses;
- imported, failed, skipped, and needs-review counts;
- paper, paper-text, and FTS row counts before and after resume;
- lineage reconciliation count.

The resume passes idempotency only when:

- no unexpected new paper is created;
- no unexpected paper-text or FTS row is created;
- every linked item has complete parent/source lineage where required;
- the parent run and parent items remain unchanged.

## Stop Conditions

Stop immediately and preserve only sanitized evidence when any of these occurs:

- unexpected parser, duplicate-resolution, ORM, assertion, type, or programming exception;
- a source, item, or terminal-outcome count mismatch;
- a linked resume creates an unexpected paper or loses lineage;
- an expected item failure cannot be distinguished from a systemic defect;
- elapsed time or database growth cannot be measured accurately;
- raw exception text, private paths, provider payloads, source documents, or database artifacts would enter Git;
- the input manifest changes after its hashes were recorded.

Do not convert a systemic exception into a routine item failure in the report.

## Rates

Calculate using exactly 500 accepted source rows as the denominator:

- failure rate = failed items / 500;
- issue rate = items with one or more blocking ingestion issues / 500;
- warning rate = items with one or more warnings / 500;
- review-required rate = needs-review items / 500.

Report both the integer numerator and decimal rate. Do not round away non-zero events.

## Artifact Hygiene

Before committing the report:

1. Inspect the complete Git diff.
2. Verify no PDF, SQLite, database journal, cache, log archive, environment file, credentials, absolute private paths, or raw exception text is present.
3. Verify identifiers in the report are limited to import-run IDs, stable source counts, manifest hashes, and public repository commit SHAs.
4. Run the exact-head quality suite again.
5. Commit only the deterministic sanitized report and any narrowly necessary tested code correction.

## Final Decision

Use one of these decisions:

- `PROCEED`: all entry conditions and reconciliation invariants passed, resume was idempotent, no stop condition occurred, and evidence is complete.
- `HOLD`: the rehearsal completed but one or more explicit uncertainties or acceptance thresholds require review.
- `STOPPED`: a defined stop condition occurred or a required input/evidence field was unavailable.

The final report must list every unknown explicitly. Missing evidence must never be represented as zero, false, or passed.

## Current Continuation Point

The repository-side preparation is complete when this runbook and the M14 evidence contract pass quality checks. Execution remains blocked until an operator supplies the actual local 500-row corpus, its 500 matching legally usable files, and an external database location.