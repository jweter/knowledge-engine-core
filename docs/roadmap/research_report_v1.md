# Research Report v1 — Product Acceptance Contract

Status: adopted product roadmap contract  
Date: 2026-08-31  
Cross-repository scope: `knowledge-engine-core`, `knowledge-engine-ai`, `knowledge-engine-web`

## Purpose

Knowledge Engine is not finished when it can technically search papers, promote Evidence Records, or synthesize a paragraph. The product milestone is a research report that is **at least as useful and readable as a strong scholarly-assistant answer while being substantially more defensible, inspectable, and reproducible underneath**.

The benchmark is therefore deliberately dual:

1. **Communication quality:** a researcher should get the practical answer quickly, in clear prose, without needing to inspect pipeline internals first.
2. **Evidence discipline:** every substantive factual claim must survive Knowledge Engine's provenance, grounding, contradiction, coverage, and release gates.

Neither dimension may substitute for the other.

## Product invariant

A technically rigorous backend with a poor final answer is not success. A polished answer whose evidence boundaries cannot be inspected is also not success.

The target is:

> **Excellent research communication on the surface; claim-level scientific provenance underneath.**

## Two-layer report model

### Layer 1 — Research answer

This is the default reading experience. It should answer the user's question before exposing implementation detail.

Required structure where applicable:

1. **Bottom line** — concise direct answer, with the most important uncertainty stated immediately.
2. **Question matrix** — separate the major sub-questions rather than collapsing unlike evidence into one conclusion.
3. **Evidence-weighted explanation** — explain why the answer is supported, contradicted, or uncertain.
4. **Practical interpretation** — what the evidence means in the context of the question, without exceeding the evidence.
5. **Missing evidence** — explicitly state the direct study or evidence class that was searched for but not found.

The primary answer should not force the user to read provider logs, acquisition details, EvidenceRecord IDs, or extraction traces before understanding the conclusion.

### Layer 2 — Evidence and methodology

This layer makes the answer auditable.

It should expose, when available:

- every source used by the released answer;
- claim → EvidenceRecord → source provenance;
- whether each source was indexed before the run or acquired during the run;
- direct evidence vs class-level or otherwise indirect evidence;
- positive, null, qualifying, and contradictory evidence;
- provider/search coverage and degraded or unavailable providers;
- acquisition/extraction failures and coverage gaps;
- source-level extraction fields relevant to the question, including population, exposure/intervention, dose, duration, comparator, measurement method, effect size, confidence interval, study design, and limitations;
- the exact reason a confidence/certainty statement is high, moderate, low, or unavailable;
- the research-session identity and enough durable state to reproduce or inspect the run.

## Research-report release rules

A report is not releaseable as a completed researched answer unless all applicable rules pass:

1. Every substantive factual claim is source-linked.
2. Search results and discovery candidates are never treated as evidence merely because they were found.
3. Newly acquired material affects synthesis only after grounding, validation/promotion, and re-retrieval.
4. Direct evidence is visibly distinguished from indirect evidence.
5. Contradictory and null findings are deliberately searched for and represented when relevant.
6. Acute, chronic, longitudinal, observational, mechanistic, or other materially different evidence dimensions are not silently collapsed.
7. A missing direct study is stated as a gap, not replaced by an extrapolation phrased as though the direct study existed.
8. Model memory is never presented as scientific evidence.
9. Confidence/certainty is never invented merely to make the answer feel complete.
10. Provider, acquisition, extraction, or verification degradation that materially limits the answer remains visible.

## Golden acceptance case: Monster Energy and one-year blood pressure

`knowledge-engine-ai` issue #79 (`monster-energy-bp-one-year`) is the first definitive Research Report v1 acceptance case.

The final report must separately answer:

- whether blood-pressure readings are likely to be higher in the hours after consumption;
- whether habitual use appears to raise baseline/resting/ambulatory BP over weeks or months;
- whether longer-term evidence supports increased incident hypertension risk;
- whether consuming caffeine before measurement can artifactually raise a reading;
- how Zero Ultra and Original Monster differ in long-term risk context;
- whether direct 6–12 month or approximately one-year Monster/energy-drink longitudinal evidence was actually found;
- how certain each conclusion is and why.

