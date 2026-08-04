# GLP-1 Binary-Outcome Verification Plan

## Status

Completed implementation plan for the first source-audited binary-outcome
calculation in the GLP-1 body-weight evidence map.

## Objective

Add one deterministic check for the STEP 5 week-104 co-primary responder
outcome: achievement of at least 5% body-weight loss. The check will verify the
two reported arm percentages from explicit event counts and denominators, then
calculate a crude risk ratio and a two-sided 95% log-Wald confidence interval.

This is a count-based descriptive calculation over observed week-104
participants. It is not a reconstruction of STEP 5's treatment-policy
estimand, logistic-regression model, baseline-covariate adjustment, multiple
imputation, or multiplicity control.

## Source Audit

The legally usable STEP 5 publisher PDF for DOI
`10.1038/s41591-022-02026-4` reports:

- page 1: 152 randomized participants per arm and the co-primary responder
  percentages, 77.1% versus 34.4%;
- page 4: the observed week-104 denominators, 144 semaglutide and 128 placebo,
  plus the distinction between observed proportions and the treatment-policy
  analysis;
- page 5, Table 2: 111/144 (77.1%) versus 44/128 (34.4%), with a reported
  adjusted odds ratio of 5.0 (95% CI 3.0 to 8.4); and
- pages 4 and 6: logistic regression with baseline body weight as a covariate,
  multiple imputation for missing data, two-sided 95% intervals, and
  multiple-comparison control for the co-primary endpoint.

The raw counts do not reproduce the paper's adjusted odds ratio. The count
contract must therefore calculate a differently named crude risk ratio and
show the adjusted odds ratio only as source-reported, display-only context.

## Command And File Boundary

Keep `ke statistical-verify` as the user-facing command, but load the binary
record from a separate file:

```text
data/corpora/glp1_weight_loss/binary_statistical_inputs.jsonl
```

The continuous-outcome file retains statistical-input schema versions 1 and 2
unchanged. The binary file starts its own schema version 1 because event-count
validation, zero-cell behavior, estimands, and interval assumptions are not
the same contract as adjusted mean-change arithmetic.

The CLI accepts the optional flag:

```text
ke statistical-verify statistical_inputs.jsonl \
  --evidence evidence_records.jsonl \
  --binary-inputs binary_statistical_inputs.jsonl
```

Omitting `--binary-inputs` preserves all existing output and behavior.

## Binary Input Contract

Each record declares:

- `schema_version`: integer `1`;
- stable `binary_input_id`;
- reviewed `evidence_record_id` and normalized source DOI;
- `review_status`: `source_verified`;
- `effect_measure`: `crude_risk_ratio`;
- `outcome`: `achievement_of_at_least_5_percent_weight_loss`;
- `timepoint`: 104 weeks;
- an explicit observed-participant analysis population;
- intervention and comparator labels, events, totals, and reported
  percentages;
- calculation method, confidence level, critical value, continuity-correction
  policy, correction value, percentage tolerance, and assumption note;
- the source-reported adjusted odds ratio, interval, method note, and a
  display-only comparison policy;
- numerical and method source locators; and
- curation provenance.

Unknown or duplicate JSON fields are rejected. Numbers must be finite; event
counts and totals must be JSON integers rather than Booleans. Events must not
exceed totals.

## Correction Policy

The first contract supports only:

```text
continuity_correction = none
continuity_correction_value = 0
```

Both event counts must be nonzero because the declared log-Wald risk-ratio
formula is undefined when either observed risk is zero. The validator rejects
such a record rather than choosing a correction silently. A later schema
version may add a named, reviewed zero-cell policy.

## Deterministic Calculations

For intervention events `a` of total `n1` and comparator events `c` of total
`n0`:

```text
risk1 = a / n1
risk0 = c / n0
RR = risk1 / risk0
SE(log(RR)) = sqrt((1/a - 1/n1) + (1/c - 1/n0))
95% CI = exp(log(RR) +/- 1.96 * SE(log(RR)))
```

For STEP 5:

