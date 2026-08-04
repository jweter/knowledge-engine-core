# GLP-1 SELECT Statistical Input Plan

**Status:** Completed. The next bounded STEP 5 interval-approximation contract
is documented in `docs/glp1_confidence_interval_approximation_plan.md`.

## Decision

Expand the version 1 typed statistical-input pilot from STEP 5 to SELECT while
preserving one supported formula: intervention mean change minus comparator
mean change.

The SELECT statistical input will carry its own source locator. A statistical
input's locator must identify the page that supports all declared formula
inputs and the reported effect; it is not required to equal the referenced
Evidence Record's claim locator.

## Source-Audit Finding

The reviewed SELECT Evidence Record points to page 1, `Abstract`. That locator
supports the abstract-level claim and its two reported arm means. The complete
statistical identity used here is reported elsewhere:

- page 4 reports semaglutide `-10.2%`, placebo `-1.5%`, treatment difference
  `-8.7` percentage points, 95% CI `-9.42` to `-7.88`, and `P < 0.0001`;
- page 2 tabulates the same values in Figure 1 context; and
- page 10 defines the in-trial analysis as intention-to-treat, including all
  randomized participants irrespective of adherence or background-medication
  changes.

The Evidence Record is not wrong and will not be rewritten: claim provenance
and statistical-input provenance are distinct locators over the same source.
Forcing them to share a page would make the typed contract less accurate.

## Objective

Add one source-verified SELECT record to:

```text
data/corpora/glp1_weight_loss/statistical_inputs.jsonl
```

Then verify both committed records with:

```text
ke statistical-verify \
  data/corpora/glp1_weight_loss/statistical_inputs.jsonl \
  --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl
```

Expected deterministic results:

```text
STEP 5: -15.2 - (-2.6) = -12.6 percentage points
SELECT: -10.2 - (-1.5) = -8.7 percentage points
```

Both should be `consistent` with an absolute difference of zero.

## Independent Locator Contract

Version 1 continues to require:

- a known reviewed `evidence_record_id`;
- a normalized DOI matching the Evidence Record;
- the supported body-weight outcome;
- a complete typed-input `source_span`;
- source-verified curation provenance; and
- explicit formula inputs, time point, analysis population, unit, reported
  effect, tolerance, and optional reported confidence interval.

The Evidence Record must retain its own valid source span, but the verifier
will no longer require the typed-input page and section to equal it. This is a
deliberate provenance rule, not relaxed validation:

- Evidence Record locator: supports the reviewed scientific claim.
- Statistical input locator: supports every numerical value used in the
  arithmetic check.

The DOI and Evidence Record identity continue to bind both artifacts to the
same source. A typed locator remains manually reviewed and is never inferred.

## SELECT Typed Values

The committed record will declare:

- Evidence Record: `ev-glp1-select-trial-weight-loss-208wk-001`;
- DOI: `10.1038/s41591-024-02996-7`;
- outcome: `body_weight_change_from_baseline`;
- unit: `percentage_points`;
- time point: 208 weeks;
- analysis population: in-trial intention-to-treat analysis including all
  randomized participants irrespective of adherence or background-medication
  changes;
- intervention: semaglutide 2.4 mg once weekly, mean change `-10.2`;
- comparator: placebo, mean change `-1.5`;
- reported effect: `-8.7`;
- reported 95% CI: `-9.42` to `-7.88`;
- formula: `intervention_minus_comparator`;
- tolerance: `0.05`; and
- primary locator: page 4, Results / Change in body weight, with Figure 1 and
  the page-10 estimand definition noted in the locator text.

No sample size, standard error, variance, or confidence-interval formula input
will be invented. The reported interval remains display-only.

## Code Scope

Update `knowledge_engine/statistical_verification.py` only to separate the two
locator responsibilities:

- continue requiring a valid Evidence Record source span;
- stop comparing its page and section with the typed statistical locator; and
- keep every identity, review, DOI, outcome, numerical, and provenance check.

No new effect measure, formula, CLI option, output format, dependency, database
table, or parser behavior is needed.

## Testing

Add or update tests proving:

- a typed locator may differ from the referenced claim locator;
- a referenced Evidence Record still must have a source span;
- DOI, review status, outcome, and identity mismatches remain blocking;
- the committed file contains STEP 5 followed by SELECT;
- both recomputed effects are exact Decimals;
- both statuses are `consistent`;
- both reported confidence intervals remain display-only;
- output order follows JSONL order;
- terminal and file output remain deterministic;
- no database is created or modified; and
- all previous discrepancy, malformed-input, duplicate-key, escaping, and
  overwrite tests continue to pass.

## Documentation Updates

Update README, corpus documentation, roadmap, Analytical Intelligence
architecture, golden-map documentation, documentation index, interface
contract, and changelog to record:

- two verified direct randomized body-weight identities;
- the independent statistical-locator rule;
- the exact SELECT arithmetic result; and
- the remaining confidence-interval prerequisite.

## Trust Boundaries

This milestone does not:

- parse numbers from Evidence Record prose;
- change the reviewed SELECT claim or its relationships;
- recompute either reported confidence interval;
- compare the clinical magnitude of STEP 5 and SELECT;
- harmonize their populations, estimands, follow-up durations, or trial goals;
- pool effects or perform sensitivity analysis or meta-analysis;
- revise Evidence Quality, Consensus, or Claim Confidence;
- use an LLM; or
- determine scientific validity, replication, clinical guidance, or truth.

Arithmetic agreement remains only a check that declared inputs reproduce a
declared reported effect under a declared formula and tolerance.

## Success Criteria

The milestone succeeds when:

- SELECT is represented with independently source-audited numerical context;
- its reported `-8.7` percentage-point difference is reproduced exactly;
- STEP 5 remains unchanged and still verifies exactly;
- typed and claim locator responsibilities are explicit and tested;
- no reviewed scientific content is silently rewritten;
- the complete repository quality gate passes; and
- PR and post-merge `main` checks pass.

## Next Handoff

After STEP 5 and SELECT both verify, design the first confidence-interval
recomputation contract. Begin only with an effect whose standard error or
equivalent variance inputs, group sizes, analysis method, confidence level, and
critical-value assumptions are explicitly source-audited. If those ingredients
are not all available, stop rather than reverse-engineering them from a rounded
reported interval.
