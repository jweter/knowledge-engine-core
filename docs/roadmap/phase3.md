# Phase 3: Search Plus Semantics

Phase 3 adds embeddings-based semantic search alongside the existing lexical
baseline.

The detailed design is maintained in `docs/phase3_design.md`. Its embedding-
generation decision -- a new-dependency and offline-posture choice the
project owner had to make, the same way the Phase 2 extraction methodology
was decided before any extraction code was written -- is now resolved: M30
built the retrieval-side plumbing first (`VectorIndex`/FAISS, against
externally-supplied vectors, without committing to an embedding-model
dependency), M31 added both a local (`sentence-transformers`) and an
external-API (OpenAI) embedding generator behind the same
`EmbeddingGenerator` interface, and M32 wired `ke vector-search` to accept
a free-text query embedded live with either generator, removing the
"queries must be pre-embedded" friction M30/M31 deliberately left in
place. Qdrant, as a second `VectorIndex` backend, is approved and not yet
built (M33).

## Goals

- Add embeddings using a pluggable vector index. (Done, M30: FAISS.)
- Support local FAISS and server-backed Qdrant. (FAISS done, M30; Qdrant
  approved, not yet built -- M33.)
- Keep lexical search as a transparent baseline. (Unchanged -- `ke search`/
  `ke answer` remain FTS5-only; `ke vector-search` is a separate command.)

## Principle

Semantic search must never replace or hide the existing lexical baseline --
`docs/decisions.md`'s "Use FTS5 before vector search" and ADR 0002 explicitly
kept `Paper.embedding_model`/`Paper.embedding_id` as reserved, unused fields
for exactly this phase. A result must remain traceable back to the exact
source text it came from; semantic ranking is an additional retrieval
signal, not a replacement for evidence traceability.
