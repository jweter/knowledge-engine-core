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
`docs/glp1_vertical_slice_demo_checklist.md`. Those files record historical
prototype work and do not impose a current manual-review prerequisite.

### Working-version review policy

Repository execution must not depend on the project owner manually reviewing
individual candidates, PDFs, metadata rows, licenses, duplicate decisions, or
manifest fields before a working version exists. Deterministic automation must
accept, reject, hold, retry, or exclude each record with preserved evidence.
Held records are automatically deferred from acquisition and do not block the
remaining accepted batch. Human evaluation is reserved for working-version
acceptance, release validation, and optional post-release quality audits.

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
- **Pre-M14 maintenance** reconciled repository state, made Ruff the authoritative
  quality tool, and hardened fresh and linked ingestion error boundaries.
- **M14** migrated PMC OA discovery and acquisition to NCBI's Cloud Service ahead
  of the August 2026 FTP/`oa.fcgi` removal, fixed a license-adjudication defect
  that had been silently accepting restricted `CC BY-NC`/`-ND`/`-SA` variants,
  and completed the controlled 500-paper rehearsal (issue #21) with a `PROCEED`
  decision: a fresh import and a linked resume against the same manifest
  snapshot both reconciled exactly, with zero failures, zero issues, and a fully
  idempotent resume. See `docs/m14_500_paper_rehearsal_report.md`.

### M14: Controlled 500-paper rehearsal

M14 is one controlled 500-paper rehearsal under the M13 entry, measurement, stop,
reconciliation, resume, and artifact-hygiene conditions. Issue #21 is the
authoritative rehearsal tracker; it completed with a `PROCEED` decision (see
`docs/m14_500_paper_rehearsal_report.md`). Persistence failure classification in
issue #22 must be complete before repeated large-run failure evidence is treated
as diagnostic. The rehearsal must not introduce new architecture solely to
collect one run's measurements.

The M14 corpus scope is **Obesity and Metabolic-Disease Therapeutics**. The
original GLP-1 weight-loss question remains the first named subtopic, but the
rehearsal may include legally reusable treatment evidence for overweight, type 2
diabetes, metabolic syndrome, metformin, SGLT2 inhibitors, dual incretin
therapies, and other explicitly allowlisted interventions within this same
Phase 1 domain. Scope expansion must never weaken license, provenance,
identifier, duplicate, or full-text validation.

M14 proceeds through explicit stages:

1. bounded PubMed/PMC candidate discovery within the committed obesity and
   metabolic-disease therapeutics scope;
2. deterministic, evidence-preserving candidate adjudication for scientific scope,
   identifier consistency, reusable-license basis, approved full-text location, and
   duplicate risk;
3. explicit `accepted`, `rejected`, or `held` decision records that remain separate
   from raw discovery output; held records are automatically deferred and discovery
   continues without waiting for manual resolution;
4. bounded acquisition of accepted files with sanitized receipts;
5. reconciliation to exactly 500 accepted rows and matching approved local PDFs;
6. preflight validation, fresh import, linked resume, and sanitized evidence.

Automated acceptance or rejection is permitted only when repository-defined rules
produce complete, non-conflicting evidence. Every decision must record reason codes,
provider provenance, the adjudication-rules version, and the evidence used. A record
must be held rather than guessed when identity, licensing, scientific relevance,
full-text eligibility, or duplicate status remains ambiguous. Discovery providers
must remain separate evidence categories; metadata from PubMed, PMC, Crossref,
OpenAlex, Europe PMC, or publishers must not be silently collapsed into one trust
category. Held and rejected records never authorize acquisition and never require
owner intervention before the working-version acceptance review.

If one query or subtopic cannot supply enough accepted records, discovery may
continue through measured query revisions inside the committed M14 domain. Each
revision must preserve its query, offset, rules version, decision counts, and
provider provenance. Unrelated scientific domains require a separate roadmap
amendment rather than silent corpus mixing.

### Supporting operator durability

The Google Drive backup subsystem is supporting operator infrastructure for
protecting local SQLite backup bundles during the M14-era rehearsal work. It does
not change corpus inclusion, discovery, approval, acquisition, parsing,
deduplication, provenance, or import semantics. It should remain optional,
operator-controlled, and independently documented. Any expansion beyond backup
transport and recovery support requires a dedicated roadmap decision or ADR.

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
- `docs/m14_500_paper_rehearsal_report.md`
- `docs/audit_remediation_register.md`

## Phase 2: Evidence Records

- Extract claims, methods, results, limitations, and evidence quality markers.
- Keep every generated structure traceable to source text spans.
- Add automated validation and optional post-working-version human audit workflows.

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
