# GLP-1 Statistical Verification Readiness Gate Plan

## Status

Approved pre-implementation plan for the Statistical Verification Readiness Gate.

The preceding second binary edge-case milestone completed under its documented stop rule: a genuine zero-cell source example was identified, but no matching reviewed Evidence Record existed for that outcome, so no binary schema extension or synthetic production record was added. This readiness milestone therefore inventories the actual verified state rather than assuming a second production binary input exists.

## Objective

Create a deterministic readiness report over the reviewed GLP-1/body-weight golden evidence map.

The report answers:

- what has source-audited typed numerical input;
- what has exact arithmetic reproduction;
- what has bounded approximation;
- what has a derived but non-source-equivalent calculation;
- what remains display-only;
- what has not been selected for numerical verification;
- what is incompatible for future pooling design; and
- whether the project is ready to design a pooling protocol.

This is an analytical readiness assessment, not scientific synthesis.

## Reviewed Population

Use only Evidence Records selected by:

`data/corpora/glp1_weight_loss/golden_evidence_map.json`

Reject records not selected by that reviewed map.

The current golden map selects 12 reviewed Evidence Records spanning landmark randomized trials, durability and safety qualifiers, observational population extensions, active-comparator context, evidence syntheses, an endpoint qualifier, and an agent/population qualifier.

## Primary Readiness Categories

Assign exactly one primary category per selected Evidence Record:

- `exactly_verified`
- `bounded_approximation`
- `derived_not_source_equivalent`
- `display_only`
- `insufficient_numerical_detail`
- `not_selected_for_verification`
- `not_applicable`

A record category is a coverage/readiness label, not a quality, confidence, validity, or truth score.

`exactly_verified` means only that declared arithmetic reproduces the audited source values under the supported deterministic contract.

## Per-Input Verification Facets

The generated report must separately enumerate linked statistical inputs and their actual deterministic behavior.

Recommended internal/report-only facet values:

- `exact_arithmetic_reproduction`
- `bounded_interval_approximation`
- `derived_non_equivalent_effect`
- `source_reported_display_only`

This distinction is required because a single Evidence Record may have multiple verification facets.

STEP 5 is the clearest current example:

1. the continuous intervention-minus-comparator arithmetic is exactly reproduced;
2. the confidence interval has a bounded independent-arm normal approximation that is not source-model-equivalent; and
3. the binary input derives a crude risk ratio that is explicitly not equivalent to the source-adjusted odds ratio.

The record's primary category may still be `exactly_verified`, but the report must not flatten or hide the other facets.

SELECT similarly has exact continuous arithmetic reproduction while its source-reported confidence interval remains display-only because both numerical arm standard errors are unavailable.

These facets do not need to be serialized in version 1 of the curated readiness map if implementation simplicity benefits from deriving them only from already-validated typed inputs.

## Compatibility Dimensions

For verified records, compare conservatively on:

- source DOI;
- study design;
- intervention;
- comparator;
- population;
- outcome definition;
- outcome type;
- unit;
- effect-measure family;
- time point;
- analysis population;
- estimand;
- adjusted versus crude status;
- missing-data method;
- variance availability;
- source-audited input status; and
- population overlap.

Two records must not be considered candidates for pooling design merely because both concern body weight.

## Curated Readiness Map

Create:

`data/corpora/glp1_weight_loss/statistical_readiness_map.json`

Use strict schema version 1.

Top-level fields:

- `schema_version`
- `research_question`
- `golden_evidence_map`
- `continuous_inputs`
- `binary_inputs`
- `records`
- `curation`

Each record entry identifies:

- `evidence_record_id`
- `readiness_category`
- `continuous_input_ids`
- `binary_input_ids`
- `compatibility_group`, when justified
- `incompatibility_reasons`
- `review_note`

The map is curated. Runtime code must not infer categories by parsing Evidence Record prose.

Reject:

- Boolean or unsupported schema versions;
- unknown fields;
- missing required fields;
- duplicate Evidence Record IDs;
- unknown Evidence Record IDs;
- Evidence Records not selected by the reviewed golden map;
- unreviewed Evidence Records;
- unknown continuous input IDs;
- unknown binary input IDs;
- statistical inputs linked to a different Evidence Record;
- duplicate statistical input assignments;
- unsupported readiness categories;
- blank required review notes or limitation explanations; and
- malformed source identity.

