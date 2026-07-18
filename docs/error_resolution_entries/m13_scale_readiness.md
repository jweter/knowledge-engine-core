# M13 Error Resolution Record

## Scope

This record covers verified M13 implementation and delivery failures. It does not treat speculative concerns as defects.

## Ruff formatting and line-length interaction

A chained equality was manually wrapped. Ruff formatting canonicalized it onto one line, which then exceeded the configured line-length rule.

Root cause: the expression structure was incompatible with both canonical formatting and the line-length constraint.

Fix: split the comparison into named boolean checks and combine those checks.

Validation: formatting, lint, strict mypy, and pytest passed.

## Constructed function default

`ReadinessThresholds()` was used directly as a function default and triggered lint.

Root cause: constructing an object in a function signature creates a shared default instance and violates the configured rule.

Fix: use a `None` sentinel and construct the default inside the function.

Validation: lint, strict mypy, and tests passed.

## Diagnostic workflow interruption

A temporary Ruff diagnostic stopped before artifact upload because formatter differences correctly returned a nonzero exit status.

Root cause: capture and failure evaluation were coupled in one shell step.

Fix: allow diagnostic capture to complete, then evaluate failure separately. The standard Quality workflow was restored unchanged.

## Connector write failures

Several file, comment, reaction-removal, and low-level Git-object writes were blocked before GitHub mutation even though the installation reported admin and push permission.

Root cause: selective pre-execution blocking in the connector mutation layer, not repository authorization or project code.

Workaround: use GitHub's mobile browser editor to advance the branch, then retry connector writes. After the mobile commits, connector deletion and file creation succeeded intermittently.

## Mobile path-entry defects

Three empty files were created under malformed or capitalized paths:

- `Docs/docs/error_resolution_entries/m13_scale_readiness.md`
- `Docs/m13_scale_readiness_decision.md`
- `docs/error_resolution_entriesm13_scale_readiness.md`

Root cause: path entry mistakes in the mobile browser editor.

Fix: create the authoritative files at lowercase canonical paths and remove malformed empty files. One malformed file was removed successfully; remaining empty placeholders must be removed before merge.

## Current validation requirement

The exact final PR head must pass formatting, lint, strict mypy, full pytest, diff hygiene, and temporary-artifact rejection before the PR is marked ready.