```text
risk1 = 111 / 144 = 0.7708333333...
risk0 = 44 / 128 = 0.34375
crude RR = 2.2424242424...
SE(log(RR)) = 0.1303047861...
95% CI = 1.7370011527... to 2.8949125768...
```

The calculated percentages are 77.0833...% and 34.375%. Their absolute
differences from the one-decimal source values are 0.0166... and 0.025
percentage points, both within the declared 0.05 percentage-point rounding
tolerance.

All arithmetic uses `Decimal` with an explicit local precision. No value is
parsed from prose at command runtime.

## Result Semantics

The binary check status is:

- `consistent`: both count-derived percentages match the declared source
  percentages within tolerance; or
- `discrepant`: either percentage exceeds tolerance.

The crude risk ratio and interval are deterministic derived outputs, not a
claim that the paper reported or endorsed that measure. The source-reported
adjusted odds ratio is never compared numerically with the crude risk ratio.

A binary discrepancy makes `ke statistical-verify` exit nonzero. A compatible
continuous calculation remains independent of the binary status.
When binary inputs are supplied, the command also prints an overall
requested-check discrepancy count while retaining the legacy continuous
`Discrepancies` line for backward compatibility.

## Report Requirements

The report must show:

- observed analysis population and time point;
- event counts, denominators, reported percentages, calculated percentages,
  and percentage differences for both arms;
- percentage tolerance and binary status;
- effect measure, interval method, confidence level, critical value, and
  correction policy;
- crude risk ratio, log-risk-ratio standard error, and calculated interval;
- the source-reported adjusted odds ratio and interval labeled display-only;
- why the crude and adjusted measures are not compared;
- both source locators and provenance; and
- explicit no-synthesis and no-scientific-validation boundaries.

## Validation And Tests

Tests will cover:

- valid source-linked input and deterministic calculation;
- Boolean and unsupported schema versions;
- invalid identifiers, status, measure, outcome, time point, and labels;
- noninteger, negative, zero, and events-greater-than-total counts;
- invalid percentages and count/percentage discrepancy;
- unsupported confidence methods and confidence levels;
- unsupported or inconsistent correction policies;
- zero-event rejection under the no-correction policy;
- malformed or incomplete source-reported comparison context;
- reviewed Evidence Record identity, DOI, body-weight outcome, and source span;
- duplicate IDs and duplicate JSON fields;
- Markdown escaping and deterministic ordering;
- optional CLI compatibility, discrepancy exit behavior, and output safety;
- the committed STEP 5 record; and
- no PDF or SQLite access.

## Documentation

Update the current roadmap, README, changelog, documentation index, analytical
architecture, interface contract, golden-map documentation, and corpus README.
Historical milestone documents remain unchanged except where they contain an
explicit current handoff.

## Non-Goals

This milestone does not:

- reproduce or validate the reported adjusted odds ratio;
- reinterpret the observed counts as the treatment-policy estimand;
- infer missing events, denominators, covariance, or correction values;
- support zero-cell corrections;
- compare risk ratios and odds ratios as interchangeable measures;
- pool studies or perform meta-analysis;
- calculate benefit-harm, Evidence Quality, Consensus, or Claim Confidence;
- open PDFs, query SQLite, follow URLs, or call an LLM at runtime;
- provide scientific synthesis, clinical guidance, or truth determination.

## Success Criteria

The milestone succeeds when the committed STEP 5 binary input verifies its
reported arm percentages, produces the deterministic crude risk ratio and
interval above, keeps the adjusted odds ratio visibly display-only, preserves
the existing continuous-input command contract when the option is omitted,
passes the complete quality gate, and leaves no ambiguity about scientific or
statistical equivalence.

## Next Handoff

After this binary contract is stable, the next analytical milestone should be
chosen from an observed limitation rather than breadth for its own sake. The
most likely bounded continuation is a second source-audited binary record that
exercises a genuinely different edge case, such as a prespecified zero-cell
correction, before any cross-study pooling or AI narration is considered.
