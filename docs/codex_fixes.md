# Codex Verified Fixes

## 2026-07-17 — Ruff formatting gate

### Verified fix

Applied the exact Ruff `0.15.20` formatting output to `knowledge_engine/metadata_enrichment.py`. The change only adjusts canonical wrapping; behavior is unchanged.

### Tests and checks run

- `ruff format --check knowledge_engine/metadata_enrichment.py` — passed.
- `ruff check knowledge_engine/metadata_enrichment.py` — passed.
- `PYTHONPATH=<isolated checkout> pytest -q tests/test_metadata_enrichment.py` — passed: `14 passed in 0.13s`.

### Outcome and remaining risk

The module-level formatting defect is corrected. Repository-wide CI remains required before the quality gate is complete.

## 2026-07-18 — Metadata test formatting

### Verified fix

Applied Ruff `0.15.20` canonical formatting to `tests/test_metadata_enrichment.py`, collapsing the manually wrapped `classify_candidate(...)` call in `test_candidate_fills_missing_value`. No test behavior changed.

### Tests and checks run

- `ruff format --check knowledge_engine/metadata_enrichment.py tests/test_metadata_enrichment.py` — passed: `2 files already formatted`.
- `ruff check knowledge_engine/metadata_enrichment.py tests/test_metadata_enrichment.py` — passed: `All checks passed!`.
- `PYTHONPATH=<isolated checkout> pytest -q tests/test_metadata_enrichment.py` — passed: `14 passed in 0.13s`.

The isolated checkout used the branch versions of `knowledge_engine/metadata_enrichment.py`, `knowledge_engine/utils.py`, and `tests/test_metadata_enrichment.py`, with Ruff pinned to `0.15.20` and the repository's 100-character line length.

### Outcome

The reproduced test-file formatting defect is fixed in commit `b3bc497b20dda3e067c28f69dac99aaa02060ed7`. A new GitHub Actions Quality result is still required to establish the next repository-wide failure, if any.

### Remaining risk

- The broad formatting check and all later quality-gate steps must pass on the new branch head.
- Connector access cannot expose an uncommitted local working tree; repository state is verified only through the remote branch and PR.
- M11 remains incomplete: Crossref adapter, preview boundary, security controls, and persistence decision are outstanding.
- PR #15 must remain draft.

### Exact continuation point

Inspect the Quality run for the current PR head. Handle only the first newly exposed failure. If the entire gate passes, begin the smallest mocked Crossref-adapter contract test without adding persistence or ingestion coupling.
