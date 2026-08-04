# GLP-1 Typed Statistical Inputs Plan

**Status:** Completed for STEP 5. The SELECT continuation and independent
typed-locator refinement are documented in
`docs/glp1_select_statistical_input_plan.md`.

## Decision

The next bounded milestone begins deterministic statistical verification with
one source-audited STEP 5 body-weight result. It introduces a typed statistical
input contract and independently verifies the reported difference in mean
percentage-point body-weight change between the randomized semaglutide and
placebo arms.

This milestone does not parse numbers from Evidence Record prose, recalculate a
confidence interval, pool studies, rank evidence, alter confidence quantities,
or use an LLM.

## Why This Is Next

The reviewed GLP-1 evidence map and `ke evidence-map-report` now make study
design, PICO, reported results, limitations, citations, and relationship
boundaries inspectable together. The report also identifies the remaining
analytical prerequisite: formula inputs must be explicit and source-linked
before arithmetic can be trusted.

STEP 5 is the safest first case because its source reports all three values
needed for a direct identity check:

- semaglutide estimated mean body-weight change at week 104: `-15.2%`;
- placebo estimated mean body-weight change at week 104: `-2.6%`; and
- reported estimated treatment difference: `-12.6` percentage points.

The source identifies the treatment-policy estimand and reports the result in
the abstract, results text, and Table 2. The arithmetic is therefore
independently reproducible without inferring an unreported statistic.

## Objective

Add a versioned JSONL contract and this command:

```text
ke statistical-verify <statistical_inputs.jsonl> \
  --evidence <evidence_records.jsonl> \
  [--output <report.md>] [--force]
```

The command will validate every input and Evidence Record reference, recompute
the supported effect with decimal arithmetic, compare it with the reported
effect under an explicit absolute tolerance, and render deterministic Markdown.

## Version 1 Contract

Each JSONL object represents one independently checkable reported effect. The
initial contract supports exactly one effect type and formula:

- `effect_measure`: `difference_in_mean_change`
- `formula`: `intervention_minus_comparator`
- calculation: `intervention_mean_change - comparator_mean_change`

Required identity and provenance fields:

- `schema_version`: integer `1`;
- `statistical_input_id`: stable unique identifier;
- `evidence_record_id`: reviewed Evidence Record reference;
- `source_doi`: DOI matching that Evidence Record after normalization;
- `review_status`: `source_verified`;
- `source_span`: page, section, and optional table/figure or locator note;
- `provenance`: creator, creation date, method, and source basis.

Required analytical-context fields:

- `outcome`: controlled value `body_weight_change_from_baseline`;
- `unit`: controlled value `percentage_points`;
- `timepoint`: positive numeric value plus controlled unit `weeks`;
- `analysis_population`: explicit non-empty text;
- intervention and comparator labels;
- intervention and comparator mean changes;
- reported effect;
- absolute comparison tolerance.

Optional reported uncertainty may be preserved as display-only lower and upper
confidence limits. Version 1 does not recompute those limits and must say so.

All numeric values are JSON numbers but are loaded from their lexical JSON
representation into `Decimal`. Boolean values are never accepted as numbers.

## Validation Rules

Validation must reject:

- malformed JSON or non-object rows;
- duplicate JSON object fields;
- unsupported or boolean schema versions;
- missing, blank, duplicate, or malformed identifiers;
- unsupported effect measures, formulas, outcomes, units, or time units;
- missing or non-finite numeric fields;
- non-positive time points or tolerances;
- malformed confidence intervals;
- missing or incomplete source spans and provenance;
- unknown Evidence Record references;
- Evidence Records not marked `reviewed`;
- DOI disagreement after normalization; and
- source identity or outcome mismatch with the referenced record.

The validator checks structure, traceability, and arithmetic reproducibility. It
does not decide whether the source analysis is methodologically correct.

## Calculation and Status

The verifier computes:

```text
recomputed_effect = intervention_mean_change - comparator_mean_change
absolute_difference = abs(recomputed_effect - reported_effect)
```

Status is deterministic:

- `consistent` when `absolute_difference <= tolerance`;
- `discrepant` otherwise.

The first STEP 5 record should produce:

