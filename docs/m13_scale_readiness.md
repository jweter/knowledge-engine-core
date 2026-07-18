# M13 Scale-Readiness Decision

## Purpose

M13 converts the completed M12 100-paper rehearsal into a conservative, reproducible decision about the next controlled ingestion scale. It defines what the repository can claim from measured evidence, what remains unknown, and which observations would require architectural changes.

M13 is a decision and observability milestone. It is not a claim of production capacity and does not authorize unbounded scaling.

## Verified baseline

The M12 real rehearsal established one bounded observation on an ephemeral GitHub-hosted Ubuntu runner:

- measured corpus size: 100 legally usable local PDFs;
- manifest: 100 source rows, all valid and present;
- fresh outcomes: 100 imported, zero persisted issues;
- persisted papers after fresh import: 100;
- operator-recorded fresh elapsed time: 9 seconds;
- resume outcomes: 100 skipped with prior-item lineage;
- persisted papers after resume: 100;
- operator-recorded resume elapsed time: 1 second;
- real retryable failures: none;
- restricted artifacts committed: none.

This baseline does not prove linear throughput, sustained resource use, a maximum corpus size, concurrency safety, or production service capacity.

## Decision semantics

A scale-readiness assessment returns exactly one decision:

- `ready`: all required measurements are present and every threshold passes;
- `ready_with_conditions`: correctness and recovery pass, but one or more noncritical measurements are unknown or near their guardrail;
- `not_ready`: correctness, recovery, privacy, or a mandatory stop threshold fails.

Unknown values must remain `unknown`. They must never be converted to zero or inferred from unrelated measurements.

## Assessment dimensions

### Correctness

Required:

- declared source count equals persisted import-item count;
- imported, duplicate, skipped, failed, and review-required outcomes reconcile exactly;
- persisted issue totals reconcile with issue categories;
- no source row disappears from the run report.

Any reconciliation failure produces `not_ready`.

### Recovery and idempotency

Required:

- a linked resume or rerun completes;
- the repeated run creates zero unexpected paper records;
- every skipped resume item links to its prior item when the mode requires lineage.

Unexpected reimport or missing lineage produces `not_ready`.

### Performance

Measurements may include:

- wall-clock elapsed seconds;
- imported documents per second;
- resume documents per second;
- stage-level timings when available.

Performance thresholds are advisory until at least two controlled corpus sizes have been measured under documented environments. M12 alone cannot establish linear scaling.

### Storage

Measurements may include:

- database bytes before and after import;
- database byte growth;
- bytes per newly imported paper.

Storage readiness is `unknown` when database-size evidence was not retained. M13 must not estimate database growth from source PDF size or row counts.

### Reliability

Required observations:

- failed-item count and rate;
- persisted issue count and rate;
- parser and persistence failure categories when present;
- retry evidence when a real retryable failure occurs.

The absence of a real failure means retry behavior remains supported by deterministic tests, not real-run evidence.

### Privacy and artifact hygiene

Required:

- no source PDFs, SQLite databases, extracted full text, private absolute paths, or raw provider responses are committed;
- retained reports contain sanitized aggregate evidence only.

Any prohibited artifact or private-path leak produces `not_ready`.

## Proposed next controlled scale

The proposed next rehearsal size is **500 papers**, subject to the conditions below.

This is a bounded experimental step, not a five-times-capacity claim. It is large enough to expose database-growth, cumulative parser, and operational-observability behavior while remaining small enough for a controlled single-process rehearsal.

## 500-paper entry conditions

Before beginning the next rehearsal:

1. M13 assessment calculations and threshold tests pass.
2. The 500-row manifest is legally curated and validates with all files present.
3. The run records wall-clock duration and database bytes before and after import.
4. Environment identity is recorded without private paths.
5. The existing single-process SQLite path remains unchanged unless a measured blocker is found first.
6. Source files, database files, and extracted text remain ephemeral or local-only.

## Stop conditions

Stop the 500-paper rehearsal and retain sanitized failure evidence when any of the following occurs:

- manifest or item counts fail reconciliation;
- unexpected duplicate paper creation occurs during resume;
- database corruption or migration failure occurs;
- private paths or prohibited artifacts enter retained evidence;
- the process exceeds the operator-defined execution timeout;
- disk growth exceeds the available controlled workspace budget;
- repeated parser or persistence failures indicate a systemic rather than item-specific defect;
- recovery cannot continue from persisted run state.

## Architecture reconsideration triggers

The following observations justify a separate architectural review; they do not automatically authorize a redesign:

- SQLite write-lock contention under the intended execution model;
- database growth incompatible with the planned deployment budget;
- report queries becoming operationally unusable at the measured scale;
- inability to resume without long exclusive transactions;
- memory growth proportional to total corpus size rather than current item size;
- a verified need for parallel ingestion;
- repeated durability failures not attributable to the runner filesystem.

## Schema decision

M13 should prefer no schema migration for its initial vertical slice. A deterministic assessment can consume explicit measurements supplied from a sanitized rehearsal record plus persisted run-report counts.

Persisting telemetry becomes justified only when repeated operational use requires cross-run queries, trend analysis, or automated thresholds that cannot be reproduced from retained sanitized measurements.

## Evidence rules

Every assessment must distinguish:

- persisted repository/database facts;
- operator-recorded measurements;
- derived calculations;
- unknown values;
- policy thresholds.

Derived values must state their source measurements. Missing denominators produce `unknown`, not division by zero or an inferred result.

## Initial implementation sequence

1. Add immutable assessment input and result types.
2. Add exact reconciliation and derived-rate calculations.
3. Add threshold evaluation with explicit unknown handling.
4. Add deterministic Markdown rendering with source labels.
5. Add synthetic boundary tests and privacy tests.
6. Decide whether a CLI boundary is needed after the pure model is stable.
7. Complete full architecture, security, privacy, dependency, and diff review.
8. Pass Quality on the exact final head before readiness and merge.
