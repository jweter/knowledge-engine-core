# VS-17 PR Readiness

VS-17 prepares the vertical slice branch for pull request review. It does not
add product features.

## Branch

```text
feature/phase-1-corpus-ingestion
```

## Capability Summary

The branch demonstrates a small GLP-1 vertical slice:

```text
scientific question
  -> SQLite FTS retrieval
  -> corpus metadata overlay
  -> validated manual evidence records
  -> DOI-matched evidence previews
  -> Markdown evidence report
```

The workflow remains retrieval and evidence display only. No synthesis,
consensus, AI, embeddings, automated extraction, confidence scoring, schema
changes, or parser changes are introduced as part of the evidence workflow.

## New CLI Commands and Options

- `ke answer QUESTION`
- `ke answer QUESTION --sources data/corpora/glp1_weight_loss/sources.csv`
- `ke answer QUESTION --sources ... --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl`
- `ke evidence data/corpora/glp1_weight_loss/evidence_records.jsonl`
- `ke evidence-validate data/corpora/glp1_weight_loss/evidence_records.jsonl`
- `ke evidence-report QUESTION --sources ... --evidence ... --output ... [--force]`

## Corpus and Evidence Files

GLP-1 corpus files:

- `data/corpora/glp1_weight_loss/README.md`
- `data/corpora/glp1_weight_loss/corpus.json`
- `data/corpora/glp1_weight_loss/scientific_question.md`
- `data/corpora/glp1_weight_loss/inclusion_criteria.md`
- `data/corpora/glp1_weight_loss/exclusion_criteria.md`
- `data/corpora/glp1_weight_loss/license_policy.md`
- `data/corpora/glp1_weight_loss/sources.csv`
- `data/corpora/glp1_weight_loss/evidence_records.jsonl`
- `papers/corpora/glp1_weight_loss/.gitkeep`

Local PDFs are required to run the demo but are ignored and must not be
committed.

## Test Status

Latest VS-17 validation:

```text
pytest: passing
ruff check .: passing
black --check .: passing
mypy knowledge_engine tests: passing
git diff --check: passing
```

## Known Limitations

- Parser-derived metadata remains weak without `--sources`.
- Retrieval snippets are noisy.
- Evidence records are manually authored draft records.
- Evidence source spans are recorded but not automatically verified against PDF
  coordinates or text.
- The Markdown report is dense and meant for review, not publication.
- The demo corpus contains three local papers, not a scientific corpus large
  enough to answer the research question.

## Remaining Risks

- Manual JSONL editing can still introduce semantic mistakes that structural
  validation cannot catch.
- The same primary trial evidence may appear directly and inside a
  meta-analysis, creating future double-counting risk once synthesis exists.
- CLI helper functions in `knowledge_engine/cli.py` are getting large and may
  deserve extraction during cleanup.
- Future contributors may confuse retrieval/evidence display with synthesis if
  docs are not kept explicit.

## Generated Artifacts Policy

Do not commit:

- `papers/**/*.pdf`
- `data/knowledge_engine.sqlite3`
- `data/corpora/**/reports/*.md`
- cache files

The generated report should remain a local ignored artifact unless a future
milestone creates a sanitized committed sample.

## Suggested PR Title

```text
Add GLP-1 vertical slice retrieval and manual evidence workflow
```

## Suggested PR Description

```text
## Summary

This PR adds a GLP-1 vertical slice demo for Knowledge Engine Core. It proves a
minimal path from scientific question to SQLite FTS retrieval, curated corpus
metadata, validated manual evidence records, DOI-matched evidence previews, and
a local Markdown evidence report.

The workflow remains retrieval and evidence display only. It does not add AI,
embeddings, automated extraction, synthesis, consensus, confidence scoring,
schema changes, parser changes, or database changes.

## Highlights

- Adds `ke answer` retrieval output for scientific questions.
- Adds corpus metadata overlays with `--sources`.
- Adds manual evidence display with `ke evidence`.
- Adds evidence JSONL validation with `ke evidence-validate`.
- Adds DOI-matched evidence previews with `--evidence`.
- Adds local Markdown evidence reports with `ke evidence-report`.
- Adds GLP-1 demo corpus metadata and draft manual evidence records.
- Documents the full vertical slice and demo checklist.

## Validation

- pytest
- ruff check .
- black --check .
- mypy knowledge_engine tests
- git diff --check
```

## Suggested Reviewer Checklist

- Confirm generated PDFs, SQLite database files, reports, and caches are not
  staged.
- Run `docs/glp1_vertical_slice_demo_checklist.md`.
- Confirm evidence records validate.
- Confirm `ke answer --sources --evidence` shows draft evidence status.
- Confirm generated report uses relative paths and no private absolute paths.
- Confirm no output claims synthesis, consensus, confidence scoring, or a final
  scientific answer.
- Review known limitations in `docs/vs16_end_to_end_demo_review.md`.

## Recommendation

The branch is ready to open a PR after final validation and a last staged-file
review. VS-17 should be the final vertical-slice milestone before PR review.
