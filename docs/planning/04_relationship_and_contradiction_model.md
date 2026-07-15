# 04. Relationship and Contradiction Model

**Status**: Future vision document. This feature does not exist in the current implementation.

**Current Implementation**: v0.2.0-alpha.1 indexes papers and allows full-text search. Relationship modeling is **not** included.

---

## Purpose

Scientific knowledge is fundamentally relational. Claims don't exist in isolation; they connect to:
- Other claims (supporting, contradicting, qualifying)
- Evidence (what data supports them)
- Methods (how evidence was generated)
- Populations (who it applies to)
- Outcomes (what was measured)
- Concepts (underlying ideas)
- Unknowns (what gaps remain)

This document defines relationship types that preserve these connections transparently, making contradictions visible rather than hidden.

---

## Relationship Types

### Support Relationships

| Relationship | Meaning | Direction |
|--------------|---------|----------|
| `supports` | Evidence strengthens the claim | Evidence → Claim |
| `is_supported_by` | Claim is strengthened by evidence | Claim ← Evidence |
| `replicates` | Independent study confirms finding | Study B → Study A |
| `is_replicated_by` | Finding confirmed by independent study | Study A ← Study B |
| `extends` | One finding builds on prior finding | Finding B → Finding A |
| `is_extended_by` | Prior finding expanded upon | Finding A ← Finding B |
| `depends_on` | One claim logically requires another | Claim B → Claim A |
| `is_prerequisite_for` | Prior claim enables later claim | Claim A → Claim B |

### Contradiction Relationships

| Relationship | Meaning | Specificity |
|--------------|---------|-------------|
| `contradicts` | Direct factual disagreement | Generic |
| `partially_contradicts` | Agrees on direction; disagrees on magnitude | Quantitative |
| `contradicts_in_direction` | One says increases; other says decreases | Directional |
| `contradicts_in_magnitude` | Both find effect in same direction; size differs | Magnitude-specific |
| `contradicts_in_population` | Finding applies to one population but not another | Population-specific |
| `contradicts_methodologically` | Different methods yield different conclusions | Method-dependent |
| `contradicts_temporally` | Finding changes over time | Temporal |
| `is_undefined_contradiction` | Apparent contradiction; cause unclear | Unresolved |

### Qualification Relationships

| Relationship | Meaning | Example |
|--------------|---------|----------|
| `qualifies` | Narrows scope or adds condition | "Effect strong in age 45–75; weak in age 75+" |
| `is_qualified_by` | Claim limited by additional finding | Claim ← Qualifier |
| `applies_to` | Finding applies to specific subgroup | General claim → Specific population |
| `does_not_apply_to` | Finding does NOT generalize to subgroup | General claim ← Negative qualifier |
| `context_dependent` | Truth varies by context | Claim ↔️ Context |
| `conditional_on` | Claim true only if condition met | Claim → Condition |

### Causality Relationships

| Relationship | Meaning | Certainty |
|--------------|---------|----------|
| `causes` | X directly causes Y | Strong |
| `may_cause` | X possibly causes Y | Weak |
| `is_caused_by` | Y results from X | Strong |
| `may_be_caused_by` | Y possibly results from X | Weak |
| `confounds` | Unknown variable explains relationship | Methodological |
| `mediates` | X causes Y through mechanism Z | Mechanistic |
| `correlates_with` | X and Y co-occur without established causation | Weaker than causal |

### Citation and Authority Relationships

| Relationship | Meaning | Direction |
|--------------|---------|----------|
| `cites` | Source references another | Paper A → Paper B |
| `cited_by` | Source is referenced by another | Paper A ← Paper B |
| `builds_on` | Work extends or relies on prior work | New → Prior |
| `contradicts_prior_consensus` | Finding opposes established belief | Study → Consensus |
| `confirms_prior_consensus` | Finding aligns with established belief | Study → Consensus |
| `corrects` | One paper corrects error in another | Correction → Original |
| `is_corrected_by` | Paper contains error later corrected | Original ← Correction |
| `retracts` | One paper officially retracts another | Retraction → Original |
| `is_retracted_by` | Paper is officially withdrawn | Original ← Retraction |

