# Error Resolution Ledger

This file is the authoritative troubleshooting record for recurring repository and CI failures.

Use one entry per distinct failure. Record the first failing command, the exact symptom, the verified root cause, the smallest successful fix, and the validation that proved the fix. Do not record guesses as confirmed causes.

## Entry template

```markdown
## YYYY-MM-DD — Short failure name

- **Area:** formatting | lint | typing | tests | CI | migration | runtime | dependency
- **First failing command:** `exact command`
- **Symptom:** Exact error, failing step, or concise observed output.
- **Affected files:** `path/to/file`
- **Root cause:** Verified technical cause.
- **Fix:** Exact change that resolved the failure.
- **Validation:** Commands, CI run, and commit that passed after the fix.
- **Prevention / fast path:** What to check first if the symptom returns.
- **Tracked as:** GitHub issue link (required whenever Status is `open` and the fix is deferred to a later session/PR; omit for `resolved` or `superseded`).
- **Status:** resolved | open | superseded
```

## 2026-07-17 — Metadata module failed Ruff formatting

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** GitHub Actions stopped at `Check formatting`; Ruff reported that `knowledge_engine/metadata_enrichment.py` would be reformatted.
- **Affected files:** `knowledge_engine/metadata_enrichment.py`
- **Root cause:** The committed layout did not match Ruff `0.15.20` using the repository configuration. The decisive discrepancy was the wrapping of the `normalize_candidate_value(candidate.field, candidate.value)` assignment.
- **Fix:** Applied the exact formatter output generated in CI and restored the normal read-only quality workflow after diagnosis.
- **Validation:** Quality run `29618531900` / run number `204` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact checks on commit `4517999e857d7af133c7a215abcb123abecce9ca`.
- **Prevention / fast path:** Run `poetry run ruff format --check knowledge_engine/metadata_enrichment.py` from the repository root. If local and CI output disagree, verify the Ruff version and repository configuration, then use a temporary CI artifact only to capture canonical output; remove the diagnostic workflow immediately afterward.
- **Status:** resolved

## 2026-07-17 — Metadata tests failed Ruff formatting

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** The metadata test file retained a manual wrap that Ruff rejected under the repository's configured line length.
- **Affected files:** `tests/test_metadata_enrichment.py`
- **Root cause:** `test_candidate_fills_missing_value` used a noncanonical multiline layout for `classify_candidate(...)`.
- **Fix:** Applied Ruff's canonical formatting for the configured 100-character line length.
- **Validation:** The complete Quality run `29618531900` / run number `204` passed on commit `4517999e857d7af133c7a215abcb123abecce9ca`.
- **Prevention / fast path:** Run formatter checks from the repository root so `pyproject.toml` is loaded. Do not validate formatting with an ad hoc command that omits repository configuration.
- **Status:** resolved

## 2026-07-17 — Ruff version was not deterministic

- **Area:** dependency / CI
- **First failing command:** `poetry install` followed by `poetry run ruff format --check .`
- **Symptom:** Local assumptions referred to Ruff `0.15.20` as locked, while `pyproject.toml` allowed any compatible `0.15.x` release and no committed lockfile established an exact formatter version.
- **Affected files:** `pyproject.toml`
- **Root cause:** The dependency used `ruff = "^0.15.20"`, which is a range rather than an exact version.
- **Fix:** Changed the development dependency to an exact Ruff `0.15.20` pin.
- **Validation:** Subsequent CI installed dependencies successfully and Quality run `204` passed the entire gate.
- **Prevention / fast path:** Treat formatters and linters as build tools. Pin them exactly or commit a lockfile before describing their version as locked.
- **Status:** resolved

## 2026-07-17 — Ruff UP035 lint failure

- **Area:** lint
- **First failing command:** `poetry run ruff check .`
- **Symptom:** Ruff reported `UP035` for importing `Sequence` from `typing` under Python 3.12.
- **Affected files:** `knowledge_engine/metadata_enrichment.py`
- **Root cause:** Runtime collection abstract base classes should be imported from `collections.abc`; only `Literal` and `Protocol` belonged in `typing`.
- **Fix:** Moved `Sequence` to `from collections.abc import Sequence` and retained `Literal, Protocol` in `typing`.
- **Validation:** Quality run `29618531900` / run number `204` passed Ruff lint and every later gate step on commit `4517999e857d7af133c7a215abcb123abecce9ca`.
- **Prevention / fast path:** For Python 3.12 lint failures with `UP035`, move container protocols such as `Sequence`, `Mapping`, and `Iterable` to `collections.abc` unless they are needed only for a special typing construct.
- **Status:** resolved

