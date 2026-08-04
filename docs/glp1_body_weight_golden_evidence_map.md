# GLP-1 and Body-Weight Golden Evidence Map

## Decision

The first golden scientific evidence map is a bounded, versioned selection of
existing Evidence Records and reviewer-authored Relationship Records for this
question:

> Do GLP-1 receptor agonists reduce body weight in adults with overweight or
> obesity?

The machine-readable artifact is
`data/corpora/glp1_weight_loss/golden_evidence_map.json`. Its status is
`provisional`, not `reviewed`, because every selected Evidence Record still has
`review_status: draft` and requires independent secondary review.

This map organizes traceable evidence. It does not calculate consensus,
confidence, benefit-harm balance, or scientific truth.

## Scope

The direct evidence is centered on semaglutide treatment during continued use
in adults with overweight or obesity. Population extensions are kept separate
when diabetes, cardiovascular disease, heart failure, or PMOS changes
applicability. Liraglutide and tirzepatide appear only as explicit endpoint or
active-comparator context.

The bounded map excludes class-wide conclusions, pediatric and pregnancy
populations, post-discontinuation maintenance, cost-effectiveness, and a
comprehensive safety analysis. A result for a different outcome is not treated
as support for or contradiction of body-weight reduction.

## Selected Evidence

| Evidence Record | Role | Design and comparison | Result represented | Principal boundary |
| --- | --- | --- | --- | --- |
| `ev-glp1-step5-body-weight-week104-001` | Landmark trial | RCT; semaglutide 2.4 mg plus behavioral intervention vs placebo plus behavioral intervention | Week-104 mean change: -15.2% vs -2.6% | Adults without diabetes; adverse events and discontinuation are not represented in this record |
| `ev-glp1-select-trial-weight-loss-208wk-001` | Landmark trial | RCT; semaglutide 2.4 mg vs placebo | Week-208 mean change: -10.2% vs -1.5% | Cardiovascular-disease population; secondary analysis with higher treatment discontinuation |
| `ev-glp1-gao-meta-analysis-body-weight-001` | Evidence synthesis | Systematic review and meta-analysis of semaglutide RCTs | Pooled relative change favored semaglutide by -10.09 percentage points | Dose, duration, population, and statistical heterogeneity vary across trials |
| `ev-glp1-semaglutide-obesity-cardiometabolic-001` | Population extension | Retrospective single-arm cohort, with and without type 2 diabetes | Within-subject body-weight reduction of 9 kg reported | No concurrent control; residual effects of concurrent care and selection remain |
| `ev-glp1-semaglutide-hfref-outcomes-001` | Population extension | Propensity-matched cohort; oral semaglutide vs no GLP-1RA | Mean change: -8.0 kg vs -1.9 kg at 24 months | HFrEF, type 2 diabetes, and obesity; residual confounding remains |
| `ev-semaglutide-pmos-menstrual-function-001` | Population extension | Prospective single-arm PMOS cohort | Six-month mean change of -11.3% reported | No concurrent control; subgroup findings are exploratory |
| `ev-tirzepatide-vs-semaglutide-weightloss-001` | Active-comparator context | Propensity-matched EHR cohort; tirzepatide vs semaglutide | Mean reduction: 14.7% vs 10.8% | Comparative effectiveness, not a randomized head-to-head or placebo trial |
| `ev-glp1-waist-circumference-meta-001` | Evidence synthesis | Meta-analysis of heterogeneous intervention categories | GLP-1RA subgroup waist change: -5.93 cm | Waist circumference is not body weight; between-category differences were not significant |
| `ev-liraglutide-alone-physical-fitness-001` | Endpoint qualifier | Randomized secondary analysis after diet-induced weight loss | Liraglutide alone did not improve physical fitness | A null fitness result does not contradict body-weight reduction |

## Population and Comparator Boundaries

The map deliberately does not flatten these studies into one population or one
comparison:

- STEP 5 and the Gao synthesis address adults with overweight or obesity
  without diabetes; SELECT additionally requires established cardiovascular
  disease.
- The diabetes, HFrEF, and PMOS records extend context but are observational and
  do not inherit randomized-trial certainty.
- Placebo-controlled evidence, within-subject change, no-GLP-1RA comparison,
  and tirzepatide active comparison remain distinct comparator classes.
- Waist circumference and physical fitness qualify interpretation but do not
  answer the body-weight question by substitution.

## Relationship Review

The map references 13 existing reviewer-authored relationships whose endpoints
are both selected: 10 `supports` and 3 `contextualizes`. It does not infer new
edges. Support links preserve aligned direction while their rationales retain
study-design and population differences. Context links prevent active
comparators, PMOS evidence, and other population extensions from being
misrepresented as direct replication.

No reviewed same-PICO `contradicts` relationship was identified in this bounded
selection. Tirzepatide's larger active-comparator estimate and liraglutide's
null fitness result are not contradictions of semaglutide-versus-placebo
body-weight findings. This absence is a search result within the selected map,
not evidence that contradictory literature does not exist.

## Citations

Each selected Evidence Record resolves by normalized DOI to a complete curated
row in `sources.csv`:

- STEP 5: `10.1038/s41591-022-02026-4`
- Gao et al. meta-analysis: `10.3389/fphar.2022.935823`
- SELECT weight analysis: `10.1038/s41591-024-02996-7`
- Obesity cardiometabolic cohort: `10.3390/jcm15124421`
- HFrEF cohort: `10.3390/ph19060894`
- PMOS cohort: `10.3390/jcm15135165`
- Tirzepatide comparison: `10.1093/pnasnexus/pgag171`
- Waist-circumference synthesis: `10.1016/j.obpill.2026.100281`
- Liraglutide fitness analysis: `10.1007/s40279-025-02386-0`

The source manifest remains authoritative for title, authors, year, venue,
source URL, and declared license provenance. Structural validation confirms
that those fields are present; it does not grant legal approval.

## Validation Contract

Run:

```bash
ke evidence-map-validate \
  data/corpora/glp1_weight_loss/golden_evidence_map.json \
  --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl \
  --relationships data/corpora/glp1_weight_loss/relationship_records.jsonl \
  --sources data/corpora/glp1_weight_loss/sources.csv
```

The validator checks schema version, required scope and review statements,
Evidence Record references, limitations, complete DOI-matched citations,
Relationship Record references and endpoints, population/comparator coverage,
contradiction consistency, and whether a map marked `reviewed` contains draft
evidence. Output and counts are deterministic.

The validator does not infer inclusion, relationships, contradiction,
consensus, confidence, or truth. It does not read PDFs, query SQLite, follow
URLs, or alter any source record.

## Remaining Work

Before the map can become `reviewed`:

1. Independently verify each selected Evidence Record against its cited source
   and advance only records that meet the repository's review contract.
2. Review the map's inclusion, role, grouping, and relationship judgments.
3. Add direct post-discontinuation evidence and a systematic safety and
   discontinuation view.
4. Expand agent and population coverage without collapsing drug, dose,
   formulation, duration, or eligibility differences.
5. Search explicitly for same-PICO contradictory or qualifying evidence and
   preserve a negative search outcome honestly when none is found.

Once those checks are complete, this map becomes the evaluated foundation for
the roadmap's structured cross-study comparison work and a traceable public
demonstration. It still will not be a declaration of scientific truth.
