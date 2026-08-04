# GLP-1 Confidence-Interval Approximation Plan

## Status

Approved implementation plan for the first bounded uncertainty calculation in
the GLP-1 body-weight evidence map.

## Objective

Extend `ke statistical-verify` with one deterministic, source-audited
confidence-interval approximation for the STEP 5 week-104 body-weight result.
The calculation will test whether an interval derived from the two explicitly
reported arm standard errors is compatible with the reported treatment-effect
interval within a declared endpoint tolerance.

This is an approximation under a declared independence and normal-critical-
value assumption. It is not a reconstruction of the trial's ANCOVA, multiple
imputation, or Rubin-combination procedure.

## Why STEP 5 Qualifies

The legally usable STEP 5 source for DOI `10.1038/s41591-022-02026-4`
explicitly reports all values needed for a bounded approximation:

- page 1 reports `n = 152` in each randomized arm and the treatment difference;
- page 2 reports estimated mean body-weight changes and their standard errors:
  `-15.2 (0.9)` for semaglutide and `-2.6 (1.1)` for placebo;
- page 2 reports the estimated treatment difference of `-12.6` percentage
  points and its two-sided 95% CI of `-15.3` to `-9.8`;
- page 5 repeats the values in Table 2; and
- page 11 documents the treatment-policy estimand, ANCOVA, multiple imputation,
  1,000 completed datasets, Rubin's formula, and two-sided 95% intervals.

The source does not report the standard error of the treatment difference or
the covariance between the two adjusted arm estimates. The production
calculation must therefore remain explicitly labeled an independent-arm normal
approximation rather than an exact model-based interval reproduction.

## Why SELECT Does Not Qualify Yet

The SELECT source reports arm estimates, a treatment difference, and a 95% CI,
but it does not provide the two numerical arm standard errors or an equivalent
variance input for the week-208 comparison. Figure error bars are not a safe
substitute for explicit numerical inputs.

SELECT will migrate to the new input schema but will not declare an uncertainty
calculation. Its confidence interval will remain display-only.

## Contract Evolution

Introduce statistical-input schema version 2 while continuing to accept
version 1 records.

Version 2 adds an optional `confidence_interval_verification` object. Version 1
records remain arithmetic-only and must reject that object so the meaning of
the published version 1 contract is not changed retrospectively.

The optional version 2 object contains:

- `method`: `independent_arm_standard_errors_normal`;
- `intervention_standard_error`: positive finite number;
- `comparator_standard_error`: positive finite number;
- `intervention_sample_size`: positive integer;
- `comparator_sample_size`: positive integer;
- `critical_value`: exactly `1.96` for this initial two-sided 95% contract;
- `endpoint_tolerance`: positive finite number; and
- `assumption_note`: non-empty human-readable disclosure.

When the object is present, the record must also declare a reported 95%
confidence interval. The group sizes are retained as source-audited context;
they are not inserted into the formula a second time because the reported
standard errors already incorporate sampling information and model behavior.

## Deterministic Calculation

For intervention standard error `SE_i`, comparator standard error `SE_c`,
reported effect `E`, and critical value `z`:

```text
SE_difference = sqrt(SE_i^2 + SE_c^2)
margin = z * SE_difference
lower = E - margin
upper = E + margin
```

For STEP 5:

```text
SE_difference = sqrt(0.9^2 + 1.1^2)
              = sqrt(2.02)
              = 1.4212670403551895...

margin = 1.96 * 1.4212670403551895...
       = 2.7856833990961715...

approximate 95% CI = -12.6 +/- 2.7856833990961715...
                   = -15.3856833990961715... to -9.8143166009038285...
```

Compared with the reported interval `-15.3` to `-9.8`, the endpoint
differences are approximately `0.0856834` and `0.0143166`. Both are within the
declared `0.1` percentage-point endpoint tolerance.

Decimal arithmetic and an explicit local precision context will make the
calculation deterministic. No value will be parsed from prose at command
runtime.

## Result Semantics

Each verification result retains its arithmetic status and gains an optional
interval-approximation result:

- `compatible`: both recomputed endpoints are within endpoint tolerance;
- `discrepant`: at least one endpoint exceeds endpoint tolerance; or
- absent: no interval approximation was requested for that record.

The command exits nonzero if either an arithmetic check or a requested interval
check is discrepant. A record without an interval calculation is not an error.
The existing `Discrepancies` summary remains an arithmetic-discrepancy count for
backward-compatible human output; new interval counts are reported separately.

The report must separately show:

- reported arm standard errors and sample sizes;
- the declared method and critical value;
- the recomputed difference standard error;
- the recomputed margin and interval;
- reported interval endpoints;
- endpoint differences and tolerance;
- interval status; and
- the assumption note.

The report must call the result an approximation, not a reproduction or
validation of the paper's model-based confidence interval.

## Validation Rules

Tests will cover:

- version 1 arithmetic-only compatibility;
- version 1 rejection of the new object;
- version 2 with and without the optional object;
- unsupported schema versions and Boolean versions;
- unsupported interval methods;
- missing reported confidence interval;
- confidence levels other than 95%;
- nonpositive or nonfinite standard errors;
- invalid sample sizes, including Boolean values;
- critical values other than `1.96`;
- nonpositive endpoint tolerance;
- blank assumption notes;
- exact deterministic calculations;
- compatible and discrepant interval outcomes;
- report ordering and trust-boundary language;
- CLI summary and exit behavior; and
- no SQLite creation or access.

The existing source-linked Evidence Record identity, reviewed status, DOI,
body-weight outcome, and source-span checks remain unchanged.

## Documentation Updates

Update the following durable surfaces:

- `README.md`;
- `CHANGELOG.md`;
- `docs/README.md`;
- `docs/roadmap.md`;
- `docs/roadmap/long_term_vision.md`;
- `docs/ai_layer_architecture.md`;
- `docs/core_interface_contract.md`;
- `docs/glp1_body_weight_golden_evidence_map.md`;
- the prior typed-input plans; and
- `data/corpora/glp1_weight_loss/README.md`.

The documentation must keep SELECT display-only and must not imply cross-study
comparability, synthesis, or confidence scoring.

## Trust Boundaries

This milestone does not:

- derive a standard error from rounded confidence limits;
- read or parse source PDFs at command runtime;
- claim to reproduce the paper's ANCOVA or multiple-imputation model;
- infer covariance between adjusted estimates;
- compare STEP 5 and SELECT clinical effect magnitude;
- harmonize populations, estimands, follow-up periods, or trial purposes;
- pool studies or perform meta-analysis;
- alter Evidence Quality, Consensus, or Claim Confidence;
- access SQLite;
- call an LLM; or
- determine scientific validity, replication, clinical guidance, or truth.

Compatibility means only that this declared approximation is close to the
reported interval within the declared rounding tolerance.

## Success Criteria

The milestone succeeds when:

- STEP 5's source-audited approximation is deterministic and compatible;
- SELECT remains explicitly display-only;
- schema version 1 remains readable without changed semantics;
- schema version 2 validation rejects incomplete or misleading inputs;
- report and CLI output make approximation assumptions unmistakable;
- all existing and new tests pass;
- no database or PDF is touched by the command; and
- PR and post-merge `main` quality checks pass.

## Next Handoff

After this interval approximation is stable, the next bounded statistical task
is to design a source-audited binary-outcome verification contract for one
reviewed result with explicit event counts and denominators. That design should
recompute a risk ratio or odds ratio and its interval only when the estimand,
continuity-correction policy, confidence method, and source locators are all
explicit. It must remain separate from cross-study pooling and scientific
synthesis.
