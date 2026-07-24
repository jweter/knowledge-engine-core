# Phase 3: Search Plus Semantics

Phase 3 adds embeddings-based semantic search alongside the existing lexical
baseline.

The detailed design is maintained in `docs/phase3_design.md`. Its first open
question -- which embedding-generation approach to use -- is a new-dependency
and offline-posture decision the project owner must make, the same way the
Phase 2 extraction methodology was decided before any extraction code was
written; no embedding or vector-index code should be written before it is.

## Goals

- Add embeddings using a pluggable vector index.
- Support local FAISS and server-backed Qdrant.
- Keep lexical search as a transparent baseline.

## Principle

Semantic search must never replace or hide the existing lexical baseline --
`docs/decisions.md`'s "Use FTS5 before vector search" and ADR 0002 explicitly
kept `Paper.embedding_model`/`Paper.embedding_id` as reserved, unused fields
for exactly this phase. A result must remain traceable back to the exact
source text it came from; semantic ranking is an additional retrieval
signal, not a replacement for evidence traceability.
