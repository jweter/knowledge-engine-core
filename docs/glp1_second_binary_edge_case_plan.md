# GLP-1 Second Binary Edge-Case Source Audit

## Status

Source audit complete.

Decision: **audit-only milestone; no production binary schema extension is justified under the current evidence contract.**

The audit identified real single-zero-cell binary outcomes in legally usable source literature, but no candidate satisfied every eligibility requirement for a committed production binary statistical input because no qualifying zero-cell outcome had an existing reviewed Evidence Record with matching outcome identity.

The current binary schema version 1 remains unchanged.

---

## Purpose

This milestone tested whether the existing deterministic binary statistical verification contract could be extended under genuine source pressure.

The preferred candidate was a source-audited binary result with:

- exactly one zero-event arm;
- nonzero denominators in both arms;
- explicit source-reported event counts;
- a meaningful binary contrast;
- an existing reviewed Evidence Record with matching DOI and result identity;
- legally usable source provenance; and
- enough methodological context to label any deterministic calculation honestly.

The milestone explicitly prohibited:

- inferring event counts from rounded percentages;
- inventing denominators;
- treating a different outcome from the same paper as already reviewed;
- modifying `evidence_records.jsonl` merely to make a candidate eligible;
- selecting a continuity correction merely because it produces convenient output; and
- introducing generic statistical machinery without a source-supported production case.

---

## Existing Binary Contract

Binary statistical input schema version 1 currently supports only:

- `effect_measure = crude_risk_ratio`;
- `method = crude_risk_ratio_log_wald`;
- `continuity_correction = none`;
- `continuity_correction_value = 0`;
- positive event counts in both treatment arms;
- fixed 95% confidence level;
- fixed normal critical value 1.96; and
- deterministic `Decimal` arithmetic.

Because events must be positive in both arms, schema version 1 cannot represent a result where either arm has zero events.

This was the real contract limitation investigated by this audit.

---

## Reviewed Evidence Population

The source audit was bounded to the reviewed GLP-1/body-weight golden evidence map and its legally usable source publications.

The reviewed map includes:

- STEP 5 long-term semaglutide trial;
- STEP 1 withdrawal extension;
- SELECT long-term semaglutide analysis;
- Gao et al. semaglutide systematic review/meta-analysis;
- Gao et al. safety/discontinuation Evidence Record;
- semaglutide obesity/cardiometabolic observational evidence;
- semaglutide HFrEF observational evidence;
- tirzepatide-versus-semaglutide comparative evidence;
- waist-circumference meta-analysis;
- liraglutide physical-fitness randomized evidence;
- GLIDE liraglutide post-gastric-banding pilot RCT;
- additional reviewed population and endpoint qualifiers.

The audit remained bounded to the source identities and outcome boundaries already represented by reviewed Evidence Records.

---

## Candidate Audit

### 1. STEP 5

**Source**

Garvey WT, et al.  
*Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5 trial.*  
Nature Medicine. 2022.  
DOI: `10.1038/s41591-022-02026-4`

**Relevant reviewed Evidence Record**

`ev-glp1-step5-body-weight-week104-001`

**Reviewed outcome**

Percentage change in body weight at week 104.

**Binary source results inspected**

STEP 5 provides explicit responder counts for body-weight thresholds, including:

- at least 5% weight loss: `111/144` semaglutide versus `44/128` placebo;
- at least 10% weight loss: `89/144` versus `17/128`;
- at least 15% weight loss: `75/144` versus `9/128`;
- at least 20% weight loss: `52/144` versus `3/128`.

All candidate weight-response comparisons have nonzero event counts in both arms.

The publication also contains safety outcomes with zero-event cells, but those outcomes are not the reviewed body-weight result represented by the existing STEP 5 Evidence Record.

**Decision**

Not selected.

Reason:

- body-weight binary responder outcomes do not exercise a zero-cell limitation; and
- unrelated safety outcomes must not silently inherit the body-weight Evidence Record's review status.

---

### 2. SELECT

**Source**

Ryan DH, et al.  
*Long-term weight loss effects of semaglutide in obesity without diabetes in the SELECT trial.*  
Nature Medicine. 2024.  
DOI: `10.1038/s41591-024-02996-7`

**Relevant reviewed Evidence Record**

`ev-glp1-select-trial-weight-loss-208wk-001`

**Reviewed outcome**

Long-term body-weight and anthropometric change through week 208.

**Binary source result inspected**

Trial-product discontinuation:

- semaglutide: `1,461` participants, `16.6%`;
- placebo: `718` participants, `8.2%`.

Both arms contain nonzero events.

The reviewed Evidence Record is also a weight/anthropometric Evidence Record rather than a dedicated discontinuation Evidence Record.

**Decision**

Not selected.

Reason:

- no zero-event cell; and
- the inspected safety/discontinuation result is not the same reviewed outcome identity.

---

### 3. Gao et al. safety/discontinuation meta-analysis

