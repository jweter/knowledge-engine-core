# M14 Controlled 500-Paper Rehearsal Report

## Decision

`STOPPED | HOLD | PROCEED`

## Execution State

`not_started | stopped | completed`

## Immutable Input Identity

- Repository commit SHA:
- Corpus ID:
- Manifest version:
- `corpus.json` SHA-256:
- `sources.csv` SHA-256:
- Accepted source rows:
- Unique source IDs:
- Included full-text rows:
- Present declared local files:
- Rows with explicit licensing or authorization basis:

## Privacy-Safe Environment

- Operating-system family and major version:
- Architecture:
- Python version:
- Storage class:
- Logical CPU count:
- Memory band:

No hostname, username, home directory, IP address, machine serial number, cloud account, or absolute private path may appear here.

## Preflight

- Exact-head quality suite passed:
- Manifest validation passed:
- Local-file readiness passed:
- Duplicate source IDs:
- Unsafe or absolute paths:
- Database bytes before import:

## Fresh Import

- Import-run ID:
- Run mode:
- Run status:
- Review status:
- Elapsed seconds:
- Source rows:
- Persisted items:
- Imported:
- Failed:
- Skipped:
- Needs review:
- Warning count:
- Issue count:
- Issue-code counts:
- Database bytes after:
- Database growth bytes:
- Count reconciliation passed:

Required reconciliation:

```text
source_rows = persisted_items = imported + failed + skipped + needs_review
```

## Linked Resume

- Resume import-run ID:
- Parent import-run ID:
- Run status:
- Review status:
- Elapsed seconds:
- Imported:
- Failed:
- Skipped:
- Needs review:
- Paper rows before/after:
- Paper-text rows before/after:
- FTS rows before/after:
- Lineage-reconciled items:
- Idempotency passed:

## Rates

Use exactly 500 accepted rows as the denominator.

- Failure numerator and rate:
- Blocking-issue numerator and rate:
- Warning numerator and rate:
- Review-required numerator and rate:

## Stop Condition

- Code:
- Sanitized summary:

Do not include raw exception text. Unexpected systemic exceptions must be identified by stable category and investigated in a separate defect issue and PR.

## Artifact Hygiene

- PDFs committed: false
- Databases committed: false
- Private paths present: false
- Raw exception text present: false
- Temporary artifacts present: false
- Complete Git diff reviewed:
- Exact-head quality suite passed after report generation:

## Unknowns

List every unknown explicitly. Missing evidence must not be represented as zero, false, passed, or not applicable.

## Final Rationale

Explain why the evidence supports `STOPPED`, `HOLD`, or `PROCEED`, including any limitations and the exact continuation point.