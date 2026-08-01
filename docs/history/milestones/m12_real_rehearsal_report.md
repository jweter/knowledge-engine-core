# M12 Real 100-Paper Rehearsal Report

## Decision

The controlled M12 rehearsal passed its operational acceptance criteria on an ephemeral GitHub-hosted Ubuntu runner. The run used exactly 100 locally staged PDFs selected from the official PubMed Central Open Access dataset service. No PDFs, SQLite database, extracted full text, private runner paths, or raw package responses are committed.

This report records operational ingestion evidence only. It does not claim scientific validation, evidence synthesis, metadata correctness, or corpus representativeness.

## Rehearsal identity

- Draft PR: `#17`
- Branch head used for the successful run: `7d27de514744c47ce4e22acbec7345e0423f2895`
- GitHub Actions merge-ref commit reported by the runner: `b0017801ed24115940c63669f97bf6685e7db26f`
- Rehearsal workflow run: `29632996792` / run number `8`
- Quality workflow run: `29632996794` / run number `294`
- Artifact digest: `sha256:a47228b3bd68a29852c9731bafed91399c0c33f1251701bb0fc75d3840c56be7`
- Fresh import run ID: `725dcf21-76d4-45f8-b266-c715363c9f3d`
- Resume import run ID: `38718390-d85b-42ac-82f2-0f5019386870`
- Combined manifest SHA-256: `e19b02687b713e3e494ce4564d6dea683fb40c89189c36916f5ab4e548b1f1ef`

## Legal and provenance preflight

The ephemeral corpus preparation accepted only PMC OA service records that:

- were not marked retracted;
- exposed an official OA dataset package;
- carried a machine-readable `CC0`, `CC BY`, `CC BY-SA`, or `CC BY-ND` license;
- contained a bounded PDF with a valid PDF signature;
- stayed within the configured response and extracted-file size limits.

Observed selected licenses:

- `CC BY`
- `CC0`

Three candidate packages were rejected by bounded validation before the final 100 were selected. They were not included in the corpus. The current preparation evidence records these as aggregate `ValueError` failures and does not retain package URLs or payloads.

Preflight results:

- Declared source rows: `100`
- Valid source rows: `100`
- Manifest validity: `valid`
- Import readiness: `ready`
- Present local PDFs: `100`
- Missing local PDFs: `0`
- Unresolved legal rows: `0`

## Environment

The rehearsal ran on a GitHub-hosted Ubuntu runner with Python 3.12 and the exact Poetry-locked project dependencies. Detailed package versions and bounded machine characteristics were captured in the sanitized workflow artifact. Private installation and workspace paths were excluded.

## Fresh run

Operator-recorded measurements:

- Elapsed wall-clock duration: `9` seconds
- Database bytes before import: `0`
- Database bytes after import: `26,349,568`

Persisted outcomes:

- Run mode: `fresh`
- Run status: `succeeded`
- Review status: `clear`
- Declared source rows: `100`
- Persisted import items: `100`
- Imported items: `100`
- Matched paper records: `100`
- Matched prior import items: `0`
- Retry-linked items: `0`
- Duplicate outcomes: `none` for all 100 items
- Warning issues: `0`
- Manifest-blocking issues: `0`
- Import-blocking issues: `0`

The fresh run created exactly 100 paper records.

## Idempotent resume

Operator-recorded measurement:

- Elapsed wall-clock duration: `1` second

Persisted outcomes:

- Run mode: `resume`
- Parent run: `725dcf21-76d4-45f8-b266-c715363c9f3d`
- Run status: `succeeded`
- Review status: `clear`
- Declared source rows: `100`
- Persisted import items: `100`
- Skipped items: `100`
- Matched paper records: `100`
- Matched prior import items: `100`
- Retry-linked items: `0`
- Warning issues: `0`
- Manifest-blocking issues: `0`
- Import-blocking issues: `0`

Paper records after the resume remained `100`. Unexpected new papers during resume: `0`.

## Failed-item retry

The real fresh run produced zero failed items, so there was no genuine corrected local or environmental failure to retry. M12 retry behavior therefore remains verified by deterministic synthetic automated tests only. No failure was manufactured in the real corpus.

## Reconciliation

The generated reports reconciled successfully:

- fresh item statuses sum to 100;
- resume item statuses sum to 100;
- fresh matched-paper count is 100;
- resume matched-paper count is 100;
- resume matched-prior-item count is 100;
- no issue-count discrepancy was present;
- paper count remained unchanged after resume.

## Security and privacy review

The successful evidence artifact passed checks that rejected:

- PDF files;
- SQLite files;
- private GitHub runner workspace paths.

The artifact contained only the sanitized environment summary, preparation summary, selected-source metadata, validation output, import command output, generated run reports, and aggregate rehearsal summary.

## Technical-debt findings

### M12-TD-1 — Preparation rejection categories are too coarse

- Category: reporting / operational diagnostics
- Evidence: three candidate packages were rejected as aggregate `ValueError` outcomes.
- Impact: the evidence does not distinguish an oversized package, missing bounded PDF, malformed archive member, or other validation rejection.
- Smallest proposed fix: use explicit internal exception types or reason codes for bounded package and PDF rejection.
- M12 blocker: no; 100 legally usable inputs were still selected and all accepted inputs passed preflight.
- Recommended milestone: M13.

### M12-TD-2 — High-resolution stage telemetry is not persisted

- Category: performance / schema gap
- Evidence: only external fresh and resume wall-clock measurements were available.
- Impact: parser, persistence, and FTS stage costs cannot be separated from persisted state.
- Smallest proposed fix: add bounded per-stage duration fields or structured run metrics after access patterns are reviewed.
- M12 blocker: no.
- Recommended milestone: M13.

### M12-TD-3 — External metadata candidates remain preview-only

- Category: metadata conflict / reporting gap
- Evidence: M11 candidates and conflicts are intentionally not persisted.
- Impact: the rehearsal cannot report durable provider conflict counts.
- Smallest proposed fix: retain the M11 no-persistence decision until a reviewed enrichment workflow justifies schema changes.
- M12 blocker: no.
- Recommended milestone: later Phase 1 work.

## Acceptance decision

- Real 100-paper preflight passed: **yes**
- Fresh run completed successfully: **yes**
- Idempotent resume demonstrated: **yes**
- Retry behavior verified: **synthetic**, because no real retryable failure occurred
- Count reconciliation passed: **yes**
- Restricted-artifact and private-path checks passed: **yes**
- Exact rehearsal-head Quality gate passed: **yes**
- Scientific validation claimed: **no**
