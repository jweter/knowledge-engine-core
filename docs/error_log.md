# Error Log

Superseded. Open, unresolved defects are now tracked as GitHub issues labeled
[`bug`](https://github.com/jweter/knowledge-engine-core/issues?q=is%3Aissue+is%3Aopen+label%3Abug),
not in this file — an issue can be assigned, linked from the fixing PR (`Fixes #N`), and
closed when resolved, none of which a prose file supports. This file is kept only so
existing links to it (PR descriptions, past ledger entries) do not break.

The authoritative resolved-failure history remains
[`docs/error_resolution_ledger.md`](error_resolution_ledger.md).

Known open issues as of 2026-07-21:

- [#78](https://github.com/jweter/knowledge-engine-core/issues/78) — Quality gate does not
  actually enforce lint, type-check, or test results (`.github/workflows/quality.yml`
  pipefail gap).
- [#79](https://github.com/jweter/knowledge-engine-core/issues/79) — PMC OA acquisition
  depends on a temporary NCBI path bridge that expires August 2026.
