# 01. Knowledge Discovery Architecture

**Status**: Future vision document. This feature does not exist in the current implementation.

**Current Implementation**: v0.2.0-alpha.1 provides local PDF ingestion, FTS search, corpus manifest validation, and import-run persistence. Discovery capabilities are **not** included.

---

## Purpose

A future Knowledge Engine may identify and propose research opportunities emerging from the indexed corpus. This document describes the architecture, inputs, outputs, guardrails, and human-review boundaries for a knowledge-discovery system that is:

- Evidence-driven (all proposals traceable to sources)
- Humility-first (acknowledges corpus limits, false-novelty risks)
- Human-review-gated (proposals awaiting expert examination)
- Provisionally-framed (proposals are hypotheses, not conclusions)
- Transparently-generated (algorithm, version, date visible)
- Contestable (reviewers can dispute; counterevidence preserved)

---

## Inputs

Discovery processes consume:

1. **Indexed Corpus**
   - Papers ingested via M9 bulk import
   - Structured claims extracted via Phase 2
   - Evidence records linked via Phase 2
   - Relationships indexed via Phase 4

2. **Knowledge Graph State**
   - Concept definitions and connections (Phase 4)
   - Citation networks (Phase 4)
   - Population/outcome/intervention taxonomies (Phase 2)
   - Existing unknown/gap inventory (this document)

3. **Assessment Profiles** (from Phase 5+)
   - Confidence dimensions for claims
   - Lifecycle status of evidence
   - Contradiction registry
   - Replication strength
   - Methodological consistency scores
   - Corpus-coverage flags

4. **Prior Discovery Output**
   - Previously proposed research avenues
   - Human-review decisions and rationale
   - Resolved vs. unresolved proposals
   - Evidence that addressed proposals

---

## Outputs

Discovery processes propose research avenues. Each proposal is a **machine-generated hypothesis**, not a fact or recommendation. Outputs include:

### 1. Missing Connections

**Format**: "Concept A and Concept B are mentioned separately in N papers each, but fewer than K papers mention both; connection may be unexplored."

**Example**: GLP-1 agonists + cardiovascular outcomes (127 papers on weight loss; 43 on CV outcomes; 8 on both).

**Inputs Required**:
- Concept definitions
- Co-occurrence statistics
- Prior knowledge about known connections

**False-Novelty Safeguard**: System must verify both concepts appear in corpus before proposing connection.

### 2. Unresolved Contradictions

**Format**: "Study A found outcome X increased by Y%; Study B found it decreased by Z% in similar population; unexplained disagreement."

**Example**: Semaglutide weight loss: 10% in study X, 5% in study Y; methodological or population differences not resolved.

**Inputs Required**:
- Extracted claims with outcome/population/comparator
- Effect-size normalization and unit conversion
- Contradiction detection algorithm
- Methodological flagging (different doses, follow-up periods, etc.)

**False-Novelty Safeguard**: Proposal must verify disagreement is genuine, not artifact of measurement unit or population differences.

### 3. Missing Replications

**Format**: "Finding F reported in paper P has not been independently confirmed; candidates for replication study."

**Example**: Specific GLP-1 mechanism demonstrated in one lab; no replication yet.

**Inputs Required**:
- Study outcomes and hypotheses
- Independent research group tracking
- Replication attempt records
- Time since original finding

**False-Novelty Safeguard**: System must distinguish "no indexed replication" from "replication not published" from "replication attempted but failed."

### 4. Underexplored Populations

**Format**: "Domain X has strong evidence in population A, but sparse evidence in populations B, C; gap in applicability."

**Example**: GLP-1 studies concentrated in age 45–75; limited data in <30 or >80 populations.

**Inputs Required**:
- Population taxonomies
- Study enrollment demographics
- Evidence-count by population
- Prior knowledge about representative sampling

**False-Novelty Safeguard**: System must not assume sparse data = global gap; may reflect legitimate lower-risk in some populations.

### 5. Candidate Hypotheses

**Format**: "Given evidence for A and evidence for B, mechanistic connection C is plausible; testable hypothesis."

