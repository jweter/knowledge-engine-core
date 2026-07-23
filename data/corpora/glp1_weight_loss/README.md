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

The committed manifest holds 317 sources: the small historical GLP-1
prototype set (3 rows) plus 314 accepted records from the first four small
(`--limit 250`) automated discovery batches (`retstart=0`, 80 records;
`retstart=250`, 72 records; `retstart=500`, 86 records; `retstart=750`, 76
records) of the project owner's larger corpus-building effort, following
M14's rules. Ruleset corrections along the way held 3 pediatric-titled
records and 1 correction-notice record that earlier rule versions had
wrongly accepted. A further nine records were manually excluded after
review, since v9's disease/intervention keyword match has no automated way
to catch either pattern: eight single-patient case reports whose abstracts
named a target disease term (type 2 diabetes, obesity, chronic kidney
disease) only as an incidental, unrelated patient comorbidity -- including
one whose title named the disease term directly, showing that title
presence alone doesn't rule out an incidental mention; and one basic
cancer biology paper (a cervical-cancer proliferation mechanism study,
flagged by a Codex review) whose abstract matched only because it used a
xenograft mouse strain literally named "non-obese diabetic (NOD)-SCID,"
unrelated to metabolic disease. Every case-report-style accepted record
(by title or venue) in a new batch is now individually read and judged,
rather than filtered by title keyword alone, after two Codex-caught misses
in the same batch. See `docs/m14_candidate_review_worksheet.md` for the
full v6-v9 rules history. Accepted records proceed
automatically; rejected and held records remain auditable but do not block
the batch or require owner review. The corpus continues to grow in small
batches toward a target of at least a couple thousand papers -- see
`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
and `docs/m27_corpus_library.md` for how the resulting parsed content is
persisted across sessions once imported.
