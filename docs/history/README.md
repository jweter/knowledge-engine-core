# Historical Record

This directory holds point-in-time documents: milestone build logs, the
vertical-slice prototype narrative, and one-off status/audit reports. They
describe what was true, decided, or built at the time they were written --
useful as record of *why* the project looks the way it does, but not
maintained going forward and not the place to look for current behavior.

For current behavior, architecture, and design, see the living docs at
`docs/` (start with `docs/roadmap.md`) or `docs/README.md`'s index.

- `milestones/` -- one document (sometimes several) per numbered milestone
  (M6 through M55): the plan, worksheet, or report written at the time that
  milestone shipped. `docs/roadmap.md`'s "Completed \* milestones" lists
  link into this directory.
- `vertical_slice/` -- the VS3 through VS17 narrative: the original
  GLP-1 retrieval-and-manual-evidence prototype that predates the
  Evidence Record and Knowledge Graph phases. `docs/roadmap.md` and
  `docs/phase2_design.md` explain how this prototype relates to what
  replaced it.
- `daily_repo_status.md`, `audit_remediation_register.md`,
  `architect_review.md`, `codex_error_log.md`, `codex_fixes.md`,
  `error_log.md` -- standalone point-in-time status and audit snapshots.
  Any item from these that was still open when archived was carried
  forward into `docs/technical_debt.md`, the living tracker -- nothing
  open was lost by archiving these.
