# ADR 0002: Use SQLite and FTS5 for Phase 0 Search

## Status

Accepted

## Context

Phase 0 needs offline storage and search. The project must be easy to run on a
single machine without PostgreSQL, Elasticsearch, Qdrant, FAISS, Neo4j, or cloud
services.

## Decision

Use SQLite as the canonical Phase 0 database and SQLite FTS5 for lexical search.
Store relational metadata separately from the FTS table. Keep future embedding
references on `Paper`, but do not implement embeddings yet.

## Consequences

- The application runs fully offline.
- Setup remains simple for beginners.
- Keyword and phrase search are available immediately.
- The canonical relational model is not coupled to a future vector or graph
  backend.
- Large-scale ingestion will eventually require PostgreSQL and specialized
  search/vector infrastructure.

## Alternatives Considered

- PostgreSQL first: rejected for Phase 0 because it increases setup burden.
- Embeddings first: rejected because the project must establish source
  preservation and traceable lexical search before semantic layers.
- External search engine first: rejected because offline local installation is a
  founding requirement.
