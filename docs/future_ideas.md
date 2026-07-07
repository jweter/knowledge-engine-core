# Future Ideas

This document captures promising ideas without disrupting the current roadmap.
Items here are not commitments. They are a place to preserve imagination until
the project is ready to evaluate, design, prioritize, or reject them.

The purpose of the Knowledge Engine is not to replace scientists. It is to help
humanity discover, connect, verify, and build upon scientific knowledge faster
than ever before, while making every conclusion transparent and reproducible.

## AI

- Evidence-grounded paper summaries with source-linked claims.
- Claim extraction with confidence, limitations, and source text spans.
- Contradiction detection across papers.
- Hypothesis generation from cross-disciplinary patterns.
- Research assistant workflows that show uncertainty and citations by default.
- Local-first AI models for privacy-sensitive research collections.

## Database

- PostgreSQL backend for larger corpora and concurrent users.
- Migration strategy for long-lived local databases.
- Field-level provenance for parsed and enriched metadata.
- Versioned records for papers, metadata, claims, and extracted text.
- Import manifests, corpus manifests, and reproducible ingestion snapshots.
- Storage adapters for local disk, object storage, and institutional archives.

## UX

- Web interface for browsing corpora and import reports.
- Search result pages that separate exact keyword matches, metadata matches, and
  future semantic matches.
- Paper detail view with extracted metadata, raw text, provenance, and parser
  diagnostics.
- Corpus health dashboard showing failures, duplicates, missing metadata, and
  license status.
- Contributor-friendly setup wizard for local installations.
- Research workflow views for reading lists, evidence maps, and open questions.

## Scientific Methods

- Explicit evidence quality scoring models.
- Study design classification.
- Methods, results, limitations, and population extraction.
- Reproducibility indicators and replication tracking.
- Citation context analysis.
- Distinguish claims, observations, interpretations, and speculation.
- Track unknowns, unresolved contradictions, and missing experiments.

## Infrastructure

- GitHub Actions matrix across operating systems and supported Python versions.
- Benchmark suite for ingestion, parsing, search, and database operations.
- Background workers for large corpus ingestion.
- Plugin architecture for parsers, metadata providers, and storage backends.
- Observability for import runs, parser failures, and enrichment calls.
- Release automation for changelogs, tags, and package publishing.

## Community

- Good-first-issue backlog for contributors.
- Public corpus contribution guidelines.
- Scientific advisory process for domain-specific corpora.
- Documentation for non-programmer researchers.
- Contributor recognition and project governance model.
- Templates for reporting parser failures, metadata issues, and licensing
  concerns.

## Long-Term Vision

- Open scientific knowledge graph with traceable evidence.
- Cross-disciplinary discovery engine.
- Transparent scientific reasoning system that shows sources and uncertainty.
- Educational interface for students, researchers, clinicians, and the public.
- Federated knowledge repositories maintained by universities, labs, and public
  institutions.
- A durable open-source ecosystem: core, AI, web, API, graph, agents, and models.
