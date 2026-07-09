# VS-12 Evidence Review Status

VS-12 adds minimal review status fields to manual evidence records and displays
that review state anywhere evidence appears.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, numeric confidence
scoring, parser changes, database schema changes, new imports, or new PDF
downloads.

## Why VS-12 Exists

VS-7 and VS-11 created manual evidence records. Before VS-12, those records
could be displayed, but a reader could not immediately tell whether a record was
newly drafted, independently reviewed, in need of revision, or rejected.

That ambiguity is risky for scientific trust. Review state must be visible
before the project accumulates many manual records.

## Extraction Status vs Review Status

`extraction_status` describes how complete the evidence extraction itself is.
For example, the current records are draft prototype extractions.

`review_status` describes the human review state of the evidence record after
extraction. It is separate from the scientific conclusion and does not imply
that evidence has been synthesized.

## Allowed Review Statuses

The initial status vocabulary is intentionally small:

- `draft`: manually created and not independently reviewed.
- `reviewed`: reviewed and accepted for use as a reviewed evidence record.
- `needs_revision`: reviewed but requiring correction or clarification.
- `rejected`: reviewed and not accepted as a valid evidence record.

Missing historical statuses display as `unspecified` for backward
compatibility.

## Review Checklist Fields

Each current evidence record now includes:

- `source_verified`
- `doi_verified`
- `manual_extraction_labeled`
- `source_span_present`
- `limitations_recorded`
- `uncertainty_recorded`
- `no_synthesis_language`
- `ready_for_secondary_review`

The checklist uses booleans. It is not a score and should not be interpreted as
scientific confidence.

## Why Current Records Remain Draft

Both existing records remain:

```text
review_status: draft
```

They are prototype manual extractions. They have not received independent
secondary review and should not be treated as finalized reviewed evidence.

## CLI Behavior

`ke evidence` displays review status, checklist summary, and review notes for
each record.

`ke answer --evidence` displays the same review status information inside each
compact evidence preview under a retrieved paper.

Records without review fields display:

```text
Review status: unspecified
Review checklist: not recorded
```

## Markdown Report Behavior

`ke evidence-report` includes review status, checklist summary, and review notes
inside each manual evidence record section.

The report remains a retrieval-plus-evidence display artifact. It does not
synthesize evidence or convert draft status into a scientific conclusion.

## Limitations

- Review fields are plain JSONL fields, not a full review workflow.
- The checklist is not enforced by a validator yet.
- There is no reviewer identity, timestamp, or approval history.
- There is no command for changing status.
- The CLI displays review state but does not decide whether a record should be
  trusted.
- Draft records can still be displayed, so readers must attend to the status.

## What This Proves

VS-12 proves that manual evidence records can carry explicit review state and
that the review state can remain visible across evidence display, retrieval
preview, and Markdown reporting.

This supports scientific trust without introducing synthesis.

## What This Does Not Prove

VS-12 does not prove:

- independent scientific review;
- review assignment or approval workflows;
- automated validation;
- scientific synthesis;
- consensus calculation;
- confidence scoring;
- contradiction detection.

## Recommendation for VS-13

VS-13 should add one command to validate `evidence_records.jsonl` explicitly,
checking JSONL validity, required fields, duplicate evidence IDs, DOI presence,
allowed review statuses, and checklist shape.
