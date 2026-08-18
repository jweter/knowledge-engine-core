# Quality Preflight

Knowledge Engine treats recurring CI failures as engineering signals, not isolated cleanup work. Before opening or updating a pull request that changes Python, run the canonical local preflight from the repository root:

```powershell
poetry run python scripts/quality_preflight.py
```

The preflight runs the deterministic gates in the same useful order as CI:

1. `ruff format --check .`
2. `ruff check .`
3. `mypy knowledge_engine tests`
4. `pytest`
5. `git diff --check` (diff hygiene)

It stops on the first failure so the first actionable defect stays visible. Fix that root cause, run the preflight again, and only then push the PR update. GitHub Actions remains the authoritative merge gate.

The diff-hygiene gate mirrors the `Check diff hygiene` step in `.github/workflows/quality.yml`. Bandit (`.github/workflows/security-bandit.yml`) and pip-audit (`.github/workflows/security-pip-audit.yml`) are intentionally not included here: both run outside the Poetry-managed environment in CI (Bandit via a bare `pip install`, pip-audit against a `poetry export`-generated requirements file), so a `poetry run` preflight step could not reproduce them faithfully without adding tools to the project dependency surface that CI itself does not use that way. Run those two commands directly when a change plausibly affects security-scanned code or dependencies:

```powershell
python -m pip install --disable-pip-version-check bandit
bandit --recursive --severity-level high knowledge_engine

poetry export --only main --without-hashes --format requirements.txt --output /tmp/requirements-audit.txt
python -m pip install --disable-pip-version-check pip-audit
pip-audit --requirement /tmp/requirements-audit.txt --no-deps --disable-pip
```

## Recurring-failure rule

When a CI or runtime failure repeats, search `docs/error_resolution_ledger.md` before making a new fix. Record verified evidence, root cause, the smallest successful correction, validation, and a prevention/fast-path note. If prevention is deferred, open a GitHub issue and link it from the ledger rather than leaving the lesson only in a PR conversation.

This preflight was introduced after PR #355 repeated a historical Ruff pattern: a formatting failure was corrected and the next CI run then exposed an independently deterministic `I001` import-order failure. Issue #356 tracks the preventive improvement. The lesson is broader than those two diagnostics: cheap deterministic checks should run locally before consuming a CI cycle.

Do not weaken CI, suppress diagnostics, or broaden ignore rules merely to make the preflight pass.
