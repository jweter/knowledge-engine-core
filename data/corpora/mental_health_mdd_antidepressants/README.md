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
27 real papers.

**Tightened-query cycle 5 (2026-08-09): 10 more real papers,
yield up to 18%.** A sixth discovery cycle (retstart=400) scanned 100
candidates, 56 deterministically accepted. 10 passed scope screen -- the
best yield yet: a trazodone-vs-SSRIs effectiveness study, a comparative-
effectiveness study of different antidepressants preventing psychiatric
rehospitalization, a sertraline-in-dialysis systematic review/
meta-analysis, a TMS-plus-paroxetine post-stroke-depression study, a
patient-level meta-analysis of mirtazapine/SSRIs/amitriptyline sedative
and appetite properties, a venlafaxine adverse-events systematic
review/meta-analysis with Trial Sequential Analysis, an insulin-
resistance/SSRI-SNRI-resistance study, a vilazodone/escitalopram/
vortioxetine metabolic-parameters RCT, an aticaprant-adjunctive-to-SSRI/
SNRI phase 2 RCT, and the ASCERTAIN-TRD comparative-effectiveness RCT.
Corpus now holds 37 real papers.

**Tightened-query cycle 6 (2026-08-09): 10 more real papers -- and a
real parser bug fixed live.** A seventh discovery cycle (retstart=500)
scanned 100 candidates, 62 deterministically accepted. 10 passed scope
screen: an escitalopram-CABG depression/quality-of-life RCT, an
escitalopram+sertraline post-stroke-depression RCT, a sertraline-PANDA
predictors-of-response secondary analysis, a CBASP-vs-escitalopram
persistent-depressive-disorder subgroup study, the VESPA
vortioxetine-vs-SSRIs tolerability RCT, an antidepressants-in-Japan
systematic review/meta-analysis, the CAN-BIND CYP2C19/CYP2D6/ABCB1
sexual-dysfunction pharmacogenetic study, an empagliflozin-adjunctive-
to-citalopram RCT, an antidepressant-side-effects/adherence systematic
review, and a vortioxetine-vs-fluoxetine metabolic-parameters RCT.
Importing the CAN-BIND paper hit a real bug: its embedded PDF metadata
lists each co-author's degree credential comma-separated from their
name ("Jane Doe, PhD, John Smith, PhD, ..."), and the repeated "PhD"
token got parsed as a duplicate pseudo-author, violating the database's
one-link-per-paper-per-author constraint and aborting the whole import
batch. Fixed in `knowledge_engine/parser.py` (filters known degree/
credential tokens out of the split author list) and
`knowledge_engine/database.py` (a defense-in-depth guard against any
repeated-author cause); see `CHANGELOG.md`. Corpus now holds 47 real
papers. More cycles are needed to build a corpus of comparable size to
GLP-1/oncology, though yield continues improving cycle over cycle (13%
-> 1.5% -> 3.8% -> 8% -> 8.3% -> 16% -> 18% -> 16%, after the query
tightening and as later-page candidates skew more
clinical/pharmacological). Individually authoring and reviewing
Evidence Records remains future, separate work.

**Tightened-query cycle 7 (2026-08-09): 13 more real papers, best yield
yet at 20%.** An eighth discovery cycle (retstart=600) scanned 100
candidates, 65 deterministically accepted. 13 passed scope screen: a
probiotic-adjunct-to-SSRIs sexual-function RCT, a TMS-plus-escitalopram
efficacy/safety meta-analysis, a psilocybin-vs-escitalopram
personality-change trial, an SSRIs-in-multiple-sclerosis systematic
review/meta-analysis, a CYP2C19-pharmacogenetic-testing
citalopram/escitalopram tolerability-and-efficacy cohort study, an
escitalopram-vs-other-antidepressants systematic review/meta-analysis,
the TED-trazodone-vs-SSRIs naturalistic effectiveness study, an
rTMS-plus-sertraline somatic-pain study, a psilocybin-for-treatment-
resistant-depression trial in patients on a concomitant SSRI, two
CAN-BIND-1 secondary analyses (multimodal treatment-outcome prediction;
abuse-history/anhedonia-persistence), a CYP2D6/CYP1A2-polymorphism
duloxetine-response study, and an EMBARC-trial secondary analysis of
reward-behavior disengagement. Corpus now holds 60 real papers. Yield
trend: 13% -> 1.5% -> 3.8% -> 8% -> 8.3% -> 16% -> 18% -> 16% -> 20%.

**Tightened-query cycle 8 (2026-08-09): yield collapsed to 2%, likely
approaching this query's exhaustion point.** A ninth discovery cycle
(retstart=700) scanned 100 candidates, only 2 deterministically
accepted (down sharply from 65 the cycle before) -- most of this page's
candidates failed the deterministic identity/license/full-text/scope
rules outright, not just the manual screen. Both of the 2 candidates
passed manual scope screen: a plasma-concentration study of SSRI/SNRI
after bariatric surgery and its effect on depressive symptoms (a
comorbid-population trial with directly-named drug classes), and an
EMBARC-trial secondary analysis of brain ventricle/choroid plexus
morphology as a treatment-response predictor. Corpus now holds 62 real
papers. This sharp drop suggests the tightened query's readily-available
PMC-OA results may be thinning out in this pagination range; a future
cycle should assess whether continuing at higher `retstart` values
remains productive or whether the query needs further adjustment.

**Tightened-query cycle 9 (2026-08-09): 0 accepted, confirming
exhaustion at this pagination range.** A tenth discovery cycle
(retstart=800) scanned 100 candidates and 0 were deterministically
accepted -- not a scope-screen problem, the page produced zero
identity/license/full-text/scope-eligible PMC-OA candidates at all.
Combined with cycle 8's 2% yield (down from cycle 7's 20%), this is a
real signal, not noise: the tightened query's readily-available PMC-OA
results are exhausted in the 700-900 `retstart` range. Pausing further
mental-health discovery cycles at this query/state file rather than
continuing to grind pages that return nothing; a future session should
either try a broader or differently-tightened query, or accept 62
papers as this corpus's current size until a query redesign is
warranted. `discovery_state_v2.json`'s `next_retstart` is left at 900
so a future cycle can pick up cleanly if the query is revisited.
