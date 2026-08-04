# GLP-1 and Body-Weight Golden Evidence Map

## Decision

The first golden scientific evidence map is a bounded, versioned selection of
existing Evidence Records and reviewer-authored Relationship Records for this
question:

> Do GLP-1 receptor agonists reduce body weight in adults with overweight or
> obesity?

The machine-readable artifact is
`data/corpora/glp1_weight_loss/golden_evidence_map.json`. Its status is
`reviewed`. AI-assisted independent source audits checked all twelve selected
Evidence Records and all seventeen selected Relationship Records against the
legally usable local PDFs. The initial audit is documented in
`docs/glp1_golden_map_secondary_review.md`; the durability and safety follow-up
is documented in `docs/glp1_map_durability_safety.md`; and the bounded
same-PICO search is documented in
`docs/glp1_same_pico_contradiction_search_audit.md`.

Reviewed means accepted for record-to-source fidelity under this map's
contract. It does not mean human domain-expert approval, independent
statistical reanalysis, scientific synthesis, consensus, confidence, or truth.

This map organizes traceable evidence. It does not calculate consensus,
confidence, benefit-harm balance, or scientific truth.

## Scope

The direct efficacy evidence is centered on semaglutide treatment during
continued use in adults with overweight or obesity. One exploratory STEP 1
extension separately represents the first year after withdrawal, and one RCT
meta-analysis record separately represents adverse events and discontinuation.
Population extensions remain separate when diabetes, cardiovascular disease,
heart failure, PMOS, or prior metabolic surgery changes applicability.
Liraglutide and tirzepatide appear only as explicit endpoint,
agent/population, or active-comparator context.

The bounded map excludes class-wide conclusions, pediatric and pregnancy
populations, cost-effectiveness, and a comprehensive current safety analysis.
The single post-withdrawal extension does not establish every agent's or every
person's trajectory. A result for a different outcome is not treated as support
for or contradiction of body-weight reduction.

## Selected Evidence

| Evidence Record | Role | Design and comparison | Result represented | Principal boundary |
| --- | --- | --- | --- | --- |
| `ev-glp1-step5-body-weight-week104-001` | Landmark trial | RCT; semaglutide 2.4 mg plus behavioral intervention vs placebo plus behavioral intervention | Week-104 mean change: -15.2% vs -2.6% | Adults without diabetes; adverse events and discontinuation are not represented in this record |
| `ev-glp1-step1-withdrawal-weight-regain-001` | Durability qualifier | Exploratory off-treatment STEP 1 extension | Regain from week 68 to 120: 11.6 vs 1.9 percentage points | Selected completers; both treatment and structured lifestyle intervention ended; no formal significance testing |
| `ev-glp1-select-trial-weight-loss-208wk-001` | Landmark trial | RCT; semaglutide 2.4 mg vs placebo | Week-208 mean change: -10.2% vs -1.5% | Cardiovascular-disease population; secondary analysis with higher treatment discontinuation |
| `ev-glp1-gao-meta-analysis-body-weight-001` | Evidence synthesis | Systematic review and meta-analysis of semaglutide RCTs | Pooled relative change favored semaglutide by -10.09 percentage points | Dose, duration, population, and statistical heterogeneity vary across trials |
| `ev-glp1-gao-meta-analysis-safety-discontinuation-001` | Safety qualifier | Safety outcomes from semaglutide RCT meta-analysis | AE RR 1.10; SAE RR 1.34; discontinuation-due-to-AE RR 2.29 | Varied doses and durations; high heterogeneity for any adverse event; not a current class-wide safety assessment |
| `ev-glp1-semaglutide-obesity-cardiometabolic-001` | Population extension | Retrospective single-arm cohort, with and without type 2 diabetes | Within-subject body-weight reduction of 9 kg reported | No concurrent control; residual effects of concurrent care and selection remain |
| `ev-glp1-semaglutide-hfref-outcomes-001` | Population extension | Propensity-matched cohort; oral semaglutide vs no GLP-1RA | Mean change: -8.0 kg vs -1.9 kg at 24 months | HFrEF, type 2 diabetes, and obesity; residual confounding remains |
| `ev-semaglutide-pmos-menstrual-function-001` | Population extension | Uncontrolled before-after PMOS treatment study | Six-month mean change of -11.3% among 96 completers | No concurrent control; nine of 105 selected participants discontinued before completion |
| `ev-tirzepatide-vs-semaglutide-weightloss-001` | Active-comparator context | Propensity-matched EHR cohort; tirzepatide vs semaglutide | Mean reduction: 14.7% vs 10.8% | Comparative effectiveness, not a randomized head-to-head or placebo trial |
| `ev-glp1-waist-circumference-meta-001` | Evidence synthesis | Meta-analysis of heterogeneous intervention categories | GLP-1RA subgroup waist change: -5.93 cm | Waist circumference is not body weight; between-category differences were not significant |
| `ev-liraglutide-alone-physical-fitness-001` | Endpoint qualifier | Randomized secondary analysis after diet-induced weight loss | Liraglutide alone did not improve physical fitness | The primary sample-size calculation was for body weight; specified fitness differences had estimated secondary-analysis power |
| `ev-glp1-glide-liraglutide-post-lagb-weight-001` | Agent/population qualifier | Underpowered pilot RCT; liraglutide 1.8 mg vs placebo after gastric banding | Six-month adjusted difference 2.0 kg (95% CI -4.2 to 8.1); p=0.50 | Adults with obesity and T2D after LAGB; different agent, dose, population, surgical context, and outcome priority from STEP 5 |

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
- GLIDE's post-gastric-banding liraglutide comparison is an explicit
  agent/population boundary and cannot be substituted for semaglutide evidence
  in non-surgical adults without diabetes.