**Example**: GLP-1 → GLP-1 receptor activation → increased satiety → reduced caloric intake → weight loss. (Or alternative pathway through hepatic glucose metabolism.)

**Inputs Required**:
- Mechanistic evidence (animal models, in vitro, patient biomarkers)
- Outcome evidence (clinical results)
- Prior hypotheses and their status
- Mechanism taxonomy

**False-Novelty Safeguard**: Proposal must cite evidence for each step; cannot invent mechanism from absence.

### 6. Validation Experiments

**Format**: "To test hypothesis H, experiment E would be valuable; expected outcome O would support/refute H."

**Example**: "To test whether GLP-1 effects are independent of weight loss, randomize groups to weight-loss-matched vs. weight-gain conditions while on GLP-1; measure CV parameters."

**Inputs Required**:
- Hypothesis statement
- Current evidence gaps
- Experimental design considerations
- Outcome measurement strategies
- Power/sample-size literature

**False-Novelty Safeguard**: Proposal must acknowledge existing similar trials; not invent from scratch.

### 7. Expected-Information-Gain Opportunities

**Format**: "Among all current unknowns, finding X would resolve Y decision-relevant questions; prioritize research toward X."

**Example**: Long-term CV outcomes in lean individuals with T2D on GLP-1; informs whether effects are weight-independent.

**Inputs Required**:
- Current gap inventory
- Applicability linkages (which decision depends on this gap)
- Estimated impact on uncertainty reduction
- Resource requirements to address gap

**False-Novelty Safeguard**: Proposal must quantify expected impact, not assume filling any gap is valuable.

### 8. Research Priorities

**Format**: "Among proposals P1, P2, …, Pn, priorities are [ranked list] based on information gain, feasibility, and applicability."

**Example**: Priority 1: CV outcomes in lean population (affects treatment guidelines). Priority 2: mechanism clarification (influences future drug development).

**Inputs Required**:
- All candidate proposals
- Impact weighting (severity of gap, affected decisions, populations)
- Feasibility scoring (technical difficulty, time, resources)
- Applicability assessment (how many stakeholders affected)
- User context (clinician vs. researcher vs. drug developer)

**False-Novelty Safeguard**: Ranking must be auditable; different contexts may have different priorities; not a single global truth.

---

## Dependencies

Discovery requires prior Knowledge Engine phases:

| Phase | Required For | Status |
|-------|--------------|--------|
| **Phase 1** | Bulk corpus ingestion | M9 implementation |
| **Phase 2** | Structured claim extraction | Planned |
| **Phase 3** | Semantic search (optional enhancement) | Planned |
| **Phase 4** | Knowledge graph, relationships | Planned |
| **Phase 5** | Discovery system launch (estimated) | Future |

**Critical Dependency**: Structured **claim extraction** (Phase 2) is the prerequisite for most discovery functions. Without machine-readable claims, discovery must rely on full-text statistics, which is fragile.

---

## Proposed Services

### Discovery Service (Umbrella)

Orchestrates discovery workflows:

```
DiscoveryService:
  - discovery_run(corpus_version, algorithm_version) → DiscoveryResult
  - list_proposals(filters, status) → [ResearchProposal]
  - get_proposal_detail(proposal_id) → ProposalDetail
  - record_review_decision(proposal_id, decision, rationale) → ReviewRecord
  - retract_proposal(proposal_id, reason) → void
  - export_proposals(format, filters) → bytes
```

### Specialized Discovery Workers

Workers implement specific discovery patterns:

1. **MissingConnectionDetector**
   - Inputs: Concept definitions, co-occurrence matrix
   - Output: Missing-connection proposals
   - Governance: Concept corpus coverage check

2. **ContradictionDetector**
   - Inputs: Extracted claims, outcomes, populations, effect sizes
   - Output: Contradiction proposals
   - Governance: Methodological differences check

3. **ReplicationGapDetector**
   - Inputs: Study findings, research-group affiliations, publication dates
   - Output: Missing-replication proposals
   - Governance: Time-since-original threshold

4. **PopulationGapDetector**
   - Inputs: Population taxonomies, evidence stratification
   - Output: Underexplored-population proposals
   - Governance: Minimum evidence-count thresholds

