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
- **Diagnostic fix applied:** `PmcOaAcquisitionService._get_pdf` now includes the numeric HTTP status code and a non-sensitive locator (1-based approval ordinal and PMCID) in both `AcquisitionError` messages it raises (transport-exception and non-2xx paths), matching the proposal above exactly. No retry behavior, PDF/host/licensing/count/checksum/transactional validation was added or weakened. Covered by two new tests: `test_non_success_status_is_reported_with_status_code_and_locator` and `test_non_success_status_locator_uses_failing_approvals_ordinal`. `poetry run pytest tests/test_pmc_acquisition.py -q` — 11 passed (was 9). Full-suite `poetry run pytest` and `poetry run mypy knowledge_engine tests` show the same 26 and 20 pre-existing, unrelated failures/errors present on this branch before this change, respectively; `poetry run ruff check knowledge_engine/pmc_acquisition.py tests/test_pmc_acquisition.py` shows the same single pre-existing `SIM102` finding (line unrelated to this change) present before this change. The next real occurrence of this failure (live, in CI) will now surface the exact status code and which approval failed, which the evidence above shows was previously discarded.
- **Status:** open — diagnostic gap fixed and unit-tested; underlying root cause still requires one more live occurrence to observe the now-captured status code and locator.
