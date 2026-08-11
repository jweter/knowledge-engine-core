# LifeOS-Inspired Architecture for Knowledge Engine Core

**Status:** architecture decision  
**Scope:** `knowledge-engine-core`  
**Source:** *LifeOS Engineering Teardown for an Ollama and Knowledge Engine Stack* (August 2026)

## Decision

Knowledge Engine Core will **borrow the portable LifeOS primitives that strengthen provenance, verification, policy, and durable state**, while remaining independent of the LifeOS runtime and any specific LLM provider or agent harness.

Core remains the scientific system of record. AI layers may plan, interpret, and explain, but they must not replace deterministic evidence ownership, relationship review, statistical verification, or provenance.

## Adopted principles

### 1. Human intent in files; scientific provenance in structured records

Long-lived project policy and research objectives are naturally human-editable and versionable. Scientific evidence, claims, relationships, source locators, transformations, and corrections require structured records.

Recommended split:

```text
Git/YAML/Markdown
  -> research doctrine, project intent, configuration, policy

SQLite/Postgres
  -> evidence, claims, relationships, runs, decisions, provenance

Content-addressed filesystem/object storage
  -> raw PDFs, datasets, fetched source artifacts

FTS/vector indexes
  -> rebuildable retrieval derivatives only
```

**Invariant:** the retrieval index is never the source of truth.

### 2. Journal before grade

Adapt Synapse's strongest invariant directly:

```text
retrieve/capture
    -> persist immutable raw evidence
    -> parse/normalize
    -> classify/extract
    -> relate claims/evidence
    -> rank/synthesize
```

A parser failure, model failure, or relevance decision must never cause a retrieved source to disappear.

Raw acquisition state should be preserved strongly enough that a later parser/model can reprocess the same source and produce a new versioned interpretation.

### 3. Append-only evidence history

Evidence acquisition is historical fact. Corrections, retractions, replacement files, improved parsing, and changed interpretations should create new records/events or versioned derived records rather than silently rewriting history.

The exact schema may evolve, but the semantic rules are:

- raw capture is immutable;
- transformations record tool/extractor version;
- source URI/external ID/content hash are preserved;
- relationship changes are auditable;
- model-produced interpretations are never confused with source-authored facts;
- a changed conclusion never erases the prior conclusion or the evidence that supported it.

### 4. Evidence and inference remain separate

The LifeOS teardown reinforces an existing Knowledge Engine seam:

> An LLM may explain evidence; it does not become evidence.

Core continues to own:

- Evidence Records;
- normalized source identity;
- source locators;
- reviewed relationships;
- deterministic statistical verification;
- lifecycle/retraction/correction state;
- provenance and audit history.

AI may propose candidate relationships or interpretations only through explicit, provenance-bearing review paths.

### 5. Verification gates instead of model-declared completion

Core should expose deterministic probes that the AI layer can use as Research ISA close gates.

Candidate probes include:

- `citation_integrity_check`;
- `orphan_claim_count`;
- `relationship_review_coverage`;
- `source_identity_resolution_check`;
- `evidence_lifecycle_check`;
- `search_coverage_check`;
- `statistical_verification_status`;
- `provenance_complete`;
- `uncertainty_inputs_available`.

Core reports facts. The AI orchestrator decides which probes are required for a particular Research ISA.

### 6. Deterministic capabilities under natural-language workflows

Scientific retrieval, DOI normalization, hashing, citation resolution, database writes, statistics, unit conversion, identity reconciliation, lifecycle checks, and policy decisions should be implemented as typed deterministic functions/services wherever feasible.

The LLM should request operations such as:

```text
search_literature(query)
resolve_doi(identifier)
read_evidence(evidence_id)
verify_statistic(input_record)
check_lifecycle(source_id)
```

It should not improvise shell commands, ad hoc database mutations, or source-normalization logic from prose.

### 7. Data-class and egress policy belongs outside the model

Core-facing network and privileged operations should be policy-gated by code.

Minimum controls:

- external content is untrusted data;
- validate URLs and destinations;
- block private/loopback/link-local SSRF targets except explicitly allowed local services;
- never interpolate retrieved content into a shell;
- secrets never enter model-visible context;
- cloud egress is deny-by-default for sensitive classes;
- consequential mutation requires schema/rule gates or human approval;
- every privileged operation is auditable.

### 8. Capability Doctor semantics

Core services should expose health/capability status with four explicit states:

- `verified`
- `degraded`
- `unavailable`
- `disabled`

This avoids silently treating an intentionally disabled network provider as broken or a broken service as absent by design.

Initial capability targets include database access, corpus read/write health, FTS, semantic index, external discovery providers, DOI/source resolution, lifecycle providers, statistics modules, and API/CLI availability.

## What Core should not adopt

- LifeOS runtime as a dependency;
- Claude-specific hooks;
- personal-assistant identity conventions;
- filesystem-only scientific memory;
- natural-language skills as an authority boundary;
- model-generated confidence as canonical data;
- vector indexes as authoritative evidence state;
- hidden automatic evidence mutation.

## Cross-repository ownership

```text
knowledge-engine-core
  owns evidence + provenance + deterministic scientific state

knowledge-engine-ai
  owns intent compilation + Research ISA + orchestration + model policy

knowledge-engine-web
  presents current state + ideal state + probe status + provenance to users
```

This preserves the central Knowledge Engine contract: AI can move research work forward, but the evidence substrate remains inspectable, reproducible, and independently verifiable.

## Near-term integration targets

1. Audit current evidence ingestion paths against **journal-before-grade**.
2. Identify which current records are immutable facts versus mutable derived projections.
3. Define a small probe interface that AI can call for Research ISA verification.
4. Add explicit capability-health states where services currently expose only success/failure.
5. Keep project/global research intent outside canonical Evidence Records.
6. Preserve existing evidence/relationship review boundaries while adding stronger execution/audit provenance.

## Architectural invariant

> Capture first. Interpret second. Preserve history. Let deterministic evidence checks, not model confidence, decide what the system can claim to have verified.
