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
for the GLP-1 and oncology corpora.

**Second discovery cycle (2026-08-08, same day): yield collapsed further,
query tightened.** A second cycle (retstart=100) scanned 100 candidates,
64 deterministically accepted; the manual scope screen passed only 1
(1.5%, down from cycle 1's 13%). Root cause: the query's bare
`OR antidepressant` term matches any depression-treatment-mechanism paper
(ketamine, psilocybin, TMS/ECT/tDCS, herbal/probiotic interventions,
preclinical animal studies), not just SSRI/SNRI trials. That one
additional paper was acquired and imported (8 total papers now in the
corpus). Future discovery cycles should use
`data/corpora/mental_health_mdd_antidepressants/discovery_state_v2.json`
with a tightened query (drops the bare `antidepressant` term, keeps
`SSRI`/`SNRI`/the named-agent list) -- see
`docs/mental_health_corpus_scoping.md`'s 2026-08-08 entry for the full
query text and reasoning.

**Tightened-query cycle 1 (2026-08-08, same day): modest yield
improvement.** The tightened query's first cycle (retstart=0) scanned 100
candidates, 60 deterministically accepted. 7 were duplicates of papers
already acquired in earlier cycles (expected overlap, since the tightened
query is a subset of the original). Of the 53 new candidates, 2 passed
scope screen (~3.8%, versus the untightened query's 1.5% on its second
cycle) -- a real but modest improvement, not a fix. Both acquired and
imported: a paroxetine post-marketing pharmacovigilance safety analysis
and a trazodone-vs-SSRIs comparative-effectiveness study. Corpus now
holds 10 real papers.

**Tightened-query cycle 2 (2026-08-08, same day): 4 more real papers,
yield up to 8%.** A third discovery cycle (tightened query, retstart=100)
scanned 100 candidates, 50 deterministically accepted. 4 passed scope
screen: a desvenlafaxine (SNRI) network meta-analysis, a
vortioxetine-vs-sertraline comparison in Parkinson's-disease-comorbid
depression, a venlafaxine (SNRI) post-marketing pharmacovigilance
analysis, and a bupropion-plus-sertraline precision-medicine SMART trial.
Acquired and imported with `work/run_paper_batch.sh` (a local
batch-runner script collapsing acquire/import/split/verify into one
call). Corpus now holds 14 real papers.

**Tightened-query cycle 3 (2026-08-08, same day): 4 more real papers,
yield holding around 8%.** A fourth discovery cycle (retstart=200)
scanned 100 candidates, 48 deterministically accepted. 4 passed scope
screen: the DEPRE'5 RCT (treatment strategies after a failed SSRI trial
in MDD), a sertraline inflammatory-markers systematic review/
meta-analysis, a paroxetine-plus-sulpiride sleep/quality-of-life study,
and a network meta-analysis of antidepressant efficacy/tolerability in
comorbid physical conditions. Corpus now holds 18 real papers.

**Tightened-query cycle 4 (2026-08-08, same day): 9 more real papers,
yield up to 16%.** A fifth discovery cycle (retstart=300) scanned 100
candidates, 56 deterministically accepted. 9 passed scope screen -- the
best yield yet: a citalopram/escitalopram glucolipid-metabolism
systematic review, an SSRI/SNRI post-stroke-depression systematic
review, a paroxetine-olanzapine drug-interaction pharmacokinetics study,
a fluoxetine oral-side-effects systematic review, an escitalopram
combined-treatment retrospective analysis, a fluoxetine-plus-probiotics
RCT, an agomelatine-plus-SSRI/SNRI RCT, a pharmacological-interventions-
in-milder-depression systematic review/meta-analysis, and a
vortioxetine-vs-escitalopram cognitive-profile comparative study.
Acquired and imported with `work/run_paper_batch.sh`. Corpus now holds
27 real papers. More cycles are needed to build a corpus of comparable
size to GLP-1/oncology, given the still-below-oncology per-cycle yield,
though it continues improving cycle over cycle. Individually authoring
and reviewing Evidence Records remains future, separate work.
