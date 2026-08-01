# VS-13 Evidence Validation

VS-13 adds a focused evidence-record validation command for manual JSONL
evidence files.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, numeric confidence
scoring, parser changes, database schema changes, new imports, or PDF downloads.

## Why VS-13 Exists

Manual evidence records now carry claims, provenance, limitations, uncertainty
notes, and review status. As the file grows, small structural mistakes could
quietly damage trust in the vertical slice.

VS-13 adds explicit validation so common evidence-file problems are caught
before records are displayed or used in reports.

## Command Example

```text
ke evidence-validate data/corpora/glp1_weight_loss/evidence_records.jsonl
```

## Successful Output Example

```text
Evidence validation passed.
Records: 2
Draft: 2
Reviewed: 0
Needs revision: 0
Rejected: 0
```

## Validation Checks

The command checks that:

- the file exists;
- the file is not empty;
- every nonblank line is valid JSON;
- every record is a JSON object;
- required core fields are present;
- `evidence_record_id` exists;
- `evidence_record_id` values are unique;
- `source_doi` exists;
- `source_title` exists;
- `research_question` exists;
- `claim_text` exists;
- `evidence_direction` exists;
- `result_summary` exists;
- `provenance` is a non-empty object;
- `extraction_method` exists;
- `review_status` exists;
- `review_status` uses an allowed value;
- `review_checklist`, when present, is an object;
- `review_notes`, when present, is a string.

## Required Fields

Required core fields:

- `schema_version`
- `evidence_record_id`
- `extraction_method`
- `extraction_status`
- `source_doi`
- `source_title`
- `source_type`
- `study_type`
- `research_question`
- `claim_text`
- `evidence_direction`
- `population`
- `intervention`
- `comparator`
- `outcome`
- `result_summary`
- `source_span`
- `limitations`
- `uncertainty_notes`
- `confidence_note`
- `provenance`
- `created_for_milestone`

Required review fields:

- `review_status`
- `review_checklist`
- `review_notes`

## Allowed Review Statuses

- `draft`
- `reviewed`
- `needs_revision`
- `rejected`

## Failure Behavior

Invalid files produce a clear validation-failed report and a nonzero exit
status. The command does not print raw Python tracebacks for normal validation
failures.

Examples of failures include invalid JSON, duplicate evidence IDs, missing DOI
values, invalid review statuses, malformed review checklists, and empty files.

## What Validation Does Not Prove

Validation does not prove that an evidence record is scientifically correct.
It does not verify PDF source spans, assess study quality, calculate confidence,
detect contradictions, or synthesize across records.

It only checks that the manual evidence file is structurally safe enough for
the current vertical slice.

## Limitations

- Validation is intentionally small and local to the CLI.
- It is not a full schema framework.
- It does not enforce every field's detailed value type.
- It does not validate DOI syntax beyond presence.
- It does not check whether source spans exist in local PDFs.
- Display commands do not yet call the validator automatically.

## What This Proves

VS-13 proves that Knowledge Engine Core can protect the manual evidence workflow
with explicit structural validation before adding more records.

## What This Does Not Prove

VS-13 does not prove:

- automated extraction;
- scientific synthesis;
- consensus modeling;
- confidence scoring;
- evidence review approval;
- source-span verification.

## Recommendation for VS-14

VS-14 should use the evidence validator inside the evidence display and report
commands so invalid evidence files fail consistently before display.