## Current Curated Classification

The approved pre-implementation map contains 12 selected Evidence Records.

Expected primary category counts:

- `exactly_verified`: 2
- `bounded_approximation`: 0
- `derived_not_source_equivalent`: 0
- `display_only`: 3
- `insufficient_numerical_detail`: 0
- `not_selected_for_verification`: 6
- `not_applicable`: 1

The zero record-level counts for `bounded_approximation` and `derived_not_source_equivalent` are intentional. Those verification types currently occur as additional STEP 5 per-input facets rather than as the primary readiness category of separate Evidence Records.

Current typed inputs:

- continuous: 2
- binary: 1

## Runtime Service

Create a focused module:

`knowledge_engine/statistical_readiness.py`

Responsibilities:

1. load the readiness map;
2. strictly validate its schema;
3. load Evidence Records;
4. validate that every mapped Evidence Record is reviewed and selected by the golden map;
5. reuse the existing continuous statistical-input validator;
6. reuse the existing binary statistical-input validator;
7. reuse the existing deterministic continuous calculations;
8. reuse the existing deterministic binary calculations;
9. verify all source-to-input identity links;
10. reject duplicate input assignment;
11. build the coverage inventory;
12. build conservative compatibility groups or pairs;
13. compute the readiness verdict; and
14. render deterministic Markdown.

Do not duplicate existing continuous or binary formulas.

## CLI

Add:

```text
ke statistical-readiness-report \
  data/corpora/glp1_weight_loss/statistical_readiness_map.json \
  --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl \
  --continuous-inputs data/corpora/glp1_weight_loss/statistical_inputs.jsonl \
  --binary-inputs data/corpora/glp1_weight_loss/binary_statistical_inputs.jsonl \
  --output glp1-statistical-readiness.md
```

Keep `cli.py` thin.

The command must return nonzero for structural validation errors or deterministic verification discrepancies.

## Deterministic Readiness Verdict

Allowed values:

- `not_ready_for_pooling_design`
- `ready_for_pooling_design_review`

Minimum gate for `ready_for_pooling_design_review`:

- at least two independent primary studies;
- same intervention/comparator family;
- materially aligned population;
- same outcome definition;
- same effect-measure family;
- compatible time point;
- compatible estimand;
- sufficient variance information;
- no known population overlap;
- every numerical input independently source-audited; and
- no unresolved deterministic verification discrepancy.

Do not weaken the gate to make the project appear ready.

## Expected Current Verdict

`not_ready_for_pooling_design`

STEP 5 and SELECT are the nearest continuous pair because both are randomized semaglutide 2.4 mg versus placebo trials with typed percentage body-weight-change inputs.

They are not currently a direct pooling-design candidate under the strict gate because:

- time points differ: 104 versus 208 weeks;
- analysis populations and estimand framing differ;
- SELECT does not expose the numerical arm standard errors required for the same independent uncertainty check available for STEP 5; and
- no pooling protocol has defined whether or how those differences could ever be harmonized.

The binary inventory contains only one production source-audited binary input, so the binary side cannot satisfy the minimum two-independent-study gate.

Existing source meta-analyses must not be treated as independent primary studies or double-counted with their underlying trial evidence.

## Required Report Content

### Scope

Include:

- research question;
- reviewed golden-map record count;
- continuous and binary input counts;
- deterministic provenance; and
- explicit no-synthesis boundary.

### Coverage Summary

Report counts and percentages for every readiness category.

### Verification Inventory

For every selected Evidence Record, show:

- source title;
- DOI;
- study design;
- primary readiness category;
- linked typed statistical inputs;
- actual verification facets;
- verified result summary;
- assumptions;
- source locators; and
- reason for missing or limited verification.

### Compatibility Groups

Prefer grouped compatibility reporting rather than a noisy all-against-all matrix.

For each candidate pair/group, show:

- shared outcome;
- effect-measure family;
- time point;
- estimand;
- compatibility status: `candidate`, `no`, or `undetermined`; and
- explicit reasons.

### Readiness Decision

Emit one deterministic verdict.

This is readiness to design a pooling protocol, not approval to pool.

### Boundaries

End with statements equivalent to:

