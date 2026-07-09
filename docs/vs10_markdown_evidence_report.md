# VS-10 Markdown Evidence Report

VS-10 creates the first Markdown evidence report workflow for the GLP-1
vertical slice.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, confidence scoring,
parser changes, database schema changes, or new paper imports.

## Why VS-10 Exists

VS-9 connected retrieval results to available manual evidence records in the
terminal. That made evidence availability visible, but the output was still
ephemeral.

VS-10 creates a durable human-review artifact: a Markdown report that combines
the research question, retrieval results, curated source metadata, matched
manual evidence records, provenance, limitations, uncertainty, and explicit
no-synthesis disclaimers.

## How It Builds on VS-9

VS-9 answered this question:

> Does this retrieved paper have reviewed manual evidence available?

VS-10 preserves that same boundary and adds a report surface. It reuses the same
retrieval, corpus metadata overlay, evidence loading, and DOI matching behavior.

## Command Example

```text
ke evidence-report "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl --output data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md
```

If `--output` is omitted, the Markdown report is printed to the terminal.

If `--output` is provided, parent directories are created as needed. Existing
files are not overwritten unless `--force` is provided.

## Report Structure

The report includes:

- Title.
- Generation date and time.
- Research question.
- Corpus source file path.
- Evidence file path.
- Scope statement.
- Retrieval-only and no-synthesis disclaimers.
- Retrieved papers.
- Curated metadata when available.
- Retrieval snippets.
- Citations.
- Reviewed evidence status.
- Manual evidence previews for matched records.
- Final disclaimer.

## Provenance Behavior

The report includes source URLs, license types, metadata source labels, source
spans, and provenance summaries when available.

The report does not verify source spans against PDFs. It records and displays
the provenance supplied by manual review.

## Manual Evidence Behavior

Manual evidence records are matched to retrieved papers by normalized DOI.

For each matched evidence record, the report includes:

- Evidence record ID.
- Extraction method.
- Evidence direction.
- Claim text.
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

Papers without matching manual evidence are labeled:

```text
Reviewed evidence: not available
```

## Output Handling

The command supports two modes:

- Terminal mode: print Markdown when no `--output` path is provided.
- File mode: write Markdown to `--output`.

File mode creates parent directories. It refuses to overwrite existing files
unless `--force` is provided.

## Limitations

- The report is a review artifact, not a scientific conclusion.
- Retrieval quality depends on the current SQLite FTS index.
- DOI matching only works when retrieved papers and evidence records both have
  usable DOIs.
- Manual evidence records are displayed, not independently validated.
- The report does not aggregate evidence across papers.
- The report does not calculate consensus.
- The report does not calculate confidence scores.
- The report does not detect contradictions.
- The report does not change search ranking.

## What This Proves

VS-10 proves that Knowledge Engine Core can produce a durable, human-readable
artifact that connects:

```text
Scientific question
  -> retrieval
  -> curated source metadata
  -> matched manual evidence
  -> provenance-aware Markdown report
```

This is an important bridge between CLI retrieval and future review workflows.

## What This Does Not Prove

VS-10 does not prove:

- scientific synthesis;
- automated evidence extraction;
- consensus modeling;
- contradiction detection;
- evidence scoring;
- report publishing;
- peer review workflow;
- corpus-scale reporting.

## Recommendation for VS-11

VS-11 should add a second manual evidence record from one of the other retrieved
papers, then use the evidence report to compare how multiple evidence records
appear together without synthesis.
