# GLP-1 Weight Loss Prototype Corpus

This directory defines the VS-0 prototype corpus for the Knowledge Engine
vertical slice.

The corpus is intentionally small. Its purpose is to prove that one scientific
question can travel through the Knowledge Engine architecture from source
documents to claims, evidence records, relationships, retrieval, synthesis, and
source citations.

No papers have been imported yet. No PDFs should be committed to the repository.

## Scientific Question

Do GLP-1 receptor agonists reduce body weight in adults with overweight or
obesity?

## Corpus Scope

The prototype corpus should contain approximately 10 legally usable scientific
papers about GLP-1 receptor agonists and body weight outcomes in adults with
overweight or obesity.

The first source set should prefer:

- Randomized controlled trials.
- Systematic reviews or meta-analyses.
- Papers with clear body weight, BMI, or percent weight change outcomes.
- Papers with accessible abstracts, methods, and results sections.
- Sources with clear licensing or usage notes.

## Files

- `corpus.json`: machine-readable corpus definition.
- `scientific_question.md`: human-readable question definition and rationale.
- `sources.csv`: source list template for approximately 10 papers.
- `inclusion_criteria.md`: criteria for adding papers.
- `exclusion_criteria.md`: criteria for excluding papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.

## Source List Fields

`sources.csv` records source metadata, local file references, inclusion status,
and legal provenance. The VS-3 fields `pdf_url`, `license_type`, and
`license_url` identify the exact publisher PDF and license evidence used for a
local import.

## Local PDF Location

When VS-1 or later milestones begin, local PDFs should be placed under:

```text
papers/corpora/glp1_weight_loss/
```

PDF files are ignored by Git. The source list should record enough provenance to
reconstruct the corpus without committing copyrighted documents.

## Current Status

VS-0 only. The corpus has been defined, but no papers have been imported,
parsed, enriched, or converted into evidence records.