```text
-15.2 - (-2.6) = -12.6 percentage points
```

with an absolute difference of zero from the reported effect.

`consistent` means only that the declared arithmetic inputs reproduce the
declared reported effect. It is not a scientific-validity judgment, replication
result, evidence-confidence score, or statement that the paper is correct.

## Module Boundary

Create a pure `knowledge_engine/statistical_verification.py` module.

- It owns typed models, JSONL loading, structural/reference validation,
  decimal calculation, deterministic results, and Markdown rendering.
- It does not import Typer, Rich, SQLite, parser, graph, retrieval, or LLM code.
- `knowledge_engine/cli.py` remains a thin adapter for existing Evidence Record
  validation, command options, rendering, output protection, and exit codes.
- No statistical field is added to the Evidence Record contract in this slice.

## Determinism and Safety

- Input order determines report order.
- Decimal arithmetic avoids binary floating-point display drift.
- Identical inputs produce identical output bytes; no generated timestamp is
  included.
- Source-controlled Markdown is escaped.
- Output may never overwrite either input, including with `--force`.
- The command opens no PDF, follows no URL, and accesses no database.
- Values are curated explicitly in JSONL; nothing is extracted from prose.

## Committed Pilot Input

Add one record to:

```text
data/corpora/glp1_weight_loss/statistical_inputs.jsonl
```

The record will reference
`ev-glp1-step5-body-weight-week104-001` and preserve the source-audited STEP 5
week-104 treatment-policy-estimand values and source locator. It remains
separate from `evidence_records.jsonl` so the scientific evidence model is not
silently expanded by an analytical prototype.

SELECT is the expected next candidate, but it is intentionally not added until
the version 1 contract and first verification survive review.

## Report Contract

The deterministic Markdown report will include:

- input count and contract version;
- source and Evidence Record identity;
- outcome, unit, time point, and analysis population;
- intervention and comparator labels and mean changes;
- the explicit formula;
- reported effect, recomputed effect, absolute difference, tolerance, and
  status;
- the source span and provenance;
- reported confidence interval when present, clearly labeled not recomputed;
- explicit interpretation and trust boundaries.

The terminal summary will report valid inputs, consistent checks,
discrepancies, and output location when applicable.

## Exit Codes

- valid inputs with all checks consistent: `0`;
- structurally valid inputs with one or more discrepancies: `1`;
- invalid inputs or Evidence Record references: `1`;
- output misuse reported by Typer: `2`.

## Testing

Tests will cover:

- valid loading and exact Decimal calculation;
- deterministic consistent and discrepant statuses;
- schema, identifier, controlled-vocabulary, numeric, time-point, tolerance,
  source-span, provenance, confidence-interval, and duplicate-ID validation;
- unknown, unreviewed, DOI-mismatched, and outcome-mismatched Evidence Records;
- malformed JSON with line context and no traceback;
- report ordering, escaping, and explicit trust boundaries;
- CLI terminal/file parity, exit codes, overwrite protection, and `--force`;
- the committed STEP 5 record reproduces `-12.6` exactly;
- invalid inputs cannot produce a report; and
- no database is created or modified.

## Documentation Updates

Update README, corpus documentation, roadmap, Analytical Intelligence
architecture, golden-map documentation, documentation index, and changelog to
record the command, the exact result, and its narrow interpretation.

## Success Criteria

The milestone succeeds when:

- one source-audited randomized body-weight result is represented without
  prose parsing;
- its reported treatment difference is independently reproduced exactly;
- malformed, unreviewed, or mismatched inputs are rejected;
- the output cannot be mistaken for synthesis, replication, confidence, or
  truth determination;
- no database, PDF, parser, network, graph, or LLM operation occurs;
- the complete quality gate passes; and
- PR and post-merge `main` checks pass.

## Next Handoff

After this contract is stable, add independently source-audited inputs for the
SELECT direct randomized body-weight result and a deliberately discrepant
synthetic fixture in tests. Then design confidence-interval recomputation only
for an effect form whose required standard errors, standard deviations, and
group sizes are explicitly available. Cross-study pooling, sensitivity
analysis, and meta-analysis remain later work.