5. **HypothesisGenerator**
   - Inputs: Mechanistic evidence, outcome evidence, prior hypotheses
   - Output: Candidate-hypothesis proposals
   - Governance: Mechanism-chain completeness check

6. **ExperimentProposer**
   - Inputs: Hypotheses, existing trials, outcome taxonomies
   - Output: Validation-experiment proposals
   - Governance: Design-similarity deduplication

7. **InformationGainRanker**
   - Inputs: Gap inventory, decision-impact assessments
   - Output: Information-gain scores, research priorities
   - Governance: Applicability weighting rules

### Governance Service

Manages human review and proposal lifecycle:

```
GovernanceService:
  - queue_for_review(proposal_id, expertise_requirements) → ReviewQueue
  - record_review(proposal_id, reviewer_id, decision, rationale) → ReviewRecord
  - appeal_decision(proposal_id, objection_text) → AppealQueue
  - accept_with_qualification(proposal_id, qualifications) → QualifiedProposal
  - retract_if_evidence_changes(proposal_id, new_evidence) → void
  - publish_accepted(proposal_id) → PublicProposal
```

---

## Proposal Lifecycle

Every proposal follows this state machine:

```
Generated
    ↓
FlaggedForReview
    ↓
InReview (expert examination)
    ↓ (decision point)
    ├→ Approved (publish as research guidance)
    ├→ ApprovedWithQualification (publish with caveats)
    ├→ Rejected (archive with rationale)
    ├→ Deferred (defer pending new evidence)
    └→ Disputed (competing expert interpretation)
         ↓
    (cycle back to InReview or Accepted if new evidence emerges)
         
Any state + NewEvidence → Reassess (may move to different state)
Any state + Retracted → Withdrawn (preserve as historical record)
```

**State Definitions**:

- **Generated**: Automated detection; awaiting triage
- **FlaggedForReview**: System determined proposal is plausible; ready for expert queue
- **InReview**: Expert(s) examining supporting/contradictory evidence
- **Approved**: Expert consensus that proposal is scientifically sound and important
- **ApprovedWithQualification**: Approved; but with specific caveats (limited population, methodological concern, etc.)
- **Rejected**: Expert consensus that proposal lacks merit, has flaw, or doesn't represent gap
- **Deferred**: Deferred pending new evidence or better prior proposals on same topic
- **Disputed**: Multiple expert views; competing interpretations preserved
- **Withdrawn**: Retracted due to evidence of error, outdated, or replaced by other proposal

**Lifecycle Rules**:

1. Proposals may remain in review indefinitely; no automatic approval by timeout
2. New evidence may trigger reassessment; state changes require documented reason
3. Rejection is not deletion; rationale preserved for future contributors
4. Competing expert views may coexist (mark as Disputed, preserve both)
5. Accepted proposals remain provisional; not treated as permanent truth
6. Retraction of supporting evidence → proposal reassessment (may move to Deferred)

---

## Traceability Requirements

Every proposal must maintain complete audit trail:

### Supporting Evidence
- For each piece of evidence: paper DOI/ID, claim ID, snippet, relevance explanation
- Link to structured claim if extracted; or full-text reference if not
- Extraction method and version (parser version, extraction algorithm version)

### Contradictory Evidence
- For each contradictory piece: same detail as supporting
- Explanation of why it contradicts (magnitude difference, population difference, etc.)
- Flag whether contradictions are resolvable or genuine disagreement

### Missing Evidence
- Explicit list of what evidence would strengthen proposal
- Explicit list of what evidence would refute proposal
- These lists make proposal **testable**

### Assumptions
- Each assumption: statement, limitation, and how to validate
- Examples:
  - Assumption: "All relevant papers before date X are indexed"
  - Limitation: "Grey literature and preprints may not be indexed"
  - Validation: "Search Google Scholar for non-indexed papers on same topic"

### Proposal Genealogy
- Algorithm that generated proposal (name, version)
- Generation date and time
- System version and configuration
- Any parameter tuning (thresholds, weights, etc.)
- Reproducibility: inputs sufficient to regenerate with same algorithm