**Source**

Gao X, et al.  
*Efficacy and safety of semaglutide on weight loss in obese or overweight patients without diabetes: A systematic review and meta-analysis of randomized controlled trials.*  
Frontiers in Pharmacology. 2022.  
DOI: `10.3389/fphar.2022.935823`

**Relevant reviewed Evidence Record**

`ev-glp1-gao-meta-analysis-safety-discontinuation-001`

**Reviewed outcome**

Pooled adverse events, serious adverse events, adverse events leading to discontinuation, nausea, diarrhea, and hypoglycemia.

**Relevant reported estimates**

The Evidence Record preserves pooled source-reported risk ratios, including:

- adverse events;
- serious adverse events;
- adverse events leading to discontinuation;
- nausea;
- diarrhea; and
- hypoglycemia.

**Decision**

Not selected.

Reason:

The reviewed result is already a pooled meta-analytic estimate rather than the simple source-level two-arm count structure used by the current deterministic binary input contract.

Adapting the milestone around trial extraction from a meta-analysis would expand scope toward pooled evidence architecture rather than cleanly test the current single-result zero-cell limitation.

---

### 4. GLIDE

**Source**

Coelho C, et al.  
*Laparoscopic adjustable gastric banding with liraglutide in adults with obesity and type 2 diabetes (GLIDE): a pilot randomised placebo controlled trial.*  
International Journal of Obesity. 2023.  
DOI: `10.1038/s41366-023-01368-4`

**Relevant reviewed Evidence Record**

`ev-glp1-glide-liraglutide-post-lagb-weight-001`

**Reviewed outcome**

Between-group body-weight difference after laparoscopic adjustable gastric banding.

**Trial population**

Randomized:

- liraglutide: `n = 13`;
- placebo: `n = 14`.

The trial was substantially underpowered relative to its planned enrollment.

**Single-zero-cell results identified**

Table 3 contains multiple explicit patient-level binary adverse-event outcomes with exactly one zero-event arm.

Examples include:

- nausea: `6/13` liraglutide versus `0/14` placebo;
- constipation: `1/13` versus `0/14`;
- gastro-oesophageal reflux: `0/13` versus `2/14`;
- loss of appetite: `2/13` versus `0/14`;
- bloating: `1/13` versus `0/14`;
- dry mouth: `1/13` versus `0/14`.

A further patient-level row reports surgery-related adverse events with a zero placebo arm.

**Preferred mathematical candidate**

Nausea:

- liraglutide: `6/13`, reported `46.2%`;
- placebo: `0/14`, reported `0%`.

This result is an excellent mathematical zero-cell test case because:

1. exactly one arm has zero events;
2. both denominators are explicit;
3. source counts are explicit;
4. source percentages are explicit;
5. no count reconstruction is required;
6. the binary outcome is clinically recognizable; and
7. a naive risk-ratio log-Wald calculation is undefined without an explicit zero-cell policy.

**Eligibility failure**

The existing reviewed GLIDE Evidence Record represents body weight.

It does **not** represent nausea, gastrointestinal adverse events, or treatment safety.

The current milestone requires an existing reviewed Evidence Record with matching source and result identity.

The milestone also explicitly forbids modifying `evidence_records.jsonl` merely to make a candidate eligible.

**Decision**

Scientifically suitable zero-cell case found, but **not eligible for a committed production binary input under the current evidence contract**.

---

### 5. Other reviewed sources

Other reviewed randomized, observational, active-comparator, withdrawal, and synthesis records were inspected for obvious qualifying binary structures.

No candidate was identified that simultaneously provided:

- exactly one zero-event arm;
- explicit counts and denominators;
- a meaningful binary contrast;
- a matching reviewed Evidence Record for that same outcome;
- legally usable source provenance; and
- compatibility with the existing deterministic single-result verification boundary.

---

## Source-Audit Decision

### Scientific candidate

**Found.**

Best source-level zero-cell example:

GLIDE nausea:

- liraglutide: `6/13`;
- placebo: `0/14`.

### Production-eligibility candidate

**Not found.**

The GLIDE nausea result lacks a matching reviewed Evidence Record.

No other inspected reviewed outcome supplied an equally defensible single-zero-cell production case.

---

## Decision Gate Outcome

Decision Rule C applies:

> No defensible second production result satisfies the complete eligibility contract.

Therefore this milestone stops after documenting the audit.

Do **not**:

- add binary schema version 2;
- change schema version 1 semantics;
- add a continuity-correction method;
- append a GLIDE nausea production record;
- modify the existing GLIDE body-weight Evidence Record;
- infer that paper-level review implies review of every result in that paper;
- add generic zero-cell statistical machinery; or
- create a synthetic example solely to exercise code.

The existing version 1 binary contract remains unchanged.

---

## Why This Is a Successful Milestone

The audit produced a useful architectural finding even though no new statistical calculation is committed.

