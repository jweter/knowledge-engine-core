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

The committed manifest holds 718 sources: the small historical GLP-1
prototype set (3 rows) plus 715 accepted records from nine small
(`--limit 250`) automated discovery batches (`retstart` 0 through 2000) of
the project owner's larger corpus-building effort, following M14's rules.
Ruleset corrections along the way held 3 pediatric-titled records and 1
correction-notice record that earlier rule versions had wrongly accepted.
A further sixty-nine records were manually excluded after individual
abstract review, since v9's disease/intervention keyword match has no
automated way to catch several recurring patterns: single-patient case
reports where the named disease is only incidental patient background or
the reported intervention treats an unrelated coexisting condition (a
dermatology case report was caught this way in the `retstart=1750` batch;
six more -- a liver-abscess, a limb-ischemia/antiphospholipid, a
renal-abscess, a Graves'-disease myopericarditis, a necrotizing-fasciitis
presentation, and an invasive-mucormycosis case report -- were caught the
same way in the `retstart=2000` batch); gene-/protein-name lexical
collisions (e.g. the NOD-SCID mouse strain, the FTO gene's "fat mass and
obesity-associated" full name); type 1 diabetes-specific sources per
`exclusion_criteria.md`'s explicit rule (two more caught in the
`retstart=1750` batch, one an immune-tolerance intervention paper and one
a fatty-acid/microbiota paper, both explicitly T1D-scoped despite
matching the batch's disease/intervention keywords; a bioelectronic
thymic-modulation immune-tolerance paper caught the same way in the
`retstart=2000` batch); a pediatric study population whose title's
forward-looking "Adult" outcome term obscured the actual (non-adult)
subjects (the same evasion pattern recurred once more in the
`retstart=1750` batch: a childhood-obesity review whose title named
"Adult Cardiometabolic Disease" only as a future burden, not an adult
intervention); and a few papers matching a target term only via generic
English phrasing unrelated to the actual disease entity.

The `retstart=2000` batch also surfaced a distinct, newly-documented
pattern, in two rounds: a first, proactive self-audit pass (before
exporting approvals) excluded 23 records under the patterns above; a
Codex review on the growth PR then caught two records this pass had
missed (a necrotizing-fasciitis case report and a MASLD/T2D
epidemiological-relationship review), which prompted a second, stricter
pass checking every accepted title directly against
`inclusion_criteria.md`'s explicit two-part requirement -- the title
must name *both* an approved scope term *and* a named therapeutic
intervention -- rather than relying on the four previously-documented
patterns alone. That second pass found 29 more records where the
deterministic ruleset had accepted a title naming no therapeutic
intervention at all, because the target disease appeared only as an
incidental covariate deep in an abstract about a different primary
disease (hemodialysis frailty, COPD hypoxemia, ventilator-weaning
prediction, heart-failure diuretic resistance, park walkability, and
others), or because the record was a mechanism-only review, a
data-quality or measurement-comparison methodology paper, a
risk-prediction model, or a conceptual framework with no treatment
evidence. Of those 29, 17 were this batch's own net-new candidates
(excluded from `sources.csv` before the final import below); the
remaining 12 had already been acquired by an earlier, already-merged
batch under query overlap and are a known, documented follow-up cleanup
rather than something this batch's diff can retroactively fix. Several
of the earlier exclusions were first caught by Codex reviews on the
growth PRs, including all four `retstart=1750` exclusions and two of the
`retstart=2000` batch's; the rest of the `retstart=2000` batch's 38
exclusions (of 40 total: 23 in the first pass, 17 more -- 2 Codex-caught,
15 self-audited -- in the second) were caught proactively during
self-audit. As of the
`retstart=1250` batch, the project owner gave explicit direction that
this corpus-building phase should prioritize breadth over precision:
only the clear-cut patterns above are now screened before acquisition,
not exhaustive gray-area sweeps for mechanism-only reviews,
analytical-chemistry papers, or drugs studied for unrelated diseases --
drugs studied for an unrelated disease (e.g. an SGLT2 inhibitor trial in
aortic stenosis, a GLP-1 receptor agonist scoping review on rotator cuff
disease) remain included under this policy, since they still name a
therapeutic agent, even when the target disease itself is absent from
the title. See `CHANGELOG.md` for the full per-batch
history and `docs/m14_candidate_review_worksheet.md` for the v6-v9
ruleset history. Accepted records proceed
automatically; rejected and held records remain auditable but do not block
the batch or require owner review. The corpus continues to grow in small
batches toward a target of at least a couple thousand papers -- see
`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
and `docs/m27_corpus_library.md` for how the resulting parsed content is
persisted across sessions once imported.

**Known follow-up:** one of the two systemic quality gaps surfaced during
the `retstart=2000` batch's Codex review remains open for a dedicated
future cleanup, since it isn't specific to that batch's own net-new
rows: roughly a dozen already-merged records from earlier batches match
the title-lacks-intervention pattern documented above -- found by
re-running that batch's stricter title check against the whole
manifest, not just its own additions.

The other -- `PyMuPDFParser`'s title extraction being unreliable for
some publisher PDF layouts (Cureus's "Review began MM/DD/YYYY"
peer-review-date banner, Frontiers' "TYPE Review"/"TYPE Original
Research" article-type header), leaving roughly 7% of imported
`Paper.title` values across the whole corpus not the actual paper title
-- has since been fixed: `CorpusIngestionService`/
`LinkedCorpusIngestionService` now pass the manifest row's own
(PubMed/PMC-sourced, always-required) title through to
`PaperRepository._build_paper` as `manifest_title`, which wins over
`parsed.title` when present. A fresh corpus-import after that fix
confirmed the bad-title count dropped from 50 of 718 to 0.
