# Scientific Question

## Question

Do selective serotonin reuptake inhibitors (SSRIs) and serotonin-norepinephrine
reuptake inhibitors (SNRIs) reduce depressive symptom severity in adults with
major depressive disorder (MDD)?

## Rationale

`docs/roadmap.md`'s "Decision: the extraction and discovery framework must be
domain-general, not per-field-patched" (2026-08-08) records the project
owner's explicit direction to expand the corpus library across many research
fields rather than build tooling that only works through GLP-1's lens. This
is the third domain, chosen by the project owner over cardiovascular disease
and infectious disease/vaccines as alternatives.

SSRIs/SNRIs in adult MDD was chosen, not "mental health" or "psychiatry"
broadly, for the same reason both prior corpora stayed bounded to one
population/intervention pair: a narrow, well-studied triple is what makes an
evidence-map-defensible corpus possible (see
`glp1_body_weight_golden_evidence_map.md` and
`docs/oncology_corpus_scoping.md`). This specific pairing was picked because
it has the evidence shape closest to what already works, while still being a
genuinely distant field from GLP-1 and oncology:

- A large, well-known randomized-trial literature spanning decades (fluoxetine,
  sertraline, escitalopram, paroxetine, venlafaxine, duloxetine, and other
  agents), comparable in scale and public recognizability to STEP/SELECT for
  GLP-1 and the KEYNOTE/CheckMate/IMpower families for oncology.
- A clear comparator arm (placebo, or an active comparator agent) in
  essentially every landmark trial.
- Quantitative primary endpoints exist (validated symptom-severity scales:
  the Hamilton Depression Rating Scale (HAM-D/HDRS) and the
  Montgomery-Asberg Depression Rating Scale (MADRS) are the two dominant,
  well-established instruments), giving a typed-statistical-verification
  target the same shape as GLP-1's percentage-body-weight-change and
  oncology's survival-outcome endpoints.
- Substantial PMC/Europe PMC/CORE open-access coverage expected, given how
  heavily antidepressant efficacy has been studied and published.

`docs/oncology_corpus_scoping.md`'s own "Alternatives considered" section
already flagged this field's genuine complexity honestly: "evidence in this
field is more heterogeneous in outcome measures (symptom-scale scores vary
by instrument, less standardized than survival endpoints), which would
likely require new statistical-verification work before a golden map could
be as rigorous as GLP-1's." That complexity is real and not being minimized
here -- it is exactly why this corpus's initial scope names two specific,
dominant scales (HAM-D, MADRS) rather than accepting any symptom measure, and
why building a golden evidence map or typed statistical inputs for this
corpus is explicitly future, separate work, not assumed to be a drop-in reuse
of the GLP-1/oncology statistical-verification contracts without review.

## Question Frame

- Population: adults (18+) diagnosed with major depressive disorder (MDD)
  by a recognized diagnostic standard (e.g. DSM or ICD criteria).
- Intervention: an SSRI (e.g. fluoxetine, sertraline, escitalopram,
  paroxetine, citalopram) or SNRI (e.g. venlafaxine, duloxetine,
  desvenlafaxine), alone or as monotherapy compared with augmentation.
- Comparator: placebo, another antidepressant class, or another active
  treatment described by the source.
- Outcomes: depressive symptom severity (HAM-D/HDRS or MADRS score change,
  response, or remission), adverse events, discontinuation/tolerability, and
  clinically relevant limitations.
- Time scope: any clearly reported acute-phase or maintenance treatment
  duration.

## Initial Subtopics

- SSRI monotherapy versus placebo in adult MDD.
- SNRI monotherapy versus placebo in adult MDD.
- Head-to-head SSRI versus SNRI comparisons.
- Treatment-resistant depression augmentation strategies (bounded to
  SSRI/SNRI-based regimens; not a general treatment-resistant-depression
  corpus).

## Out of Scope for Initial Discovery

- Pediatric-only populations.
- Non-pharmacological interventions studied without an SSRI/SNRI arm (e.g.
  psychotherapy-only trials) -- a possible future corpus, not this one.
- Bipolar depression, psychotic depression, or perinatal/postpartum-specific
  populations as the sole focus (genuinely different treatment paradigms;
  may be revisited as a separate bounded question later).
- Mechanism-only (pharmacology/neuroscience) papers without a named clinical
  trial or treatment-outcome result.
- Cost-effectiveness or policy-only papers without treatment-outcome
  evidence.
- Editorials, news, marketing material, and unsupported opinion pieces.
- Records without verified reusable full text under an approved source
  policy (same PMC OA / Europe PMC / CORE trust boundaries as the GLP-1 and
  oncology corpora -- see `license_policy.md`).

## Status

Corpus definition created 2026-08-08. No discovery cycles have been run;
`sources.csv` is header-only. Seeding this corpus with real papers, then
individually authoring and reviewing Evidence Records, remain future,
separate work -- mirroring both prior corpora's own progression from
scoping to bulk acquisition to a reviewed evidence base.
