# Daily Repository Status

**Date:** 2026-07-19 07:00 CEST  
**Repository:** `jweter/knowledge-engine-core`  
**Branch inspected:** `main`  
**Draft PR:** None open  
**Current milestone:** M14 — controlled 500-paper ingestion rehearsal

## Current state

The latest repository commit visible through the connected GitHub app is `6d4a02bacccb6e2dee66f590babd8aa63eacd012` (`feat: add approval-gated PMC OA acquisition`). It is the squash-merge commit for PR #31. PR #31 is closed and merged; it is not a current draft pull request.

M14 has advanced from planning and candidate discovery to an approval-gated PMC Open Access acquisition path. Operators can now review discovery candidates, create an explicit approval file, acquire approved PDFs from the official PMC OA host, and persist a sanitized receipt. M14 is not complete because the repository still lacks verified evidence for exactly 500 accepted source rows with matching approved local PDFs and the controlled fresh-import plus linked-resume rehearsal.

The GitHub connector does not expose a local checkout, so uncommitted working-tree changes cannot be inspected. No claim is made about local-only changes on the Codex machine.

## Recent completed work

- PR #25 prepared the controlled M14 rehearsal documentation.
- PR #29 added PubMed/PMC candidate discovery.
- PR #31 added approval-gated PMC OA acquisition.
- Candidate approvals are cross-checked against PMID, PMCID, reported license, and PDF URL before network access.
- Acquisition rejects unsafe URLs, unsupported hosts or ports, duplicate identifiers or filenames, symlinks, existing outputs, oversized responses, and non-PDF payloads.
- The acquisition batch stages every PDF before finalizing names and rolls back PDFs if acquisition or receipt persistence fails.
- Sanitized receipts include filename, byte count, and SHA-256 without committing PDFs or private working artifacts.

## Current errors and likely root causes

No open runtime or CI error was visible in the connected GitHub state inspected during this update.

The latest completed PR documents five errors found and resolved during implementation:

1. **Non-transactional multi-file acquisition** — High confidence root cause: files were initially committed independently rather than staged as one batch.
2. **Receipt failure could leave PDFs without durable evidence** — High confidence root cause: receipt persistence and PDF rollback were not coupled at the CLI boundary.
3. **Duplicate approved filenames could collide** — High confidence root cause: uniqueness validation did not cover output filenames before staging.
4. **Rollback failures could leak raw filesystem errors** — High confidence root cause: low-level `OSError` values were not translated into the sanitized domain error boundary.
5. **Ruff formatting failures** — High confidence root cause: generated edits did not exactly match repository formatting and final-newline requirements.

All five are recorded as resolved in PR #31. No new error was reproduced because this status task is read-only and the connector cannot execute the repository test suite.

## Tests and checks observed

PR #31 records Quality workflow run 407 as passing on exact head `9cbfd9a1707dee1e18bd04b06dd1ba1464e2ef16`, including:

- Ruff formatting;
- Ruff lint;
- strict mypy;
- full pytest;
- diff hygiene;
- temporary-artifact rejection.

The connected GitHub status endpoint returned no separate commit-status records for merge commit `6d4a02bacccb6e2dee66f590babd8aa63eacd012`. This does not contradict the PR-recorded workflow result, but it means no additional post-merge status evidence was available through that endpoint.

## Remaining M14 work before a PR can be marked ready and merged

1. Run candidate discovery for the selected M14 corpus scope in controlled pages.
2. Perform explicit human review of candidate licenses, identifiers, and PMC OA PDF URLs.
3. Create approval records without automatically promoting discovery output.
4. Acquire approved PDFs in bounded batches and retain sanitized acquisition receipts outside committed private artifacts.
5. Reconcile receipts against curated `sources.csv` rows.
6. Reach and validate exactly 500 accepted rows with exactly 500 matching approved local PDF files.
7. Run the controlled M14 preflight and verify manifest, row, file, provenance, and prohibited-artifact constraints.
8. Execute the fresh 500-paper import and record sanitized aggregate evidence.
9. Execute the linked-resume run and verify prior-item linkage, expected skips, stable paper counts, and no unexpected reimports.
10. Exercise a retryable-failure path with real evidence if one occurs; otherwise preserve the explicit synthetic-only boundary.
11. Record performance, reliability, privacy, security, and operational findings in the M14 report and error-resolution documentation.
12. Run the complete Quality gate on the exact final branch head.
13. Confirm a draft PR exists, is mergeable, has a clean review state, and satisfies its acceptance criteria before marking it ready.
14. Merge only after all M14 acceptance evidence is complete and independently reviewable.

## Exact continuation point

Begin the controlled operator phase from `main` at commit `6d4a02bacccb6e2dee66f590babd8aa63eacd012`: run bounded PubMed/PMC candidate discovery, review candidates, create the first explicit approval batch, and use `ke pmc-oa-acquire` to acquire approved PDFs with a sanitized receipt. Do not claim M14 completion until the curated corpus reaches exactly 500 accepted rows and matching files and both fresh-import and linked-resume rehearsal evidence are complete.

## Access limitations

- The connected GitHub app can inspect repository, commit, PR, file, and selected CI metadata.
- It cannot inspect the Codex machine's local working tree or uncommitted files.
- It cannot execute Poetry, Ruff, mypy, pytest, or the M14 operator workflow in this read-only status run.
- No website post or email was attempted.
