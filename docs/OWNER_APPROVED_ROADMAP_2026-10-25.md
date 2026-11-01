# Owner-approved roadmap direction — 2026-10-25

Status: OWNER-APPROVED — standing development direction and implementation authorization, reaffirmed 2026-11-01.

This document records the owner's accepted product objectives and constitutes standing authorization to plan, implement, test, review, and deliver development work that advances those objectives during an owner-authorized Iron God session. The owner has already specified **what to achieve**. Iron God and its qualified builders are responsible for deciding **how to achieve it**. Ordinary roadmap-derived development does not require a second, per-slice owner approval, a manually maintained approved-item list, or a fresh permission request whenever the backlog is exhausted.

## Standing development authorization and autonomous continuation (owner decision 2026-11-01)

- **Scope comes from this roadmap.** Treat the outcomes, constraints, and acceptance criteria below as approved development direction. The "Next slices" are starting points, not an exhaustive ceiling or an approval queue. Continue deriving dependency-ready slices until the outcomes are demonstrably achieved, or a genuine blocker requires guidance.
- **Plan from evidence, not guesses.** Reconcile this document with the project's authoritative local roadmap, AGENTS.md, current source, GitHub issues and reviews, verified acceptance evidence, existing PRs and file ownership, and the shared engineering, working, and development memory layers. Do not treat GitHub main as newer than an authoritative local version merely because it is remote; preserve dirty worktrees and reconcile conflicting changes.
- **Reuse existing implementations.** Before proposing a new feature or helper, search code, preserved branches, verified history, and shared memory for reusable work. Decompose larger outcomes into bounded, testable slices with explicit dependencies, allowed paths, baseline identity, verification steps, and traceability to the roadmap. Avoid duplicate, disconnected, or repeatedly failed work.
- **Proceed without routine reapproval.** The autonomous planner may generate, prioritize, and execute roadmap-derived slices without separately asking the owner to approve each slice. Use an available, capability-appropriate builder; a local worker's measured Level 1–2 limits do not limit the owner's roadmap authorization or justify silently skipping complex work. If a qualified implementer or necessary test environment is unavailable, record the blocker and keep other eligible repositories progressing.
- **Ask only when actual direction is missing.** Investigate unresolved details first using project context and verified evidence. If materially conflicting objectives, missing requirements, or choices with significant consequences remain, ask one focused clarification instead of inventing owner intent. Preserve all unaffected authorized work in the meantime.
- **Preserve engineering and product gates.** Maintain exact-head verification, native tests, canonical preflight, required GitHub CI/reviews, branch protection, provenance, product-reality checks, file-ownership reservations, resource limits, and safe publication/merge rules. Failed gates require repair, retry within bounded policy, or a recorded blocker—not a bypass. Never count an unmerged PR or synthetic-only result as a completed product outcome.
- **Separate scope authorization from runtime control.** This roadmap is ongoing authorization for development objectives; it is not itself a Take the Wheel execution grant. Iron God must still obey the existing authenticated owner-controller session, Give Me Control revocation, release pinning, and worker/lease fences. Shared memory provides context and verified lessons, never execution authority.
- **Respect scope and stop conditions.** Do not silently expand into unrelated products, alter owner-control safeguards, expose secrets, spend money, destroy user data, or install/deploy an unapproved engine release. If an unavoidable action falls outside the roadmap's authorization, ask first. Record progress, failures, merged deliverables, and remaining roadmap gaps in shared memory so subsequent cycles continue from verified evidence rather than start over.

The product-specific objectives, owner decisions, and acceptance criteria that follow remain in force. This authorization clarification does not replace or weaken them.

## Research architecture: local compute, online evidence
- Research is initiated by one user request and executed locally on the owner's machine; online sources are retrieved on demand.
- No mandatory preloaded local corpus, large persistent PDF warehouse, or mandatory local ingestion prerequisite for standard Research Reports.
- Keep citation provenance, source identity, evidence traceability, uncertainty and reproducible report outputs.
- Stream/process remote sources where practical; impose bounded ephemeral cache, retention and cleanup policies. Do not silently delete existing user documents.
- Preserve optional offline corpus tools as separate capabilities pending compatibility review, not standard-path dependencies.

## Next slices
1. Map corpus-dependent interfaces and propose online retrieval/evidence adapter with stable provenance contract.
2. Implement bounded on-demand source extraction with tests for citations, errors, cache cleanup, and disk limits.
3. Prove end-to-end integration with AI/Web using online sources and no pre-ingested corpus.

## Owner decision 2026-10-30: the local vector index is an optional capability

Approved by the owner on 2026-10-30. This applies the research architecture above to the local vector-index
lineage (`63581db`, `56f2eb4`, `f744584` = KE-CORE-S2..S4 backend selection, plus `4177b9b`/`c5b1e75` hybrid
lexical+vector search). That work is preserved off-machine on
`backup/azathoth-20261030/iron-god/ke-core-s4-qdrant-vector-search-cli-wiring-f744584` and must not be discarded.

- The default Research Report workflow stays online and request-driven. It never requires building, loading or
  maintaining a local vector index, embedding model download or document corpus.
- FAISS/Qdrant/sentence-transformers remain an optional, independently enabled capability of the full
  `knowledge-engine` CLI. The slim `ke-research` runtime must keep proving the vector stack is absent
  (`Slim Research runtime install` CI job, `SLIM_VECTOR_STACK_ABSENT=1`).
- No default download or retention of large document collections or models; any optional index lives where the
  operator points it and is bounded by the same disk-limit and cleanup rules as other caches.

### Integration requirements for the preserved vector-index lineage
1. Rebase or merge the five commits onto current `main` in a small PR (they are 11 commits behind).
2. Import `qdrant_client`/FAISS lazily inside the vector commands (today `backend_selection.py` imports
   `qdrant_client` at module import, and `entrypoint.py` imports it at top level), so non-vector CLI commands work
   without the vector packages installed.
3. Follow-up slice: move `faiss-cpu`, `sentence-transformers` and `qdrant-client` from required dependencies to an
   opt-in extra (for example `knowledge-engine[vector]`) so a default install does not pull torch and model weights.

### Verification criteria
- `Slim Research runtime install` stays green: vector packages absent and every `ke-research` command answers `--help`.
- A test proves the default research path imports none of `faiss`, `qdrant_client`, `sentence_transformers`, `torch`.
- `vector-search`/`embedding-index-build`/hybrid commands keep their existing tests green when the extra is installed,
  and fail with a clear "optional vector capability not installed" message when it is not.
- Canonical preflight GREEN at the exact PR head; required CI checks green.

### Known limitation: the `vector` extra is Windows/Linux only (owner decision 2026-10-31)
The `vector` extra pins CPU-only PyTorch from the `pytorch-cpu` index, which publishes no macOS wheels, so
`poetry install --extras vector` does not resolve on macOS. This is accepted for now. The default install, the full
`ke` CLI and the online Research Report workflow are cross-platform and unaffected: a default install on macOS needs
no vector package, and the vector commands report "optional vector capability is not installed".

Future compatibility improvement (not scheduled): make the extra installable on macOS without a second,
incompatible PyTorch and without heavyweight GPU packages. Constraint learned while locking: declaring `torch` with
several platform-specific constraints made Poetry merge their markers with `sentence-transformers`' own `torch`
requirement and lock a second, CUDA-enabled PyPI build for Linux/Windows next to the CPU build, which
`tests/test_optional_vector_capability.py::test_the_locked_vector_extra_installs_only_cpu_torch` now forbids.
