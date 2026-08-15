# Architecture

Knowledge Engine Core is a local-first Phase 1 scientific-corpus application. It imports legally available documents, preserves source and provider provenance, records durable ingestion state, and provides transparent lexical retrieval. It is not yet a distributed ingestion platform, public web application, knowledge graph, vector-search service, or autonomous reasoning system.

## Application boundaries

- `parser.py` owns document parsing and returns typed parse results.
- `corpus.py` owns manifest and local-corpus validation boundaries.
- `import_runs.py` owns durable run, item, issue, snapshot, resume, and rehearsal-reporting state.
- `duplicate_resolution.py` evaluates duplicate evidence and review outcomes before persistence; it must not silently merge probable matches.
- `database.py` owns SQLAlchemy sessions, schema creation, additive pre-1.0 migrations, relational writes, and atomic relational/FTS persistence.
- `models.py` defines durable relational structures.
- `search.py` owns SQLite FTS5-backed lexical search behind a service boundary.
- `pubmed_discovery.py`, `pubmed_batch_discovery.py`, and `ncbi_http.py` own bounded PubMed/PMC discovery and transport boundaries.
- PMC Open Access acquisition components require explicit reviewed approvals before network acquisition and preserve sanitized receipts.
- Drive-backup modules provide an optional operator-controlled durability boundary for local SQLite backup bundles; they are not part of scientific ingestion semantics.
- `cli.py` adapts command-line input to application services and should not contain parsing, ranking, duplicate-decision, or persistence logic.

## Federated scholarly-discovery boundary

The project now adopts a provider-neutral federated-discovery direction. Existing
PubMed/PMC and Crossref implementations remain Knowledge Engine-owned services;
future OpenAlex, Semantic Scholar, and arXiv support must join them behind a
common Discovery Broker contract rather than becoming separate product silos or
third-party runtime dependencies.

The broker's responsibility is deterministic discovery and provenance only:
execute bounded provider queries, normalize candidates without erasing provider
identity, record provider success/failure, support citation/reference traversal,
and hand results into Knowledge Engine's existing identity/acquisition/evidence
pipeline. It does not decide evidence quality, truth, support, contradiction, or
research policy.

A failed provider must not discard successful results from other providers, but
a partial search must be recorded and exposed as partial/degraded. Provider
metadata such as citation counts, retraction flags, open-access assertions, and
provider-generated summaries must retain their source and must never be silently
promoted into source-paper evidence.

MCP is considered a possible future interoperability facade over these services,
not an internal architecture requirement. Core behavior must remain directly
callable and testable without an MCP process. The detailed adoption contract and
FRD milestones are in `docs/roadmap/federated_research_discovery_adoption.md`.

## Ingestion flow

1. Validate a versioned manifest and local source readiness.
2. Create or resume a durable import run and item records.
3. Parse one document through the typed parser boundary.
4. Evaluate duplicate evidence before persistence.
5. Persist relational metadata and FTS content atomically for the item.
6. Record sanitized item outcomes while allowing expected item-level failures to continue.
7. Reconcile run state and produce bounded, sanitized rehearsal evidence.

Unexpected programming, ORM, database, and assertion failures must not be misclassified as independent bad-document outcomes. Recoverable categories remain intentionally narrow and evidence-driven.

## Storage and provenance

SQLite stores canonical metadata, extracted text, import-run state, review outcomes, and additive schema-version information. SQLite FTS5 stores a search-optimized copy of title, abstract, body text, and raw text, keyed so results can join back to relational metadata.

Provider metadata is previewed and compared without silently overwriting canonical values. Current Phase 1 identity remains document-oriented; explicit scholarly-work, version, file, extraction-run, assertion, and canonical-selection identities are deferred until operational evidence requires them.

Federated discovery strengthens rather than weakens this rule: one scholarly work
may have observations from PubMed, Crossref, OpenAlex, Semantic Scholar, arXiv,
or later providers. Canonical identity may collapse a defensible duplicate, but
each provider observation and disagreement must remain inspectable. A retrieval
index or provider response is never the source of truth for historical
provenance.

## Current operating constraints

- Corpus discovery and acquisition are bounded and review-gated.
- Candidate discovery output is review-only and must not automatically become an approval record.
- Only legally available and explicitly approved PMC Open Access files may be acquired.
- Private corpora, PDFs, databases, provider payloads, and temporary rehearsal artifacts must not be committed.
- Page-level extraction provenance is deferred until before Phase 2 evidence-record work.
- Third-party discovery telemetry, persistent external analytics identifiers, and remote bootstrap installers are not part of Core's scientific functionality.
- Optional provider credentials must stay in environment/secret boundaries and must never enter evidence records, prompts, receipts, committed config, or logs.

## Future extension points

- Replace SQLite session construction with PostgreSQL when multi-user or larger operational requirements justify it.
- Add OCR, HTML, EPUB, XML, patent, dataset, and stronger scientific-PDF parser implementations behind stable contracts.
- Add page/span extraction identity before Phase 2 claim and evidence records.
- Add embeddings behind a pluggable vector index while retaining lexical search as a transparent baseline.
- Add citation, claim, evidence, contradiction, uncertainty, and concept graph models only in their scheduled phases.
- Add a provider-neutral Discovery Broker and search-run ledger, then OpenAlex, Semantic Scholar, and arXiv adapters behind it; see `docs/roadmap/federated_research_discovery_adoption.md`.
- Add bounded citation/reference snowball discovery only when seed identity, depth, provider status, and provenance can be replayed deterministically.
- Add an optional Knowledge Engine MCP facade only after direct service contracts are stable and a measured integration need exists.
- Add worker queues only when measured workload requires asynchronous or distributed execution.

## Architecture decision records

Durable design decisions are recorded in `docs/architecture/adr/`.

- `0001-use-python-poetry-and-typed-service-boundaries.md`
- `0002-use-sqlite-and-fts5-for-phase-0.md`

New cross-cutting infrastructure should be traceable to the roadmap, an ADR, or an explicit technical-debt entry before it expands further.
