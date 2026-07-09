# VS-15 Evidence Status Summary

VS-15 adds a small evidence review status summary to CLI and Markdown report
output.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, numeric confidence
scoring, parser changes, database schema changes, new imports, or PDF downloads.

## Why VS-15 Exists

VS-12 added review status fields. VS-13 added explicit evidence validation.
VS-14 made evidence-consuming commands use shared validation before display or
report generation.

VS-15 makes the validated evidence file's review state visible at a glance so
draft records are not mistaken for reviewed evidence.

## Status Categories

The summary reports:

- total evidence records;
- draft records;
- reviewed records;
- records needing revision;
- rejected records;
- unspecified records.

`unspecified` exists for backward-compatible display of older otherwise-valid
records. The strict validator still requires current records to include review
fields.

## Readiness Notes

The readiness note is intentionally simple:

- All records draft: `draft only; secondary review needed.`
- Any record needs revision: `revision needed before use.`
- Any record rejected: `contains rejected records; review before reporting.`
- All records reviewed: `reviewed evidence available.`
- Otherwise: `mixed review status.`

This is a review-workflow note, not a scientific confidence score.

## Where Summaries Appear

The summary appears in:

- `ke evidence`, before listing individual records;
- `ke answer --evidence`, before retrieval results;
- `ke evidence-report`, as a Markdown section titled
  `Evidence Review Status Summary`;
- `ke evidence-validate`, reusing the shared summary helper.

The summary does not replace per-record review status.

## Why This Is Not Synthesis

The summary counts review states. It does not compare findings, combine results,
resolve contradictions, calculate consensus, or answer the scientific question.

The summary is about evidence-record readiness, not whether GLP-1 receptor
agonists reduce body weight.

## Why This Is Not Confidence Scoring

The readiness note is not a numeric or scientific confidence score. A reviewed
record may still contain limitations, uncertainty, or evidence that only applies
to a narrow population.

## Limitations

- The summary only reflects records present in the evidence JSONL file.
- It does not inspect local PDFs.
- It does not verify source spans.
- It does not know whether review was performed by an independent reviewer.
- It does not rank evidence quality.
- It does not distinguish trial-level and review-level evidence quality.

## What This Proves

VS-15 proves that the review state of a manual evidence file can be made visible
across CLI display, retrieval preview, validation, and Markdown reporting.

This supports safer human review without adding synthesis.

## What This Does Not Prove

VS-15 does not prove:

- scientific synthesis;
- scientific consensus;
- confidence scoring;
- peer review approval;
- source-span verification;
- automated evidence extraction.

## Recommendation for VS-16

VS-16 should be a full end-to-end vertical slice demo review rather than a new
feature. It should run the complete workflow from question to report, inspect
output quality, document remaining gaps, and decide whether the vertical slice is
ready for cleanup and PR preparation.
