# GLP-1 Vertical Slice Demo Checklist

This checklist runs the current GLP-1 retrieval and manual evidence-display
demo. It is a local demo workflow, not a scientific synthesis workflow.

## Prerequisites

- Python 3.12 or newer.
- Project dependencies installed.
- Three legally usable local PDFs available under:

```text
papers/corpora/glp1_weight_loss/
```

- Corpus metadata available at:

```text
data/corpora/glp1_weight_loss/sources.csv
```

- Manual evidence records available at:

```text
data/corpora/glp1_weight_loss/evidence_records.jsonl
```

## Expected Ignored Local Files

These files are local artifacts and should not be committed:

```text
papers/corpora/glp1_weight_loss/*.pdf
data/knowledge_engine.sqlite3
data/corpora/glp1_weight_loss/reports/*.md
```

Verify ignore behavior:

```text
git check-ignore data/knowledge_engine.sqlite3
git check-ignore papers/corpora/glp1_weight_loss/*.pdf
git check-ignore data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md
```

## Initialize the Database

```text
python -m knowledge_engine.cli init
```

## Import the Three Local PDFs

Run these only when rebuilding the local demo database:

```text
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf --keyword glp1 --keyword obesity
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/s41591-022-02026-4.pdf --keyword glp1 --keyword obesity
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/s41591-024-02996-7.pdf --keyword glp1 --keyword obesity
```

## Run Stats

```text
python -m knowledge_engine.cli stats
```

Expected characteristics:

- The demo database should contain three papers.
- Word counts may vary if PDFs are re-imported from different source files.

## Run Retrieval Only

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?"
```

Expected characteristics:

- Returns matching papers from SQLite FTS.
- Ends with the retrieval-only no-synthesis disclaimer.
- Parser-derived metadata may be incomplete.

## Run Retrieval With Corpus Metadata

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
```

Expected characteristics:

- Displays curated title, authors, year, journal, source URL, and license type.
- Labels metadata as coming from `corpus sources.csv`.
- Still performs retrieval only.

## Display Manual Evidence

```text
python -m knowledge_engine.cli evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
```

Expected characteristics:

- Shows two draft manual evidence records.
- Shows evidence review status summary.
- Shows manual extraction, source spans, provenance, limitations, and uncertainty.
- Ends with the no-synthesis disclaimer.

## Validate Evidence Records

```text
python -m knowledge_engine.cli evidence-validate data/corpora/glp1_weight_loss/evidence_records.jsonl
```

Expected characteristics:

- Validation passes.
- Reports two draft evidence records.
- Reports that secondary review is needed.

## Run Retrieval With Metadata and Evidence

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
```

Expected characteristics:

- Shows evidence available for Gao et al. and STEP 5.
- Shows evidence not available for SELECT.
- Shows draft review status and secondary review need.
- Ends with the retrieval-only no-synthesis disclaimer.

## Generate the Markdown Evidence Report

```text
python -m knowledge_engine.cli evidence-report "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl --output data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md --force
```

Expected characteristics:

- Creates a local ignored Markdown report.
- Includes the research question, metadata, evidence records, review status,
  limitations, uncertainty, provenance, and no-synthesis disclaimers.
- Uses relative paths.

## Do Not Commit

Do not commit:

- local PDFs;
- SQLite databases;
- generated reports;
- cache files.

## Known Demo Limitations

- This is retrieval plus manual evidence display, not synthesis.
- Evidence records are draft and need secondary review.
- Parser-derived metadata is weak without `--sources`.
- Snippets can be noisy because they come from raw PDF extraction and FTS
  matching.
- The report is intentionally dense because it preserves provenance and
  limitations.
