# Daily Repository Status

**Date:** 2026-07-21 06:58 CEST  
**Repository:** `jweter/knowledge-engine-core`  
**Branch inspected:** `m14-acquire-exactly-500`  
**Current draft PR:** #75 — `feat: acquire exactly 500 approved M14 PDFs`  
**Current milestone:** M14 — controlled 500-paper rehearsal, stages 4–5 acquisition and exact reconciliation

## Current state

PR #75 is open, draft, mergeable, and targets `main`. The verified head before this status-only update was `66995e2e88498611f8f3996f3ed4bba44864e3a0`. The PR is scoped to acquiring the exactly 500 approvals produced by PR #74, validating receipt and local-PDF evidence, and stopping before manifest generation or ingestion.

The connected GitHub app cannot inspect a Codex machine's local checkout. Local `git status`, uncommitted changes, untracked files, and the currently checked-out local branch remain unverified. No clean-working-tree claim is made.

## Completed work

- PR #74 produced a deterministic set of exactly 500 approved M14 records from the previously measured accepted pool.
- PR #75 added exact-count approval validation, duplicate-PMCID rejection before network access, acquisition regression coverage, transactional PDF acquisition, and reconciliation across approvals, receipts, files, byte counts, and SHA-256 evidence.
- The prior formatter failure in `knowledge_engine/pmc_acquisition.py` was corrected on commit `efad9813a2a77d32448759bfe7f9e795d0b1cef4`.
- `docs/error_log.md` was added on commit `66995e2e88498611f8f3996f3ed4bba44864e3a0` to record the unresolved external acquisition failure and evidence limitations.
- Exact-head Quality CI now passes on commit `66995e2e88498611f8f3996f3ed4bba44864e3a0`.

## Tests and checks actually observed

### GitHub Actions on exact head `66995e2e88498611f8f3996f3ed4bba44864e3a0`

- `Quality` run `29801582506`: **success**.
  - formatting: passed
  - Ruff lint: passed
  - strict mypy: passed
  - pytest: passed
  - diff hygiene: passed
  - temporary-delivery-artifact rejection: passed
- `M14 Mass Discovery` run `29801582496`: **failure**.
  - checkout and environment setup: passed
  - bounded-input validation: passed
  - bounded mass discovery: failed
  - adjudication: skipped
  - exactly-500 selection: skipped
  - PDF acquisition: skipped
  - acquisition reconciliation: skipped
  - evidence artifact upload: passed

### Commands run by this report task

No local Git, Poetry, Ruff, mypy, pytest, discovery, acquisition, import, or resume command was executed. This lightweight report used authenticated GitHub repository, PR, workflow, job, log, and artifact evidence only. The failed workflow artifact was downloaded and its sanitized `discovery.log` was inspected.

## Current errors and likely root causes

### 1. Exact-head discovery failed on PubMed metadata retrieval

**Workflow:** `M14 Mass Discovery` run `29801582496`  
**Failing step:** `Run bounded mass discovery`  
**Observed artifact evidence:**

```text
M14 batch discovery failed: PubMed metadata request returned a non-success status.
```

**Immediate root cause:** The PubMed metadata HTTP request returned a non-success response, and the discovery command stopped before candidate adjudication.  
**Confidence:** High.

**Underlying cause:** Not yet verified because the sanitized log does not retain the HTTP status code, response headers, endpoint, attempt number, or bounded retry evidence. A transient NCBI/PubMed service response, throttling response, or other provider-side non-success is plausible because prior identical bounded discovery runs completed successfully.  
**Confidence:** Medium for an external/transient provider condition; low for any specific status code or transport mechanism.

**Affected area:** PubMed discovery transport and workflow observability, including the code path that converts provider non-success responses into the sanitized discovery failure.

**Risk:** Re-running the full discovery phase repeatedly without preserving bounded status metadata can consume time and obscure whether failures are transient, rate-related, or deterministic. Any change must preserve legal, scientific, provenance, duplicate, count, and artifact controls.

