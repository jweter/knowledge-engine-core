# GLP-1 Cross-Study Comparison Foundation Plan

## Decision

The next project milestone begins Current Project Path Goal 4 with a
deterministic cross-study comparison report over the reviewed GLP-1/body-weight
golden evidence map.

The milestone will make the map inspectable as a coherent set of studies before
attempting statistical recomputation. It will not parse numerical estimates out
of prose, pool effects, calculate consensus, revise confidence, or use an LLM.

## Why This Is Next

The golden map now has twelve source-audited Evidence Records, seventeen
reviewed relationships, explicit PICO boundaries, citations, limitations, and a
reproducible contradiction audit. That is enough reviewed structure to compare
the selected studies honestly.

It is not yet enough structured numerical data to run the Statistics Auditor
safely. Effect estimates, confidence intervals, time points, analysis
populations, and units are currently embedded in record prose. Treating that
prose as a typed statistical contract would create false precision.

## Objective

Add this command:

```text
ke evidence-map-report <map.json> \
  --evidence <evidence_records.jsonl> \
  --relationships <relationship_records.jsonl> \
  --sources <sources.csv> \
  [--output <report.md>] [--force]
```

The command will validate every input with the existing contracts, then render
a deterministic Markdown comparison report. With no `--output`, it will print
the report to the terminal without Rich interpreting source-controlled text as
markup.

## Report Contract

The report will include:

1. map identity, question, status, and scope;
2. a compact study index in evidence-node order;
3. one comparison section per selected Evidence Record containing:
   - map role and inclusion rationale;
   - source title, DOI, venue, year, source URL, and declared license;
   - study type and review status;
   - population, intervention, comparator, and outcome;
   - evidence direction and reported result summary;
   - all recorded limitations;
   - reviewed relationships touching that record;
4. the map's population and comparator groups with interpretation boundaries;
5. the contradiction assessment;
6. an analytical-readiness section stating that reported results remain prose
   and are not valid inputs for automatic effect recomputation;
7. explicit no-synthesis, no-consensus, no-confidence, no-legal-approval, and
   no-scientific-review boundaries.

## Module Boundary

Create a focused pure module, preferably
`knowledge_engine/evidence_map_report.py`.

- The module will build typed comparison rows and Markdown from already-loaded,
  validated data.
- It will not import Typer, Rich, SQLite, parser, graph repository, retrieval,
  or LLM modules.
- `knowledge_engine/cli.py` will remain a thin adapter responsible for loading
  existing contracts, rejecting invalid inputs, writing output, and applying
  the exit code.
- Existing evidence-map validation remains authoritative; the report builder
  will not duplicate its scientific or structural decisions.

## Determinism

- Evidence rows follow `golden_evidence_map.json` node order.
- Relationships follow the map's selected relationship order.
- Relationship references are rendered from the current validated files only.
- Missing optional values render as `Not recorded`; they are never guessed.
- Markdown-sensitive source text is escaped.
- No generated timestamp appears in the report, so identical inputs produce
  identical output bytes.

## Trust Boundaries

The report displays reviewed records and reviewer-authored relationships. It
does not:

- infer that a relationship exists;
- turn a `qualifies` edge into disagreement;
- count support as consensus;
- assign or alter Evidence Quality, Evidence Consensus, or Claim Confidence;
- extract statistical values from prose;
- calculate or pool an effect;
- rank studies;
- decide legal permission, scientific validity, clinical applicability, or
  truth.

## Testing

Tests will cover:

- deterministic row and relationship ordering;
- map role and source citation mapping by normalized DOI;
- complete PICO, result, limitation, and review-status display;
- population, comparator, and contradiction boundaries;
- missing optional metadata rendered without invention;
- Markdown escaping for user-controlled text;
- invalid evidence, relationship, source, and map inputs rejected through
  existing validation;
- output overwrite protection and `--force`;
- terminal output and file output parity;
- required analytical-readiness and trust-boundary statements;
- the committed GLP-1 report contains twelve studies and seventeen selected
  relationships;
- no database creation or mutation.

## Documentation Updates

Update the README, roadmap, golden-map documentation, and changelog to record:

- the exact command;
- what the report compares;
- why this begins Analytical Intelligence responsibly;
- why it is not statistical synthesis; and
- the next prerequisite for deterministic statistical verification.

## Success Criteria

The milestone succeeds when:

- the reviewed GLP-1 map renders as one deterministic, source-linked comparison
  report;
- every selected record remains visibly bounded by its own PICO, design,
  result, limitations, and relationship context;
- invalid or incomplete inputs cannot produce a report;
- no database, PDF, network, parser, graph-build, or LLM operation occurs;
- the full repository quality gate passes; and
- the PR and post-merge `main` checks pass.

## Next Handoff

After this report is stable, the next milestone should design a small typed
statistical-input contract for only the most direct randomized body-weight
records. It should begin with one supported effect form and independently
recompute one reported estimate or confidence interval. No value should be
parsed from free prose or pooled until its source span, unit, time point,
analysis population, and formula inputs are explicit.
