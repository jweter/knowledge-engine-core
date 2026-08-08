# GLP-1 Golden Map Gap-Closure: Post-Bariatric Agent Coverage and Real-World Adherence

## Decision

The reviewed GLP-1/body-weight golden evidence map now includes two further
bounded qualifiers, promoted from the corpus's existing evidence-promotion
backlog rather than newly acquired:

1. a single-arm, uncontrolled tirzepatide cohort in adults with recurrent
   weight gain after bariatric surgery or endoscopic bariatric therapy; and
2. a large real-world retrospective cohort relating baseline comorbidities and
   digestive-system adverse events to first-year GLP-1 receptor agonist
   adherence.

These records extend agent and population coverage and add a real-world
tolerability lens. They do not establish a tirzepatide efficacy claim
comparable to STEP 5, recompute a class-wide safety conclusion, or resolve
the map's still-open post-discontinuation-trajectory or safety-synthesis gaps
in full. This is a bounded, partial gap closure, addressing pieces of the
`docs/glp1_body_weight_golden_evidence_map.md` "Remaining Work" items 2 and 3;
item 1 (longer/more-agent withdrawal trajectories) remains open.

## Sources

### Tirzepatide Post-Bariatric Cohort

*Tirzepatide for Recurrent Weight Gain after Bariatric Procedures: Real-World
Evidence of Efficacy and Safety*, DOI `10.1007/s11695-026-08754-7`, was
already present in the corpus's evidence-promotion backlog
(`ev-tirzepatide-post-bariatric-weight-regain-001`,
`extraction_method: manual_human_review`) at `review_status: draft`. The
legally usable local PDF (`papers/corpora/glp1_weight_loss/PMC13323781.pdf`)
was re-read directly and its page-1 abstract/results text confirmed the
record's claimed mean %TBWL of `18.1 +/- 5.6%` (p < 0.0001) and waist
circumference finding before promotion.

### GLP-1RA Adherence and Comorbidity Predictors

*Association of Baseline Comorbidities With First-Year Adherence to GLP-1
Receptor Agonists in Patients With Diabetes or Obesity: A Retrospective
Cohort Study*, DOI `10.1177/10600280251384637`, was already present in the
corpus's evidence-promotion backlog
(`ev-glp1ra-adherence-comorbidity-predictors-001`,
`extraction_method: manual_human_review`) at `review_status: draft`. The
legally usable local PDF (`papers/corpora/glp1_weight_loss/PMC13332170.pdf`)
was re-read directly and its page-1 text confirmed the record's claimed odds
ratios for atherosclerotic cardiovascular disease (OR 0.90, 95% CI 0.86-0.95)
and digestive-system adverse events (OR 0.94, 95% CI 0.90-0.98) before
promotion.

No new PDF was downloaded for this round; both files were already present in
the corpus's gitignored local `papers/` tree from prior acquisition.

## Evidence Record Promotion

Both records were previously `review_status: draft`, pending "independent
secondary review before use as reviewed evidence" per their own
`review_notes`. This round performed that secondary review: each record's
`provenance.secondary_review` block was completed
(`reviewer_type: ai_assisted_independent_source_audit`,
`review_date: 2026-08-08`, `outcome: accepted`, no corrections), each
`review_checklist.secondary_review_completed` was set `true`, and
`review_status` was promoted to `reviewed`, matching the exact pattern used
for every other record already selected into this map.

## Relationships

Two new reviewed relationships connect the promoted records without
reclassifying their design or population as directly comparable to the map's
landmark semaglutide trials:

- `rel-glp1-tirzepatide-postbariatric-contextualizes-001`: the tirzepatide
  post-bariatric cohort `contextualizes` STEP 5's week-104 body-weight result.
  Different drug class (dual GIP/GLP-1 vs. GLP-1-only), different population
  (post-bariatric weight regain vs. treatment-naive), no concurrent control,
  and a much shorter 24-week window.
- `rel-glp1-adherence-comorbidity-safety-qualifies-001`: the adherence cohort
  `qualifies` the Gao safety/discontinuation record. Adherence is a real-world
  tolerability proxy, not a trial discontinuation-due-to-adverse-event rate;
  the comparator is presence versus absence of comorbidity within one treated
  cohort, not a placebo or active-drug arm.

## Review Status

Both Evidence Records and both Relationship Records were independently
audited against the legally usable local PDFs and carry
`ai_assisted_independent_source_audit` provenance dated 2026-08-08. This is
source-fidelity review, not human domain-expert approval, independent
statistical reanalysis, scientific synthesis, consensus, confidence scoring,
or truth determination.

## Remaining Gaps

- Longer and independently replicated post-discontinuation trajectories
  across agents remain represented by only one exploratory STEP 1 extension;
  this round added agent/safety context, not a second withdrawal
  observation.
- Broader agent-level coverage is still bounded to one uncontrolled
  tirzepatide cohort; it is not a randomized or placebo-controlled result.
- The adherence cohort's odds ratios describe first-year medication
  adherence, not adjudicated adverse-event rates; it does not replace a
  current class-wide safety synthesis.
- A sufficiently aligned contradictory result, if one exists, was not
  searched for again in this round; the 2026-08-04 bounded search remains the
  most recent same-PICO contradiction audit.

## Validation

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

Validation checks structure, review state, references, and citation
traceability. It does not grant legal approval or infer a scientific
conclusion.
