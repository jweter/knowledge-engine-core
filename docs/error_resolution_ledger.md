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

## Operating rule

When CI fails:

1. Record the first failing command and exact evidence before editing code.
2. Search this ledger for the error code, command, or affected file.
3. Reuse a prior fix only when the root cause matches; similar symptoms can have different causes.
4. Apply the smallest source fix. Do not weaken the quality gate or suppress a diagnostic without justification.
5. Validate locally with repository configuration, then require the complete GitHub Actions Quality gate.
6. Add or update the ledger entry with the passing commit and workflow run.
7. Remove temporary diagnostic workflows, artifacts, scripts, and delivery files before considering the fix complete.
