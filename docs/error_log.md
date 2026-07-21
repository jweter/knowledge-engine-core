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
- **Controlled reproduction:** Failed jobs for workflow run `29815549208` were requested for one bounded retry. The replacement job (`29822421628`, `discover`) completed discovery, adjudication, and exact-500 selection (`Selected 500 of 596 validated accepted records`) and then failed acquisition again, `0.1s` after starting network access — the very first PDF request in the batch, not after any sustained load. This is a materially different failure shape than the M14 discovery-side PMC identifier conversion issue (which only ever manifested after 20+ minutes of sustained traffic); an instant first-request failure is more consistent with a bad URL, unexpected host/path behavior, or a genuine PMC OA response than with rate limiting, though this remains unconfirmed without the status code.
- **Diagnostic fix applied:** `PmcOaAcquisitionService._get_pdf` now includes the numeric HTTP status code and a non-sensitive locator (1-based approval ordinal and PMCID) in both `AcquisitionError` messages it raises (transport-exception and non-2xx paths), matching the proposal above exactly. No retry behavior, PDF/host/licensing/count/checksum/transactional validation was added or weakened. Covered by two new tests: `test_non_success_status_is_reported_with_status_code_and_locator` and `test_non_success_status_locator_uses_failing_approvals_ordinal`. `poetry run pytest tests/test_pmc_acquisition.py -q` — 11 passed (was 9). Full-suite `poetry run pytest` and `poetry run mypy knowledge_engine tests` show the same 26 and 20 pre-existing, unrelated failures/errors present on this branch before this change, respectively; `poetry run ruff check knowledge_engine/pmc_acquisition.py tests/test_pmc_acquisition.py` shows the same single pre-existing `SIM102` finding (line unrelated to this change) present before this change.

- **Underlying cause — confirmed:** The diagnostic fix immediately paid off. Pushed commit `e1d6469`, PR #75 auto-triggered workflow run `29825013457` (`discover`, job `88616250949`), which failed with the now-informative message:

  ```text
  PMC OA acquisition failed: PMC OA PDF request returned a non-success status (404) for approval 1 (PMC13378728).
  ```

  Independently reproduced outside CI with direct `curl` requests to the exact NCBI-announced URL from `oa.fcgi` for `PMC13378728`:

  ```text
  curl -sI https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/29/61/KGMI_18_2696645.PMC13378728.pdf
  → HTTP/1.1 404 Not Found
  ```

  `https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt` (fetched directly) explains why: "All legacy files for the PMC Article Datasets were moved to a new temporary directory named 'deprecated'. All legacy files on the FTP Service will be removed in August 2026." Confirmed the files now live under `/pub/pmc/deprecated/oa_pdf/...` (HTTP 200), and confirmed this is systemic, not specific to one recent article, by reproducing the same 404→200 pattern on an unrelated, much older record (`PMC9500000`, originally published 2022). `oa.fcgi` has not yet been updated to reflect NCBI's own path migration, so every PDF/package URL it returns currently 404s at the announced path.
- **Confidence in underlying cause:** High — independently reproduced against live NCBI infrastructure outside of and in agreement with CI, with NCBI's own documentation confirming the migration and its August 2026 legacy-removal deadline.
- **Fix applied:** `PmcOaAcquisitionService._get_pdf` now retries once against NCBI's confirmed `/pub/pmc/deprecated/` relocation when the announced path returns 404 (same host, no allowlist change, no change to retry behavior for any other status code). Covered by two new tests: `test_legacy_path_404_falls_back_to_deprecated_ncbi_relocation` (fallback succeeds) and `test_deprecated_fallback_failure_still_reports_original_locator` (fallback also fails, original locator still reported). `poetry run pytest tests/test_pmc_acquisition.py -q` — 13 passed (was 9 before either fix). Full-suite `pytest` and `mypy` show the same pre-existing counts as the diagnostic-fix commit, zero new failures.
- **Known expiration — action required before August 2026:** NCBI's `readme.txt` states the `deprecated/` copies will themselves be removed in August 2026. This fix is a confirmed, working, but **temporary** bridge. Before that removal, this project needs a durable fix — most likely migrating PMC OA acquisition to NCBI's documented cloud/AWS access path (`https://pmc.ncbi.nlm.nih.gov/tools/cloud/`, referenced in the same `readme.txt`) or watching for `oa.fcgi` to be updated to return corrected paths. Tracked here so it is not lost; a dedicated roadmap/ADR decision should own the long-term replacement rather than another silent path patch.
- **Status:** open — pending one more live CI run to confirm the fallback resolves acquisition end-to-end; will move to `docs/error_resolution_ledger.md` as resolved once confirmed, with the August 2026 expiration carried forward as a named follow-up.
