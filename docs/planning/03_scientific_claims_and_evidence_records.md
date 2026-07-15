# 03. Scientific Claims and Evidence Records

**Status**: Future vision document. This feature does not exist in the current implementation.

**Current Implementation**: v0.2.0-alpha.1 indexes full PDF text only. Structured claim/evidence extraction is **not** included.

---

## Purpose

This is the most foundational document in the planning series.

It defines the distinction between:
- What a source **says**
- What was **observed**
- What **evidence** supports
- What an analyst or system **concludes**
- What **action** is recommended

These distinctions are essential for scientific integrity. Conflating them creates hidden epistemic transformations that obscure reasoning and enable error propagation.

---

## Core Object Types

### 1. Source

The original document or observation.

```
Source:
  - source_id (UUID)
  - doi (optional)
  - title
  - authors
  - publication_year
  - publication_venue (journal/conference)
  - source_type (enum: journal_article, preprint, book, conference_paper, report, data_paper, etc.)
  - peer_review_status (enum: peer_reviewed, preprint, grey_literature, internal)
  - availability (enum: open_access, subscription, restricted, archived)
  - ingested_at (when added to Knowledge Engine)
  - extraction_method (how text/claims were obtained)
```

**Key Point**: A source exists independent of what it claims. A retracted paper remains a source (understanding why it deceived the field is historically important).

---

### 2. SourceVersion

Sources can change (corrections, retractions, updated versions).

```
SourceVersion:
  - version_id (UUID)
  - source_id (reference)
  - version_number
  - content_hash (SHA256 of full text)
  - publication_date (when this version published)
  - status (enum: original, corrected, retracted, partially_retracted, superseded)
  - status_change_rationale (if status changed)
  - extraction_date (when ingested into Knowledge Engine)
```

**Example**: Original paper published Jan 2024 → Correction published Mar 2024 (SourceVersion 2) → Expression of concern Jun 2024 (SourceVersion 3).

---

### 3. SourceLocation

Where within a source the relevant information appears.

```
SourceLocation:
  - location_id (UUID)
  - source_version_id (reference)
  - location_type (enum: abstract, methods, results, discussion, conclusion, table, figure, supplementary)
  - page_number (optional)
  - paragraph_text (quoted text from source)
  - confidence (enum: direct_quote, paraphrase, inferred)
```

---

### 4. Observation

The raw empirical data or phenomenon described.

```
Observation:
  - observation_id (UUID)
  - source_id (reference)
  - source_location (reference)
  - observation_type (enum: measurement, count, binary_outcome, qualitative_description)
  - measured_variable (what was measured)
  - measurement_value (what was found)
  - measurement_unit
  - population (reference to PopulationRecord)
  - intervention (reference if applicable)
  - comparator (reference if applicable)
  - time_point (when measured)
  - context_description (text)
```

**Example**: "In 127 patients with type 2 diabetes treated with semaglutide 1.0mg weekly for 12 weeks, mean weight change was -5.2 kg (SD 3.1)."

---

### 5. Claim

An assertion or interpretation by the source authors.

```
Claim:
  - claim_id (UUID)
  - source_id (reference)
  - source_location (reference)
  - claim_type (enum: descriptive, causal, correlational, mechanistic, recommendation, interpretation, null_finding)
  - statement (text of claim)
  - subject (what is being claimed about)
  - predicate (what is asserted)
  - object (the thing being asserted)
  - population (reference)
  - intervention (reference)
  - comparator (reference)
  - outcome (reference)
  - context (reference)
  - direction (enum: increases, decreases, no_effect, mixed, unclear)
  - magnitude (optional; effect size, percent, etc.)
  - uncertainty (optional; 95% CI, error bars)
  - qualifiers (text: "in patients age 45–75" / "when combined with metformin")
  - observation_basis (reference to Observation if claim is based on data)
  - supporting_rationale (text: why authors claim this)
  - author_confidence (if stated: "likely" / "definitely" / "possible")
  - is_author_claim (bool: did authors explicitly state, or inferred from data)
```

**Critical Distinction**: 
- **Observation**: "Mean weight change was -5.2 kg"
- **Claim**: "Semaglutide is effective for weight loss in type 2 diabetes"

The observation is a fact (measurable). The claim is an interpretation (arguable).

---

### 6. EvidenceRecord

How evidence relates to a claim.

