# GLP-1 Golden Evidence Map Secondary Review

## Decision

The bounded GLP-1/body-weight golden evidence map completed an independent
record-to-source audit on 2026-08-03. All nine selected Evidence Records and all
thirteen selected Relationship Records were checked against legally usable
local source PDFs. The accepted records now carry `review_status: reviewed`,
and the map carries `map_status: reviewed`.

This was an AI-assisted audit performed by OpenAI Codex. It was not human
domain-expert approval, independent statistical reanalysis, scientific
synthesis, consensus assessment, confidence scoring, or truth determination.
Reviewed means that the selected records are accepted for source fidelity
under the version 1 map contract.

## Method

For each selected Evidence Record, the audit checked:

- source identity, title, and normalized DOI;
- the tagged page and quoted source excerpt;
- study design and population, intervention, comparator, and outcome fields;
- numerical values and time points in the result summary;
- limitations and uncertainty language; and
- the retrieval and no-synthesis boundaries.

Each selected Relationship Record was then checked against both endpoint
records and source PDFs for endpoint identity, PICO and outcome alignment,
relationship type, rationale, and population/comparator boundaries.

The nine PDFs remain local and ignored by Git. The six PMC Open Access files
that were not already present were retrieved from the exact S3 URLs already
recorded in `sources.csv`; their MD5 values matched the checksums encoded in
those curated URLs. No PDF or checksum was added to the repository.

## Evidence Review Results

| Evidence Record | Outcome | Review note |
| --- | --- | --- |
| `ev-glp1-step5-body-weight-week104-001` | Accepted | Week-104 treatment-policy estimates and trial boundary matched the source. |
| `ev-glp1-select-trial-weight-loss-208wk-001` | Accepted | Week-208 arm and placebo-adjusted estimates, estimands, and discontinuation boundary matched. |
| `ev-glp1-gao-meta-analysis-body-weight-001` | Accepted | Relative and absolute pooled estimates and heterogeneity limitation matched. |
| `ev-glp1-semaglutide-obesity-cardiometabolic-001` | Accepted | Uncontrolled retrospective design, measurements, and confounding limitations matched. |
| `ev-glp1-semaglutide-hfref-outcomes-001` | Accepted | Propensity-matched cohort result and residual-confounding boundary matched. |
| `ev-semaglutide-pmos-menstrual-function-001` | Corrected and accepted | Reclassified as an uncontrolled before-after treatment study and added completer-selection and discontinuation limitations. |
| `ev-tirzepatide-vs-semaglutide-weightloss-001` | Accepted | Propensity-matched EHR comparison and active-comparator boundary matched. |
| `ev-glp1-waist-circumference-meta-001` | Accepted | Pooled and GLP-1 subgroup estimates, nonsignificant subgroup difference, and publication-bias signal matched. |
| `ev-liraglutide-alone-physical-fitness-001` | Corrected and accepted | Replaced an overbroad power limitation with the source's body-weight primary calculation and specified secondary fitness-power estimate. |

## Relationship Review Results

All thirteen selected relationships remained scientifically bounded and
traceable after review: ten `supports` and three `contextualizes`. Two
rationales were corrected:

- the PMOS relationship now describes an uncontrolled before-after treatment
  cohort rather than asserting a prospective cohort design; and
- the tirzepatide/SELECT relationship distinguishes SELECT's -10.2% treatment
  arm change from its -8.7 percentage-point placebo-adjusted estimate.

No selected edge was reclassified as `contradicts`. That result is bounded to
the selected records and is not evidence that contradictory literature does
not exist.

## Review Provenance

Every selected Evidence Record and Relationship Record contains a
`provenance.secondary_review` object with reviewer identity, reviewer type,
date, source basis, checks, outcome, and corrections. Evidence Records also
mark `review_checklist.secondary_review_completed: true`.

No record claims `human_reviewed`. Disputed records or substantive future
changes can still be routed to human domain-expert adjudication.

## Remaining Gaps

The initial audit identified the gaps below. The direct post-discontinuation
and first pooled safety/discontinuation gaps were subsequently addressed in
`docs/glp1_map_durability_safety.md`; the broader forms of those gaps remain.

The audit did not close the map's scientific coverage gaps:

- direct post-discontinuation weight maintenance or regain;
- systematic adverse-event and treatment-discontinuation evidence;
- broader drug, formulation, dose, duration, and population coverage; and
- an explicit search for a sufficiently aligned contradictory result.

It also did not perform full risk-of-bias assessment or reanalyze source data.
These are the next constraints to address before broader analytical
intelligence is built over the map.

## Validation

The reviewed map is validated with:

```bash
ke evidence-validate data/corpora/glp1_weight_loss/evidence_records.jsonl
ke relationship-validate \
  data/corpora/glp1_weight_loss/relationship_records.jsonl \
  --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
ke evidence-map-validate \
  data/corpora/glp1_weight_loss/golden_evidence_map.json \
  --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl \
  --relationships data/corpora/glp1_weight_loss/relationship_records.jsonl \
  --sources data/corpora/glp1_weight_loss/sources.csv
```

These commands check structure, references, review state, and source/citation
traceability. They do not infer evidence, relationships, consensus,
confidence, or scientific truth.
