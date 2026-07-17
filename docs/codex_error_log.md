# Codex Error Log

## 2026-07-17 — Ruff formatting gate failure

- **Exact command:** `poetry run ruff format --check .`
- **Observed evidence:** GitHub Actions Quality run `29604546266` on PR #15 head `1e2cd50f34c04f788e5b4cb8937d25d8cbb0b0b3` failed at `Check formatting`. Ruff reported `Would reformat: knowledge_engine/metadata_enrichment.py` and `1 file would be reformatted, 49 files already formatted`. Lint, strict mypy, pytest, diff hygiene, and temporary-artifact checks were skipped.
- **Local reproduction:** Ruff `0.15.20` reformatted `knowledge_engine/metadata_enrichment.py` by wrapping the `validate_candidates` signature, the `normalize_candidate_value` call, and the long `ValueError` construction. `ruff format --check` then passed on the formatted file.
- **Likely root cause:** Three lines in `validate_candidates` exceeded the formatter's canonical layout under the repository-locked Ruff version.
- **Confidence:** High. The exact CI-identified file and exact Ruff `0.15.20` generated diff were reproduced.
- **Affected files:**
  - `knowledge_engine/metadata_enrichment.py`
- **Proposed fix:** Commit the exact Ruff `0.15.20` formatting output, then verify the targeted metadata-enrichment tests and the next GitHub Actions Quality run.
- **Scope assessment:** Formatting-only and within the current M11 draft PR scope. No behavioral, schema, network, CLI, or persistence change is justified.

## 2026-07-18 — Metadata test formatting gate failure

- **Exact command:** `poetry run ruff format --check .`
- **Observed evidence:** GitHub Actions Quality run `29618333641` on PR #15 head `5ee5e85c6d5939df02c29007638ce6ba0358932c` failed at `Check formatting`; lint, strict mypy, pytest, diff hygiene, and temporary-artifact checks were skipped.
- **Local reproduction:** With Ruff `0.15.20` and the repository's `line-length = 100`, `ruff format tests/test_metadata_enrichment.py` collapsed the three-line `classify_candidate(...)` call in `test_candidate_fills_missing_value` to one line. The formatter then reported the file as canonical.
- **Likely root cause:** The test retained a manual wrap that is non-canonical under the repository's 100-character Ruff configuration.
- **Confidence:** High for the reproduced formatting defect; medium that it was the only file reported by the broad CI command because the available step summary did not expose the complete formatter output.
- **Affected files:**
  - `tests/test_metadata_enrichment.py`
- **Proposed fix:** Commit the exact Ruff `0.15.20` formatting output for the test file and verify formatting, lint, and the targeted metadata-enrichment tests.
- **Scope assessment:** Formatting-only and within the current M11 draft PR scope.