```
EvidenceRecord:
  - evidence_id (UUID)
  - claim_id (reference; what claim is this evidence about)
  - source_id (reference; where evidence comes from)
  - observation_id (reference; what observation)
  - direction (enum: supports, contradicts, qualifies, is_neutral_toward, is_insufficient_to_assess)
  - strength (enum: primary, secondary, methodological_critique, interpretation_dispute)
  - support_type (enum: empirical_result, secondary_analysis, subgroup_analysis, meta_analysis, mechanistic_evidence, replication, negative_result, null_finding)
  - confidence (enum: high, medium, low)
  - effect_size_match (optional: how closely does effect size match/contradict claim)
  - population_match (optional: does population in evidence match claim population)
  - mechanism_fit (optional: does evidence support proposed mechanism)
  - limitations_noted (text: what limits how strongly evidence supports)
  - conflicting_evidence_exists (bool; are there contradictory observations)
  - extracted_at (when created)
  - reviewed_at (when human assessed)
```

**Key Point**: Evidence can be **partial or qualified**. A study might support the claim's direction but contradict the magnitude.

---

### 7. MethodRecord

How evidence was generated.

```
MethodRecord:
  - method_id (UUID)
  - source_id (reference)
  - source_location (reference)
  - method_type (enum: randomized_trial, observational_cohort, case_control, cross_sectional, case_report, animal_model, in_vitro, simulation, meta_analysis, systematic_review)
  - sample_size (if applicable)
  - study_duration
  - follow_up_duration (optional)
  - blinding_status (enum: open_label, single_blind, double_blind, triple_blind, unknown)
  - randomization_method (optional)
  - primary_outcome (what was main goal)
  - secondary_outcomes (list)
  - statistical_method (text description)
  - power_calculation (optional)
  - pre_registration (optional; reference to registry)
  - conflict_of_interest (optional; text)
  - funding_source (optional)
  - methodological_strengths (list of MethodRecord)
  - methodological_limitations (list; author-stated and reviewer-identified)
  - comparison_to_standard_of_care (optional)
```

---

### 8. PopulationRecord

Who the evidence applies to.

```
PopulationRecord:
  - population_id (UUID)
  - source_id (reference)
  - population_type (enum: patients, healthy_volunteers, animal_model, in_vitro, other)
  - disease_or_condition (reference to condition taxonomy)
  - age_range (min, max)
  - gender_composition (optional; % male, % female, % other)
  - ethnicity_composition (optional; % reported by category)
  - comorbidities (list of conditions)
  - prior_treatment_history (text)
  - inclusion_criteria (text)
  - exclusion_criteria (text)
  - sample_size
  - loss_to_followup (optional; %)
  - generalizability_notes (text; author assessment of applicability)
```

---

### 9. OutcomeRecord

What was measured or assessed.

```
OutcomeRecord:
  - outcome_id (UUID)
  - source_id (reference)
  - outcome_name (text)
  - outcome_type (enum: binary, continuous, categorical, time_to_event, quality_of_life, safety_adverse_event, mortality, morbidity)
  - measurement_method (how was outcome assessed)
  - measurement_instrument (if applicable; e.g., "HOMA-IR")
  - unit_of_measurement
  - time_point_assessed
  - primary_or_secondary (enum: primary, secondary, exploratory)
  - clinically_significant_threshold (optional; what magnitude matters)
  - missing_data_rate (optional; %)
  - data_quality_issues (optional; text)
```

---

### 10. LimitationRecord

What weakens the evidence.

```
LimitationRecord:
  - limitation_id (UUID)
  - evidence_id or source_id (what does this limit)
  - limitation_type (enum: sample_size, short_followup, lack_of_blinding, selection_bias, attrition_bias, reporting_bias, conflicts_of_interest, methodological_concern, applicability_concern, funding_bias)
  - severity (enum: minor, moderate, major)
  - description (text of limitation)
  - identified_by (enum: source_authors, peer_reviewers, meta_analysts, Knowledge_Engine_extraction)
  - impact_on_evidence (text; how does this limit strength)
  - mitigation_possible (bool; can limitation be addressed)
  - remediation_method (optional; how to address in future research)
```

---

### 11. Conclusion

What the authors conclude from their evidence.

```
Conclusion:
  - conclusion_id (UUID)
  - source_id (reference)
  - source_location (reference)
  - statement (text)
  - based_on_claims (list of claim_id references)
  - level_of_certainty (enum: definite, probable, possible, speculative, insufficient_evidence)
  - applicability_statement (text; to whom does this apply)
  - future_research_needed (text; what gaps remain)
```

**Key Point**: Conclusion is author's judgment. It may or may not be warranted by evidence. Both are preserved.

---

### 12. Recommendation

What action is proposed.

