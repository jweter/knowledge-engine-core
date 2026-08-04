# GLP-1 Golden Map Durability and Safety Qualifiers

## Decision

The reviewed GLP-1/body-weight golden evidence map now includes two bounded
qualifiers that were missing from its first version:

1. direct body-weight follow-up for one year after semaglutide and structured
   lifestyle-intervention withdrawal; and
2. pooled adverse-event and treatment-discontinuation estimates from
   semaglutide randomized trials in adults with overweight or obesity without
   diabetes.

These records make durability and tolerability visible beside continued-use
efficacy. They do not calculate a benefit-harm balance, recommend treatment,
or establish class-wide safety.

## Sources

### STEP 1 Withdrawal Extension

Wilding et al., *Weight regain and cardiometabolic effects after withdrawal of
semaglutide: The STEP 1 trial extension*, DOI `10.1111/dom.14725`, is available
through PubMed Central (`PMC9542252`) under CC BY.

The local ignored PDF came from the PMC Open Access S3 object already identified
by the PMC record. Its MD5 matched the S3 ETag
`dd5ba41fd601c4ac0cc759c42a597866`; its SHA-256 is recorded in `sources.csv`.

### Semaglutide Safety Meta-Analysis

Gao et al., *Efficacy and safety of semaglutide on weight loss in obese or
overweight patients without diabetes*, DOI `10.3389/fphar.2022.935823`, was
already a curated CC BY source in the corpus. The new record uses the adverse
event analysis from its legally usable local publisher PDF.

No PDF is committed. No URL was followed by application code.

## Evidence Records

`ev-glp1-step1-withdrawal-weight-regain-001` records the exploratory extension's
observed body-weight trajectory. During the 52 weeks after withdrawal, the
prior semaglutide group regained 11.6 percentage points and the prior placebo
group regained 1.9 percentage points. Net changes from baseline at week 120
were -5.6% and -0.1%, respectively.

The boundary is essential: the extension followed selected STEP 1 completers;
both study treatment and structured lifestyle intervention ended; analyses
were exploratory; other lifestyle participation was not recorded; and no
systematic adverse-event collection occurred during the extension.

`ev-glp1-gao-meta-analysis-safety-discontinuation-001` records pooled risk
ratios for adverse events (1.10), serious adverse events (1.34), adverse events
leading to discontinuation (2.29), nausea (2.58), and diarrhea (2.01), with no
difference in hypoglycemia (0.94; 95% CI 0.66 to 1.34).

That record preserves high heterogeneity for any adverse event, variation in
dose and duration, the review's limited study set, and the difference between
aggregate event incidence and an individual benefit-harm decision.

## Relationships

Three reviewed relationships connect the qualifiers without changing what the
underlying studies measured:

- STEP 1 withdrawal `contextualizes` STEP 5 continued-treatment efficacy;
- Gao safety outcomes `qualify` Gao body-weight efficacy; and
- Gao safety outcomes `qualify` STEP 5 body-weight efficacy while retaining
  dose, duration, and included-trial differences.

Withdrawal does not contradict on-treatment efficacy because the treatment
window changes. Safety outcomes do not negate efficacy outcomes, and the graph
does not compute whether benefits outweigh harms.

## Review Status

Both Evidence Records and all three Relationship Records were independently
audited against legally usable local PDFs and carry
`ai_assisted_independent_source_audit` provenance. This is source-fidelity
review, not human domain-expert approval, independent statistical reanalysis,
scientific synthesis, consensus, confidence scoring, or truth determination.

## Remaining Gaps

- Longer post-withdrawal follow-up and replication across other agents,
  treatment durations, and populations.
- Newer safety syntheses that preserve dose, duration, event severity, and
  agent-level differences.
- Direct evidence about access, cost, patient preference, and treatment
  decisions.
- A sufficiently aligned contradictory result, if one exists.

## Validation

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
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
