# Obesity and Metabolic-Disease Therapeutics Corpus

This directory began as the GLP-1 weight-loss vertical slice and remains at the
same stable repository path for compatibility. Its Phase 1 scope now covers
legally reusable research on obesity and metabolic-disease therapeutics, with
GLP-1 receptor agonists retained as the first named subtopic.

The corpus exercises scientific metadata, legal provenance, deterministic
adjudication, bounded acquisition, retrieval, evidence display, and manifest
validation. It does not by itself provide a final scientific conclusion.

## Scientific Question

What treatment effects, limitations, and safety findings are reported for
therapeutic interventions used in adults with obesity, overweight, type 2
diabetes, or metabolic syndrome?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: version 1 source manifest with curated metadata, legal-use
  status, provenance, and local file names.
- `scientific_question.md`: human-readable question definition and rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.
- `evidence_records.jsonl`: historical draft evidence records from the original
  GLP-1 vertical slice.

## Manifest Validation

Validate the committed corpus metadata without checking local PDFs:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
```

If the local ignored PDFs are present, check file readiness:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Validation does not import papers, parse PDFs, write to SQLite, infer a license,
or produce scientific synthesis. Legal and scientific eligibility for M14 is
recorded by deterministic adjudication rules before acquisition.

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

The committed manifest holds 607 sources: the small historical GLP-1
prototype set (3 rows) plus 604 accepted records from seven small
(`--limit 250`) automated discovery batches (`retstart` 0 through 1500) of
the project owner's larger corpus-building effort, following M14's rules.
Ruleset corrections along the way held 3 pediatric-titled records and 1
correction-notice record that earlier rule versions had wrongly accepted.
A further twenty-three records were manually excluded after individual
abstract review, since v9's disease/intervention keyword match has no
automated way to catch several recurring patterns: single-patient case
reports where the named disease is only incidental patient background or
the reported intervention treats an unrelated coexisting condition;
gene-/protein-name lexical collisions (e.g. the NOD-SCID mouse strain, the
FTO gene's "fat mass and obesity-associated" full name); type 1
diabetes-specific sources per `exclusion_criteria.md`'s explicit rule; and
a few papers matching a target term only via generic English phrasing
unrelated to the actual disease entity. Several of these were first caught
by Codex reviews on the growth PRs. As of the `retstart=1250` batch, the
project owner gave explicit direction that this corpus-building phase
should prioritize breadth over precision: only the clear-cut patterns
above are now screened before acquisition, not exhaustive gray-area
sweeps for mechanism-only reviews, analytical-chemistry papers, or drugs
studied for unrelated diseases. See `CHANGELOG.md` for the full per-batch
history and `docs/m14_candidate_review_worksheet.md` for the v6-v9
ruleset history. Accepted records proceed
automatically; rejected and held records remain auditable but do not block
the batch or require owner review. The corpus continues to grow in small
batches toward a target of at least a couple thousand papers -- see
`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
and `docs/m27_corpus_library.md` for how the resulting parsed content is
persisted across sessions once imported.
