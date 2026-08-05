# Future Plan: Structured Paper Records and Section-Level Provenance

## Status

Future architectural milestone.

Do not implement as part of the current second binary-outcome verification milestone.

## Problem

The Knowledge Engine currently represents individual scientific findings primarily through Evidence Records.

This is useful for claim-level verification, but a scientific paper is a larger source object that may contain many independently useful findings:

- efficacy outcomes
- safety outcomes
- subgroup analyses
- adverse events
- discontinuations
- statistical methods
- sensitivity analyses
- limitations
- references

A single Evidence Record should not implicitly authorize every result contained in the same paper.

The current binary-verification work exposed this limitation.

The reviewed GLIDE Evidence Record represents body-weight outcomes, while the same GLIDE publication also contains source-auditable safety outcomes, including adverse-event counts.

The publication is therefore scientifically useful beyond the scope of the existing Evidence Record, but those additional findings should not silently inherit the review status of an unrelated Evidence Record.

## Goal

Introduce a first-class `Paper Record` representing the scientific publication independently of individual Evidence Records.

Conceptual hierarchy:

```text
Paper Record
    |
    +-- Bibliographic metadata
    +-- Structured sections
    +-- Statistical-method metadata
    +-- References
    +-- Source provenance
    |
    +-- Evidence Record 1
    +-- Evidence Record 2
    +-- Evidence Record 3
            |
            +-- Statistical Verification
```

A Paper Record describes the publication.

An Evidence Record describes one bounded result or claim extracted from that publication.

A Statistical Verification deterministically checks a supported numerical claim.

## Required bibliographic fields

At minimum:

- paper_id
- DOI
- title
- authors
- journal
- publication date
- publication year
- source URL
- PDF URL, when available
- local PDF path, when locally available
- license type
- license URL
- provenance

Authors should eventually be represented structurally where feasible rather than only as a flattened citation string.

## Required scientific sections

Paper Records should be able to represent:

- abstract
- introduction
- methods
- statistical methods
- results
- discussion
- conclusions
- limitations
- references

Not all publications contain all of these sections.

The ingestion contract must preserve absence rather than inventing missing content.

For example:

```text
section_presence:
  abstract: true
  introduction: true
  methods: true
  statistical_methods: true
  results: true
  discussion: true
  conclusions: false
  references: true
```

A missing Conclusions heading must not cause the system to generate a synthetic conclusion section.

## Section-level provenance

Every extracted section should retain source-location metadata where possible:

- source heading
- page start
- page end
- table or figure
- supplement identifier
- locator note
- extraction method
- review status

This should allow the engine to distinguish:

1. source text,
2. structured extraction,
3. reviewed interpretation,
4. derived analysis.

## Statistical-method structure

Statistical methods should be represented separately from general study methods.

Candidate fields include:

- analysis population
- estimand
- intention-to-treat / per-protocol status
- statistical tests
- regression models
- effect measures
- confidence level
- critical values
- covariates
- missing-data handling
- imputation method
- multiplicity adjustment
- subgroup methods
- sensitivity analyses
- continuity corrections
- statistical software

These distinctions are important because crude risk ratios, adjusted odds ratios, hazard ratios, model estimates, and source-reported percentages are not interchangeable.

## References

References should initially be represented independently of Evidence Records.

Suggested fields:

- reference number
- raw citation
- title
- authors
- journal
- year
- DOI
- PMID
- PMCID
- resolved paper_id

A reference should not automatically become trusted evidence simply because a reviewed publication cites it.

Future resolution can support a citation graph without changing trust semantics.

## Evidence Record relationship

One Paper Record may support multiple Evidence Records.

Example:

```text
GLIDE Paper Record
    |
    +-- body-weight Evidence Record
    +-- HbA1c Evidence Record
    +-- diabetes-remission Evidence Record
    +-- nausea/adverse-event Evidence Record
    +-- discontinuation Evidence Record
```

Review status must remain outcome-specific.

A reviewed body-weight Evidence Record must not automatically make a safety result reviewed.

## Trust boundary

Preserve the following conceptual sequence:

```text
source publication
    ->
structured Paper Record
    ->
bounded Evidence Record
    ->
deterministic Statistical Verification
    ->
later synthesis
```

These layers must not silently collapse into one another.

## Initial implementation strategy

Implement this as a separate bounded milestone:

1. Define the Paper Record schema.
2. Add bibliographic metadata.
3. Add section-presence representation.
4. Add section-level source spans.
5. Add statistical-method metadata.
6. Add structured references.
7. Link Evidence Records to Paper Records.
8. Migrate only the small reviewed GLP-1 corpus.
9. Add validation tests.
10. Expand ingestion only after the reviewed pilot is stable.

## Non-goals

This milestone must not:

- generate scientific consensus;
- infer missing paper sections;
- promote every result into an Evidence Record;
- perform meta-analysis;
- determine treatment truth;
- make clinical recommendations;
- automatically trust cited references;
- replace source review with LLM summaries.

## Success criteria

For any reviewed Evidence Record, the engine should be able to answer:

- Which paper contains this result?
- Who are the authors?
- When was it published?
- What was the study design?
- What population was studied?
- Where are the Methods?
- What statistical method produced the result?
- Where in the paper is the numerical result?
- What did the authors discuss?
- What limitations were reported?
- What conclusions were stated?
- What references were cited?
- What other Evidence Records come from the same publication?

The Paper Record becomes the durable source object.

Evidence Records remain bounded scientific claims.

Statistical Verification remains deterministic analysis of explicitly supported inputs.