### Mechanism Relationships

| Relationship | Meaning | Example |
|--------------|---------|----------|
| `uses_mechanism` | Finding operates via specific pathway | GLP-1 effect → Satiety pathway |
| `proposes_mechanism` | Study suggests mechanistic explanation | Study → Proposed mechanism |
| `tests_mechanism` | Study directly tests proposed mechanism | Study → Mechanism test |
| `resolves_mechanism` | Mechanism previously unclear; now established | Study → Mechanism resolution |
| `leaves_mechanism_open` | Study doesn't determine mechanism | Study → Unresolved mechanism |

### Outcome Relationships

| Relationship | Meaning | Example |
|--------------|---------|----------|
| `measures` | Study measures specific outcome | Study → Outcome |
| `affects` | Intervention impacts outcome | Intervention → Outcome |
| `does_not_affect` | Intervention has no effect on outcome | Intervention ↛ Outcome |
| `mediated_by` | Effect on outcome mediated by intermediate | Primary outcome → Mediator → Final outcome |

### Proposal Relationships

| Relationship | Meaning | Direction |
|--------------|---------|----------|
| `proposes` | Study or analysis proposes hypothesis/question | Source → Proposal |
| `tests` | Study tests proposed hypothesis | Study → Hypothesis |
| `resolves` | New evidence answers previously open question | Evidence → Question |
| `leaves_unresolved` | Evidence doesn't fully answer question | Evidence ↛ Question |
| `supersedes` | Newer finding replaces older understanding | New → Old |
| `is_superseded_by` | Older finding replaced by newer evidence | Old ← New |

---

## Contradiction Types

Not all apparent contradictions are equal. Relationship model distinguishes:

### 1. Direct Factual Contradiction
**Type**: Study A says X; Study B says NOT X
**Example**: "GLP-1 reduces weight" (Study A) vs. "GLP-1 does not reduce weight" (Study B)
**Resolution Path**: Methodological review, replication, larger sample
**Status**: Typically marked `is_undefined_contradiction` pending investigation

### 2. Magnitude Disagreement
**Type**: Both agree on effect; disagree on size
**Example**: "5 kg weight loss" (Study A) vs. "8 kg weight loss" (Study B)
**Resolution Path**: Meta-analysis, standardization, check for population differences
**Status**: Marked `partially_contradicts` + `magnitude`

### 3. Direction Disagreement
**Type**: One says increases; other says decreases
**Example**: "GLP-1 increases satiety" vs. "GLP-1 decreases appetite" (may actually agree if satiety ≠ appetite)
**Resolution Path**: Clarify definitions; may not be true contradiction
**Status**: Marked `contradicts_in_direction` pending definition review

### 4. Population-Specific Disagreement
**Type**: Finding applies in one population but not another
**Example**: "Weight loss 7 kg in age 45–75" (Study A) vs. "No weight loss in age 75+" (Study B)
**Resolution Path**: Recognize as population-specific, not contradiction
**Status**: Marked `qualifies` or `does_not_apply_to`; NOT actually a contradiction

### 5. Methodological Disagreement
**Type**: Different study designs yield different findings
**Example**: RCT found effect; observational study found no effect
**Resolution Path**: Methodological review; determine which is more reliable
**Status**: Marked `contradicts_methodologically` + reference to methodology difference

### 6. Temporal Disagreement
**Type**: Finding changes over time (may not be contradiction)
**Example**: "Earlier studies found X; recent studies find Y"
**Resolution Path**: Determine if change reflects improved methods, changed population, changed treatment
**Status**: Marked `contradicts_temporally` + investigate source of change

