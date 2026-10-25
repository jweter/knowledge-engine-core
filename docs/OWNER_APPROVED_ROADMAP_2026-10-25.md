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
