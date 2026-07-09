# VS-14 Shared Evidence Validation

VS-14 integrates the evidence validator into every CLI command that reads
manual evidence records.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, numeric confidence
scoring, parser changes, database schema changes, new imports, or PDF downloads.

## Why VS-14 Exists

VS-13 added `ke evidence-validate`, but validation only protects the workflow if
evidence-consuming commands use the same checks.

VS-14 centralizes evidence loading so malformed JSONL files are rejected before
records are displayed, attached to retrieval results, or written into Markdown
reports.

## Commands Using Shared Validation

The shared validation path is now used by:

- `ke evidence`
- `ke answer --evidence`
- `ke evidence-report`
- `ke evidence-validate`

## Validation Failures

Normal validation failures produce user-facing messages instead of raw Python
tracebacks.

Example:

```text
Evidence validation failed.
Line 2: missing required field(s): source_doi.
```

Other failures include invalid JSONL, empty files, non-object records, duplicate
evidence IDs, missing DOI values, invalid review statuses, and malformed review
checklists.

## Scientific Trust Impact

The display and report commands no longer silently accept malformed evidence
files. This makes manual evidence safer to inspect because contributors see
structural problems before evidence appears in user-facing output.

This is still structural validation only. It does not validate scientific
truth, source-span accuracy, study quality, or evidence interpretation.

## Review Status Compatibility

Display commands preserve the VS-12 compatibility behavior for older otherwise
valid records:

```text
Review status: unspecified
```

That compatibility applies only to display/report commands. The standalone
`ke evidence-validate` command continues to enforce the current standard and
requires `review_status`, `review_checklist`, and `review_notes`.

This split keeps old structurally safe records readable while keeping the
official validator strict for current project files.

## What This Proves

VS-14 proves that evidence validation can become part of the normal display and
report workflow without changing the database, parser, or scientific boundary.

## What This Does Not Prove

VS-14 does not prove:

- scientific synthesis;
- source-span verification;
- automated evidence extraction;
- consensus calculation;
- confidence scoring;
- peer review approval.

## Limitations

- Validation is still implemented inside the CLI module.
- The validator is structural, not semantic.
- Display commands use compatibility mode for missing review fields.
- There is no automatic repair for invalid records.
- There is no detailed schema version migration path yet.

## Recommendation for VS-15

VS-15 should add a small evidence status summary to CLI and/or Markdown report
output, showing counts of draft, reviewed, needs revision, and rejected evidence
records for the current evidence file.