## Relationship Review

The map references 17 reviewer-authored relationships whose endpoints are both
selected: 10 `supports`, 4 `contextualizes`, and 3 `qualifies`. It does not
infer edges. Support links preserve aligned direction while their rationales
retain study-design and population differences. Context and qualifier links
prevent active comparators, withdrawal trajectories, safety outcomes, PMOS
evidence, and other population extensions from being misrepresented as direct
replication or as a computed benefit-harm conclusion.

No reviewed same-PICO `contradicts` relationship was identified. The
2026-08-04 audit screened 156 Evidence Records, 952 source rows, 261
shared-concept candidate pairs, 113 direct PubMed results, and 45
negative-signal abstracts. GLIDE's null six-month liraglutide result after
gastric banding, liraglutide's null fitness result, and tirzepatide's larger
active-comparator estimate are qualifiers rather than contradictions of
semaglutide-versus-placebo body-weight findings. This bounded negative search
is not evidence that contradictory literature does not exist.

## Citations

Each selected Evidence Record resolves by normalized DOI to a complete curated
row in `sources.csv`:

- STEP 5: `10.1038/s41591-022-02026-4`
- STEP 1 withdrawal extension: `10.1111/dom.14725`
- Gao et al. meta-analysis: `10.3389/fphar.2022.935823`
- SELECT weight analysis: `10.1038/s41591-024-02996-7`
- Obesity cardiometabolic cohort: `10.3390/jcm15124421`
- HFrEF cohort: `10.3390/ph19060894`
- PMOS cohort: `10.3390/jcm15135165`
- Tirzepatide comparison: `10.1093/pnasnexus/pgag171`
- Waist-circumference synthesis: `10.1016/j.obpill.2026.100281`
- Liraglutide fitness analysis: `10.1007/s40279-025-02386-0`
- GLIDE pilot: `10.1038/s41366-023-01368-4`

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

The initial record-to-source review and the first durability/safety follow-up
are complete. The bounded map still has explicit work before broader
analytical intelligence:

1. Replicate and extend post-discontinuation trajectories across agents,
   treatment durations, and longer follow-up.
2. Add newer safety syntheses while preserving event severity, dose, duration,
   and population differences.
3. Expand agent and population coverage without collapsing drug, dose,
   formulation, duration, or eligibility differences.
4. Rerun the documented same-PICO contradiction search as new trials mature or
   the map's direct PICO changes; preserve future negative results honestly.
5. Route disputed records and substantive future changes through another
   traceable review; human domain-expert adjudication remains available where
   the scientific stakes or disagreement warrant it.

The reviewed map is now an evaluated foundation for closing those coverage
gaps, structured cross-study comparison, and a traceable public demonstration.
It still is not a declaration of scientific truth.
