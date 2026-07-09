# VS-9 Answer With Manual Evidence Preview

VS-9 connects retrieval results from `ke answer` to available manual evidence
records by DOI.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, parser changes, database schema changes, or
new paper imports.

## Why VS-9 Exists

VS-8 made manual evidence records readable through `ke evidence`, but that
workflow was separate from retrieval. A reviewer could inspect evidence records,
but `ke answer` could not yet show whether a retrieved paper had already been
reviewed.

VS-9 closes that gap with the smallest useful connection: retrieved papers can
display a compact preview of matching manual evidence records.

## Problem Solved After VS-8

After VS-8, the project had two separate surfaces:

- `ke answer` retrieved relevant papers.
- `ke evidence` displayed manual evidence records.

VS-9 lets a single retrieval result show whether reviewed evidence is available
for that paper. This makes the vertical slice easier to audit without treating
retrieval as reasoning.

## Command Example

```text
ke answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
```

The command still performs normal SQLite FTS retrieval. The `--sources` option
adds display-time corpus metadata. The `--evidence` option adds display-time
manual evidence previews.

## Evidence Matching

Evidence records are matched to retrieved papers by DOI.

The matching behavior:

- reads manual evidence records from JSONL;
- uses each evidence record's `source_doi` field;
- normalizes DOI strings by lowercasing and removing common DOI prefixes;
- compares normalized evidence DOIs to normalized retrieved-paper DOIs;
- displays matching evidence under the retrieved paper.

Records without a DOI are ignored safely because they cannot be linked to a
retrieved paper in this prototype.

## Displayed Evidence Fields

For each matched record, `ke answer --evidence` displays:

- Evidence record ID.
- Extraction method.
- Evidence direction.
- Claim text.
- Outcome.
- Result summary.
- Limitations.
- Uncertainty notes.
- Confidence note.
- Source span.

If no manual evidence matches a retrieved paper, the command displays:

```text
Reviewed evidence: not available
```

If evidence is available, the command displays:

```text
Reviewed evidence: available
Extraction method: manual
```

## Manual Extraction Behavior

The preview labels evidence as manual. It does not imply that the system
extracted, interpreted, or validated the evidence automatically.

The command continues to end with:

```text
This is retrieval only.
No scientific synthesis has been performed.
```

## Provenance Behavior

The preview includes the evidence record's source span. More complete
provenance remains available through `ke evidence`, which displays the full
record.

VS-9 does not verify source spans against PDFs. It displays the provenance
recorded during manual review.

## Error Handling

The command fails clearly when the evidence JSONL file:

- does not exist;
- contains invalid JSON;
- contains non-object JSON records;
- contains no evidence records.

## Limitations

- DOI matching only works when both the retrieved paper and evidence record have
  usable DOIs.
- Evidence previews are compact and do not replace full evidence review.
- The command does not validate an evidence schema.
- The command does not verify source spans against local PDFs.
- The command does not aggregate evidence across papers.
- The command does not classify consensus or contradiction across the corpus.
- The command does not change ranking based on evidence availability.

## What This Proves

VS-9 proves that the retrieval layer can surface manually reviewed evidence
without turning that evidence into synthesis.

It also proves an important architectural boundary: evidence can be connected to
retrieval results as a separate layer, using source identity and provenance,
without rewriting the parser, database schema, or search index.

## What This Does Not Prove

VS-9 does not prove:

- automated evidence extraction;
- scientific synthesis;
- evidence quality scoring;
- contradiction detection;
- consensus modeling;
- report generation;
- graph relationships;
- corpus-scale ingestion.

## Recommendation for VS-10

VS-10 should create a simple Markdown evidence report for the research question
using retrieval results plus matched manual evidence records.

The report should remain retrieval-and-evidence-display only. It should not
claim scientific synthesis yet.
