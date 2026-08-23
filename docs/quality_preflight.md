# Quality Preflight

Knowledge Engine treats recurring CI failures as engineering signals, not isolated cleanup work. Before opening or updating a pull request that changes Python, run the canonical local preflight from the repository root.

For normal development, use the autofix mode first:

```powershell
poetry run python scripts/quality_preflight.py --fix
```

`--fix` performs only deterministic Ruff changes that are already allowed by the repository configuration:

1. `ruff format .`
2. `ruff check --fix .`
3. `ruff format .` again, because lint fixes can alter layout

It then immediately runs the check-only gates in the same useful order as CI:

1. `ruff format --check .`
2. `ruff check .`
3. `mypy knowledge_engine tests`
4. `pytest`
5. `git diff --check` (diff hygiene)

This means formatting and safe lint issues such as import ordering, Python-version modernization, and other Ruff-fixable diagnostics should be corrected before a CI cycle is consumed. The script intentionally does **not** use Ruff `--unsafe-fixes`.

To verify a tree without modifying it, omit `--fix`:

```powershell
poetry run python scripts/quality_preflight.py
```

Both modes stop on the first non-zero command. In `--fix` mode, the entire check-only sequence still runs after fixes so a branch is not considered preflight-clean merely because Ruff could rewrite it. GitHub Actions remains the authoritative merge gate.

The diff-hygiene gate mirrors the `Check diff hygiene` step in `.github/workflows/quality.yml`. Bandit (`.github/workflows/security-bandit.yml`) and pip-audit (`.github/workflows/security-pip-audit.yml`) are intentionally not included here: both run outside the Poetry-managed environment in CI (Bandit via a bare `pip install`, pip-audit against a `poetry export`-generated requirements file), so a `poetry run` preflight step could not reproduce them faithfully without adding tools to the project dependency surface that CI itself does not use that way. Run those two commands directly when a change plausibly affects security-scanned code or dependencies:

```powershell
python -m pip install --disable-pip-version-check bandit
bandit --recursive --severity-level high knowledge_engine

poetry export --only main --without-hashes --format requirements.txt --output /tmp/requirements-audit.txt
python -m pip install --disable-pip-version-check pip-audit
pip-audit --requirement /tmp/requirements-audit.txt --no-deps --disable-pip
```

## Required development sequence

For Python changes, use this sequence before marking a branch ready for review:

1. Make the focused implementation and tests.
2. Run `poetry run python scripts/quality_preflight.py --fix`.
3. Review any Ruff-generated diff rather than committing it blindly.
4. Fix any remaining mypy or pytest failure.
5. Re-run the same command until it exits successfully.
6. Only then push or update the pull request.

This is especially important for automated or agent-authored code. Repository configuration is the authority for style and lint policy; generated code must be normalized against the pinned toolchain before it is treated as delivery-ready.

## Recurring-failure rule

When a CI or runtime failure repeats, search `docs/error_resolution_ledger.md` before making a new fix. Record verified evidence, root cause, the smallest successful correction, validation, and a prevention/fast-path note. If prevention is deferred, open a GitHub issue and link it from the ledger rather than leaving the lesson only in a PR conversation.

This preflight was introduced after PR #355 repeated a historical Ruff pattern: a formatting failure was corrected and the next CI run then exposed an independently deterministic `I001` import-order failure. The later PR #404 sequence exposed the same class of avoidable staircase again: formatting first, then a Ruff `UP037` modernization diagnostic. The `--fix` phase exists specifically to collapse those deterministic failures into one local step before CI.

Do not weaken CI, suppress diagnostics, broaden ignore rules, or enable unsafe autofixes merely to make the preflight pass.
