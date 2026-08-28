# Slim Research Runtime Surface

## Purpose

The normal `ke` CLI remains Core's complete production command surface. It also imports Phase 3 vector-search modules at startup, which means a deployment that only needs Research Copilot's deterministic retrieval, discovery, acquisition, extraction, and review commands still inherits FAISS, sentence-transformers, PyTorch, and Qdrant runtime dependencies.

`ke-research` is an additive deployment surface for reducing that hosted runtime footprint without changing or weakening the normal `ke` contract.

## Trust rule

A slim runtime is useful only if it is honest about what it can execute. The command:

```text
ke-research research-runtime-capabilities
```

returns a versioned JSON capability document with:

- the exact Research Copilot command manifest;
- commands currently available on the slim surface;
- commands still missing; and
- `complete`, which is true only when no required command is missing.

Hosted Web must not switch to `ke-research` until `complete` is true. A partially extracted runtime is therefore development progress, not a false production-ready boundary.

## Stage 1: deterministic base

Stage 1 builds `ke-research` on `knowledge_engine.cli`, which avoids importing the Phase 3 vector package at command-surface import time. It preserves the deterministic base commands already registered there, including `evidence-report`, and reports every still-missing federated/GQR command explicitly.

## Stage 2: federated discovery and acquisition planning

Stage 2 registers `federated-discover` and `general-question-acquisition-plan` directly on the slim surface. The implementation composes the existing provider adapters, recorded federated-search ledger, public result serializer, and GQR planner directly from their focused modules; it does not import `knowledge_engine.entrypoint` to borrow the existing command functions.

The structured JSON boundaries remain the same ones `knowledge-engine-ai` already consumes:

- `federated-discover --output <path>` writes `build_public_federated_result_payload(...)`;
- `general-question-acquisition-plan --output <path>` writes `GeneralQuestionAcquisitionPlan.to_json()`.

Provider failures remain coverage facts, not evidence quality. Acquisition dispositions remain acquisition eligibility, not scientific support. No source is downloaded by the planning command.

The existing `ke` entry point remains unchanged throughout both stages.

## Ordered continuation

The next slices should move the remaining command groups onto this surface in dependency-bounded steps:

1. citation snowball;
2. PMC and Europe PMC acquisition executors;
3. CORE and Unpaywall acquisition executors;
4. any remaining grounding/review commands not already registered by the base CLI;
5. a live contract test proving the complete Web -> AI -> `ke-research` command manifest; and
6. only then, hosted dependency slimming and Web deployment adoption.

This sequence separates **command completeness** from **package-size optimization**. Removing heavy dependencies before command completeness is proven would make deployment smaller but less capable. The capability contract prevents that inversion.

## Database boundary

This work does not make the Web alpha's trimmed SQLite snapshot a Core operational database. Hosted Research Copilot still needs a complete writable Core workspace with the schema and paper-page state required by acquisition, extraction, grounding, and promotion. That bootstrap/persistence boundary is a separate deployment slice.
