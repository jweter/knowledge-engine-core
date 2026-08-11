# ADR 0005: Borrow LifeOS primitives without a runtime dependency

- **Status:** Accepted
- **Date:** 2026-08-11
- **Scope:** `knowledge-engine-core`, with cross-repository implications for `knowledge-engine-ai` and `knowledge-engine-web`

## Context

The Knowledge Engine architecture increasingly needs persistent intent, durable workflow state, explicit definitions of done, capability-aware execution, and stronger provenance controls. The LifeOS engineering teardown identified a set of portable architectural primitives that map well to those needs: TELOS-style long-lived intent, task-level Ideal State Artifacts, deterministic verification gates, journal-before-grade ingestion, typed capabilities, capability health reporting, provider-role routing, and append-only audit history.

LifeOS itself is optimized around a fast-moving personal-agent harness and currently carries runtime, filesystem, and provider assumptions that are not appropriate as foundational dependencies for a scientific evidence system. Knowledge Engine also has stricter requirements around immutable source provenance, structured claims/evidence relationships, reproducible deterministic computation, and provider neutrality.

## Decision

Knowledge Engine will **adopt the portable architectural ideas, not the LifeOS runtime**.

The dependency direction is:

```text
optional personal/client layer
    -> Knowledge Engine stable API/CLI
        -> provider-neutral core/AI services
            -> local or policy-approved model/tool providers
```

Knowledge Engine must remain independently runnable if LifeOS, Claude Code, Codex, or any other external harness disappears.

## Adopted invariants

### Intent hierarchy

Human/project intent is represented separately from canonical scientific evidence.

- global research doctrine describes stable epistemic principles;
- project intent describes longer-lived objectives and constraints;
- a Research ISA describes the falsifiable completion criteria for one bounded run.

### Deterministic completion

An LLM may propose that work is complete. It does not own the `completed` state.

A run closes only when the deterministic Research ISA close gate confirms every required criterion has passed its named probe.

### Journal before grade

Acquired evidence is persisted before parsing, classification, ranking, or model interpretation. Parser/model failure must not erase the acquisition event.

### Source of truth

- raw evidence and acquisition history are authoritative historical records;
- normalized scientific state belongs in structured records;
- search/vector indexes are rebuildable derivatives;
- model narration is never evidence.

### Append-only observations

Probe results, workflow events, acquisition events, corrections, and reprocessing history are preserved as new observations/events rather than silently rewriting prior state.

### Typed capability boundaries

Natural-language intent may select a capability, but authority is granted by typed contracts and deterministic policy. Privileged actions, cloud egress, file/database mutation, and credentials are never authorized by model prose.

### Provider neutrality and privacy

Workflows request abstract model roles/capabilities, not concrete model brands. Provider selection is constrained by data class and egress policy. Sensitive research remains local unless an explicit policy permits otherwise; secret-class data never enters model context.

### Capability Doctor

Capabilities are reported as one of:

- `verified`
- `degraded`
- `unavailable`
- `disabled`

The system must distinguish intentionally-disabled behavior from broken behavior.

## Cross-repository ownership

```text
knowledge-engine-core
  evidence, provenance, source identity,
  reviewed relationships, deterministic scientific state,
  verification probe facts

knowledge-engine-ai
  global/project intent, Research ISA,
  orchestration, provider-role policy,
  capability Doctor, model-facing interpretation

knowledge-engine-web
  researcher-facing current state, ideal state,
  completion criteria, probe results,
  provenance, capability/routing visibility
```

## Consequences

### Positive

- preserves local-first operation and provider independence;
- makes completion auditable instead of model-declared;
- improves resilience to parser/model changes because raw evidence survives;
- supports reproducible reprocessing and debugging;
- gives the UI a principled way to show current state, remaining gaps, and verified completion;
- prevents a third-party agent harness from becoming part of the scientific trust boundary.

### Costs

- Knowledge Engine must implement and maintain the narrow primitives it adopts;
- durable state and append-only history increase schema and migration complexity;
- provider/capability routing needs regression tests against actual local models;
- completion probes require explicit design rather than relying on a single generative answer.

## Rejected alternatives

### Make LifeOS a foundational Knowledge Engine dependency

Rejected because it would couple scientific execution to an external harness/runtime with different stability, provider, and data-model assumptions.

### Copy LifeOS wholesale

Rejected because personal-assistant machinery, filesystem-only durable memory, Claude-specific lifecycle behavior, and natural-language skill authority do not fit Knowledge Engine's scientific provenance requirements.

### Ignore the architecture and keep prompt-scripted agents

Rejected because free-form agent loops do not provide a sufficiently strong authority boundary for scientific evidence, completion, egress, or reproducibility.

## Implementation status

The adoption is incremental. Initial implementation slices include:

1. Research ISA contracts and deterministic close-gate semantics in `knowledge-engine-ai`;
2. durable ISA/probe-result attachment to `ResearchSession`;
3. provider-role/privacy routing and Capability Doctor primitives;
4. core-side journal-before-grade and verification-probe architecture guidance;
5. web-side Definition-of-Done and provenance UX guidance.

Future implementation remains gated by tests and existing Knowledge Engine review boundaries.

## References

- `docs/architecture/lifeos_adoption.md`
- `docs/ai_layer_architecture.md`
- `SECURITY_ARCHITECTURE.md`
- `docs/decisions.md`