### 7. Definition Mismatch
**Type**: Studies use different definitions of same term
**Example**: Study A defines "obesity" as BMI >30; Study B uses BMI >28
**Resolution Path**: Standardize definitions; likely not true contradiction
**Status**: Marked with metadata about definitions; typically not a contradiction

### 8. Apparent Contradiction from Context
**Type**: Statements seem to contradict but don't when context is examined
**Example**: "GLP-1 increases weight loss in treatment-naive patients" (true) vs. "GLP-1 does not increase weight loss" (referring to add-on to other agents)
**Resolution Path**: Clarify context and applicability
**Status**: Marked `context_dependent`; surface context alongside claims

### 9. Unresolved Contradiction
**Type**: Genuine disagreement without clear resolution path
**Example**: Two high-quality RCTs reach opposite conclusions; cause unknown
**Resolution Path**: Flag for future investigation; preserve both views
**Status**: Marked `is_undefined_contradiction` + flag for research

### 10. Invalid Comparison
**Type**: No contradiction; studies are too different to compare
**Example**: Animal study vs. human clinical trial (not contradictory; different domains)
**Resolution Path**: Don't mark as contradiction; note study types differ
**Status**: Marked with `does_not_apply_to` or note that comparison is inappropriate

---

## Relationship Data Structure

(Conceptual only; not a production schema)

```
Relationship:
  - relationship_id (UUID)
  - source_entity_id (UUID of source object: claim, evidence, paper, etc.)
  - source_entity_type (enum: claim, evidence, study, concept, outcome, population, unknown)
  - relationship_type (enum: supports, contradicts, qualifies, causes, ...)
  - target_entity_id (UUID of target object)
  - target_entity_type (enum)
  - direction (enum: forward, backward, bidirectional)
  - confidence (enum: high, medium, low, unknown)
  - strength (optional numeric: 0–1)
  - specificity (enum: generic, magnitude_specific, population_specific, methodological, temporal)
  - contradiction_type (if applicable; enum: factual, magnitude, direction, population, methodological, temporal, definition_mismatch, apparent, unresolved, invalid_comparison)
  - resolution_suggested (optional text)
  - competing_relationships (list of alternative relationship interpretations)
  - supporting_evidence (list of evidence IDs that support this relationship)
  - contradicting_evidence (list of evidence IDs against this relationship)
  - created_at
  - created_by (human or automated)
  - reviewed_at (if manually reviewed)
  - reviewed_by (expert ID)
  - review_notes (optional)
  - versioned (bool; relationships can be versioned as understanding changes)
```

---

## Contradiction Detection as Proposal

**Key Principle**: Automated contradiction detection is a **proposal** requiring expert review, not an automatic declaration.

**Workflow**:
1. System detects apparent contradiction between Claims A and B
2. System surfaces contradiction as **proposal** for expert review
3. Expert examines: methodology, population, definitions, temporal factors
4. Expert decides: actual contradiction OR false alarm OR population-specific difference
5. Decision recorded with expert rationale
6. Competing expert views preserved if disagreement exists

---

## Open Questions

1. **Relationship Strength Scoring**
   - How to score "supports" on 0–1 scale? (high quality evidence? many replications? effect size?)
   - Can one relationship type be compared across relationship types (e.g., is strong support > weak contradiction)?

2. **Transitive Contradiction**
   - If A contradicts B, and B contradicts C, does A contradict C?
   - Or can A support C despite contradicting B?

3. **Temporal Contradictions**
   - When a finding changes over time, should older and newer versions be linked as contradictions?
   - Or should they be separate claims with lifecycle tracking?

4. **Expert Disagreement on Relationships**
   - If experts disagree on whether A supports or contradicts B, how to preserve both views?

5. **Prediction of New Relationships**
   - Should system propose relationships it infers but that aren't explicitly stated in papers?
   - What's the threshold for proposing inferred relationships?

---

**Next Document**: [05_confidence_uncertainty_and_assessment_profiles.md](05_confidence_uncertainty_and_assessment_profiles.md)
