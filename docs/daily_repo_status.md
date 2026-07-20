# Daily Repository Status

**Date:** 2026-07-20 18:33 CEST  
**Repository:** `jweter/knowledge-engine-core`  
**Branch inspected:** `main`  
**Current draft PR:** None verified open  
**Current milestone:** M14 — controlled 500-paper rehearsal

## Current state

Repository metadata verifies `main` as the default branch. No open pull request, including no draft pull request, was returned by the connected GitHub search at the time of this report.

The latest verified commit on `main` is `0e43517dfb9252b01463e7d351706d619796e63d`, the squash merge of PR #72, `ci: measure 2500-candidate M14 pool`. PR #72 is merged and closed; it was explicitly scoped to candidate-supply measurement and did not claim M14 completion.

The connected GitHub app cannot inspect a Codex machine's local checkout. Therefore, local `git status`, uncommitted changes, untracked files, and the currently checked-out local branch remain unverified. No claim of a clean local working tree is made.

## Recent completed work

- PR #70 repaired bounded PubMed-to-PMC Open Access resolution.
- PR #71 added PubMed abstract evidence for deterministic M14 scope adjudication.
- PR #72 increased the bounded discovery default from 500 to 2,500 candidates without weakening scientific, legal, provenance, identifier, duplicate, license, or direct-PDF rules.
- The exact PR #72 head `1f934e29fbde34e08dfd8652c21ac05f1c0b1b20` completed both the `Quality` workflow and the `M14 Mass Discovery` workflow successfully.
- The M14 workflow successfully completed checkout, Python and Poetry setup, dependency installation, bounded-input validation, mass discovery, candidate adjudication, metric summarization, and temporary-artifact upload.

## Measured M14 candidate result

Workflow run `29745438536` produced a temporary `m14-pubmed-candidates` artifact. Its `summary.txt` records:

```text
candidate_count=2500
adjudication_item_count=2500
accepted=430
rejected=19
held=2051
fetched_page_count=25
duplicate_pmids_removed=0
pmcid_resolved=2500
pmcid_resolution_rate=1.000000
oa_verified=2481
oa_verification_rate=0.992400
exhausted=False
```

The measured accepted yield was 17.2% (`430 / 2500`). The run did not meet the issue #21 entry requirement of exactly 500 accepted rows. It remains 70 accepted records short. Because discovery reported `exhausted=False`, further bounded discovery inside the committed M14 domain remains possible without relaxing acceptance rules.

## Current failures, blockers, and risks

### 1. Candidate-supply gate remains incomplete

**Observed evidence:** Only 430 of 2,500 adjudicated candidates were accepted. Issue #21 requires exactly 500 legally accepted rows with matching approved local PDFs before the controlled rehearsal can proceed.

**Likely cause:** The deterministic adjudication rules correctly hold or reject records when scientific-scope, direct-PDF, licensing, identity, provenance, or duplicate evidence is incomplete or conflicting. The current discovery pool did not contain enough fully supported records.

**Confidence:** High.

**Risk:** Expanding the candidate pool without preserving offsets and provenance could duplicate work or weaken traceability. Acceptance rules must not be relaxed merely to reach 500.

### 2. No current draft PR exists

There is no verified open draft PR to receive continuation commits. Any implementation continuation must begin on a new focused branch and draft PR unless a currently open branch exists only in an inaccessible local checkout.

### 3. Local working-tree state is unavailable

The GitHub connector cannot verify local uncommitted or untracked changes. A clean working tree must be confirmed in a real repository checkout before any implementation or rehearsal execution.

### 4. Review feedback on workflow timeout remains a residual risk

PR #72 received review feedback that the 20-minute timeout could be tight for 2,500 candidates. The exact-head run nevertheless completed successfully, so this is not a reproduced failure. It remains a capacity risk for larger or slower future runs and should be changed only if measured runtime or a failure demonstrates the need.

## Tests and commands actually observed

### GitHub Actions observed passing

- `Quality` run `29745437994` on PR #72 head: **success**.
- `M14 Mass Discovery` run `29745438536` on PR #72 head: **success**.
- Every reported M14 job step completed successfully, including artifact upload.

### Commands run by this report task

No local Poetry, Ruff, mypy, pytest, corpus-import, or Git commands were executed. This report used connected GitHub repository, PR, commit, workflow, issue, and artifact evidence only. The temporary artifact was downloaded and `summary.txt` was read; candidate JSON and provider payloads were not committed.

## Exact continuation point

Starting from verified `main` commit `0e43517dfb9252b01463e7d351706d619796e63d`, create a focused continuation branch and perform one bounded discovery extension within the committed obesity and metabolic-disease therapeutics scope. Preserve the exact query, rules version, provider provenance, offset, decision records, and duplicate controls. The immediate objective is to obtain at least 70 additional accepted records without reclassifying held records or weakening legal and scientific evidence requirements.

## Next smallest task

Determine and document the next unused PubMed discovery offset from the 2,500-candidate artifact, then run one bounded continuation page or small page group using the existing production discovery and adjudication path. Record incremental accepted, rejected, held, duplicate, PMCID, PMC OA, page-count, and exhaustion metrics. Do not acquire PDFs or construct the final 500-row manifest until cumulative accepted records can be deterministically reconciled and deduplicated.

## Steps remaining before any PR can be marked ready and merged

1. Confirm the local checkout is on a clean branch derived from verified `main`.
2. Create a focused continuation branch and draft PR for the bounded next-offset discovery work.
3. Preserve the prior 2,500-candidate evidence and use the next unused offset.
4. Run the smallest bounded continuation needed to measure additional accepted yield.
5. Reconcile cumulative candidates and remove duplicate PMIDs deterministically.
6. Verify cumulative accepted records reach at least 500 without weakening adjudication rules.
7. Select exactly 500 accepted records through a separate deterministic approval step.
8. Verify explicit reusable-license basis, identity, provenance, and approved direct full-text location for all 500.
9. Acquire exactly 500 matching approved PDFs with sanitized receipts; do not commit PDFs.
10. Validate the immutable 500-row manifest and local-file readiness.
11. Execute the fresh import, exact reconciliation, measured database growth and elapsed time, and linked-resume rehearsal.
12. Commit the sanitized deterministic M14 report and final `PROCEED`, `HOLD`, or `STOPPED` decision.
13. Pass exact-head Ruff formatting, Ruff lint, strict mypy, full pytest, diff hygiene, and artifact hygiene.
14. Confirm the final PR is clean, focused, mergeable, and has no unresolved required review feedback.
15. Mark ready and merge only when every applicable acceptance criterion is evidenced.

## Access and publication notes

- Repository status and committed GitHub state were accessible through the authenticated GitHub connector.
- Local working-tree state was not accessible.
- This report updated only `docs/daily_repo_status.md` on `main`.
- No merge or ready-for-review action was performed.
- No website publication was attempted.
