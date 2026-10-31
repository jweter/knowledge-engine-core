# Owner-approved roadmap direction — 2026-10-25

Status: proposed roadmap addendum for review, not an accepted implementation or permission to execute.

This records explicit owner decisions. Reconcile with the authoritative local roadmap, AGENTS.md, active claims, dirty worktrees, and newer accepted work before implementation. Existing safety, provenance, testing, product-reality, controller authorization, and worker lease gates remain mandatory. Do not treat GitHub main as newer than the authoritative local version.

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
