# Mental Health: Antidepressants in Major Depressive Disorder Corpus

The third research domain (`docs/roadmap.md`'s "Decision: the extraction
and discovery framework must be domain-general, not per-field-patched"),
added alongside continued GLP-1 and oncology work, not instead of it.
Mirrors `data/corpora/glp1_weight_loss` and
`data/corpora/oncology_nsclc_checkpoint_inhibitors`'s exact file shape and
the same deterministic, legally-traceable discovery/adjudication pipeline
-- see `docs/mental_health_corpus_scoping.md` for why this specific
population/intervention pair was chosen.

## Scientific Question

Do selective serotonin reuptake inhibitors (SSRIs) and
serotonin-norepinephrine reuptake inhibitors (SNRIs) reduce depressive
symptom severity in adults with major depressive disorder (MDD)?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: source manifest, 7 rows (see Status below).
- `discovery_state.json`: `ke discovery-cycle-run` pagination bookmark.
- `scientific_question.md`: human-readable question definition and
  rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.

## Status

**Scoped (2026-08-08).** Corpus definition, scope vocabulary
(`knowledge_engine.scientific_scope.MENTAL_HEALTH_MDD_ANTIDEPRESSANT_SCOPE`),
and inclusion/exclusion criteria exist.

**First seeding batch (2026-08-08).** A first `ke discovery-cycle-run`
cycle scanned 100 raw PubMed candidates and produced 54 unique
deterministically-accepted candidates (identity/license/full-text/scope
rules passed; 0 already in the rejected-PMID ledger). A documented,
rule-based title/abstract scope screen -- applying `exclusion_criteria.md`
to exclude pediatric-only and bipolar/psychotic populations,
non-pharmacological interventions with no SSRI/SNRI arm,
mechanism-only/preclinical (animal-model) papers, biomarker/genetic
association studies without a treatment-outcome endpoint, and
single-patient case reports -- selected only **7 of the 54** candidates.
This is a much lower yield than the oncology corpus's 70% (336/478): the
"depression" search space this query casts is broader and noisier
(mechanism/animal studies, comorbid-condition case reports, and
non-pharmacological interventions dominate the raw candidate pool in a
way advanced-NSCLC-plus-checkpoint-inhibitors did not). This is an
honest finding about this field, not a screening bug -- see
`docs/mental_health_corpus_scoping.md`.

All 7 approved candidates were acquired as real PMC OA PDFs
(`ke pmc-oa-acquire`) and imported into the corpus database
(`ke corpus-import`: 7 imported, 0 failed, 0 skipped). This is bulk
ingestion, not a reviewed evidence base: `sources.csv`'s
`study_type`/`population`/`intervention`/`comparator` fields are
intentionally blank, matching the same two-stage discipline already used
for the GLP-1 and oncology corpora. Continue discovery with
`--corpus mental_health_mdd_antidepressants` and
`data/corpora/mental_health_mdd_antidepressants/discovery_state.json` as
`--state` to resume from `retstart=100` -- more cycles are needed to build
a corpus of comparable size to GLP-1/oncology, given the low per-cycle
yield. Individually authoring and reviewing Evidence Records remains
future, separate work.
