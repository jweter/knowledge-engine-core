# Daily Repository Status

**Date:** 2026-07-20 19:32 CEST  
**Repository:** `jweter/knowledge-engine-core`  
**Branch inspected:** `m14-3250-candidate-pool`  
**Current draft PR:** #73 — `ci: measure 3250-candidate M14 pool`  
**Current milestone:** M14 — controlled 500-paper rehearsal

## Current state

PR #73 is open, draft, mergeable, and targets `main`. Its verified head before this status-only update was `a4e9b5b10704cc205a439fc46b241bcc522ec61c`, two commits ahead of base `3a6b0999eefaddcaac103b37942dfc65aa199c4e`. The PR changes only `.github/workflows/m14-mass-discovery.yml` and `docs/m14_mass_pubmed_candidate_discovery.md`; its stated scope is bounded candidate-supply measurement, not completion of M14.

The connected GitHub app cannot inspect a Codex machine's local checkout. Local `git status`, uncommitted changes, untracked files, and the currently checked-out local branch therefore remain unverified. No clean-working-tree claim is made.

## Completed work

- Increased the bounded M14 discovery pool from 2,500 to 3,250 candidates while preserving the existing query, page-size ceiling, adjudication rules, provenance controls, duplicate controls, licensing checks, and direct-PDF rules.
- Raised the workflow timeout from 20 to 30 minutes based on the prior measured 2,500-candidate runtime.
- Completed the exact-head `Quality` and `M14 Mass Discovery` workflows successfully.
- Produced a temporary 3,250-candidate adjudication artifact with reconciled metrics.
- No unresolved pull-request review threads were present when inspected.

## Verified M14 candidate result

Workflow run `29761508774` reported:

```text
candidate_count=3250
adjudication_item_count=3250
accepted=589
rejected=24
held=2637
fetched_page_count=33
duplicate_pmids_removed=0
pmcid_resolved=3250
pmcid_resolution_rate=1.000000
oa_verified=3226
oa_verification_rate=0.992615
exhausted=False
```

The candidate-supply prerequisite is now met numerically: 589 records were accepted, exceeding the 500-record selection requirement by 89. This does not complete M14. A separate deterministic step must select exactly 500 accepted records and verify their reusable-license, identity, provenance, and approved local-PDF readiness before ingestion.

## Tests and commands actually observed

### GitHub Actions

- `Quality` run `29761508853`: **success**.
  - formatting check: passed
  - Ruff lint: passed
  - strict mypy: passed
  - pytest: passed
  - diff hygiene: passed
  - temporary-delivery-artifact rejection: passed
- `M14 Mass Discovery` run `29761508774`: **success**.
  - bounded-input validation: passed
  - mass discovery: passed
  - adjudication: passed
  - metric reconciliation: passed
  - artifact upload: passed

### Commands run by this report task

No local Git, Poetry, Ruff, mypy, pytest, import, or resume commands were executed. This lightweight report used authenticated GitHub repository, PR, commit, workflow, log, and review-thread evidence only.

## Failures and documented errors

No current failing workflow, failing test, or unresolved review thread was verified on PR #73. The workflow logs contain a Node 20 deprecation notice from GitHub-hosted actions, but the job ran using Node 24 defaults and completed successfully; this is informational, not a reproduced repository failure.

## Blockers and risks

1. **Local working-tree state unavailable.** The connector cannot verify local uncommitted or untracked files. Confidence: high.
2. **Exactly-500 selection not yet evidenced.** The 589 accepted records must be deterministically reduced to exactly 500 without weakening scientific or legal acceptance rules. Confidence: high.
3. **PDF readiness not yet evidenced.** Matching approved local PDFs, sanitized acquisition receipts, and immutable manifest reconciliation remain outstanding. Confidence: high.
4. **M14 rehearsal not yet run.** Fresh import, exact reconciliation, measured database growth and elapsed time, and idempotent linked resume remain required. Confidence: high.
5. **PR #73 remains a measurement PR.** Its successful result advances the candidate-supply prerequisite but does not itself satisfy the full milestone acceptance criteria. Confidence: high.

## Exact continuation point

From the successful 3,250-candidate artifact produced by workflow run `29761508774`, preserve the full adjudication evidence and deterministically select exactly 500 of the 589 accepted records using a documented, reproducible ordering rule. Do not reclassify held or rejected records and do not weaken license, provenance, identity, duplicate, scientific-scope, or direct-PDF requirements.

## Next smallest task

Document and test the deterministic exactly-500 selection rule against the 3,250-candidate adjudication artifact, producing a reconciled 500-row approval candidate manifest without acquiring PDFs or running ingestion yet.

## Steps remaining before the milestone PR can be marked ready and merged

1. Preserve and verify the 3,250-candidate artifact and summary.
2. Define a deterministic, reproducible ordering and selection rule.
3. Select exactly 500 from the 589 accepted records.
4. Reconcile selected rows against original PMIDs, PMCIDs, decisions, provenance, licenses, and duplicate controls.
5. Verify approved direct full-text locations and reusable-license basis for all 500.
6. Acquire exactly 500 matching local PDFs with sanitized receipts; do not commit PDFs.
7. Validate the immutable 500-row manifest and local-file readiness.
8. Run the fresh import or record a policy-compliant documented stop.
9. Reconcile source rows, import items, papers, FTS rows, issues, warnings, database growth, and elapsed time exactly.
10. Run and verify the idempotent linked-resume rehearsal.
11. Commit the sanitized deterministic M14 report and final `PROCEED`, `HOLD`, or `STOPPED` decision.
12. Pass exact-head formatting, lint, strict mypy, full pytest, diff hygiene, and artifact hygiene.
13. Confirm a clean working tree and no unresolved required review feedback.
14. Mark ready and merge only when every applicable milestone and repository-policy criterion is evidenced.

## Access and publication notes

- Authenticated GitHub read and file-write access succeeded.
- Local checkout and local working-tree inspection were unavailable.
- This run changed only `docs/daily_repo_status.md` on the existing draft PR branch.
- No broad test suite was rerun by this report task.
- No merge or ready-for-review action was performed.

## Coding lesson

A larger candidate pool is useful only when every decision remains reproducible and the final exactly-sized manifest can be traced back to immutable source evidence.