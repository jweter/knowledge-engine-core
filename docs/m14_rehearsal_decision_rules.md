# M14 Rehearsal Decision Rules

## STOPPED

Use `STOPPED` when the rehearsal did not begin or terminated under a defined stop condition. Examples include a failed entry gate, unavailable measurements, changed immutable inputs, systemic exceptions, reconciliation mismatch, idempotency failure, lineage failure, or artifact-hygiene risk.

## HOLD

Use `HOLD` when execution completed and counts reconcile, but the evidence exposes a material uncertainty requiring explicit review before the next milestone. A hold must name the uncertainty, its observed impact, and the evidence needed to resolve it.

## PROCEED

Use `PROCEED` only when:

- exactly 500 accepted rows were validated;
- all required local files and licensing bases were present;
- the fresh import completed without a stop condition;
- source, persisted-item, and terminal-outcome counts reconcile exactly;
- database growth and elapsed time were measured;
- the linked resume created no unexpected paper, paper-text, or FTS rows;
- linked lineage reconciles completely;
- the sanitized evidence and report contain no prohibited artifacts or private information;
- the exact-head quality suite passes after report generation.

A non-zero expected item-failure, warning, or review-required rate does not automatically determine the decision. The report must explain whether the observed rate is compatible with the next milestone and identify every remaining unknown.