# Corpus Import Run Report

This example is synthetic and demonstrates report structure only. It is not evidence that the real M12 rehearsal occurred.

## Run identity

- Import run ID: `00000000-0000-0000-0000-000000000100`
- Run mode: `fresh`
- Parent import run ID: `none`
- Run status: `partially_succeeded`
- Review status: `needs_review`
- Validation mode: `check_files`
- Created at: `2026-07-18T00:00:00Z`
- Completed at: `2026-07-18T00:05:00Z`

## Corpus and manifest

- Corpus ID: `m12_synthetic_example`
- Corpus name: M12 Synthetic Example
- Manifest version: `1`
- Manifest validity: `valid`
- Import readiness: `ready`
- Manifest snapshot ID: `00000000-0000-0000-0000-000000000200`
- Combined manifest SHA-256: `cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc`
- Corpus path: `data/corpora/m12_synthetic_example/corpus.json`
- Source manifest path: `data/corpora/m12_synthetic_example/sources.csv`

## Reconciled outcomes

- Declared source rows: 100
- Persisted import items: 100
- Valid source rows: 100
- Matched paper records: 90
- Matched prior import items: 10
- Retry-linked items: 5

### Item statuses

- `duplicate`: 10
- `failed`: 5
- `imported`: 80
- `needs_review`: 2
- `skipped`: 3

### Duplicate outcomes

- `same_paper_same_file`: 10

## Persisted issues

- Warning issues: 3
- Manifest-blocking issues: 0
- Import-blocking issues: 2

### Issue codes

- `duplicate_candidate`: 1
- `legal_status_not_approved`: 1
- `missing_doi`: 1
- `parser_warning`: 1
- `unreadable_pdf`: 1

### Issue severities

- `error`: 2
- `warning`: 3

### Issue categories

- `duplicate`: 1
- `legal`: 1
- `metadata`: 1
- `parser`: 2

## Item lineage

- source=`source-001`; status=`imported`; duplicate=`none`; paper_id=`1`; matched_item=`none`; retry_of=`none`
- source=`source-081`; status=`duplicate`; duplicate=`same_paper_same_file`; paper_id=`1`; matched_item=`prior-81`; retry_of=`none`
- source=`source-091`; status=`failed`; duplicate=`none`; paper_id=`none`; matched_item=`none`; retry_of=`failed-prior-91`

The actual generated report contains one sanitized lineage line per persisted import item.

## Measurement boundaries

- Counts in this report are derived from persisted import-run, item, issue, and manifest-snapshot state.
- The current schema does not store high-resolution stage timing, CPU, memory, or disk telemetry.
- Wall-clock duration and environment measurements must be recorded separately by the rehearsal operator.
- M11 external metadata candidates and metadata-conflict counts are not persisted in the current schema.
- This report does not contain extracted full text and does not provide scientific validation or synthesis.
