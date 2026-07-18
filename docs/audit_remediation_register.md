# Audit Remediation Register

This register reconciles the read-only audit performed against M13 main commit
`0831d0861aa1282f43834a16e0ba208dc6d1b248` with the repository after PR #20.

## Confirmed defects

| Audit defect | Current status | Evidence or follow-up |
|---|---|---|
| 1. Roadmap stale at M8 | Fixed | PR #20 added M9–M13 history and the M14 continuation. A post-merge wording cleanup remains on this branch. |
| 2. README capability drift | Fixed | PR #20 replaced the stale Phase 0 status and removed completed limitations. |
| 3. Resolved M9 debt shown active | Fixed | `docs/technical_debt.md` now records it under Resolved. |
| 4. Broad parser exception catch | Fixed | Typed `DocumentParseError` hierarchy; unexpected defects propagate. |
| 5. Broad duplicate-resolution catch | Fixed | Typed `DuplicateResolutionError`; unexpected defects propagate in fresh and linked ingestion. |
| 6. Persistence failure taxonomy | Active | GitHub issue #22. Must be completed before relying on repeated large-run failure evidence. |
| 7. Result DTO raw status strings | Fixed | `ImportedCorpusRun` uses `RunStatus` and `ReviewStatus`. |
| 8. Generic path `ValueError` | Fixed | `UnsafePersistedPathError` is used and caught explicitly. |
| 9. Early returns omit review state | Fixed | Shared explicit result construction covers fresh and linked early returns. |
| 10. Unused status-helper parameter | Fixed | Removed from `_final_run_status` and callers. |
| 11. Changelog incomplete | Fixed | M10–M13 and pre-M14 hardening are represented under Unreleased. |
| 12. Black/Ruff inconsistency | Fixed | Ruff is the sole documented formatter and CI formatter. |

## Audit debt disposition

### Immediate or prerequisite

- TD-006 persistence failure classification: issue #22.
- TD-016 exact-head CI evidence: PR #20 exact head passed Quality run 359; the
  workflow also runs on pushes to `main`. GitHub's legacy combined-status endpoint
  still returns no contexts for the squash merge commit, so PR-run evidence remains
  the authoritative recorded proof.
- TD-018 tracked next milestone: issue #21.

### Active, evidence-driven Phase 1 debt

- Poetry certificate behavior on the affected Windows machine.
- Best-effort scientific PDF parsing and metadata extraction.
- FTS update/delete synchronization.
- Lightweight migration threshold.
- Work/version/file/assertion identity model.
- Page-level extraction provenance before Phase 2.
- Parser and duplicate-resolution taxonomies should expand only from observed,
  recoverable corpus failures.

### Deferred by design

- Alembic or another formal migration framework until schema complexity warrants it.
- GROBID or another structured scholarly parser until corpus evidence justifies it.
- Persistent operational telemetry until repeated runs establish stable semantics.
- Vector search, knowledge graph, AI reasoning, API, web, provider frameworks, and
  distributed orchestration remain outside the current milestone.

## Test gaps retained for future milestones

- Persistence category and rollback tests are required by issue #22.
- Property-based status, path-safety, DOI-normalization, and duplicate-conflict tests
  remain useful hardening work but are not prerequisites for the first bounded M14
  rehearsal unless observed evidence exposes those risks.
- Migration history, interruption, and rerun tests become mandatory when the project
  adopts a formal migration framework or retains multiple complex schema histories.
- FTS repair/rebuild tests belong with update/delete synchronization.
- Page/span provenance and provider-conflict tests belong before Phase 2 evidence
  extraction and multi-provider canonicalization.

## Current continuation order

1. Complete issue #22 without starting the 500-paper rehearsal.
2. Re-run exact-head quality checks and review the persistence-contract PR.
3. Confirm issue #21 entry conditions and prepare the legal 500-row corpus locally.
4. Execute one bounded rehearsal and linked resume under M13 stop and hygiene rules.
