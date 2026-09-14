# Knowledge Engine Emerging-Compute Readiness

## Decision

Knowledge Engine is the portfolio's strongest candidate for future quantum and quantum-inspired experimentation, but **no quantum runtime dependency is justified today**.

The near-term goal is to make research, provenance, benchmarking, and evidence contracts capable of evaluating quantum-science claims and hybrid-compute experiments without changing the product architecture prematurely.

## Governing principle

A new compute substrate is a hypothesis, not an upgrade.

Every experiment must follow:

**verified classical baseline → identical measurement contract → bounded candidate → cost/reproducibility evidence → independent verification → retain or reject**.

A local benchmark win may be reported as bounded benchmark superiority. It must not be generalized into a claim of broad quantum advantage.

## First capability: quantum-science evidence quality

Knowledge Engine should eventually distinguish at least these evidence classes when researching quantum-computing claims:

1. **Theoretical** — mathematical/algorithmic result without empirical device execution.
2. **Classical simulation** — quantum method evaluated on a classical simulator.
3. **Physical hardware run** — result produced by a named physical backend.
4. **Hardware run with error mitigation/correction context** — device result whose noise-handling method is part of the claim.
5. **Independent reproduction** — materially independent team/backend/run reproduces the result.
6. **Classical comparator evidence** — explicit classical baseline used for the claimed workload.

A strong answer should not collapse those categories into a single “quantum result.”

## Provenance fields for future hybrid-compute evidence

When a source or local experiment depends on an execution backend, capture the fields that materially determine interpretation:

- substrate class;
- backend/provider/device identity;
- execution/simulation date;
- problem size and representation;
- qubit/resource count when relevant;
- circuit/algorithm depth or equivalent complexity measure when relevant;
- shots/replicates/seeds;
- simulator/noise model when simulated;
- calibration/noise/error-mitigation context when hardware-dependent;
- queue time, execution time, and wall-clock time when comparing performance;
- external financial cost;
- result distribution, variance/confidence, and failure rate;
- classical baseline identity and version;
- exact measurement contract;
- raw permitted artifact/evidence references;
- independent verification references.

Not every research paper exposes every field. Missing material context should be represented as missing evidence, not inferred.

## Hybrid-compute experiment ladder

### Gate 1 — real Knowledge Engine problem

Do not search for a problem merely because a quantum method exists. Candidate problems should come from measured Knowledge Engine bottlenecks or research capabilities such as:

- bounded combinatorial optimization;
- ranking/selection experiments with a mathematically credible mapping;
- scientific-computing or quantum-chemistry research support;
- benchmarking claims made in quantum literature.

### Gate 2 — freeze the best available classical baseline

Record the exact code/environment and measurement contract. The baseline should be competitive enough that beating a deliberately weak implementation does not count as meaningful progress.

### Gate 3 — quantum-inspired or simulator experiment

Prefer the lowest-cost reversible candidate. No provider credential or paid QPU should be required for the first experiment when a simulator can answer the structural question.

Measure at minimum:

- correctness/solution quality;
- runtime and wall-clock latency;
- variance/repeatability;
- memory/resource use when material;
- engineering complexity;
- monetary cost;
- failure rate.

### Gate 4 — independent verification

A candidate is not promoted because its authoring environment says it worked. Reproduce the bounded result independently under the same contract.

### Gate 5 — physical QPU only when justified

A paid hardware run becomes eligible only when simulation or prior evidence leaves a meaningful unresolved question that physical hardware can answer. Record exact backend identity and hardware-state context.

## Architecture rule

Do not import a QPU provider SDK into core product paths merely to be “quantum-ready.”

If repeated experiments justify a real integration, introduce a narrow provider-neutral adapter so that:

- Core owns the experiment/evidence contract;
- provider SDKs remain replaceable implementation details;
- simulator and hardware backends can share the same comparison surface;
- provenance and cost metadata are mandatory, not optional logging.

## Cross-repository responsibilities

### Core

Own canonical research/experiment evidence structures and substrate-neutral benchmark contracts.

### AI

Reason over evidence without overstating theoretical, simulated, or hardware results. Surface missing comparator/noise/reproduction evidence explicitly.

### Web

Present substrate identity, evidence class, uncertainty, cost, and comparator context. Never render a “quantum advantage” style claim from a local benchmark flag alone.

## First real experiment activation trigger

Do not implement a simulator dependency yet. Open the first experiment only when all are true:

- a specific Knowledge Engine problem is identified;
- current classical performance is measured and versioned;
- a credible non-classical mapping is documented with evidence;
- the same measurement contract can evaluate both;
- the first candidate can run locally/free or has explicit cost approval;
- failure would still teach something reusable.

Until then, this document is a readiness contract, not backlog pressure.

## Success

Knowledge Engine is quantum-ready when it can accurately answer **whether** a quantum claim or candidate is actually better, under what conditions, at what cost, with what uncertainty, and with what reproducibility — not when it merely contains quantum code.
