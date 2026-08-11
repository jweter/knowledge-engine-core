# GLP-1 Statistical Readiness Compatibility Analysis

## Status

Approved pre-implementation review note.

This file records the expected compatibility decision before the final coding implementation. The runtime command must validate these assumptions from structured, already-curated inputs and must not infer missing values from prose.

## Nearest Potential Pooling-Design Group

Provisional group:

`semaglutide_placebo_percent_body_weight_change`

Members:

- STEP 5 week 104
- SELECT week 208

Shared characteristics:

- randomized semaglutide 2.4 mg versus placebo;
- continuous percentage body-weight change;
- reported intervention-minus-comparator treatment difference;
- source-audited typed arithmetic inputs; and
- no unresolved arithmetic discrepancy.

Material differences:

| Dimension | STEP 5 | SELECT | Current decision |
| --- | --- | --- | --- |
| Time point | 104 weeks | 208 weeks | not directly pooling-compatible under the current strict gate |
| Analysis population | treatment-policy estimand | in-trial intention-to-treat | estimand/analysis-population mismatch |
| Missing-data/model context | ANCOVA plus multiple-imputation context | in-trial analysis | not harmonized |
| Independent variance check | explicit arm SEs available | arm SEs unavailable | insufficient shared variance basis |
| CI verification status | bounded project approximation | source CI display-only | asymmetric verification depth |

Provisional pair status:

`no`

This does not mean the studies could never appear in the same future synthesis. It means the repository is not currently justified in treating them as a ready-to-pool pair.

## STEP 5 Verification Facets

STEP 5 must not be flattened to a single statistical label.

Its current structured verification contains three distinct facets:

1. exact arithmetic reproduction of the reported continuous treatment difference;
2. bounded independent-arm normal approximation of the confidence interval, explicitly not a reconstruction of the source model; and
3. a project-derived crude binary risk ratio and log-Wald interval that are explicitly not equivalent to the source-adjusted odds ratio.

The primary Evidence Record readiness category is `exactly_verified`, while the generated report must preserve the additional bounded and non-equivalent facets.

## SELECT Verification Facets

SELECT contains:

1. exact arithmetic reproduction of the week-208 treatment difference; and
2. a source-reported confidence interval that remains display-only because the necessary numerical arm standard errors or equivalent variance terms are unavailable.

## Binary Evidence

Only one production binary typed input currently exists:

- STEP 5 achievement of at least 5% weight loss at week 104.

Therefore binary pooling design cannot satisfy the minimum requirement of two independent source-audited primary studies.

The prior zero-cell audit identified a genuine GLIDE nausea result, but no matching reviewed Evidence Record existed for that outcome. No production zero-cell binary input was added.

## Source Meta-Analysis Records

The Gao body-weight and safety Evidence Records and the waist-circumference synthesis are already pooled source publications.

They must not be mixed into a new primary-study pooling input set as if they were independent trials. Doing so would risk double counting and would cross the current architecture's evidence boundaries.

## Other Reviewed Golden-Map Records

The remaining records serve durability, safety, population-extension, active-comparator, endpoint, or agent/population qualifier roles.

They are scientifically relevant to the map but are not currently a homogeneous pool-ready statistical set.

## Deterministic Readiness Verdict

Expected current verdict:

`not_ready_for_pooling_design`

### Primary blockers

1. No pair of independently source-audited primary-study inputs currently satisfies the complete compatibility gate.
2. STEP 5 and SELECT differ materially in time point and estimand/analysis population.
3. SELECT lacks the explicit numerical variance ingredients needed for the same deterministic uncertainty check available for STEP 5.
4. Only one production binary statistical input exists.
5. Several reviewed records are observational, uncontrolled, active-comparator, different-agent, different-outcome, or meta-analytic records.
6. Existing source meta-analyses must not be double-counted as independent primary evidence.

## Recommended Post-Step-2 Direction

If the implemented readiness command reproduces this verdict, choose the smallest source-audit blocker rather than forcing pooling.

A strong next target would be a second independent primary randomized semaglutide-versus-placebo body-weight result with:

- explicit percentage-change effect in the same effect-measure family;
- clearly defined estimand;
- sufficiently aligned time point;
- explicit numerical variance inputs;
- no known population overlap with the selected primary study;
- matching reviewed Evidence Record identity; and
- legally usable source provenance.

Do not design pooling until the readiness gate can identify at least two genuinely compatible candidates.

## 2026-08-10 search: no legally usable second candidate found

Searched PubMed/PMC/Europe PMC specifically for a second independent primary
semaglutide-vs-placebo body-weight RCT per the criteria above. Result: a
genuine, well-investigated dead end, not an unexplored gap.

- **STEP 1's own primary result** (Wilding et al. 2021, NEJM,
  PMID 33567185, [10.1056/NEJMoa2032183](https://doi.org/10.1056/NEJMoa2032183))
  -- the corpus already holds only STEP 1's withdrawal-extension record
  (`ev-glp1-step1-withdrawal-weight-regain-001`), not this primary
  68-week result -- has no PMC record at all (NEJM, closed).
- **STEP 7's China-subpopulation analysis** (Gu et al. 2025, Diabetes Obes
  Metab, PMID 40069849, PMC11964988,
  [10.1111/dom.16253](https://doi.org/10.1111/dom.16253)) -- a real,
  independent 44-week semaglutide-vs-placebo result (ETD -8.3%-points,
  95% CI -10.2 to -6.4) with no population overlap with STEP 5/SELECT --
  is CC BY-NC, which this project's license policy rejects.
- Two pooled/secondary STEP analyses returned genuine CC BY licenses
  (PMID 36467859, C-reactive protein across STEP 1/2/3; PMID 39756397,
  antihypertensive/lipid-lowering medication use across five STEP
  trials), but neither is itself an independent primary body-weight
  result, and the CRP paper shares STEP 1's population, already
  represented in the corpus -- both excluded by this document's own
  "existing source meta-analyses/pooled analyses must not be
  double-counted as independent primary evidence" rule.
- Two genuine CC BY network meta-analyses (PMID 41992023, PMID 41111360)
  were found but are meta-analyses, not primary trials, and excluded by
  the same rule.
- A broader 2023+ sweep of "semaglutide obesity randomized placebo
  primary results" (15 candidates checked) and a "STEP 2/STEP 3" sweep
  (6 candidates checked) found no further genuine CC BY primary-trial
  candidates -- the pattern (large industry-sponsored RCTs publish in
  closed venues; the rare open ones are CC BY-NC/-ND or are themselves
  pooled/meta-analytic, not primary) closely mirrors the oncology
  corpus's PACIFIC-trial investigation the same day (see
  `docs/roadmap.md`'s 2026-08-10 update).

This remains `not_ready_for_pooling_design` on a genuinely verified basis:
the blocker is not that nobody looked, but that no legally usable second
primary candidate currently exists. Re-run this search periodically, the
same way the corpus's contradiction searches are periodically rerun --
new STEP-family or competitor trials publish regularly, and a future
one may clear this bar.