- No studies were pooled.
- No meta-analysis was performed.
- No scientific synthesis was performed.
- No treatment conclusion was generated.
- Verification does not establish scientific truth or clinical guidance.
- Missing numerical detail was not inferred.

## Testing Priorities

### Schema

- valid readiness map;
- unsupported or Boolean schema version;
- missing required fields;
- unknown fields;
- duplicate Evidence Record IDs;
- unknown Evidence Record ID;
- unreviewed or non-golden-map Evidence Record;
- unknown continuous input ID;
- unknown binary input ID;
- input linked to wrong Evidence Record;
- duplicate input assignment;
- invalid readiness category;
- missing limitation/review explanation.

### Classification

Exercise all seven primary categories.

### Compatibility

- aligned records produce `candidate`;
- outcome mismatch produces `no`;
- time-point mismatch produces `no`;
- effect-measure mismatch produces `no`;
- estimand mismatch produces `no`;
- adjusted-versus-crude mismatch produces `no`;
- overlapping populations produce `no`;
- missing variance produces `undetermined` where appropriate;
- fewer than two qualifying studies keeps the gate not ready.

### Report

- deterministic ordering;
- stable category counts;
- correct verification totals;
- assumptions displayed;
- source locators displayed;
- Markdown escaping;
- required boundary statements;
- no private absolute paths;
- no extracted source prose beyond existing curated summaries.

### CLI

- help output;
- success exit code;
- invalid-map exit code;
- verification-discrepancy exit code;
- missing-file handling;
- existing statistical commands unchanged.

### Isolation

- no PDF access;
- no SQLite access;
- no network access;
- no LLM access;
- no generated report staged;
- no Evidence Record mutation;
- no Relationship Record mutation.

## Documentation Updates After Implementation

Update only where necessary:

- this plan;
- `docs/roadmap.md`;
- `docs/roadmap/long_term_vision.md`;
- `docs/glp1_body_weight_golden_evidence_map.md`;
- `docs/ai_layer_architecture.md`;
- `docs/core_interface_contract.md`;
- `docs/README.md`;
- `data/corpora/glp1_weight_loss/README.md`;
- `README.md`;
- `CHANGELOG.md`.

Do not update:

- package version;
- dependencies;
- releases or tags;
- database schema;
- Evidence Records;
- Relationship Records.

## Explicit Non-Goals

This milestone does not:

- pool studies;
- perform meta-analysis;
- harmonize effects;
- infer missing standard errors or covariance;
- parse numerical values from prose;
- rank treatments;
- calculate benefit-harm;
- alter Evidence Quality, Consensus, or Claim Confidence;
- read PDFs at command runtime;
- access SQLite;
- use network access;
- call an LLM;
- add AI narration; or
- determine scientific truth or clinical guidance.

## Quality and Manual Review

Run:

```text
poetry run pytest
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy knowledge_engine tests
git diff --check
```

Use `COLUMNS=500` only if necessary for the known Windows Rich/Typer console-capture issue.

Run the real readiness command against the committed GLP-1 files.

Manually inspect:

- every category assignment;
- every linked statistical input;
- all compatibility decisions;
- the readiness verdict;
- category and input counts;
- source identity and DOI matching;
- report boundaries; and
- absence of private paths.

Verify no PDF, SQLite database, network service, or LLM was accessed and no numerical value was parsed from source prose at runtime.

## Success Criteria

The milestone succeeds when:

- every reviewed golden-map Evidence Record receives exactly one valid primary readiness category;
- all mapped statistical inputs are validated against the correct reviewed Evidence Record;
- existing deterministic continuous and binary calculations are reused rather than duplicated;
- all verification facets are represented honestly;
- compatibility decisions expose explicit reasons;
- the current corpus deterministically resolves to the justified readiness verdict;
- no studies are pooled;
- no scientific synthesis is introduced;
- all tests and quality gates pass; and
- the next bounded milestone is chosen from the actual reported blockers.

## Next Decision

If the report says `ready_for_pooling_design_review`, the next milestone is a design-only statistical pooling protocol. Do not implement pooling immediately.

If the report says `not_ready_for_pooling_design`, use the explicit gaps to choose the smallest next source-audit milestone, such as:

- obtaining a missing variance term;
- auditing a second compatible primary trial;
- resolving an estimand mismatch; or
- documenting that an estimate must remain display-only.

Do not use AI narration to bypass missing deterministic evidence.
