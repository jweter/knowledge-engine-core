# M12 Reporting Error-Resolution Addendum

This file is the authoritative M12 supplement to `docs/error_resolution_ledger.md`. It records verified M12 failures and review findings that occurred after the consolidated ledger was created. Keep both files when investigating M12 history. Consolidate them only through a lossless patch-capable checkout; do not replace or manually reconstruct the historical ledger from truncated connector output.

## 2026-07-18 — Typer/Rich wrapping made reconciliation assertion brittle

- **Area:** tests
- **First failing command:** `poetry run pytest`
- **Symptom:** Quality run `29622045284` / run number `264` passed formatting, lint, and strict mypy, then failed one CLI assertion for the reconciliation error message.
- **Affected files:** `tests/test_corpus_run_report_cli.py`
- **Root cause:** Typer and Rich wrapped the detailed error text inside the formatted terminal panel. The test asserted one contiguous physical line rather than stable semantic content.
- **Fix:** Asserted the stable fragments `Import run report reconciliation failed` and `Declared source rows` independently. Application behavior was unchanged.
- **Validation:** Quality run `29622187037` / run number `267` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `601fb6de2eb4291d71837ae2aa845d81cb675631`.
- **Prevention / fast path:** For Typer/Rich terminal output, test exit status and semantic fragments unless physical layout is explicitly part of the interface contract.
- **Status:** resolved

## 2026-07-18 — Persisted corpus name could inject Markdown or HTML into reports

- **Area:** security / privacy
- **First failing command:** Full-diff security and privacy review of PR #17.
- **Symptom:** Persisted values were bounded to one line and backticks were replaced, but `corpus_name` was rendered outside a code span without escaping Markdown or HTML control characters.
- **Affected files:** `knowledge_engine/import_runs/reporting.py`, `tests/test_import_run_reporting.py`
- **Root cause:** One sanitizer was reused for both code-span values and free Markdown text even though those output contexts require different escaping rules.
- **Fix:** Split sanitization into `_safe_code` for bounded code-span values and `_safe_text` for escaped free Markdown text. Added regression coverage for headings, links, HTML tags, emphasis, backticks, and embedded newlines.
- **Validation:** Quality run `29631145907` / run number `275` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `f1e3b8812904e7e6fd71a4ddc6ef06d74fe98a97`.
- **Prevention / fast path:** Sanitize according to the output context. Code spans, Markdown text, HTML attributes, URLs, SQL, and shell arguments are distinct encoding boundaries and should not share a generic escape helper.
- **Status:** resolved

## 2026-07-18 — Report hardening files lacked final newline characters

- **Area:** formatting
- **First failing command:** `poetry run ruff format --check .`
- **Symptom:** Quality run `29631048988` / run number `271` stopped at formatting after the Markdown hardening change.
- **Affected files:** `knowledge_engine/import_runs/reporting.py`, `tests/test_import_run_reporting.py`
- **Root cause:** Both replacement file writes omitted their final newline. Ruff's canonical diff contained no structural edits; it added only POSIX file terminators.
- **Fix:** Added one final newline to each file and removed the temporary diagnostic workflow.
- **Validation:** Quality run `29631145907` / run number `275` passed the complete standard gate on commit `f1e3b8812904e7e6fd71a4ddc6ef06d74fe98a97`.
- **Prevention / fast path:** Ensure replacement text files end with exactly one newline. When Ruff reports a file would be reformatted but visible structure appears unchanged, inspect the canonical diff for `No newline at end of file` before changing code.
- **Status:** resolved

## 2026-07-18 — Report output followed symbolic links and exposed filesystem errors

- **Area:** security / privacy / reliability
- **First failing command:** Full-diff review of the `corpus-run-report --output` boundary.
- **Symptom:** `Path.write_text` followed symbolic-link outputs, including when `--force` was supplied, and raw `OSError` details could propagate through the CLI with private filesystem paths.
- **Affected files:** `knowledge_engine/entrypoint.py`, `tests/test_corpus_run_report_cli.py`
- **Root cause:** Output validation checked only `Path.exists()` and treated the user-supplied path as an ordinary file. Symbolic links are a distinct filesystem object, and write failures were not translated at the CLI boundary.
- **Fix:** Reject symbolic-link output paths before database access, preserve existing-file overwrite protection, and translate filesystem write failures into a stable path-free CLI error. Added tests proving the symlink target remains unchanged and private error details are not rendered.
- **Validation:** Quality run `29631373173` / run number `278` passed formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection on commit `867f70b82dc262cffa2e2bb3192abec9509f0604`.
- **Prevention / fast path:** Treat symlinks, regular files, and directories as different output-path states. Validate before loading expensive state, and translate low-level filesystem errors at the user-facing boundary without echoing private paths.
- **Status:** resolved