### Human Review Trail
- Reviewer name/ID, affiliation, conflict-of-interest declaration
- Review date and time
- Rationale for decision (link to specific evidence or reasoning)
- Any evidence the reviewer added or corrected
- If rejected/disputed: alternative interpretation or evidence

---

## False-Novelty Safeguards

**Central Principle**: Absence from the indexed corpus ≠ evidence of gap or novelty.

### Rule 1: Bi-Directional Verification

Before proposing "Connection between A and B is unexplored":
- ✅ Verify both A and B appear separately in corpus
- ✅ Verify neither A nor B are rare (threshold: >N papers each)
- ❌ Do NOT propose merely because A+B co-occurrence is zero (could be database error or indexing lag)

### Rule 2: Competing Explanations

Before proposing "Study X contradicts Study Y":
- ✅ Verify actual disagreement, not mere measurement-unit difference
- ✅ Check for population-specific effects (not contradictory if applied to different pops)
- ✅ Check for temporal effects (not contradictory if one is preliminary/later corrected)
- ❌ Do NOT propose if disagreement resolves through context

### Rule 3: Replication vs. Absence

Before proposing "Finding F has no replication":
- ✅ Verify direct replication attempts exist; check whether they succeeded/failed
- ✅ Distinguish: "no replication attempt yet" vs. "attempted but failed" vs. "attempted and succeeded but not indexed"
- ❌ Do NOT assume sparse indexed results = sparse real attempts

### Rule 4: Population Gaps vs. Natural Variation

Before proposing "Population P is underexplored":
- ✅ Verify P is clinically relevant or scientifically important
- ✅ Verify sparse evidence is not due to lower disease incidence (e.g., fewer <20-year-olds with T2D)
- ❌ Do NOT propose gaps in inherently rare populations as equal-priority with common populations

### Rule 5: Mechanism Plausibility vs. Invention

Before proposing mechanistic hypothesis:
- ✅ Verify each step in causal chain has at least some evidence
- ✅ Cite specific evidence for each intermediate
- ❌ Do NOT invent missing steps from first principles alone

### Rule 6: Explicit Corpus-Coverage Caveats

Every proposal must state:
- "Proposal based on papers indexed as of [date]"
- "Non-indexed categories: [grey literature / preprints / non-English / other specific gaps]"
- "Gap may not represent true gap in scientific literature"

---

## Human-Review Boundary

Discovery is **evidence-proposing**, not **evidence-adjudicating**. The system proposes; humans decide.

### System Responsibility (Automated)
- ✅ Detect statistical patterns in corpus
- ✅ Propose hypotheses matching patterns
- ✅ Collect supporting and contradictory evidence
- ✅ Compute information-gain metrics
- ✅ Flag false-novelty risks
- ✅ Route to qualified reviewers
- ✅ Preserve rationale for every proposal

### Human Responsibility (Expert Review)
- ✅ Verify proposal accurately represents evidence
- ✅ Assess scientific merit and novelty
- ✅ Identify hidden assumptions or alternative explanations
- ✅ Judge importance and research priority
- ✅ Declare conflicts of interest
- ✅ Preserve minority viewpoints
- ✅ Approve only proposals meeting institutional standards

### Never Automatic
- ❌ Proposal approval cannot be automatic or by-default
- ❌ High statistical significance does not bypass review
- ❌ System cannot make binding decisions on proposal publication
- ❌ System cannot suppress contrary expert opinion
- ❌ System cannot declare proposals "ground truth" or "consensus"

---

## Non-Goals

The discovery system deliberately does **not**:

1. **Make clinical recommendations**
   - Discovery proposes research; recommendations require clinical governance
   - System cannot advise treatment changes based on proposals

2. **Determine global novelty**
   - Only audits indexed corpus
   - Cannot claim propositions are novel outside that corpus

3. **Replace expert judgment**
   - Automates evidence synthesis, not expertise
   - Experts retain final decision authority

4. **Optimize for consensus**
   - Does not suppress minority viewpoints
   - Does not hide dissenting expert opinions
   - Disagreement is preserved, not resolved by voting

