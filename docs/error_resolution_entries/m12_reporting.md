# M12 Reporting Error-Resolution Addendum

This file supplements `docs/error_resolution_ledger.md` for M12 reporting work. It records verified failures and review findings that occurred after the consolidated ledger was created. These entries should be merged into the consolidated ledger during the final M12 documentation review.

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
