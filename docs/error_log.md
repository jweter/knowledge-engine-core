# Error Log

This file records the currently active, unresolved failure for the bounded M14 continuation. The authoritative resolved-failure history remains [`docs/error_resolution_ledger.md`](error_resolution_ledger.md).

## 2026-07-21 — Exact-500 PMC OA acquisition step failed

- **Area:** CI / runtime / external acquisition
- **Current draft PR:** #75, `feat: acquire exactly 500 approved M14 PDFs`
- **Branch:** `m14-acquire-exactly-500`
- **First failing workflow step:** `Acquire exactly 500 approved PDFs`
- **Command executed by the workflow:**

  ```bash
  poetry run ke pmc-oa-acquire \
    --candidates work/m14/pubmed-candidates.json \
    --approvals work/m14/approvals-500.json \
    --papers-dir work/m14/papers \
    --receipt work/m14/acquisition-receipt.json
  ```

- **Observed evidence:** Quality run `29784139928` passed on head commit `efad9813a2a77d32448759bfe7f9e795d0b1cef4`. M14 Mass Discovery run `29784139917` passed checkout, environment setup, bounded discovery, adjudication, and exact-500 selection, then failed in the acquisition step. Reconciliation was skipped, the evidence artifact uploaded, and the approved-PDF artifact was skipped. The uploaded evidence artifact contains `approvals-500.json` but no acquisition receipt or PDF artifact.
- **Exact terminal error text:** Not yet recoverable from the connected artifact because the workflow does not currently persist acquisition stdout/stderr in the always-uploaded evidence bundle. Do not infer a provider status, timeout, payload defect, or code exception until the retry or preserved logs provide it.
- **Likely root cause:** Unverified. Plausible categories include a transient transport/provider failure, a non-200 response for at least one approved URL, or a non-PDF payload. The current evidence does not distinguish among them.
- **Confidence:** Low until exact acquisition output is preserved or the controlled retry completes.
- **Affected files under investigation:** `.github/workflows/m14-mass-discovery.yml`, `knowledge_engine/pmc_acquisition.py`, and possibly transport code used by `pmc-oa-acquire`.
- **Proposed next fix:** First preserve the acquisition command's stdout/stderr as `work/m14/acquisition.log` in the always-uploaded evidence artifact. Then apply the smallest behavior fix supported by the exact reproduced failure; do not add broad retries or weaken PDF, host, licensing, count, checksum, or transactional requirements speculatively.
- **Reproduction status:** A single failed-job retry was requested for workflow run `29784139917`. At the time of this entry, the retry had passed setup and was still executing bounded discovery; it had not yet reached acquisition.
- **Status:** open