5. **Prioritize high-profile research**
   - Does not rank by citation count, journal prestige, or author reputation
   - Ranks only by information-gain and applicability

6. **Predict publication**
   - Does not forecast which proposals will lead to funded research
   - Only proposes research questions that seem important

7. **Guarantee completeness**
   - Does not claim to find all gaps
   - Algorithm-dependent; different algorithms may find different proposals

8. **Make binding policy decisions**
   - Proposals inform policy; do not determine it
   - Policy-makers retain discretion

---

## Future Milestone Placement

Knowledge discovery is estimated for **Phase 5** or later:

| Phase | Timeline | Focus |
|-------|----------|-------|
| **0–1** | Now–6mo | Bulk corpus ingestion (M9–M14) |
| **2** | 6–12mo | Claim extraction, evidence records |
| **3** | 12–18mo | Semantic search, embeddings |
| **4** | 18–24mo | Knowledge graph, relationships |
| **5** | 24–36mo | Discovery system (this document) |
| **6+** | 36mo+ | Advanced reasoning, synthesis |

**Earliest Realistic Start**: After Phase 4 relationships exist (estimated 2 years).

**Prerequisite Decisions**:
- Phase 2 must define machine-readable claim/evidence schemas
- Phase 4 must define relationship types and contradiction model
- Phase 5 must specify expert-review governance
- Before launch: pilot with small corpus and 2–3 discovery algorithms

---

## Open Design Questions

1. **Algorithm Selection**
   - Which discovery algorithms to implement first?
   - How to avoid favoring certain research styles (hypothesis-driven vs. exploratory)?
   - How to guard against algorithm bias?

2. **Thresholds and Tuning**
   - What frequency thresholds define "sparse" evidence?
   - What effect-size disagreement constitutes contradiction?
   - How many papers define "established finding"?
   - Should thresholds be domain-specific or universal?

3. **Corpus Coverage**
   - At what coverage level is discovery meaningful? (e.g., 80% of field? 50%?)
   - How to validate coverage against external literature surveys?
   - Should corpus gaps be explicitly documented before discovery runs?

4. **Proposal Deduplication**
   - How to detect when multiple discovery runs propose the same research avenue?
   - Should proposals be merged or kept separate?

5. **Reviewer Recruitment**
   - How to identify qualified reviewers for proposals?
   - What mechanism prevents conflicts of interest?
   - What compensation/incentive model sustains review workload?

6. **Appeal Process**
   - How can proposers or alternative experts challenge review decisions?
   - What is the re-review threshold (how many appeals before automatic reconsideration)?

7. **Cross-Disciplinary Relationships**
   - How to detect when a GLP-1 finding relates to, e.g., appetite research in neuroscience?
   - What ontologies or concept maps enable cross-domain discovery?
   - How to prioritize recommendations for specialists outside primary domain?

8. **Temporal Evolution**
   - How often should discovery re-run? (daily / weekly / on-demand)
   - Should old proposals be archived or re-evaluated?
   - How to handle proposal lifecycle when supporting evidence is retracted?

9. **Integration with Other Phases**
   - How does discovery surface unknowns to Phase 2 evidence extraction?
   - Should gaps feed back into ingestion priorities (focus next corpus on high-gap domains)?

10. **Explainability and Skepticism**
    - How to communicate to users that proposals are provisional?
    - What UI/UX prevents accidental misinterpretation as facts?
    - How to explain proposals to non-experts?

---

## Glossary (Local to This Document)

- **Proposal**: Machine-generated hypothesis about research opportunity; awaits review
- **Discovery**: Automated analysis to identify proposals
- **Review**: Expert evaluation of proposal quality, merit, and novelty
- **Acceptance**: Expert decision to publish proposal as research guidance
- **False Novelty**: Claiming gap exists based on absence from indexed corpus, not actual scientific gap
- **Traceability**: Complete audit trail of proposal genealogy, evidence, and assumptions

---

**Next Document**: [02_knowledge_lifecycle_and_evidence_decay.md](02_knowledge_lifecycle_and_evidence_decay.md)