### 2. Prior exact-500 acquisition failure remains unresolved

The previous M14 run reached `Acquire exactly 500 approved PDFs` and failed there, but did not preserve acquisition stdout/stderr in the always-uploaded evidence artifact. The newer exact-head run failed earlier during discovery, so it neither reproduced nor cleared the acquisition failure.

**Likely root cause:** Unverified. Existing plausible categories remain a transient provider/transport failure, non-success response for an approved URL, or invalid/non-PDF payload.  
**Confidence:** Low until acquisition is reached again and exact sanitized output is preserved.

## Blockers and risks

1. **Discovery reliability and observability:** The exact-head workflow cannot currently distinguish the provider's non-success status or whether a bounded retry would have succeeded. Confidence: high.
2. **Acquisition failure not yet reproduced with preserved evidence:** The current run stopped before acquisition. Confidence: high.
3. **Exactly-500 receipt and PDF reconciliation remains incomplete:** No successful run has yet produced 500 receipts and 500 validated local PDFs. Confidence: high.
4. **Local working-tree state unavailable:** The connector cannot verify local uncommitted or untracked files. Confidence: high.
5. **M14 downstream rehearsal remains outstanding:** Manifest validation, fresh import or documented stop, exact reconciliation, measured database growth and elapsed time, and idempotent linked resume remain required. Confidence: high.

## Exact continuation point

Starting from PR #75 head `66995e2e88498611f8f3996f3ed4bba44864e3a0`, preserve bounded and sanitized discovery failure diagnostics that include at least the provider response category or status code, request stage, and retry count without exposing secrets or unsafe payloads. Then perform one controlled retry or targeted reproduction of the bounded PubMed metadata request. Do not change adjudication, approval, license, provenance, duplicate, direct-PDF, exact-count, checksum, or transactional requirements.

## Next smallest task

Add or verify a sanitized `discovery.log` diagnostic that records the non-success HTTP status and bounded attempt metadata, then run the narrowest discovery-focused test or controlled workflow retry needed to determine whether the failure is transient or deterministic. Do not proceed to speculative acquisition changes until discovery succeeds and acquisition is reached again.

## Steps remaining before PR #75 can be marked ready and merged

1. Preserve sanitized PubMed discovery failure details sufficient to identify the non-success response category.
2. Reproduce or clear the discovery failure with one controlled, bounded retry or targeted test.
3. Verify bounded discovery and adjudication complete successfully on the exact PR head.
4. Verify deterministic selection still produces exactly 500 approved records.
5. Reach the acquisition step again and preserve sanitized acquisition stdout/stderr in the always-uploaded evidence artifact.
6. Identify the exact root cause of the prior acquisition failure.
7. Apply only the smallest acquisition fix justified by reproduced evidence, if a code change is required.
8. Reconcile exactly 500 approvals, 500 receipt rows, and 500 validated local PDFs, including byte counts and SHA-256 values.
9. Run targeted discovery and acquisition tests plus exact-head Quality CI.
10. Confirm no unresolved required review feedback.
11. Confirm the real working tree is clean in an authenticated local checkout.
12. Keep PR #75 draft unless every PR-specific acceptance criterion is evidenced; do not treat completion of PR #75 as completion of all M14 ingestion and resume stages.

## Access and publication notes

- Authenticated GitHub repository, PR, workflow, job-log, artifact-download, and file-write access succeeded.
- Local checkout and local working-tree inspection were unavailable.
- This run changed only `docs/daily_repo_status.md` on the existing draft PR branch.
- No broad test suite was rerun by this report task.
- No merge or ready-for-review action was performed.
- No email or website publication was attempted.

## Coding lesson

External-service failures become actionable only when sanitized diagnostics preserve the response category and bounded retry context; a generic non-success message protects secrets but is insufficient for deterministic debugging.