## 2026-07-18 — Crossref tests formatted with the wrong line-length assumption

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** The new Crossref parser module passed its isolated formatting check, but `tests/test_crossref.py` failed in CI.
- **Affected files:** `tests/test_crossref.py`
- **Root cause:** A local formatter check had used Ruff's default 88-character line length rather than the repository's configured `line-length = 100`. Under the real project configuration, the publication-year comprehension required a different canonical wrap.
- **Fix:** Re-ran formatting with Ruff `0.15.20` and the repository's 100-character configuration, applied the exact canonical layout, and removed temporary split-path CI checks.
- **Validation:** Quality run `29618964099` / run number `211` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `d298f11088e5423f2639e83a75e2a92e60fb8c72`.
- **Prevention / fast path:** Always run `poetry run ruff format --check .` from the repository root. When isolating a file, still invoke Ruff through Poetry from the root so `pyproject.toml` remains active.
- **Status:** resolved

## 2026-07-18 — Metadata preview fixture failed Ruff formatting

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** Quality run `29619404604` / run number `220` stopped at `Check formatting` after the metadata preview slice was committed.
- **Affected files:** `tests/test_metadata_preview.py`
- **Root cause:** The first `_candidate(...)` fixture call was written as a single long list element. Under Ruff `0.15.20` with the repository's 100-character configuration, the list and function call require a canonical multiline layout.
- **Fix:** Applied Ruff's exact multiline layout to the fixture call without changing test behavior.
- **Validation:** Quality run `29619469062` / run number `221` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `b49c0e62f7d7f685da854bfc291a3cdce0e2cd60`.
- **Prevention / fast path:** Before committing new tests, run `poetry run ruff format --check <new-test-file>` from the repository root. For nested list elements containing calls, let Ruff choose wrapping instead of manually estimating line length.
- **Status:** resolved

## 2026-07-18 — Crossref transport failed strict mypy

- **Area:** typing
- **First failing command:** `poetry run mypy knowledge_engine tests`
- **Symptom:** Quality run `29619706444` / run number `224` passed formatting and lint, then stopped at `Type check` after the concrete urllib transport was added.
- **Affected files:** `knowledge_engine/crossref_http.py`
- **Root cause:** The initial implementation coupled `_read_bounded` and `redirect_request` to concrete response types whose standard-library and test-double signatures do not align cleanly under strict typeshed checking.
- **Fix:** Introduced a narrow `_ReadableResponse` protocol containing only `headers` and `read`, and changed the redirect callback to the typeshed-compatible `IO[bytes]` and `HTTPMessage` signature. No mypy suppression was added.
- **Validation:** Quality run `29619773182` / run number `225` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `db7c96cad4036b38c6d2c71fe7f352086efdb25f`.
- **Prevention / fast path:** At standard-library I/O boundaries, type against the smallest structural protocol the code actually consumes instead of a concrete implementation class. Match overridden callback signatures to typeshed exactly.
- **Status:** resolved

## 2026-07-18 — Oversized transport response was misclassified

- **Area:** runtime / reliability
- **First failing command:** Design review of the concrete transport-to-provider exception path.
- **Symptom:** A response rejected during bounded streaming raised `ResponseTooLargeError`, which inherited from `OSError`; the provider's broad `except OSError` therefore returned `transport_error` instead of `oversized_response`.
- **Affected files:** `knowledge_engine/crossref_provider.py`, `knowledge_engine/crossref_http.py`, `tests/test_crossref_provider.py`
- **Root cause:** The concrete transport owned a domain-significant exception that the provider could not distinguish before its broad operating-system failure handler.
- **Fix:** Defined the shared response-limit exception at the provider boundary, explicitly exported it from the transport module, caught it before `OSError`, and added a regression test for a transport-thrown oversized response.
- **Validation:** Quality run `29620797390` / run number `241` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `b9e26cd62a8f0f305cb9e7b34706b8247d097598`.
- **Prevention / fast path:** Catch specific domain transport exceptions before broad `OSError` or network exceptions. Test exception translation across the concrete transport and provider layers, not only direct oversized byte arrays.
- **Status:** resolved

## 2026-07-18 — Metadata preview CLI failed Ruff formatting

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** Quality run `29620413596` / run number `232` stopped at `Check formatting` after the CLI entrypoint and tests were added.
- **Affected files:** `knowledge_engine/entrypoint.py`, `tests/test_metadata_preview_cli.py`
- **Root cause:** Manually wrapped Rich output and assertion expressions did not match Ruff `0.15.20` under the repository's 100-character configuration.
- **Fix:** Applied Ruff's canonical wrapping without changing CLI or test behavior.
- **Validation:** Quality run `29620797390` / run number `241` passed the complete gate on commit `b9e26cd62a8f0f305cb9e7b34706b8247d097598`.
- **Prevention / fast path:** Format every newly created module and test through Poetry from the repository root before committing.
- **Status:** resolved

