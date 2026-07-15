# 02. Knowledge Lifecycle and Evidence Decay

**Status**: Future vision document. This feature does not exist in the current implementation.

**Current Implementation**: v0.2.0-alpha.1 treats all indexed papers as equally current. Knowledge lifecycle tracking is **not** included.

---

## Purpose

Knowledge does not exist in a timeless state. Scientific findings evolve through multiple dimensions:
- Direct replication attempts (confirming or contradicting)
- Methodological critique (revealing limitations or strengths)
- Superseding evidence (newer, larger, better-designed studies)
- Technical advancement (enabling what was previously impossible)
- Real-world application (revealing practical limits)
- Retraction or correction (fixing errors)
- Changing applicability (as populations, conditions, or technology shift)

This document defines lifecycle models that preserve **historical knowledge** while acknowledging **current applicability**, without collapsing evidence into a single "truth score" or silently erasing prior work.

---

## Core Principle: Age Is Not Decay

**Important**: Age alone does not indicate decline in knowledge value.

- A 1950s epidemiology study may be methodologically sound and remain relevant
- A 2024 industry-funded trial may have serious limitations
- A retracted paper remains historically important (it deceived the field for X years)
- A superseded theory reveals what was believed, even if now proven false

**Lifecycle tracking must separate**:
- Historical importance (what was believed when)
- Methodological validity (does evidence support conclusion)
- Current applicability (does finding apply to my population/context)
- Technical obsolescence (can finding be improved by newer methods)
- Formal status (accepted, contested, retracted)
- Review freshness (when was this last assessed)

---

## Lifecycle Dimensions

Every piece of evidence occupies a position in multiple, independent dimensions:

### Dimension 1: Evidentiary Stability

How robust is the evidence base supporting a claim?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Singular** | One study; no replication attempts yet | "Study A found X; no follow-up yet" |
| **Replicated** | Multiple independent groups confirm finding | "Three RCTs found similar effect sizes" |
| **Contested** | Some studies replicate; others contradict | "Five studies found effect; two found null" |
| **Robust** | Consistent finding across many study types, populations | "Meta-analysis: 50+ studies, consistent direction" |
| **Fragile** | Finding disappears or reverses with minor methodological change | "Effect observed only if P<0.05; disappears with multiple-comparison correction" |

### Dimension 2: Current Applicability

Does this evidence apply to current clinical/research practice?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Directly Applicable** | Finding applies to current populations, treatments, outcomes | "RCT in modern T2D patients on current GLP-1 agents" |
| **Conditionally Applicable** | Applies to specific subgroups; not universal | "Finding applies to age 45–75; unclear in younger/older" |
| **Context-Dependent** | Applies in some settings but not others | "Finding valid in high-income countries; unclear in resource-limited" |
| **Obsolete** | No longer applicable due to changed technology, guidelines, population | "Pre-insulin-pump era diabetes management; outdated" |
| **Unknown Applicability** | May apply; insufficient current data | "Historical finding; modern generalizability untested" |

### Dimension 3: Historical Importance

Is this evidence important for understanding how the field evolved?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Foundational** | Seminal work that established field or direction | "First description of GLP-1 receptor in pancreatic beta cells" |
| **Landmark** | Major finding that shifted consensus | "First RCT showing GLP-1 CV benefit; changed treatment paradigm" |
| **Incremental** | Adds to established body of evidence; not transformative | "Another Phase II trial of similar agent; confirms prior pattern" |
| **Archival** | Mostly historical interest; not cited in modern work | "1980s observational study; superceded by modern methods" |
| **Erased** | Once influential, now forgotten despite no formal retraction | "Study cited heavily 1990s–2000s; rarely cited now" |

### Dimension 4: Technical Obsolescence

Can current methods do better than this evidence?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Current Gold Standard** | Best available method for this question | "Recent Phase III RCT with modern statistical methods" |
| **Still Valid** | Method is sound; newer methods available but not always superior | "Meta-analysis from 5 years ago; newer studies don't change conclusion" |
| **Methodologically Dated** | Sound for its time; better methods now available | "2000 observational study; modern prospective design would be better" |
| **Technically Superseded** | Newer technology renders method obsolete | "Manual blood glucose monitoring; CGM now standard" |
| **Fundamentally Flawed** | Method has known limitations that weren't appreciated when conducted | "Study couldn't account for confounder X; now recognized as critical" |

### Dimension 5: Formal Validity Status

