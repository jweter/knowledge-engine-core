# Roadmap

This file is the roadmap index. Phase-specific notes live in `docs/roadmap/`.

## Phase 0: Local Source Vault

- Import PDFs.
- Extract text and best-effort metadata.
- Store papers, authors, journals, keywords, and full text.
- Search with SQLite FTS5.
- Run fully offline.
- Establish open-source project hygiene, governance files, issue templates, and
  automated quality checks.

## Phase 1: Focused Scientific Corpus

- Choose one domain, such as obesity and metabolic disease.
- Import 500 to 1,000 legally available papers through bounded rehearsals.
- Improve metadata extraction with Crossref or PubMed adapters.
- Add citation metadata.
- Add deduplication reports and import manifests.
- Define legal corpus inclusion rules and source provenance requirements.
- Add a repeatable corpus ingestion workflow.
- Use `docs/phase1_design.md` as the detailed design reference.

The current GLP-1 vertical slice is a retrieval and manual evidence-display
prototype. See `docs/vertical_slice.md` and
`docs/glp1_vertical_slice_demo_checklist.md`.

### Completed Phase 1 milestones

- **M6** defined the Phase 1 corpus-ingestion architecture.
- **M7** implemented versioned manifest validation and local-file readiness checks.
- **M8** added durable import-run, item, issue, and manifest-snapshot persistence.
- **M9** connected validated local PDFs to persisted import runs and atomic
  paper/FTS persistence while preserving item-level continuation.
- **M10** added duplicate evidence decisions, linked resume/retry behavior, and
  explicit execution/review status semantics.
- **M11** added provenance-preserving metadata preview and Crossref enrichment
  boundaries without silently overwriting canonical data.
- **M12** completed the controlled 100-paper rehearsal and sanitized reporting.
- **M13** assessed scale readiness and conditionally authorized one controlled
  500-paper rehearsal with explicit measurement and stop conditions.

### Next bounded milestone

The next milestone is **one controlled 500-paper rehearsal** under the M13 entry,
measurement, stop, reconciliation, resume, and artifact-hygiene conditions. Before
that rehearsal begins, repository documentation and expected-versus-unexpected
ingestion exception contracts must be reconciled. The rehearsal must not introduce
new architecture solely to collect one run's measurements.

Detailed milestone records include:

- `docs/m6_phase1_corpus_ingestion_plan.md`
- `docs/m7_manifest_validation_foundation.md`
- `docs/m8_import_run_persistence.md`
- `docs/m9_small_ingestion_pilot.md`
- `docs/m10_duplicate_detection_resumability_plan.md`
- `docs/m10_operational_contract.md`
- `docs/m10_release_notes.md`
- `docs/m12_100_paper_rehearsal.md`
- `docs/m13_scale_readiness_decision.md`

## Phase 2: Evidence Records

- Extract claims, methods, results, limitations, and evidence quality markers.
- Keep every generated structure traceable to source text spans.
- Add human review workflows.

## Phase 3: Search Plus Semantics

- Add embeddings using a pluggable vector index.
- Support local FAISS and server-backed Qdrant.
- Keep lexical search as a transparent baseline.

## Phase 4: Knowledge Graph

- Model concepts, claims, citations, support, contradiction, and uncertainty.
- Add Neo4j or another graph backend behind a repository interface.

## Phase 5: Human Interface

- Add API and web repositories as separate projects.
- Provide evidence-first explanations with visible uncertainty and sources.

## Release Milestones

- `v0.1.0`: Phase 0 local source vault, CLI, tests, docs, and repository hygiene.
- `v0.1.1`: Bug fixes and setup improvements.
- `v0.2.0-alpha.1`: GLP-1 retrieval and manual evidence vertical-slice prerelease.
- `v0.2.0`: Repeatable corpus ingestion, duplicate handling, resume/retry, metadata
  preview/enrichment, and bounded scale-rehearsal evidence.
- `v0.3.0`: Expanded metadata enrichment and citation capture.
- `v0.4.0`: Knowledge graph foundation.
- `v0.5.0`: Vector search.
- `v0.6.0`: AI-assisted reasoning experiments.
- `v0.9.0`: Feature-complete beta.
- `v1.0.0`: Stable public release.

## Detailed Roadmaps

- `docs/phase1_design.md`
- `docs/roadmap/phase0.md`
- `docs/roadmap/phase1.md`
- `docs/roadmap/phase2.md`
- `docs/roadmap/long_term_vision.md`