```
Recommendation:
  - recommendation_id (UUID)
  - source_id (reference)
  - conclusion_id (reference; based on what conclusion)
  - recommendation_statement (text)
  - target_audience (enum: clinicians, patients, researchers, policy_makers, drug_developers)
  - recommended_action (text)
  - strength_of_recommendation (enum: strong, weak, conditional)
  - evidence_quality_grade (enum: high, moderate, low, very_low)
  - context_for_recommendation (text; when does this apply)
  - contraindications (text; when NOT to recommend)
  - uncertainty_statement (text; what remains unknown)
```

**Critical Boundary**: Recommendation is **not** a fact. It depends on values, applicability, and context. Same evidence can support different recommendations depending on who decides and what they prioritize.

---

### 13. Unknown

Explicit statement of what remains unknown.

```
Unknown:
  - unknown_id (UUID)
  - statement (text of what is unknown)
  - related_claim (optional reference; what claim leaves this open)
  - knowledge_gap_type (enum: never_studied, insufficient_evidence, conflicting_evidence, inaccessible_evidence, currently_unmeasurable, unresolved_dependency)
  - importance (enum: critical, important, useful_but_not_critical, exploratory)
  - methods_to_address (text; how could this be studied)
  - estimated_priority (enum: urgent, high, medium, low)
```

---

## Claim Granularity and Identity

A claim should be precise enough to compare across sources.

### Poor Claim Granularity
❌ "Semaglutide works"

### Better Claim Granularity
✅ "Semaglutide 1.0 mg weekly reduces body weight by 5–8 kg in adults with type 2 diabetes without prior GLP-1 treatment, compared to placebo, over 12 weeks, with higher effect in BMI 30–35 than BMI >35."

### Minimum Claim Precision
A claim should include (where applicable):

| Element | Example |
|---------|----------|
| **Subject** | Semaglutide (specific agent, dose, route) |
| **Predicate/Relationship** | Reduces |
| **Object** | Body weight |
| **Magnitude** | 5–8 kg |
| **Population** | Adults with T2D, no prior GLP-1, age 45–75 |
| **Intervention** | Semaglutide 1.0 mg weekly |
| **Comparator** | Placebo (or alternative agent) |
| **Outcome** | Change in body weight |
| **Context** | Without other lifestyle changes |
| **Time Horizon** | 12-week treatment |
| **Direction** | Decrease (reduction) |
| **Uncertainty** | 95% CI or error bars |
| **Qualifiers** | "Heterogeneous by baseline BMI; larger in BMI 30–35" |

---

## Evidence Direction

### Supports
Evidence is consistent with and strengthens the claim.
- Example: "Study found 6 kg weight loss with semaglutide; claim states 5–8 kg." ✅ Supports

### Contradicts
Evidence directly opposes the claim.
- Example: "Study found weight loss of only 1 kg; claim states 5–8 kg." ❌ Contradicts

### Qualifies
Evidence supports the general claim but reveals limitations or subgroup specificity.
- Example: "Weight loss 7 kg in age 45–75 but only 3 kg in age >75; claim didn't specify age dependency." ⚠️ Qualifies

### Is Neutral Toward
Evidence doesn't directly address the claim.
- Example: "Study showed GLP-1 reduces cardiovascular mortality; claim is about weight loss." ↔️ Neutral

### Is Insufficient to Assess
Evidence is ambiguous or too limited.
- Example: "Small case report suggests possible weight loss; too few patients to confirm." ❓ Insufficient

---

## Review State and Provenance

Every record includes:

```
Review Metadata:
  - created_at
  - created_by (system or human)
  - creation_method (enum: manual_extraction, automated_parsing, AI_assisted, user_submission)
  - creation_confidence (enum: high_confidence, medium_confidence, uncertain)
  - reviewed_at (when expert examined)
  - reviewed_by (expert ID)
  - review_decision (enum: approved, approved_with_edits, needs_revision, rejected)
  - review_notes (text)
  - last_modified_at
  - modification_reason (text)
  - version_history (list of prior versions)
```

---

## Open Questions

1. **Claim Extraction Automation**
   - How much can NLP reliably extract vs. require manual review?
   - What confidence threshold justifies auto-extraction vs. requiring human review?

2. **Subjectivity in Evidence Direction**
   - When evidence partially supports/contradicts, who decides the primary direction?
   - Should conflicting assessments be preserved?

3. **Negative Results and Null Findings**
   - How to represent "Study found NO difference" vs. "Study was too small to detect difference"?
   - Are both treated equally?

4. **Secondary vs. Primary Evidence**
   - Should secondary analyses (post-hoc subgroups) be weighted differently than primary outcomes?

5. **Author Interpretation vs. Data**
   - When authors interpret findings one way but data could support alternative interpretation, which is recorded as the claim?

---

**Next Document**: [04_relationship_and_contradiction_model.md](04_relationship_and_contradiction_model.md)