The report must keep distinct:

- Zero Ultra vs Original Monster;
- direct Monster/commercial-energy-drink evidence vs class-level energy-drink evidence;
- energy-drink evidence vs caffeine/coffee/soda evidence;
- supportive vs null/contradictory findings.

The benchmark is failed if the system produces a sophisticated research trace but a weaker, less understandable answer than a strong scholarly-assistant response.

## Cross-repository responsibilities

### `knowledge-engine-core`

Core owns the trustworthy evidence substrate.

Research Report v1 requires Core to preserve and expose enough structured evidence for AI and Web to report:

- source identity and stable provenance;
- exact source spans where available;
- EvidenceRecord validation state;
- study design and limitations when extractable;
- PICO/exposure/comparator/outcome fields when grounded;
- effect sizes and confidence intervals when available from grounded extraction;
- relationship/contradiction structure where available;
- acquisition/search-run provenance and reusable evidence identity.

Core must continue to prefer absence over invented metadata.

### `knowledge-engine-ai`

AI owns research planning, adequacy, synthesis, and release discipline.

Research Report v1 requires AI to:

- decompose a question into scientifically distinct answer dimensions;
- construct and execute a bounded research plan;
- search counter-evidence deliberately;
- preserve direct-vs-indirect evidence classes;
- re-retrieve after new evidence is promoted;
- synthesize only from grounded evidence returned by Core;
- produce a structured report contract, not narrative prose alone;
- attach claims to evidence and certainty rationales;
- fail closed when citation, contradiction, coverage, or ISA criteria are not satisfied.

### `knowledge-engine-web`

Web owns the researcher's experience.

Research Report v1 requires Web to:

- make the bottom line and main conclusion immediately readable;
- render a compact question/conclusion/certainty matrix where appropriate;
- keep evidence and methodology available one level deeper rather than cluttering the primary answer;
- expose citations, provenance, provider coverage, missing evidence, and degradation clearly;
- show progress during long runs without pretending unfinished work is a conclusion;
- preserve durable session identity across refresh/redeploy where configured.

## Priority order

Until Research Report v1 passes the Monster acceptance case, roadmap priority should be:

1. **Complete, source-grounded report quality** — the answer must be useful and scientifically disciplined.
2. **Structured report contract** — conclusions, claim evidence, certainty rationales, missing evidence, and provenance must be machine-readable.
3. **Two-layer Web presentation** — excellent primary answer plus inspectable evidence/methodology.
4. **End-to-end Monster acceptance run** — record and compare the actual report, not just backend traces.
5. **Cross-domain golden cases** — chemistry/materials, biology/medicine, and other domains after the first contract passes.
6. **Latency optimization** — optimize bottlenecks without weakening evidence gates.

New backend abstractions should not outrank these items unless they are required to satisfy one of the report acceptance criteria.

## Definition of done

Research Report v1 is complete when the same durable research session can:

1. take an arbitrary scientific question;
2. retrieve indexed evidence and broaden research when needed;
3. acquire, ground, validate/promote, and re-retrieve new evidence under bounded policy;
4. deliberately include counter-evidence and missing-evidence disclosure;
5. produce a clear Layer-1 answer with question-specific conclusions and certainty;
6. produce a Layer-2 evidence/methodology view with inspectable provenance;
7. release no substantive factual claim without source linkage;
8. pass the Monster golden case end to end on the deployed product path;
9. remain at least as readable/useful as a strong scholarly-assistant baseline while providing materially stronger auditability.

## Related roadmap work

- `knowledge-engine-ai` #69 — General Question Research Loop v1
- `knowledge-engine-ai` #79 — Monster Energy golden research case
- `knowledge-engine-ai` #84 — question-to-report bottlenecks
- `knowledge-engine-web` #86 — research-state UI and provenance
- `knowledge-engine-web` #93 — progressive research UX
- `knowledge-engine-core` #402 — bounded acquisition and reusable evidence
- `docs/roadmap/progressive_answer_pipeline.md` — continuous Draft → Sourced → Verified → Deep interaction model
