# M14 Rehearsal Readiness

## Repository Preparation

- [x] Persistence failure taxonomy merged in PR #24.
- [x] Fresh and linked ingestion use narrow expected failure contracts.
- [x] Unexpected programming and ORM defects propagate systemically.
- [x] Controlled rehearsal runbook added.
- [x] Machine-checkable evidence schema added.
- [x] Stopped-state example added and tested.
- [x] Sanitized report template added.

## Execution Entry Gate

- [ ] Exactly 500 legally curated accepted rows are available locally.
- [ ] Exactly 500 unique stable source IDs are present.
- [ ] Every included row has an explicit usage and licensing basis.
- [ ] Every declared included file exists and is readable.
- [ ] The immutable manifest and source CSV hashes are recorded.
- [ ] A fresh external database location is available and measurable.
- [ ] The operator can run the complete local quality and rehearsal sequence.

## Current Decision

`STOPPED`

The repository-side preparation can be reviewed and tested, but the actual M14 rehearsal cannot begin in this environment because the required local 500-paper corpus and external database are unavailable. No corpus counts, timings, database growth, import outcomes, or resume-idempotency results have been inferred or fabricated.

## Exact Continuation Point

1. Check out `m14-controlled-rehearsal` at its verified exact head.
2. Supply the legally curated local corpus without adding PDFs to Git.
3. Execute the entry gate in `docs/m14_controlled_rehearsal_runbook.md`.
4. Stop immediately if any gate fails.
5. Populate a new evidence JSON instance and the report template from measured persisted results.
6. Commit only the sanitized report and evidence, rerun the exact-head quality suite, and review artifact hygiene before merging.