# Slim Research Runtime Surface

## Purpose

The normal `ke` CLI remains Core's complete production command surface. It also imports Phase 3 vector-search modules at startup, which means a deployment that only needs Research Copilot's deterministic retrieval, discovery, acquisition, extraction, and review commands otherwise inherits FAISS, sentence-transformers, PyTorch, and Qdrant runtime dependencies.

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

The command manifest is complete. That is a **command-boundary milestone**, not by itself a hosted-deployment claim. The persistent Core operational workspace, Web adoption, and hosted inference still have to pass their own gates.

## Stage 1: deterministic base

Stage 1 builds `ke-research` on `knowledge_engine.cli`, which avoids importing the Phase 3 vector package at command-surface import time. It preserves deterministic base commands already registered there, including `evidence-report` and `extraction-review-promote`.

## Stage 2: bounded discovery and planning

The slim surface directly composes focused Core modules for:

- `federated-discover`;
- `citation-snowball`; and
- `general-question-acquisition-plan`.

The structured JSON boundaries are the same ones `knowledge-engine-ai` already consumes. Provider failures remain coverage facts, not evidence quality. Acquisition dispositions remain acquisition eligibility, not scientific support.

## Stage 3: all four reusable full-text acquisition routes

The composed runtime exposes:

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

## Lean hosted installation path

The dependency half of the hosted runtime gate is now implemented without changing the normal Core installation.

`knowledge_engine.research_runtime_packaging` derives a lean dependency projection from the authoritative `[tool.poetry.dependencies]` table in `pyproject.toml`. It excludes only the four Phase-3/vector-only packages that `ke-research` does not require:

- `faiss-cpu`;
- `sentence-transformers`;
- `torch`; and
- `qdrant-client`.

All other main runtime dependencies are rendered from the same project metadata rather than copied into a second hand-maintained requirements file. Unsupported dependency declaration shapes fail closed so a future dependency cannot silently disappear from the hosted package.

A deployment can render that projection with:

```text
python scripts/render-research-runtime-requirements.py > /tmp/ke-research-requirements.txt
```

and build an isolated runtime with the equivalent of:

```text
python -m venv /opt/ke-research
/opt/ke-research/bin/pip install -r /tmp/ke-research-requirements.txt
/opt/ke-research/bin/pip install --no-deps .
```

The normal `poetry install` / `ke` installation is unchanged and still receives the complete vector stack.

CI now constructs that lean runtime in a fresh virtual environment, asserts that `faiss`, `torch`, `sentence_transformers`, and `qdrant_client` are genuinely absent, runs `ke-research research-runtime-capabilities`, requires `complete == true` and `missing_commands == []`, and then requires every command in the manifest to answer `--help`. This is an installation-level gate, not merely an import-unit-test claim.

## Persistent Core operational workspace

Hosted Research needs a writable Core database with the complete schema and paper-page state; Web's trimmed read-oriented alpha snapshot is not sufficient for acquisition, extraction, grounding, promotion, and reuse.

`ke-research-workspace` is the additive deployment bootstrap for that state. It requires both a persistent writable directory and an explicit corpus-library seed snapshot:

```text
ke-research-workspace \
  --workspace /var/data/knowledge-engine \
  --snapshot data/corpus_library/obesity_metabolic_disease_library.sqlite3.gz
```

The bootstrap:

- initializes and verifies the full current Core schema in `<workspace>/knowledge_engine.sqlite3`;
- imports the existing corpus-library snapshot through Core's established idempotent content-hash import path, including page text and search-index population;
- restores embedded EvidenceRecords into `<workspace>/evidence_records.jsonl` by `evidence_record_id` when the snapshot carries them;
- creates an empty evidence JSONL when an older snapshot contains no embedded evidence so downstream paths have a stable writable location;
- preserves papers and evidence acquired after the initial seed because repeated bootstrap runs merge/dedupe rather than replace the persistent workspace; and
- emits a machine-readable JSON summary containing imported/skipped paper and evidence counts plus the resulting total paper count.

The command does not provision a persistent disk. Deployment configuration still has to mount durable storage at the chosen workspace path; otherwise the process will honestly rebuild ephemeral state on each redeploy.

## Hosted deployment gates

The import/dependency boundary is covered by two independent regressions:

1. `tests/test_research_command_surface.py::test_slim_runtime_import_does_not_require_phase3_vector_modules` poisons `faiss`, `torch`, `sentence_transformers`, `qdrant_client`, and `knowledge_engine.vector_search` in a fresh subprocess interpreter and proves that importing `knowledge_engine.research_runtime` does not touch them.
2. the `Slim Research runtime install` CI job creates an actual isolated environment without those packages and proves that the complete Research command manifest is still executable.

The persistent-workspace bootstrap has its own deterministic regression coverage for initial seed, repeated idempotent reconciliation, EvidenceRecord deduplication, and fail-closed missing-snapshot behavior.

Two distinct software gates remain before hosted Web can truthfully expose full Research, plus one infrastructure requirement:

1. **Web adoption contract.** Web must install this lean runtime, point `KE_WEB_KE_EXECUTABLE` at its `ke-research` executable, and configure all Core research-session/discovery/evidence paths inside the persistent workspace. Web's own hosted command preflight remains an independent fail-closed guard.
2. **Inference boundary.** `evidence-review-automate` and final narration still require a configured, reachable model endpoint. Command completeness and lean packaging do not make that endpoint exist.
3. **Real persistent mount.** The host must provision durable storage at the workspace path. Declaring `/var/data` paths in a blueprint without an attached disk is not persistence.

## Next slice

The next dependency-safe hosted slice is **Web adoption of the tested Core runtime/workspace contract**. Core now has both the lean `ke-research` install path and a deterministic writable-workspace bootstrap, so the Web repository can install the slim runtime, bind its research paths to one persistent mount, and retain its existing fail-closed capability checks.

Only after Web adoption, a real persistent mount, and reachable inference all pass their own capability probes should the public hosted Ask experience claim full Research capability.