## 2026-07-18 — PMC package preparation selected zero PDFs

- **Area:** external dataset integration / operations
- **First failing command:** `poetry run python .github/scripts/prepare_m12_pmc_corpus.py --workspace "$GITHUB_WORKSPACE" --count 100`
- **Symptom:** M12 rehearsal run `29632121801` / run number `2` stopped before preflight with `selected 0 usable PDFs; required 100`.
- **Affected files:** the temporary PMC corpus preparation script and rehearsal workflow.
- **Root cause:** PMC moved legacy individual OA article packages under `/pub/pmc/deprecated/oa_package/` during its 2026 dataset transition, while the OA service still supplied legacy package paths. The original script requested the pre-transition path and every package retrieval failed. The original failure accumulator also discarded useful aggregate categories.
- **Fix:** Translate only allowlisted `ftp.ncbi.nlm.nih.gov` legacy package paths to the official deprecated transition directory, preserve HTTPS and response-size bounds, parse the documented resumption token attribute, and emit bounded aggregate failure categories.
- **Validation:** Rehearsal run `29632996792` / run number `8` selected exactly 100 licensed PDFs and passed preparation, preflight, fresh import, resume, and artifact checks.
- **Prevention / fast path:** Treat external dataset URL structures as versioned integration contracts. Preserve host and size validation while isolating transition mapping in one tested function, and keep aggregate failure reason codes even when individual URLs are suppressed.
- **Status:** resolved

## 2026-07-18 — Rehearsal workflow invoked superseded preparation and deleted evidence

- **Area:** workflow configuration / evidence retention
- **First failing command:** M12 rehearsal workflow preparation and artifact upload.
- **Symptom:** A corrected preparation script existed, but the workflow still invoked the original script. The workflow also recorded environment evidence before preparation, while preparation recreated `.m12-runtime`, deleting that evidence directory.
- **Affected files:** `.github/workflows/m12-rehearsal.yml`.
- **Root cause:** The workflow and script evolved in separate commits without an exact-path synchronization check; destructive runtime initialization occurred after evidence creation.
- **Fix:** Point the workflow at the corrected script, move environment recording after preparation, keep the preparation log outside the recreated runtime until preparation completes, and remove the temporary diagnostic workflow and superseded script.
- **Validation:** Rehearsal run `29632996792` / run number `8` passed preparation and retained the complete sanitized evidence set.
- **Prevention / fast path:** Keep destructive workspace initialization as the first runtime operation. When replacing scripts, update workflow paths in the same change and remove superseded entrypoints after the new path is verified.
- **Status:** resolved

## 2026-07-18 — Preparation log exposed the private runner workspace

- **Area:** privacy / artifact sanitization
- **First failing command:** `! grep -R "$GITHUB_WORKSPACE" .m12-runtime/evidence`
- **Symptom:** Rehearsal run `29632879904` / run number `7` passed preflight, fresh import, reports, and resume, then failed only the prohibited-artifact check. `preparation.log` ended with the absolute runner path to `corpus.json`.
- **Affected files:** `.github/scripts/prepare_m12_pmc_corpus_v2.py`.
- **Root cause:** The evidence JSON stored a relative corpus path, but the human-readable final status line printed the absolute `Path` object.
- **Fix:** Compute the corpus path relative to the workspace once and use that value in both structured evidence and terminal output.
- **Validation:** Rehearsal run `29632996792` / run number `8` passed the private-path scan and uploaded a sanitized artifact with digest `sha256:a47228b3bd68a29852c9731bafed91399c0c33f1251701bb0fc75d3840c56be7`.
- **Prevention / fast path:** Apply privacy rules consistently to structured and human-readable outputs. Sanitization checks should scan the final artifact directory, not only generated reports.
- **Status:** resolved
