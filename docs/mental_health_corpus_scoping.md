# Mental Health Corpus Scoping

## Decision

`docs/roadmap.md`'s "Decision: the extraction and discovery framework must
be domain-general, not per-field-patched" (2026-08-08) records the project
owner's explicit direction to expand the corpus library across many
research fields, not filter discovery, extraction, or evidence-matching
only through a single field's lens. The project owner chose mental health
(specifically, antidepressants in major depressive disorder) as the third
domain, over cardiovascular disease and infectious disease/vaccines as
alternatives.

## Chosen question

**Do selective serotonin reuptake inhibitors (SSRIs) and
serotonin-norepinephrine reuptake inhibitors (SNRIs) reduce depressive
symptom severity in adults with major depressive disorder (MDD)?**

See `data/corpora/mental_health_mdd_antidepressants/scientific_question.md`
for the full question frame (population, intervention, comparator, outcomes,
subtopics, and explicit out-of-scope boundaries) and
`knowledge_engine/scientific_scope.py`'s
`MENTAL_HEALTH_MDD_ANTIDEPRESSANT_SCOPE` for the exact deterministic
scope-matching vocabulary.

## Why this pairing, not mental health broadly

Mirrors the GLP-1 and oncology corpora's own shape and the same lesson
their scoping docs already document: a corpus too narrow to reliably supply
a legally-reusable full-text sample is as much a failure mode as one too
broad to be evidence-map-defensible. "Mental health" or "psychiatry" alone
would be too broad -- dozens of disparate disorders, intervention classes,
and outcome measures with no coherent single evidence map possible. A
single named population/intervention pair, matching GLP-1's "GLP-1 receptor
agonists and weight loss" and oncology's "checkpoint inhibitors and NSCLC"
framing, is the shape that has actually worked here twice already.

SSRIs/SNRIs in adult MDD was picked because it has the evidence shape
closest to what already works, while still being a genuinely distant field:

- A large, well-known randomized-trial literature spanning decades
  (fluoxetine, sertraline, escitalopram, paroxetine, citalopram,
  venlafaxine, duloxetine, desvenlafaxine), comparable in scale to
  STEP/SELECT for GLP-1 and the KEYNOTE/CheckMate/IMpower families for
  oncology.
- A clear comparator arm (placebo, or an active comparator agent) in
  essentially every landmark trial.
- Two dominant, well-established quantitative primary-outcome instruments
  (the Hamilton Depression Rating Scale, HAM-D/HDRS, and the
  Montgomery-Asberg Depression Rating Scale, MADRS) -- narrower than "any
  symptom scale," giving a typed-statistical-verification target with the
  same shape GLP-1's percentage-body-weight-change and oncology's
  survival-outcome contracts already expect.
- Substantial PMC/Europe PMC/CORE open-access coverage expected, given how
  heavily antidepressant efficacy has been studied and published.

## Alternatives considered

- **Cardiovascular disease**: strong candidate (large RCT base, comparable
  evidence shape), but closer conceptually to GLP-1's own metabolic-disease
  scope (semaglutide/tirzepatide already have cardiovascular-outcome trials
  in the GLP-1 corpus) -- less effective at demonstrating the platform
  generalizes to a genuinely different field.
- **Infectious disease / vaccines**: also a strong candidate (large,
  fast-moving literature including observational/real-world-evidence
  studies, a good test of the domain-general extraction path against a
  field further from GLP-1's RCT-heavy shape), but not the project owner's
  choice this round.
- **Mental health / psychiatry**: `docs/oncology_corpus_scoping.md`'s own
  "Alternatives considered" section (written 2026-08-08, before this
  corpus existed) already named this field as "genuinely distant from
  GLP-1, but evidence in this field is more heterogeneous in outcome
  measures (symptom-scale scores vary by instrument, less standardized
  than survival endpoints), which would likely require new
  statistical-verification work before a golden map could be as rigorous
  as GLP-1's" -- flagged as "a reasonable future third domain." The
  project owner selected it as that third domain. That heterogeneity
  concern is real and is addressed here by naming two specific dominant
  scales (HAM-D, MADRS) rather than accepting any symptom measure, not by
  ignoring the concern.

## Status

Corpus definition files exist
(`data/corpora/mental_health_mdd_antidepressants/`: `corpus.json`,
`inclusion_criteria.md`, `exclusion_criteria.md`, `scientific_question.md`,
`license_policy.md`, `sources.csv`). `ke discovery-cycle-run`,
`europepmc-candidate-review-prepare`, and `core-candidate-review-prepare`
all accept `--corpus mental_health_mdd_antidepressants` to adjudicate
against this corpus's scope vocabulary instead of the GLP-1 or oncology
defaults (see `knowledge_engine/scientific_scope.py`).

**2026-08-08: scoped, not yet seeded.** No discovery cycles have been run
yet; `sources.csv` is header-only. Seeding this corpus with real papers,
then individually authoring and reviewing Evidence Records, and eventually
a golden evidence map for this research question, remain future, separate
work -- mirroring both prior corpora's own progression.
