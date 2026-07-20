# Daily Repository Status

**Date:** 2026-07-20 07:03 CEST  
**Repository:** `jweter/knowledge-engine-core`  
**Branch inspected:** `m14-actions-mass-discovery`  
**Draft PR:** #65 — `ci: run M14 mass discovery as temporary artifact`  
**Current milestone:** M14 — controlled 500-paper ingestion rehearsal

## Current state

Draft PR #65 is open, mergeable, and still correctly marked as draft. Its base is `main` at `114239cd71c671df4c8d68fa6d941bb380bdb70f`; the inspected PR head is `d44850915392694882a7b3fef462016db9128b2d`. The PR contains one commit and one changed file: `.github/workflows/m14-mass-discovery.yml`.

The PR's purpose is to run the existing PubMed candidate-discovery implementation on GitHub-hosted infrastructure, emit candidate metrics, and upload review-only JSON and summary artifacts without committing candidate data, PDFs, databases, or provider payloads.

The connected GitHub app cannot inspect the Codex machine's local checkout. Therefore, no claim is made about local uncommitted or untracked changes outside GitHub. The PR itself shows one committed changed file.

## Recent completed work

- Added a reusable `M14 Mass Discovery` workflow with manual and pull-request triggers.
- Bounded manual inputs to 150–5000 requested candidates and a PubMed page size of 1–100.
- Configured Python 3.12, Poetry installation, dependency installation, read-only repository permissions, a 20-minute timeout, metric summarization, and a 14-day temporary artifact.
- Standard `Quality` workflow run `29707579041` completed successfully on PR head `d44850915392694882a7b3fef462016db9128b2d`.
- The new workflow successfully completed checkout, Python setup, Poetry installation, dependency installation, and bounded-input validation before failing in the production discovery step.

## Current errors and likely root causes

### 1. M14 Mass Discovery cannot import the project package

**Workflow run:** `29707579052`  
**Job:** `discover` (`88247018073`)  
**Failing step:** `Run review-only mass discovery`  
**Command:**

```bash
poetry run python scripts/m14_pubmed_batch_discover.py \
  --query "$DISCOVERY_QUERY" \
  --limit "$DISCOVERY_LIMIT" \
  --page-size "$DISCOVERY_PAGE_SIZE" \
  --output work/m14/pubmed-candidates.json
```

**Observed evidence:**

```text
Traceback (most recent call last):
  File ".../scripts/m14_pubmed_batch_discover.py", line 12, in <module>
    from knowledge_engine.ncbi_http import UrllibNcbiTransport
ModuleNotFoundError: No module named 'knowledge_engine'
Process completed with exit code 1.
```

**Likely root cause:** The workflow installs dependencies with `poetry install --no-interaction --no-root`, which deliberately does not install the repository package. It then executes the script by filesystem path. Under direct script execution, Python places the `scripts/` directory rather than the repository root at the front of `sys.path`, so the sibling `knowledge_engine` package is unavailable unless the project is installed or the repository root is otherwise added to the module search path.

**Confidence:** High.

**Affected files:**

- `.github/workflows/m14-mass-discovery.yml`
- indirectly, `scripts/m14_pubmed_batch_discover.py` at its package import boundary

**Proposed fix for the implementation run:** Install the project package by removing `--no-root`, or invoke the production entry point in a way that guarantees the repository package is importable. Prefer the smallest change consistent with existing repository conventions, then rerun the workflow and inspect the artifact.

No additional current error was investigated in this status-only run.

## Tests and checks observed

### Passing

- `Quality` workflow run `29707579041`: **success**.
- M14 workflow setup steps: checkout, Python setup, Poetry installation, dependency installation, and bounded-input validation: **success**.

### Failing

- `M14 Mass Discovery` workflow run `29707579052`: **failure**.
- Failing step: `Run review-only mass discovery`.
- Candidate summarization and artifact upload were skipped because the discovery command failed.

No Poetry, Ruff, mypy, pytest, or local Git commands were executed by this status task. The statements above are based only on connected GitHub PR metadata and GitHub Actions records.

## Remaining M14 work before PR #65 can be marked ready and merged

1. Fix the project-import failure in `.github/workflows/m14-mass-discovery.yml` using the smallest repository-consistent change.
2. Rerun the M14 workflow on the exact updated PR head.
3. Confirm installation, bounded-input validation, NCBI execution, metric summarization, and artifact upload all succeed.
4. Download and inspect the temporary artifact.
5. Verify the artifact contains the expected JSON and summary files and no prohibited repository artifacts.
6. Record exact candidate count, Open Access count, duplicate-PMID count, fetched-page count, and exhaustion state on issue #21 as required by the PR acceptance steps.
7. Confirm the standard Quality workflow passes on the exact final PR head.
8. Confirm the PR remains limited to its intended workflow scope, is mergeable, and has no unresolved review threads.
9. Keep the PR as draft until every acceptance step above is evidenced.
10. Mark ready and merge only after all PR #65 gates pass; this status task must not perform either action.

## Remaining broader M14 work after PR #65

1. Use successful mass discovery to build a sufficiently large review pool.
2. Perform explicit human review of identifiers, licenses, and PMC OA PDF URLs.
3. Create approval records without automatically promoting raw discovery output.
4. Acquire approved PDFs in bounded batches and retain sanitized receipts.
5. Reconcile receipts against curated `sources.csv` rows.
6. Reach exactly 500 accepted rows with exactly 500 approved matching local PDFs.
7. Run M14 preflight and verify manifest, provenance, privacy, security, and prohibited-artifact constraints.
8. Execute the fresh 500-paper import and record aggregate evidence.
9. Execute the linked-resume rehearsal and verify stable linkage, expected skips, and no unexpected reimports.
10. Complete M14 reporting, error-resolution documentation, and the final Quality gate.

## Exact continuation point

On `m14-actions-mass-discovery`, update the workflow so `knowledge_engine` is importable during `scripts/m14_pubmed_batch_discover.py`, then rerun `M14 Mass Discovery` and inspect the resulting metrics and temporary artifact. PR #65 must remain draft until that workflow and the standard Quality workflow both pass and all acceptance evidence listed in the PR is complete.

## Access limitations

- The connected GitHub app can inspect repository metadata, pull requests, committed files, and GitHub Actions workflow results and logs.
- It cannot inspect the Codex machine's local working tree, uncommitted files, or untracked files.
- This run did not execute local tests or modify source code.
- The only repository write in this run is this status-file update.
- No website post or email was attempted.
