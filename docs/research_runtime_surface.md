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

The command manifest is now complete. That is a **command-boundary milestone**, not a hosted-deployment claim. Dependency packaging, the persistent Core operational workspace, Web adoption, and hosted inference still have to pass their own gates.

## Stage 1: deterministic base

Stage 1 builds `ke-research` on `knowledge_engine.cli`, which avoids importing the Phase 3 vector package at command-surface import time. It preserves deterministic base commands already registered there, including `evidence-report` and `extraction-review-promote`.

## Stage 2: bounded discovery and planning

The slim surface directly composes focused Core modules for:

- `federated-discover`;
- `citation-snowball`; and
- `general-question-acquisition-plan`.

The structured JSON boundaries are the same ones `knowledge-engine-ai` already consumes. Provider failures remain coverage facts, not evidence quality. Acquisition dispositions remain acquisition eligibility, not scientific support.

## Stage 3: all four reusable full-text acquisition routes

The composed runtime now exposes:

- `general-question-acquire-pmc`;
- `general-question-acquire-europe-pmc`;
- `general-question-acquire-core`; and
- `general-question-acquire-unpaywall`.

Each route composes its existing resolver, acquisition service, persistence transaction, receipt contract, and rollback behavior directly. The production `knowledge_engine.entrypoint` / `command_surface` registry is not imported merely to reach those commands.

## Stage 4: extraction, grounding, promotion, and Evidence Intelligence

The remaining Research Copilot steps are also reachable on `ke-research`:

- `extraction-review-batch-generate`;
- `extraction-review-autoclassify`;
- `extraction-review-promote` (inherited from the deterministic base CLI);
- `evidence-review-automate`;
- `evidence-record-review-promote`; and
- `evidence-intelligence`.

This closes the explicit 14-command manifest currently invoked by `knowledge-engine-ai`'s bounded research workflow. The capability test requires `missing_commands == []` and `complete == true`; every required command must also answer `--help` without executing research work.

## Command complete is not deploy complete

Four distinct gates remain before hosted Web should adopt `ke-research`:

1. **Import/dependency boundary.** Prove `knowledge_engine.research_runtime` imports without loading the Phase 3 vector modules, then produce a lean install that omits FAISS, sentence-transformers, PyTorch, and Qdrant while preserving the complete manifest.
2. **Persistent Core operational workspace.** The Web alpha's trimmed SQLite snapshot is not sufficient. Hosted Core needs a writable database with the schema and paper-page state required for acquisition, extraction, grounding, and later reuse.
3. **Web adoption contract.** Web should point `KE_WEB_KE_EXECUTABLE` at the slim executable only after the command-completeness and lean-install tests pass; its hosted command preflight remains the independent guard.
4. **Inference boundary.** `evidence-review-automate` and final narration still require a configured, reachable model endpoint. Command completeness does not make that endpoint exist.

Only after all four are real should the hosted Research Copilot checkbox become available.

## Next slice

The import/dependency regression gate is implemented: `tests/test_research_command_surface.py::test_slim_runtime_import_does_not_require_phase3_vector_modules` poisons `faiss`, `torch`, `sentence_transformers`, `qdrant_client`, and `knowledge_engine.vector_search` in a fresh subprocess interpreter and proves that importing `knowledge_engine.research_runtime` still succeeds without touching them. CI protects that invariant on every PR.

The next implementation slice is the packaging half of the same gate: today's `pyproject.toml` still lists `faiss-cpu`, `torch`, `sentence-transformers`, and `qdrant-client` as unconditional dependencies, so no install actually omits them yet. Splitting them into an optional extra (while leaving the normal `ke` install's default behavior unchanged) is what would let a hosted `ke-research` deployment skip the vector stack the import-boundary test now proves it does not need.

## Database boundary

This work does not make the Web alpha's trimmed SQLite snapshot a Core operational database. Hosted Research Copilot still needs a complete writable Core workspace with the schema and paper-page state required by acquisition, extraction, grounding, and promotion. That bootstrap/persistence boundary remains a separate deployment slice.