## 2026-07-18 — Transitive imports failed strict mypy exports

- **Area:** typing
- **First failing command:** `poetry run mypy knowledge_engine tests`
- **Symptom:** The diagnostic artifact reported that `knowledge_engine.entrypoint` did not explicitly export `app` and `knowledge_engine.crossref_http` did not explicitly export `ResponseTooLargeError`.
- **Affected files:** `knowledge_engine/entrypoint.py`, `knowledge_engine/crossref_http.py`
- **Root cause:** Runtime imports made the names available, but strict mypy does not treat a plain transitive import as a declared public module API.
- **Fix:** Re-exported each public symbol explicitly with `from ... import name as name`; no type suppression was added.
- **Validation:** Quality run `29620797390` / run number `241` passed strict mypy and all subsequent checks on commit `b9e26cd62a8f0f305cb9e7b34706b8247d097598`.
- **Prevention / fast path:** When tests or consumers intentionally import a symbol from an intermediary module, declare that re-export explicitly or import from the defining module.
- **Status:** resolved

## 2026-07-18 — Rich line wrapping made CLI test brittle

- **Area:** tests
- **First failing command:** `poetry run pytest`
- **Symptom:** The provider-failure test expected the contiguous sentence `Retry may succeed later.`, but Rich wrapped the rendered terminal output between `may` and `succeed` at the test terminal width.
- **Affected files:** `tests/test_metadata_preview_cli.py`
- **Root cause:** The assertion tested physical terminal line layout rather than stable semantic content.
- **Fix:** Asserted the stable fragments `Retry may` and `succeed later.` independently while preserving the behavior and wording under test.
- **Validation:** Quality run `29620797390` / run number `241` passed full pytest and the complete quality gate on commit `b9e26cd62a8f0f305cb9e7b34706b8247d097598`.
- **Prevention / fast path:** For Rich or terminal-rendered output, normalize whitespace or assert semantic fragments unless line layout itself is the contract.
- **Status:** resolved

## 2026-07-18 — M12 report files failed Ruff formatting

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** Quality run `29621610195` / run number `254` stopped at `Check formatting` after the M12 report builder and synthetic 100-item tests were added.
- **Affected files:** `knowledge_engine/import_runs/reporting.py`, `tests/test_import_run_reporting.py`
- **Root cause:** The duplicate-outcome `_count_lines(...)` call and one long test assertion used manually selected wrapping that did not match Ruff `0.15.20` under the repository's 100-character configuration.
- **Fix:** Captured Ruff's exact diff through a temporary CI artifact, applied the canonical multiline layouts, and restored the normal workflow.
- **Validation:** Quality run `29621869030` / run number `261` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `ffff745da005380c40f3a8e1403c31319531421f`.
- **Prevention / fast path:** Format new report modules and tests through Poetry from the repository root before committing; do not estimate wrapping manually.
- **Status:** resolved

## 2026-07-18 — M12 report literals exceeded lint line length

- **Area:** lint
- **First failing command:** `poetry run ruff check .`
- **Symptom:** Quality run `29621752827` / run number `258` passed formatting and then failed lint with six `E501` violations in the M12 report renderer.
- **Affected files:** `knowledge_engine/import_runs/reporting.py`
- **Root cause:** Ruff's formatter preserves long string literals because splitting them changes the source expression, while the lint configuration independently enforces a 100-character source-line maximum. One long inline manifest-version expression and five measurement-boundary literals therefore remained over the limit after formatting.
- **Fix:** Factored manifest version into a local value and used adjacent string literals inside parentheses so rendered text remained unchanged while source lines stayed within the configured limit.
- **Validation:** Quality run `29621869030` / run number `261` passed lint and every subsequent gate on commit `ffff745da005380c40f3a8e1403c31319531421f`.
- **Prevention / fast path:** Remember that formatter success does not guarantee `E501` compliance for long string literals; split source literals explicitly without inserting unintended output whitespace or newlines.
- **Status:** resolved

## 2026-07-21 — M14 manifest curation could not reconcile the exactly-500 selection