The system encountered a genuine real-world numerical limitation:

> a reviewed source publication contains a valid zero-cell binary result that the current statistical verifier cannot calculate.

The system also encountered an upstream evidence-boundary limitation:

> the publication is reviewed for a different outcome, so paper identity alone is not sufficient to authorize the new result as reviewed evidence.

The correct behavior is to refuse to weaken that trust boundary merely to make the statistical contract more general.

This is evidence that the architecture is failing closed as intended.

---

## Statistical Method Not Implemented

Because no qualifying production record exists, no continuity-correction contract is adopted in this milestone.

The candidate method considered in planning was a declared constant added to every cell of a 2x2 table, producing corrected arm risks such as:

`risk1 = (a + correction) / (n1 + 2 * correction)`

`risk0 = (c + correction) / (n0 + 2 * correction)`

and a corrected crude risk ratio:

`RR = risk1 / risk0`

No value, policy name, or formula is promoted into the production contract by this audit.

Any future zero-cell implementation must independently document:

- the exact method name;
- why the method is appropriate for the bounded use case;
- correction value;
- event and non-event transformation;
- confidence-interval method;
- limitations;
- whether the calculation is source-reported or project-derived; and
- why schema version 1 remains unchanged.

---

## Raw Versus Derived Boundary

The source-audit findings must preserve these distinctions:

### Source-reported

Examples:

- GLIDE randomized arm sizes;
- GLIDE nausea counts;
- GLIDE reported percentages;
- source-reported study methods;
- source-reported pooled or adjusted estimates.

### Project-derived

Potential future calculations such as:

- corrected crude risks;
- corrected crude risk ratio;
- corrected log-risk-ratio standard error;
- corrected confidence interval.

No project-derived zero-cell value is committed in this milestone.

---

## Evidence Boundary

A scientific publication is not equivalent to one Evidence Record.

One publication may contain:

- efficacy outcomes;
- safety outcomes;
- subgroup analyses;
- adverse events;
- discontinuation;
- secondary endpoints; and
- multiple statistical estimands.

Review of one bounded Evidence Record does not automatically review every other result in the same publication.

This audit therefore reinforces the need for a future first-class Paper Record layer with section-level provenance and multiple Evidence Records per publication.

That future architecture is separate from this statistical milestone.

---

## Legal Provenance

The candidate sources inspected were limited to legally usable sources represented by the curated corpus and reviewed evidence-map process.

No PDF should be committed to Git as part of this milestone.

Source PDFs remain local and excluded from version control according to repository practice.

---

## Explicit Non-Goals

This milestone does not:

- establish treatment truth;
- establish scientific consensus;
- compare overall treatment safety;
- calculate benefit-harm;
- pool studies;
- perform meta-analysis;
- rank GLP-1 therapies;
- infer missing event counts;
- create new reviewed evidence;
- modify Evidence Quality;
- modify Evidence Consensus;
- modify Claim Confidence;
- provide clinical guidance;
- add AI narration; or
- implement a general statistical library.

---

## Success Criteria

This audit is successful if:

- reviewed source candidates were inspected;
- actual source tables and methods were used where necessary;
- at least one genuine zero-cell source result was identified;
- event counts were not inferred from percentages;
- the evidence-identity mismatch was recognized;
- no Evidence Record was modified to force eligibility;
- no unsupported schema extension was introduced;
- version 1 behavior remains unchanged;
- the decision is documented reproducibly; and
- the next milestone can reason from an honest inventory of what is and is not statistically verified.

These criteria are satisfied by the audit decision recorded here.

---

## Next Handoff

Proceed to the **Statistical Verification Readiness Gate**, with the prerequisite updated to recognize this milestone's documented stop-rule outcome.

The readiness gate should treat the current binary state as:

- first binary verification: implemented and source-audited;
- second binary edge-case investigation: completed as an audit-only milestone;
- zero-cell support: not implemented;
- zero-cell limitation: demonstrated by real source evidence;
- matching reviewed production input: unavailable under the current evidence contract.

The readiness gate should determine:

- which reviewed Evidence Records are exactly verified;
- which are bounded approximations;
- which derived values are not source-equivalent;
- which remain display-only;
- which lack adequate numerical detail;
- what statistical compatibility exists;
- whether enough independently source-audited evidence exists to begin a pooling-protocol design; and
- what blockers must be resolved before broader analytical intelligence.

If the readiness assessment concludes that pooling design is not justified, the next milestone must address the smallest named blocker rather than forcing pooling.

---

## Final Decision

**Zero-cell source example:** found.

**Preferred example:** GLIDE nausea, `6/13` versus `0/14`.

**Matching reviewed Evidence Record:** not present.

**Schema version 2:** not justified.

**Continuity correction:** not implemented.

**Production binary input:** not added.

**Version 1 semantics:** preserved.

**Milestone disposition:** complete as a documented source-audit stop-rule outcome.
