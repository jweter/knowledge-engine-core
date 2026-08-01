# M13 Scale-Readiness Decision

## Decision

The current offline, single-process SQLite ingestion architecture is ready with conditions for a controlled 500-paper rehearsal.

This decision is bounded. It does not claim production capacity, linear scaling, concurrent safety, or a maximum supported corpus size.

## Evidence

The M12 baseline established 100 accepted PMC Open Access PDFs, 100 successful fresh imports, 100 paper records, zero persisted issues, and an idempotent linked resume with 100 skipped items and zero new papers. Fresh elapsed time was operator-recorded as 9 seconds and resume elapsed time as 1 second.

Storage growth was not measured, so storage readiness remains unknown rather than inferred.

## Entry conditions

- exactly 500 accepted local source documents;
- offline and single-process execution;
- no automatic document acquisition;
- database size recorded before and after the run;
- environment identity recorded without private paths;
- no committed PDFs, databases, extracted text, private paths, or raw telemetry.

## Acceptance thresholds

- exact source, item, outcome, and paper reconciliation;
- resume creates zero additional papers;
- failure rate no higher than 1 percent;
- persisted issue rate no higher than 2 percent;
- no prohibited artifacts or private-path leakage;
- database growth is non-negative and explainable.

## Stop conditions

Stop immediately for reconciliation failure, non-idempotent resume, storage corruption, prohibited artifacts, privacy leakage, or evidence that retry behavior cannot be explained.

## Architecture decision

No CLI or schema migration is justified for M13. The pure assessment model and deterministic Markdown renderer are sufficient. Persisted telemetry should be added only after stable query, retention, and recovery requirements are defined.

## Priority technical debt

1. Measure database growth and bytes per imported paper.
2. Record stage timing with stable semantics.
3. Record privacy-safe environment provenance.
4. Capture retry and recovery evidence from a real failure.
5. Improve parser and persistence reason-code granularity.