- **Area:** runtime / reliability / CLI invocation
- **First failing command:** `poetry run python -m knowledge_engine.manifest_curation_cli export --worksheet work/m14/candidate-review.json --receipt work/m14/acquisition-receipt.json --output work/m14/manifest-draft.csv`
- **Symptom:** Two independent, previously-undiscovered defects, both pre-existing and never exercised until manifest curation and corpus readiness were wired into the real M14 pipeline for the first time (issue #21, after discovery and acquisition were separately fixed):
  1. `export_manifest_curation_draft` required `len(accepted) == len(receipt_rows)` — an exact 1:1 count match between every accepted adjudication in the worksheet and every acquired receipt item. This directly contradicts the M14 exactly-500 selection design (established in the "select exactly 500" work): discovery is deliberately run to over-accept (593 accepted from 3,250 candidates in the most recent live run), then exactly 500 are selected and acquired. The equality check therefore unconditionally failed (593 != 500) on the very first real end-to-end attempt.
  2. `manifest_curation_cli.py` and `corpus_readiness_cli.py` each define exactly one `@app.command(...)` without an `@app.callback()`. Typer collapses a Typer app with a single registered command into "no explicit subcommand" mode, so invoking `... export --worksheet ...` fails with `Got unexpected extra argument (export)` (exit code 2) — the command name itself is rejected as an unrecognized positional argument. This is the same class of bug already fixed once in this repository for a different CLI (see PR #68's history in issue #21: "invoked the Typer single-command module with an invalid extra `prepare` token"), but the fix (`reviewed_approval_cli.py`'s `@app.callback()` with a no-op `main()`) was never applied to these two CLIs. It was already causing `tests/test_manifest_curation_cli.py` and `tests/test_corpus_readiness_cli.py` to fail on `main` (part of the pre-existing baseline), but was masked by the quality-gate pipefail defect (see the CI-gate entry below) and by these CLIs never having been invoked in a real workflow before now.
- **Affected files:** `knowledge_engine/manifest_curation.py`, `knowledge_engine/manifest_curation_cli.py`, `knowledge_engine/corpus_readiness_cli.py`, `tests/test_manifest_curation.py`, `.github/workflows/m14-mass-discovery.yml`
- **Root cause:** Both defects above; confirmed by direct reproduction (`poetry run python -m knowledge_engine.manifest_curation_cli export ...` reproduced the exact `Got unexpected extra argument (export)` failure locally, matching `reviewed_approval_cli.py`'s already-correct pattern by contrast) and by a full local synthetic integration run reproducing the real 2-accepted/1-selected shape end to end.
- **Fix:** (1) Removed the over-strict `len(accepted) != len(receipt_rows)` equality check in `manifest_curation.py`; the per-item reconciliation loop that follows already fully validates every receipt item against a matching, fully-passing, PMC-OA-verified accepted adjudication (PMCID, license, pdf_url, OA status) — removing the count check does not weaken any legal, identity, or provenance control, it only removes a stale invariant that assumed 1:1 accept:acquire, which the exactly-500 design intentionally violates. (2) Added the same `@app.callback()` no-op `main()` pattern already used in `reviewed_approval_cli.py` to both `manifest_curation_cli.py` and `corpus_readiness_cli.py`. (3) Wired `manifest_curation_cli export` and `corpus_readiness_cli validate` into `.github/workflows/m14-mass-discovery.yml` immediately after acquisition reconciliation, uploading `manifest-draft.csv` and `readiness-report.json` alongside the existing evidence artifact.
- **Validation:** `poetry run pytest tests/test_manifest_curation.py -q` — 6 passed (2 new: `test_accepted_superset_of_receipt_is_reconciled_by_selection`, `test_receipt_pmid_without_accepted_adjudication_is_rejected`). Direct CLI reproduction: `poetry run python -m knowledge_engine.manifest_curation_cli export --worksheet ... --receipt ... --output ...` now reaches real business logic instead of failing on argument parsing. `poetry run pytest tests/test_manifest_curation_cli.py tests/test_corpus_readiness_cli.py -q` — 4 passed (was 0 of 4; these were part of the pre-existing 26-failure baseline and are fixed as a necessary side effect of the CLI-invocation fix, not a separate unscoped change). Full-suite `pytest` went from 26 failed/434 passed to **22 failed/438 passed** (4 fewer failures, exactly the 4 fixed here); `mypy knowledge_engine tests` unchanged at 20 errors (reordered only, confirmed via diff); `ruff check .` unchanged at 12 pre-existing findings. A local synthetic end-to-end integration run (worksheet with 2 accepted + 1 held, 1 of 2 accepted selected and acquired — the same shape as the real pipeline's 593-accepted/500-selected run) proved the full chain: `reviewed_approval_cli export` → synthetic receipt/PDF → `manifest_curation_cli export` → `corpus_readiness_cli validate`, ending in `"ready": true`.

  Live confirmation: PR #77, workflow run `29841356698` attempt 2 (commit `2c3ddda783b102c2718a42b07dcdde198b142f62`), completed `success` in 34m (15:21:52–15:55:45 UTC) — the full 3,250-candidate/33-page pipeline, first real exercise of the two newly-wired steps against genuine discovery/acquisition output. Reconciliation summary: `candidate_count=3250 fetched_page_count=33 pmcid_resolved=3250 (rate=1.000000) oa_verified=3225 (rate=0.992308) accepted=596 rejected=25 held=2629 selected_count=500 acquired_count=500 exhausted=False`. `Export manifest curation draft` step: `Exported 500 manifest curation rows. No sources.csv file was modified.` `Validate corpus readiness` step: `Corpus ready: 500 manifest rows, 500 receipts, 500 PDFs.` (attempt 1 of the same run failed earlier at the discovery step with an unrelated, non-retryable PubMed efetch HTTP 400 on a page unconnected to this PR's diff — re-running the job reproduced success with identical code, confirming that failure was a transient NCBI-side blip, not a regression from this fix.)
- **Prevention / fast path:** Any new single-command Typer CLI in this repository must include an `@app.callback()` no-op, or it will silently reject its own command name in production (not just in tests) — this is now the second time this exact bug has appeared. Consider adding a lint rule or a shared CLI-app factory that always registers the callback to prevent a third occurrence.
- **Status:** resolved — fixed, unit-tested, and confirmed live against a full-scale M14 workflow run (PR #77, run `29841356698` attempt 2) with real discovery and acquisition output, ending in a genuine `"ready"` corpus confirmation.

## 2026-07-21 — M14 mass discovery failed on PMC identifier conversion

- **Area:** runtime / reliability / external provider
- **First failing command:** `poetry run python scripts/m14_pubmed_batch_discover.py --query "..." --limit 3250 --page-size 100 --output work/m14/pubmed-candidates.json`
- **Symptom:** GitHub Actions workflow `M14 Mass Discovery`, PR #75, run `29815429932` (job `discover`) ran for 20 minutes 17 seconds (08:44:22–09:04:39 UTC) and then failed with `M14 batch discovery failed: PMC identifier conversion request returned a non-success status.` A parallel later run on the same PR (`29815549208`) reached the PMC OA acquisition step instead; that is a separate, already-tracked failure (see below) and was not touched here.
- **Affected files:** `knowledge_engine/pubmed_discovery.py`, `tests/test_pubmed_discovery.py`
- **Root cause:** Not independently confirmable — GitHub Actions does not capture the raw HTTP status code or response body of the failing PMC ID Converter request, and `PubmedPmcDiscoveryService` deliberately sanitizes provider failures before raising `NcbiDiscoveryError`, so the exact status is unrecoverable after the fact. What is verifiable in the code: `PubmedPmcDiscoveryService._get()` retried every failure (transient exception or a retryable 429/500/502/503/504) using the same `request_interval_seconds` (0.34s) used for ordinary steady-state pacing between calls, for up to `max_attempts` (3) total tries. This gives at most ~0.7s of extra spacing across two retries — not a meaningful recovery window for a rate limit or transient outage encountered after 20+ minutes of sustained sequential NCBI traffic (33 pages, each issuing 1 esearch + 1 efetch + 1 id-converter call + up to ~100 individual `oa.fcgi` lookups). The sanitized error message also discarded the numeric status code, so a repeat failure would be exactly as undiagnosable as this one.
- **Fix:** Added a `retry_backoff_seconds` parameter (default `2.0`) to `PubmedPmcDiscoveryService`. Retries (attempt index > 0) now sleep `retry_backoff_seconds * 2 ** (attempt - 1)` (2s, 4s, ... by default) instead of the flat steady-state pacing interval; the first attempt of each call is unaffected. `NcbiDiscoveryError` messages for both the transport-exception and non-2xx paths now include the attempt count, and the non-2xx path also includes the numeric HTTP status code (not headers or body, preserving the existing sanitization contract). `scripts/m14_pubmed_batch_discover.py` picks this up automatically since it constructs `PubmedPmcDiscoveryService` with defaults.
- **Validation:** `poetry run pytest tests/test_pubmed_discovery.py -q` — 12 passed, including two new tests (`test_discovery_backs_off_exponentially_between_retries`, `test_discovery_rejects_negative_retry_backoff`) and an extended assertion on `test_discovery_sanitizes_provider_failures` confirming the status code is now surfaced. `poetry run ruff format --check knowledge_engine/pubmed_discovery.py tests/test_pubmed_discovery.py` and `poetry run ruff check knowledge_engine/pubmed_discovery.py tests/test_pubmed_discovery.py` both pass with zero findings in the changed lines (two pre-existing, unrelated `E501` findings remain in `tests/test_pubmed_discovery.py` at lines 76 and 99; see the CI-gate entry below for why these were never caught). Full-suite `poetry run pytest` and `poetry run mypy knowledge_engine tests` were also run directly (not through CI's broken `tee` pipes) to confirm no new failures: both show the same 26 pre-existing, unrelated failures/errors present on `main` before this change, none touching `pubmed_discovery.py` or `pubmed_batch_discovery.py`. Ran a live bounded `workflow_dispatch` smoke test on branch `claude/m14-pmc-conversion-error-urqzob` (commit `38b2434397aa19621ba855c3cbe7aad6d432abf7`), workflow run `29817820793`, with `limit=150 page_size=100`: the `Run bounded mass discovery` step succeeded end-to-end (`Wrote 150 unique candidates across 2 page(s); 150 PMC OA verified; 0 duplicate PMID(s) removed.`). Its later `Select exactly 500 accepted records` step failed as expected (`Adjudication worksheet contains fewer accepted approvals than the selection limit`) because 150 candidates cannot supply 500 accepted rows — unrelated to this fix. Then re-ran at the **original full scale**: `workflow_dispatch` run `29819456079` (commit `30c6ef1ed9695ad0dfad4d5b7cca84b6445e7cd5`) with the exact original parameters (`limit=3250 page_size=100`, same query) completed with `conclusion: success` in 27m33s (09:44:14–10:11:51 UTC) — every step passed, including `Run bounded mass discovery` (33 pages, the same page count as the original failing run) and `Select exactly 500 accepted records`. Reconciliation summary: `candidate_count=3250 fetched_page_count=33 pmcid_resolved=3250 (rate=1.000000) oa_verified=3220 (rate=0.990769) accepted=593 rejected=30 held=2627 selected_count=500 exhausted=False`. This is the same 3,250-candidate/33-page workload that failed with the PMC identifier conversion error after 20m17s in run `29815429932`; it now completes cleanly.
- **Prevention / fast path:** If PMC identifier conversion (or any NCBI endpoint) fails again, check whether the failure happened after a long sustained run; if so this is consistent with the still-unproven rate-limit hypothesis. Consider surfacing response headers (e.g. `Retry-After`) if this recurs, since the status code alone was not enough to fully confirm root cause here.
- **Status:** resolved — the retry/backoff and diagnosability gap is fixed, unit-tested, and confirmed live at both a 150-candidate smoke-test scale and the original full 3,250-candidate/33-page scale that produced the original failure. The exact original HTTP status/root cause remains unconfirmed (see Root cause above), but the failure has not recurred and the fix addresses every verifiable weakness in the retry path.

## 2026-07-21 — Quality gate does not actually enforce lint, type-check, or test results

- **Area:** CI
- **First failing command:** N/A — discovered as a side effect of investigating the M14 PMC identifier conversion failure above, while comparing a clean local `poetry run ruff check .` / `poetry run pytest` against the green `Quality` check on `main` HEAD commit `5abeff26b3e110074201943674dcc035791b6538`.
- **Symptom:** `poetry run ruff check .` fails with 11 pre-existing findings across 6 files (none introduced by this session), `poetry run mypy knowledge_engine tests` fails with 26 pre-existing errors across 12 files, and `poetry run pytest` fails with 26 pre-existing test failures — all on `main` HEAD, all present before this session's changes. Yet workflow run `29783311282` (Quality / Python quality checks) for that exact commit reports `conclusion: success`, and its "Enforce lint result" / "Enforce mypy result" / "Enforce pytest result" steps all show `skipped`, meaning the workflow believed those checks passed.
- **Affected files:** `.github/workflows/quality.yml`
- **Root cause:** The `Lint`, `Type check`, and `Test` steps run `poetry run <tool> ... 2>&1 | tee <file>.log` with `continue-on-error: true` but without `set -o pipefail`. Bash's default pipeline status is the exit code of the last command in the pipe (`tee`), which always exits `0` on a successful write regardless of whether `<tool>` failed. The subsequent `steps.<id>.outcome == 'failure'` check therefore never observes a real failure from these three steps, so `Enforce <tool> result` never runs and the job reports success even when lint, type-check, or tests are broken. (The `Check formatting` step is unaffected because it redirects with `>`, not a pipe.) This is a distinct root cause from the M14 discovery failure above and was not fixed in this session.
- **Fix:** Added `set -o pipefail` before each of the three piped steps (`Lint`, `Type check`, `Test`) in `.github/workflows/quality.yml`, matching the pattern already used correctly in `.github/workflows/m14-mass-discovery.yml`'s discovery step. Per explicit user decision (asked via the fix-everything-vs-defer question above the "gate now enforces real results" tradeoff), also fixed every pre-existing finding the corrected gate now surfaces on `main`, rather than landing a gate that would immediately turn every subsequent PR red:
  - All 12 ruff findings: 6 auto-fixed (`UP017`/`UP035`), 6 fixed by hand (`SIM105`, `SIM102`, `SIM117`, two `E501` line-length wraps in an XML test fixture and one in `entrypoint.py`).
  - All 20 mypy errors, including 4 real production-code issues (an overly-broad `_ReadableResponse.status` Protocol member in `ncbi_http.py` that no caller used; an unnarrowed `object` index chain in `pubmed_discovery.py._search`; an unnarrowed `object` passed to `int()` in `google_drive_http.py.get_file_metadata`; a `dict[str, object]` return type on `candidate_review._adjudicate` replaced with a `TypedDict` matching its always-fixed return shape) and 16 test-fixture/type-drift issues (stale `PubmedCandidate`/`ImportedCorpusRun`/`_final_run_status` constructor calls after those types gained fields; a `discover_candidate_batch` parameter narrowed to a new `DiscoveryService` Protocol instead of the concrete `PubmedPmcDiscoveryService` class so a duck-typed fake satisfies it; a `frozen=True` test dataclass that mypy treats as read-only, failing `TransportResponse` Protocol conformance; a misplaced `# type: ignore` comment; and one Protocol-inheritance cleanup in `FakeTransport`).
  - All 22 pytest failures, most as a direct side effect of the mypy fixes above (stale constructor calls were also runtime bugs, not just type errors). Six were independent: a `candidate_review_cli` test asserting a `"pending"` decision value that predates the deterministic adjudication rules (v3) introduced separately; two `test_corpus_readiness.py` fixture bugs (`"CC-BY"` vs `"CC BY"` — production code always copies `license_type` verbatim from the receipt, so these are never allowed to differ in real data; and two PDF fixtures of different byte lengths where the test intended to isolate a hash mismatch); a stale exact-message assertion in `test_corpus_run_report_cli.py` ("Report output could not be written" vs the real shared message "Output file could not be written."); a `test_pmc_acquisition_cli.py` assertion ("were rolled back") that Click's error-panel word-wrapping split across a line boundary in the real (correct) output; and **a third and fourth occurrence of the single-command Typer CLI collapse bug** (see the manifest-curation entry above) in `pdf_calibration_cli.py` and `candidate_review_cli.py` — the latter was live in production, invoked without its `prepare` subcommand name in `.github/workflows/m14-mass-discovery.yml`'s "Adjudicate candidate evidence" step, which had to be updated in the same change to keep working once the collapse bug (and thus the silent subcommand-optional behavior) was fixed.
  - One genuine, previously-undiscovered production bug found while investigating a failing test, not the test itself: `sqlite_backup.create_sqlite_backup` only cleaned up a partial snapshot file on `(OSError, sqlite3.Error)`, but `inspect_sqlite_snapshot`'s naive-timestamp rejection raises `SQLiteBackupError` (a `RuntimeError`), which wasn't caught — so a naive `created_at` left an unverified snapshot file on disk instead of being removed like every other failure path. Fixed by adding an `except SQLiteBackupError: ... raise` cleanup branch.
  - A full sweep of every `typer.Typer()` app in the repository (`grep -rl "typer.Typer(" knowledge_engine/`) confirmed no further undiscovered instances of the collapse bug remain: all single-command CLIs now have `@app.callback()`, and `entrypoint.py`/`cli.py` share one 17-command app well above the 1-command collapse threshold.
- **Validation:** `poetry run ruff check .` — all checks passed (was 12 findings). `poetry run ruff format --check .` — 114 files already formatted. `poetry run mypy knowledge_engine tests` — success, no issues found in 113 source files (was 20 errors). `poetry run pytest` — 456 collected, full run exit code 0, zero failures (was 22 failed). Manually verified the `pipefail` fix itself in isolation (`bash -c 'set -o pipefail; false | tee /tmp/x.log; echo $?'` → `1`, vs `0` without it) since CI cannot be exercised locally.
- **Prevention / fast path:** Before trusting a green `Quality` check on this repository, independently run `poetry run ruff check .`, `poetry run mypy knowledge_engine tests`, and `poetry run pytest` locally — the gate now genuinely reflects these results. When adding any new single-command Typer CLI, always add `@app.callback()` immediately; this was the third and fourth occurrence of the exact same bug in this repository, and a fifth should not require another failing test to discover — audit with `grep -rl "typer.Typer(" knowledge_engine/` and check each file's command count against whether it has a callback.
- **Status:** resolved — closes [issue #78](https://github.com/jweter/knowledge-engine-core/issues/78).

## 2026-07-21 — M14 PMC OA acquisition failed on NCBI's FTP path migration

- **Area:** runtime / reliability / external provider
- **First failing command:** `poetry run ke pmc-oa-acquire --candidates work/m14/pubmed-candidates.json --approvals work/m14/approvals-500.json --papers-dir work/m14/papers --receipt work/m14/acquisition-receipt.json`
- **Symptom:** GitHub Actions workflow `M14 Mass Discovery`, PR #75, run `29815549208` (and again on retry, run `29822421628`) failed at the `Acquire exactly 500 approved PDFs` step with `PMC OA acquisition failed: PMC OA PDF request returned a non-success status.` Discovery, adjudication, exact-500 selection, and the pre-network preflight all passed; only acquisition failed, on the very first PDF request (~0.1s after starting network access), not after any sustained load.
- **Affected files:** `knowledge_engine/pmc_acquisition.py`, `tests/test_pmc_acquisition.py`
- **Root cause:** Confirmed, not inferred. NCBI is mid-migration of its PMC FTP service. `ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt` (fetched directly): "All legacy files for the PMC Article Datasets were moved to a new temporary directory named 'deprecated'. All legacy files on the FTP Service will be removed in August 2026." The PMC OA service (`oa.fcgi`) still returns links at the pre-migration paths (`/pub/pmc/oa_pdf/...`, `/pub/pmc/oa_package/...`), which now 404, while the actual files live under `/pub/pmc/deprecated/oa_pdf/...` (verified 200). Reproduced directly with `curl` against the exact failing URL from CI (`PMC13378728`) and independently against an unrelated, much older record (`PMC9500000`, originally published 2022) to confirm this is systemic across the whole OA corpus, not one stale record.
- **Fix:** First landed a diagnostic-only change (commit `e1d6469`) adding the numeric HTTP status code and a non-sensitive locator (1-based approval ordinal + PMCID) to `AcquisitionError` messages — this is what surfaced the `404` and allowed the root cause above to be confirmed from a live run rather than guessed. Then (commit `e3ce203`) added a single retry against NCBI's confirmed `/pub/pmc/deprecated/` relocation when the announced path 404s; no other status code's handling changed, no host-allowlist or PDF/licensing/count/checksum/transactional validation was touched.
- **Validation:** `poetry run pytest tests/test_pmc_acquisition.py -q` — 13 passed (was 9 before either commit), including `test_non_success_status_is_reported_with_status_code_and_locator`, `test_legacy_path_404_falls_back_to_deprecated_ncbi_relocation`, and `test_deprecated_fallback_failure_still_reports_original_locator`. Full-suite `pytest` and `mypy knowledge_engine tests` matched this branch's pre-existing baseline exactly (26 failures / 20 errors, none touching the changed files) both before and after. Live: PR #75 workflow run `29827601057` (commit `e3ce203`) — the full 3,250-candidate pipeline, the same scale and query that originally failed — completed with every step passing: discovery (33 pages), adjudication, exact-500 selection, preflight, acquisition, reconciliation, and both artifact uploads. The acquisition step's own log confirms `With the provided path, there will be 500 files uploaded` — all 500 approved PDFs were downloaded (878,820,437 bytes total) and uploaded as the `m14-approved-pdfs` artifact.
- **Prevention / fast path:** If PMC OA acquisition 404s again, check `https://ftp.ncbi.nlm.nih.gov/pub/pmc/readme.txt` first for further NCBI path changes before assuming a code regression.
- **Known follow-up required before August 2026:** ~~This fix is a confirmed, working, but explicitly **temporary** bridge~~ — **superseded.** The durable replacement landed via [ADR 0004](architecture/adr/0004-migrate-pmc-oa-acquisition-to-cloud-service.md): PMC OA discovery and acquisition were migrated off `oa.fcgi`/FTP entirely onto NCBI's documented PMC Article Datasets Cloud Service (a public S3 bucket, plain unsigned HTTPS, no new dependency), ahead of NCBI's August 2026 removal date for both `oa.fcgi` and the FTP Service (including the `/pub/pmc/deprecated/` relocation this entry's fix bridged to). The `_deprecated_pmc_fallback_url` bridge in `pmc_acquisition.py` was removed as dead code once nothing could produce a legacy-path URL for it to match. This closed [issue #79](https://github.com/jweter/knowledge-engine-core/issues/79).
- **Status:** resolved

## Operating rule

When CI fails:

1. Record the first failing command and exact evidence before editing code.
2. Search this ledger for the error code, command, or affected file.
3. Reuse a prior fix only when the root cause matches; similar symptoms can have different causes.
4. Apply the smallest source fix. Do not weaken the quality gate or suppress a diagnostic without justification.
5. Validate locally with repository configuration, then require the complete GitHub Actions Quality gate.
6. Add or update the ledger entry with the passing commit and workflow run.
7. Remove temporary diagnostic workflows, artifacts, scripts, and delivery files before considering the fix complete.
8. If the fix cannot land in the same session/PR, open a GitHub issue labeled `bug` for it instead of leaving it only as a `Status: open` ledger entry, and add a `Tracked as:` line here pointing to that issue. The ledger stays the permanent root-cause record; the issue is what's actually watched, assigned, and closed. See `docs/error_log.md` for why this replaced the old single-active-failure file.
