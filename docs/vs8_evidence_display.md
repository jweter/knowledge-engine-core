# VS-8 Evidence Display

VS-8 creates the first human-readable evidence display workflow for manual
evidence records.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, database schema changes, parser changes, or
new imports.

## Why VS-8 Exists

VS-7 created the first manual evidence record as JSONL. That proved the project
can represent one source-linked evidence object, but the record was still
machine-oriented and difficult to review directly.

VS-8 adds a small CLI reader so humans can inspect manual evidence records
clearly before the project designs any larger Evidence Layer framework.

## Command Example

```text
ke evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
```

The command reads a JSONL file and displays each evidence record in a readable
format.

## Displayed Fields

For each evidence record, the command displays:

- Evidence record ID.
- Research question.
- Source title.
- DOI.
- Study type.
- Claim text.
- Evidence direction.
- Population.
- Intervention.
- Comparator.
- Outcome.
- Result summary.
- Limitations.
- Uncertainty notes.
- Confidence note.
- Source span.
- Provenance summary.
- Extraction method.

## Provenance Behavior

The display includes the record's source span and provenance fields directly
from JSONL. For the VS-7 record, this includes the local PDF path, source URL,
PDF URL, license type, license URL, metadata source, creation note, and manual
review context.

The CLI does not verify the evidence against the PDF. It displays the provenance
that was recorded during manual extraction.

## Manual Extraction Behavior

The command clearly labels manual extraction:

```text
Extraction method: manual_human_review (manual)
```

It also ends with:

```text
This is manually extracted evidence.
No scientific synthesis has been performed.
```

This prevents the display from being confused with automated extraction,
reasoning, or synthesis.

## Failure Behavior

The command fails clearly when:

- the JSONL file does not exist;
- a JSON line is invalid;
- a JSON line is not an object;
- the file contains no evidence records.

## Limitations

- The command is a prototype reader, not an evidence framework.
- It does not validate a universal evidence schema.
- It does not verify source spans against PDFs.
- It does not connect evidence records to search results.
- It does not aggregate evidence across papers.
- It does not score confidence.
- It does not distinguish support, contradiction, and qualification beyond
  displaying the recorded field.

## What This Proves

VS-8 proves that manual evidence records can move from JSONL into a readable
review surface while preserving provenance, limitations, uncertainty notes, and
the no-synthesis boundary.

It also proves that the Evidence Layer can start as simple, inspectable files
before requiring database tables or automation.

## What This Does Not Prove

VS-8 does not prove:

- automated extraction;
- scientific synthesis;
- evidence aggregation;
- confidence scoring;
- source-span validation;
- relationship modeling;
- database-backed evidence storage.

## Recommendation for VS-9

VS-9 should connect `ke answer` retrieval results to available manual evidence
records by DOI.

The goal should be to show, for each retrieved paper, whether the corpus already
has manual evidence records available. It should still avoid synthesis.

