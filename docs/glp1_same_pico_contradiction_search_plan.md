# GLP-1 Same-PICO Contradiction Search Plan

## Purpose

The reviewed GLP-1/body-weight golden evidence map currently contains no
reviewed `contradicts` relationship. This milestone will test that absence with
a reproducible, bounded search. It will not add a contradiction merely to make
the graph look balanced.

The output must distinguish three conclusions:

1. an aligned contradictory result was identified and source-verified;
2. a materially qualifying result was identified, but it does not contradict
   the direct evidence; or
3. no admissible contradictory result was found within the documented search.

The third conclusion is a bounded negative search result, not proof that no
contradictory literature exists.

## Direct PICO Contract

The search target is the map's most direct efficacy question:

- **Population:** adults with overweight or obesity, with diabetes status and
  other major eligibility differences kept explicit;
- **Intervention:** continued semaglutide treatment for chronic weight
  management, with dose and co-intervention preserved;
- **Comparator:** placebo or control receiving the same stated behavioral
  co-intervention where applicable;
- **Outcome:** body-weight change during the randomized treatment window.

Withdrawal, adverse events, physical fitness, waist circumference alone,
active-drug comparisons, observational cohorts, and different GLP-1 receptor
agonists may qualify interpretation. They cannot be called same-PICO
contradictions of semaglutide-versus-placebo body-weight efficacy.

## Decision Rules

### Contradicts

Use `contradicts` only when population, intervention, comparator, outcome, and
treatment window are sufficiently aligned and the result's direction is
materially incompatible with the target claim, such as no supported
semaglutide advantage or a control-favoring body-weight result.

Statistical uncertainty around the size of an effect is not automatically a
directional contradiction. Neither is a smaller effect in a materially
different population.

### Qualifies

Use `qualifies` when a credible result changes the applicable magnitude,
population, dose, duration, endpoint, or interpretation boundary without
reversing the aligned body-weight direction.

### Exclude

Exclude a candidate from the map when it lacks source-verifiable numerical
results, falls outside the direct PICO, duplicates a selected record, is not
legally usable for the required source audit, or cannot support a precise
Evidence Record.

## Search Layers

1. **Existing evidence layer:** inspect all committed Evidence Records, with
   special attention to null, non-significant, control-favoring, and hedged
   body-weight claims.
2. **Relationship candidates:** inspect high-similarity candidate pairs and
   existing reviewed relationships for a missed aligned disagreement.
3. **Corpus manifest:** screen all committed source titles, identifiers, study
   types, and PICO metadata for randomized semaglutide/control weight studies
   and systematic reviews that may contain discordant trials or subgroups.
4. **Current literature:** search authoritative bibliographic sources for
   randomized semaglutide/control body-weight evidence and trace plausible
   candidates to stable source pages and legally usable full text where
   possible.
5. **Source audit:** read the relevant source text for every finalist before
   classifying it. Abstract or title wording alone is insufficient.

## Required Audit Record

The completed audit will record:

- search date and exact queries or commands;
- the number of records and manifest rows screened;
- each plausible candidate and its disposition;
- PICO alignment and mismatch reasons;
- source and license basis;
- whether any Evidence Record or Relationship Record was added;
- the bounded conclusion and remaining uncertainty.

## Implementation Rules

- Preserve the current map's reviewed status only if every selected addition
  receives an independent source-fidelity audit.
- Never infer a relationship from similarity, shared concepts, or a null result
  on another endpoint.
- Never weaken grounding, provenance, review, or no-synthesis boundaries.
- Do not download or commit a PDF without a verified legal-use basis; PDFs
  remain ignored even when used locally.
- Do not add AI narration, consensus, confidence scoring, or truth
  determination.

## Success Criteria

This milestone succeeds when:

- the search is reproducible and its scope is explicit;
- every plausible candidate has a documented disposition;
- any added record and relationship pass the existing validators;
- the map's contradiction assessment cites the completed search rather than an
  informal absence;
- documentation states clearly that a negative search is not proof of
  universal agreement; and
- the full repository quality gate passes.

## Failure Criteria

The milestone is not complete if it labels a different endpoint, population,
agent, comparator, or treatment window as a direct contradiction; relies on an
unverified abstract for a reviewed record; omits rejected candidates; or
implies that the Knowledge Engine established scientific consensus or truth.

## Planned Deliverables

- this written plan;
- `docs/glp1_same_pico_contradiction_search_audit.md` with executed search and
  candidate dispositions;
- the smallest justified updates to the golden map, roadmap, corpus
  documentation, and changelog;
- Evidence or Relationship Records only if a source-verified candidate meets
  the rules above;
- validator and full quality-gate results.

## Handoff

After this audit, the next milestone should follow the evidence rather than a
fixed feature sequence. A verified contradiction would require careful graph
and public-rendering review. A negative result would leave the map ready for a
bounded expansion into a documented population or agent gap, without
misrepresenting the absence of contradiction as consensus.
