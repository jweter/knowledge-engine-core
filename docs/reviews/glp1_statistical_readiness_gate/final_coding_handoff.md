# Final Coding Handoff: GLP-1 Statistical Verification Readiness Gate

## Branch

Continue on:

`agent/glp1-statistical-readiness-gate`

## Groundwork Already Committed

The branch already contains:

- `docs/glp1_statistical_readiness_gate_plan.md`
- `data/corpora/glp1_weight_loss/statistical_readiness_map.json`
- `docs/reviews/glp1_statistical_readiness_gate/compatibility_analysis.md`
- this coding handoff

These files define the approved pre-implementation contract.

## Implement

Create:

- `knowledge_engine/statistical_readiness.py`
- `tests/test_statistical_readiness.py`

Add CLI command:

- `ke statistical-readiness-report`

Keep `cli.py` thin.

Update durable documentation only after behavior is real and tested.

## Reuse Existing Verification Code

Continuous:

- reuse `validate_statistical_inputs`
- reuse `verify_statistical_inputs`

Binary:

- reuse the existing binary statistical-input validator
- reuse the existing binary verification function

Evidence loading:

- reuse the repository's established strict JSONL/Evidence Record loading seam where available

Do not:

- reimplement continuous formulas;
- reimplement binary formulas;
- parse `result_summary` or other Evidence Record prose for numbers;
- open PDFs;
- access SQLite;
- use network access;
- call an LLM.

## Important Modeling Detail

### One primary category versus multiple verification facets

The curated readiness map assigns one primary category per Evidence Record.

STEP 5 must still report all three actual verification facets:

1. exact continuous arithmetic reproduction;
2. bounded confidence-interval approximation; and
3. derived crude binary risk ratio that is not source-equivalent to the adjusted odds ratio.

Do not flatten STEP 5 to a misleading single calculation description merely because its primary record category is `exactly_verified`.

SELECT similarly has:

1. exact continuous arithmetic reproduction; and
2. source-reported confidence interval display-only.

## Expected Current Counts

Golden-map reviewed records: 12

Primary category counts:

- `exactly_verified`: 2
- `bounded_approximation`: 0
- `derived_not_source_equivalent`: 0
- `display_only`: 3
- `insufficient_numerical_detail`: 0
- `not_selected_for_verification`: 6
- `not_applicable`: 1

Typed inputs:

- continuous: 2
- binary: 1

The zero record-level counts for `bounded_approximation` and `derived_not_source_equivalent` are intentional because those are currently additional STEP 5 verification facets rather than primary categories of separate Evidence Records.

## Expected Readiness Verdict

Unless current structured repository facts invalidate the approved map, the deterministic result should be:

`not_ready_for_pooling_design`

Do not weaken compatibility rules to force a ready verdict.

If implementation discovers a factual mismatch in the approved curated map, update the map and document the structured evidence for the correction.

## Required Runtime Validation

At minimum validate:

- strict schema version 1;
- Boolean schema version rejection;
- unknown fields;
- missing required fields;
- duplicate Evidence Record IDs;
- unknown Evidence Record IDs;
- records not selected by the reviewed golden map;
- unreviewed Evidence Records;
- unknown continuous input IDs;
- unknown binary input IDs;
- input-to-Evidence identity mismatch;
- duplicate input assignment;
- unsupported readiness category;
- required nonblank review notes/limitation explanations.

## Compatibility Rules

The current STEP 5 / SELECT pair should not be direct pooling-compatible because of:

- 104 versus 208 weeks;
- treatment-policy versus in-trial intention-to-treat analysis framing;
- asymmetric numerical variance availability.

The implementation should support conservative statuses:

- `candidate`
- `no`
- `undetermined`

Tests must cover:

- aligned candidate;
- outcome mismatch;
- time-point mismatch;
- effect-measure mismatch;
- estimand mismatch;
- crude-versus-adjusted mismatch;
- overlapping population rejection;
- missing variance leading to `undetermined` where appropriate;
- fewer than two qualifying studies keeping the overall gate not ready.

## Required Report Content

The generated deterministic Markdown should include:

- Scope
- Coverage Summary
- Verification Inventory
- Compatibility Groups
- Readiness Decision
- Blockers
- Boundaries

Required boundary statements:

- No studies were pooled.
- No meta-analysis was performed.
- No scientific synthesis was performed.
- No treatment conclusion was generated.
- Verification does not establish scientific truth or clinical guidance.
- Missing numerical detail was not inferred.

## Required Manual Checks

Run the real command against committed GLP-1 files and verify:

- 12 golden-map records;
- 2 continuous inputs;
- 1 binary input;
- no duplicate assignments;
- STEP 5 exact arithmetic shown;
- STEP 5 bounded CI approximation shown;
- STEP 5 crude RR shown as non-source-equivalent;
- SELECT exact arithmetic shown;
- SELECT CI shown as display-only;
- compatibility reasons shown;
- readiness verdict `not_ready_for_pooling_design`;
- no private absolute paths;
- no source prose parsed;
- no PDF, SQLite, network, or LLM access.

## Quality Gate

Run:

```text
poetry run pytest
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy knowledge_engine tests
git diff --check
```

Use `COLUMNS=500` only if necessary for the known Windows Rich/Typer console-capture issue.

## Documentation After Implementation

Update only where necessary:

- `docs/glp1_statistical_readiness_gate_plan.md`
- `docs/roadmap.md`
- `docs/roadmap/long_term_vision.md`
- `docs/glp1_body_weight_golden_evidence_map.md`
- `docs/ai_layer_architecture.md`
- `docs/core_interface_contract.md`
- `docs/README.md`
- `data/corpora/glp1_weight_loss/README.md`
- `README.md`
- `CHANGELOG.md`

Do not modify:

- Evidence Records;
- Relationship Records;
- package version;
- dependencies;
- database schema;
- releases or tags;
- source PDFs.

## Commit and PR

After the complete gate passes, preferred final commit message:

`feat: add statistical verification readiness report`

Preferred PR title:

`feat: add GLP-1 statistical readiness gate`

The PR body must report:

- readiness categories;
- actual coverage counts;
- compatibility decision;
- actual pooling-design readiness verdict;
- blockers;
- no-pooling/no-synthesis boundaries;
- validation results;
- files changed; and
- exact next milestone recommendation.

## Stop Rule

If implementation reveals that classifications or compatibility decisions cannot be justified from existing structured inputs without parsing prose or inferring missing statistical detail, stop and tighten the curated map instead of adding inference.
