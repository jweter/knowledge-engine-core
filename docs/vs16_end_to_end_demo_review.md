# VS-16 End-to-End Demo Review

VS-16 reviews the GLP-1 vertical slice as a complete demo workflow. It does not
add features, import papers, download PDFs, modify schemas, change parser
behavior, add AI, add embeddings, or perform synthesis.

## Purpose

The goal of this review is to decide whether the vertical slice is ready for
cleanup and pull request preparation.

The reviewed research question was:

```text
Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?
```

## Commands Run

Repository and local artifact checks:

```text
git status --short --branch --untracked-files=all --ignored
git log --oneline --decorate -5
Get-Item data/knowledge_engine.sqlite3 papers/corpora/glp1_weight_loss/*.pdf
git check-ignore data/knowledge_engine.sqlite3 papers/corpora/glp1_weight_loss/*.pdf data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md
```

Demo workflow:

```text
python -m knowledge_engine.cli stats
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?"
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
python -m knowledge_engine.cli evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
python -m knowledge_engine.cli evidence-validate data/corpora/glp1_weight_loss/evidence_records.jsonl
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
python -m knowledge_engine.cli evidence-report "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl --output data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md --force
```

Quality checks:

```text
pytest
ruff check .
black --check .
mypy knowledge_engine tests
git diff --check
```

## Observed Results

Git state:

- Current branch: `feature/phase-1-corpus-ingestion`.
- Current head before VS-16 documentation: `c309946`.
- The tracked working tree was clean before this review documentation was
  created.
- Local PDFs, the SQLite database, generated reports, and cache files were
  ignored.

Local demo artifacts:

- `data/knowledge_engine.sqlite3` exists locally and is ignored.
- Three GLP-1 PDFs exist locally under `papers/corpora/glp1_weight_loss/` and
  are ignored.
- The generated Markdown report exists locally under
  `data/corpora/glp1_weight_loss/reports/` and is ignored.

`ke stats`:

- Papers: 3.
- Authors: 2.
- Keywords: 6.
- Words: 30,854.

`ke answer` without sources:

- Retrieved all three local GLP-1 papers.
- Preserved the retrieval-only no-synthesis disclaimer.
- Exposed parser/database metadata limitations:
  - Gao et al. displayed as `fphar-2022-935823 1..14`.
  - Publication years were unknown.

`ke answer --sources`:

- Retrieved all three local GLP-1 papers.
- Displayed curated titles, authors, journals, years, source URLs, license
  types, and citations.
- Clearly labeled metadata as coming from `corpus sources.csv`.
- Preserved the retrieval-only no-synthesis disclaimer.

`ke evidence`:

- Displayed two manual evidence records.
- Showed both records as `draft`.
- Displayed the evidence review status summary:
  - Evidence records: 2.
  - Draft: 2.
  - Reviewed: 0.
  - Needs revision: 0.
  - Rejected: 0.
  - Unspecified: 0.
  - Evidence readiness: draft only; secondary review needed.
- Preserved manual extraction, provenance, limitations, uncertainty notes, and
  no-synthesis language.

`ke evidence-validate`:

- Passed validation.
- Reported 2 records, both draft.
- Reused the evidence status summary.

`ke answer --sources --evidence`:

- Retrieved all three papers.
- Matched manual evidence for Gao et al. and STEP 5 by DOI.
- Correctly showed `Reviewed evidence: not available` for SELECT.
- Displayed draft review status and secondary review need before evidence
  previews.
- Preserved the retrieval-only no-synthesis disclaimer.

`ke evidence-report`:

- Generated a local ignored Markdown report.
- Included the research question, input file paths, scope statement, evidence
  review status summary, retrieved papers, curated metadata, manual evidence
  records, provenance, limitations, uncertainty notes, and final no-synthesis
  disclaimer.
- Used relative local paths rather than private absolute machine paths.

## Demo Readiness Assessment

The vertical slice works end to end for the current GLP-1 demo corpus.

The strongest successful path is:

```text
Question
  -> SQLite retrieval
  -> sources.csv metadata overlay
  -> evidence_records.jsonl validation
  -> DOI-matched manual evidence
  -> Markdown report
  -> explicit no-synthesis boundary
```

This is ready for cleanup and PR preparation, with a few known demo-quality gaps
documented below.

## Output Quality Notes

What works well:

- The CLI commands are understandable in sequence.
- The metadata overlay makes the demo much more readable.
- Evidence records clearly show manual extraction, source span, provenance,
  limitations, uncertainty, and review status.
- The status summary makes draft evidence visible at a glance.
- The Markdown report is a useful durable review artifact.
- Generated reports, PDFs, and SQLite files remain outside Git.

What feels fragile:

- Raw `ke answer` without `--sources` exposes weak parser metadata.
- Retrieval snippets are noisy and sometimes show awkward PDF extraction gaps.
- `ke stats` reports only two authors despite three papers, suggesting author
  extraction remains weak in the local database.
- Evidence records are still manually authored JSONL, so editing mistakes are
  possible despite validation.
- The report is useful, but dense; future cleanup may need formatting polish.

## Scientific Trust Boundary Assessment

The trust boundaries are clear enough for a prototype:

- Retrieval is explicitly labeled as retrieval.
- Evidence is explicitly labeled as manual.
- Evidence records are marked as draft.
- The status summary says secondary review is needed.
- Confidence notes avoid scientific confidence scoring.
- The output repeatedly states that no scientific synthesis has been performed.
- SELECT remains clearly marked as having no reviewed evidence available.

The system does not claim that the research question has been answered.

## Remaining Gaps

Before PR preparation:

- Add a short demo script or checklist so reviewers can reproduce the workflow
  without reconstructing command order from milestone docs.
- Consider documenting that `--sources` is expected for the current demo because
  parser metadata is incomplete.
- Consider whether the generated report should remain ignored only, or whether a
  sanitized sample report should be committed later.
- Review README or docs entry points so contributors know where the vertical
  slice docs live.
- Consider whether evidence validation helpers should eventually move out of
  `cli.py` during cleanup.

Not required before PR preparation:

- More papers.
- More evidence records.
- Automated extraction.
- Synthesis.
- Consensus modeling.
- Confidence scoring.
- Schema changes.

## Recommended Cleanup Before PR

- Run a code organization pass focused only on readability and module size.
- Ensure the README references the vertical slice demo.
- Add a reproducible demo command checklist.
- Confirm no generated report, PDF, SQLite database, or cache file can be
  staged accidentally.
- Re-run the full validation gate after cleanup.

## VS-17 Recommendation

VS-17 should proceed as cleanup and PR preparation, not as a feature milestone.

Recommended VS-17 scope:

- polish documentation entry points;
- create a repeatable demo checklist;
- review CLI helper organization;
- run the full test and lint gate;
- prepare the feature branch for pull request review.

Do not add new scientific capabilities in VS-17.