What is the official status of this evidence?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Accepted** | Passed peer review; no concerns raised | "Published in peer-reviewed journal; no retractions" |
| **Accepted with Caveat** | Peer-reviewed; but limitations or criticisms noted | "Published; subsequent letter published critiquing methods" |
| **Contested** | Legitimate scientific disagreement about validity | "Published; competing interpretation in other papers" |
| **Questioned** | Concerns raised (editorial notice, expression of concern) | "Journal issued expression of concern; under investigation" |
| **Partially Retracted** | Some findings retracted; others stand | "Retraction of Figure 2; other figures valid" |
| **Fully Retracted** | Paper withdrawn; considered invalid | "Retracted for fraud; all findings discredited" |
| **Withdrawn** | Author withdrew for reasons other than error | "Author withdrew due to ethical concern; not fraud" |

### Dimension 6: Review Freshness

When was this evidence last formally assessed?

| Status | Meaning | Examples |
|--------|---------|----------|
| **Recently Reviewed** | Expert assessment completed within 1–2 years | "Meta-analysis from 2025; incorporates 2024 trials" |
| **Due for Review** | 3–5 years since last formal assessment | "Systematic review from 2022; new trials likely available" |
| **Overdue for Review** | >5 years; significant new evidence may exist | "Review from 2020; GLP-1 landscape changed substantially" |
| **Never Systematically Reviewed** | No formal review; only cited in passing | "Observational finding; never subject of systematic analysis" |
| **Excluded from Recent Review** | Deliberately not included in recent assessment | "Meta-analysis excluded papers before 2000; older finding not reassessed" |

---

## Lifecycle Labels

These labels combine dimensions into practical states:

### Core Labels

| Label | Status Combination | Use Case |
|-------|-------------------|----------|
| **Current** | Directly applicable + Robust evid. + Recently reviewed | Use as basis for current decisions |
| **Stable** | Conditionally/directly applicable + Replicated + Methodologically sound | Can rely on; note conditions |
| **Emerging** | Singular or replicated + Directly applicable + Recent | Shows promise; needs more evidence |
| **Contested** | Contested evidence + Accepted with caveats | Multiple interpretations; note disagreement |
| **Qualified** | Conditionally applicable + Context-dependent + Accepted | Apply cautiously; specify conditions |
| **Superseded** | Methodologically outdated + Newer evidence available | Note prior finding; cite newer evidence |
| **Historically Important** | Landmark + No longer directly applicable | Preserve for historical understanding |
| **Obsolete** | No longer applicable + Methodologically dated | Archive; rarely consult |
| **Retracted or Invalidated** | Fully retracted or fundamentally flawed + Rejected by community | Treat with extreme caution; understand why |

---

## Key Distinctions

### Source Lifecycle vs. Claim Lifecycle

The same paper can have claims with different lifecycles:
- **Source**: Published in 2020, still valid, recently reviewed
- **Claim A (primary finding)**: Current, robust evidence
- **Claim B (secondary finding)**: Emerging, singular evidence
- **Claim C (mechanistic interpretation)**: Contested, with competing interpretations

Each claim gets its own lifecycle independent of source publication date.

---

### Claim Versioning

A single claim can evolve:

```
Initial Claim: "GLP-1 agonists reduce weight by 5%"
  ↓ (newer evidence)
Refined Claim: "GLP-1 agonists reduce weight by 5% ± 2% (95% CI) in non-insulin-dependent T2D"
  ↓ (subgroup analysis)
Qualified Claim: "GLP-1 agonists reduce weight by 5% in age 45–75; 3% in age 75+; data sparse in <45"
  ↓ (mechanistic understanding)
Mechanistically-Grounded: "Weight reduction through combination of decreased appetite + increased satiety + possible metabolic effects"
```

Each version is timestamped, linked to supporting evidence, and clearly marked as historical or current.

---

### Competing Assessments Coexist

The same evidence can have competing lifecycle labels based on different expert assessments:

- Expert A: "Finding is Robust; safe to apply"
- Expert B: "Finding is Contested; wait for more evidence"
- Both assessments preserved; not averaged or collapsed

---

## Reassessment Triggers

Lifecycle status should be **actively reassessed** when:

1. **New evidence appears**
   - New studies directly testing the claim
   - New meta-analyses incorporating more data
   - Retraction or correction of cited evidence

2. **New methodological critique**
   - Published critique of study design
   - Recognition of previously-unappreciated confounder
   - Statistical reanalysis with multiple-comparison correction

3. **Time milestone**
   - 5+ years since last formal review
   - Domain consensus has shifted
   - Real-world application reveals unexpected limits

4. **Change in applicability**
   - New population group studied
   - New treatment variant introduces questions
   - Guidelines change, affecting relevance
   - Technology advancement enables better assessment

5. **Retraction, correction, or expression of concern**
   - Any formal problematization of source
   - New evidence of methodological flaw
   - Conflict of interest disclosure

---

## Preservation Requirements

When knowledge lifecycle changes, **all prior assessments remain preserved**:

