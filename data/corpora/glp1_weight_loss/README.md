# GLP-1 Weight Loss Prototype Corpus

This directory defines the GLP-1 demonstration corpus for Knowledge Engine
Core.

The corpus is intentionally small. It is used to exercise corpus metadata,
legal provenance, retrieval, manual evidence display, and manifest validation.
It does not represent a complete scientific corpus and does not provide a
scientific conclusion.

## Scientific Question

Do GLP-1 receptor agonists reduce body weight in adults with overweight or
obesity?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: version 1 source manifest with curated metadata, legal-use
  status, provenance, and local file names.
- `scientific_question.md`: human-readable question definition and rationale.
- `inclusion_criteria.md`: criteria for adding papers.
- `exclusion_criteria.md`: criteria for excluding papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.
- `evidence_records.jsonl`: draft manual evidence records for the vertical
  slice demonstration.

## Manifest Validation

Validate the committed corpus metadata without checking local PDFs:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
```

If the local ignored PDFs are present, check file readiness:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Validation does not import papers, parse PDFs, write to SQLite, provide legal
approval, perform scientific review, or produce scientific synthesis.

## Path Contract

The corpus uses the Phase 1 version 1 path contract:

- `source_manifest` and `license_policy` are relative to this directory.
- `default_local_papers_directory` is relative to the project root.
- Source-row `local_path` values are filenames relative to
  `papers/corpora/glp1_weight_loss`.

PDF files are ignored by Git. The source list records enough provenance to
reconstruct the corpus without committing copyrighted or licensed full-text
documents.

## Current Status

The committed manifest contains three legally traceable open-access sources.
Local PDFs may exist on a contributor's machine for demonstration, but they are
not committed. The evidence records are draft manual records and need secondary
review before scientific use.
