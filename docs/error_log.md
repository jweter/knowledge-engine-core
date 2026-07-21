# Error Log

This file records the currently active, unresolved failure for the bounded M14 continuation. The authoritative resolved-failure history remains [`docs/error_resolution_ledger.md`](error_resolution_ledger.md).

## 2026-07-21 — Exact-500 PMC OA acquisition step failed

- **Area:** CI / runtime / external acquisition
- **Current PR:** #75, `feat: acquire exactly 500 approved M14 PDFs`
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

- **Observed evidence:** On exact head `91798dceed079ce82237b281b8d92b5368127d0a`, Quality run `29815549093` passed. M14 Mass Discovery run `29815549208` passed setup, bounded discovery, adjudication, exact-500 selection, and the preflight validation of 500 unique approvals. It then failed during acquisition; reconciliation and PDF artifact upload were skipped, while the always-uploaded evidence artifact succeeded.
- **Preserved acquisition evidence:** The uploaded `acquisition.log` contains:

  ```text
  Network access: acquiring explicitly approved PDFs from official PMC OA resources.
  PMC OA acquisition failed: PMC OA PDF request returned a non-success status.
  ```

- **Immediate root cause:** At least one allowlisted PMC OA PDF GET returned an HTTP status other than 200, causing transactional acquisition to stop and roll back before a receipt or approved-PDF artifact was produced.
- **Confidence:** High.
- **Underlying cause:** Not yet verified. The current sanitized diagnostic does not retain the status code, failing approval index or PMCID, response category, or retry metadata. A transient provider response, throttling response, stale OA PDF location, or another non-success response remains possible; no specific status code is inferred.
- **Confidence in any specific underlying category:** Low.
- **Affected files under investigation:** `knowledge_engine/pmc_acquisition.py`, `knowledge_engine/ncbi_http.py`, `.github/workflows/m14-mass-discovery.yml`, and `tests/test_pmc_acquisition.py`.
- **Proposed next fix:** Preserve a sanitized status code and non-sensitive record locator such as approval ordinal and PMCID when acquisition receives a non-success response. Do not expose query strings, response bodies, private paths, or credentials. Add targeted coverage before changing retry behavior.
- **Controlled reproduction:** Failed jobs for workflow run `29815549208` were requested for one bounded retry. At the time of this entry, the replacement job was queued. This retry is diagnostic and does not alter scientific, legal, provenance, duplicate, exact-count, PDF-signature, checksum, or transactional controls.
- **Status:** open