```
Claim: "GLP-1 reduces weight"

v1 (2015): Current (based on limited evidence)
  → Evidence: Single RCT
  → Expert assessment: "Promising"
  → Status: Emerging
  
v2 (2018): Current (based on meta-analysis)
  → Evidence: Meta-analysis of 5 RCTs
  → Expert assessment: "Established"
  → Status: Robust
  
v3 (2023): Qualified (based on subgroup analysis)
  → Evidence: 20 RCTs, but heterogeneous effect sizes by age/BMI
  → Expert assessment: "Effect size varies; not universal"
  → Status: Qualified
  
v4 (2025): Contested (based on industry-funded trials controversy)
  → Evidence: Same trials, but questions raised about funding bias
  → Expert assessment: "Valid effect, but question about magnitude"
  → Status: Contested

Current User Can See: All versions; choose which to rely on
Previous Readers Can See: What was accepted in 2015, 2018, 2023 (historical understanding)
```

---

## Conceptual Data Model

(Conceptual only; do not implement without Phase 5+ milestone and ADR)

```
Claim:
  - claim_id (UUID)
  - statement (text)
  - population (reference)
  - intervention (reference)
  - comparator (reference)
  - outcome (reference)
  - created_at
  - current_version (→ ClaimVersion)
  - versions (list of ClaimVersion)

ClaimVersion:
  - version_id (UUID)
  - claim_id (reference)
  - version_number
  - statement (may differ slightly from current)
  - evidence_base (list of Evidence)
  - expert_assessment (→ ExpertAssessment)
  - lifecycle_status (enum: current, stable, emerging, contested, qualified, superseded, historically_important, obsolete, retracted)
  - validity_status (enum: accepted, accepted_with_caveat, contested, questioned, partially_retracted, fully_retracted, withdrawn)
  - applicability_status (enum: directly_applicable, conditionally_applicable, context_dependent, obsolete, unknown)
  - evidentiary_stability (enum: singular, replicated, contested, robust, fragile)
  - technical_obsolescence (enum: current_gold_standard, still_valid, methodologically_dated, technically_superseded, fundamentally_flawed)
  - historical_importance (enum: foundational, landmark, incremental, archival, erased)
  - last_reviewed_date
  - review_due_date
  - superseded_by (optional reference to newer ClaimVersion)
  - qualifications_text (caveat/context)
  - created_at
  - updated_at

Evidence:
  - evidence_id (UUID)
  - source_id (reference to Paper)
  - supporting (bool: true if supports; false if contradicts)
  - direction (enum: supports, contradicts, qualifies, neutral, insufficient)
  - strength (enum: primary, secondary, methodology, interpretation)
  - effect_size (optional)
  - confidence_interval (optional)
  - population_specificity (optional)
  - extracted_at
  - extraction_method (string: "manual" / "automated" / "algorithm_name")

ExpertAssessment:
  - assessment_id (UUID)
  - claim_version_id (reference)
  - reviewer_id (reference to Expert)
  - reviewer_affiliation
  - conflict_of_interest_disclosure
  - assessment_date
  - validity_opinion (enum)
  - applicability_opinion (enum)
  - historical_importance_opinion (enum)
  - rationale_text
  - suggested_status (enum)
  - supported_by_evidence (list of Evidence)
  - contradicted_by_evidence (list of Evidence)
  - concerns_text (optional)
  - competing_assessments (list of ExpertAssessment)
```

---

## Governance

Lifecycle status changes are **not automatic**:

1. **System Proposes**: Algorithm detects new evidence or review-due milestone
2. **System Routes**: Proposal sent to qualified expert reviewer
3. **Expert Reviews**: Examines evidence, rationale, competing interpretations
4. **Expert Decides**: Proposes new status with rationale
5. **Governance Records**: Decision, dissent, and rationale become permanent record

---

## Open Questions

1. **Frequency of Reassessment**
   - How often to automatically flag claims as "due for review"?
   - Who decides reassessment priority?
   - Can researchers request reassessment of specific claims?

2. **Conflicting Expert Opinions**
   - If experts disagree on lifecycle status, which to show?
   - Should all opinions be visible, or just consensus?
   - How to resolve stalemate?

3. **Temporal Scope**
   - How many years of historical assessment to preserve?
   - Do we keep assessments from 30 years ago?
   - When does archival evidence become too old to maintain?

4. **Population-Specific Lifecycles**
   - Should lifecycle status be indexed by population (e.g., "Current for age 45–75, Qualified for age 75+")?
   - How granular can populations be?

5. **Decay Rates**
   - Different domains have different obsolescence rates
   - Should "review due" dates be domain-specific?
   - What about fast-moving fields (AI) vs. stable fields (anatomy)?

---

**Next Document**: [03_scientific_claims_and_evidence_records.md](03_scientific_claims_and_evidence_records.md)
