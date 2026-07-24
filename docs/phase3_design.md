# Phase 3 Design: Search Plus Semantics

Status:
This is the Phase 3 design sketch, written before any Phase 3 implementation
milestone -- the same role `docs/m6_phase1_corpus_ingestion_plan.md` played
for Phase 1 and `docs/phase2_design.md` played for Phase 2. It turns
`docs/roadmap/phase3.md`'s three-bullet goal statement into an
implementation-ready architecture and, most importantly, surfaces the one
real open decision (embedding-generation approach) before any code is
written, the same way Phase 2's Extraction Methodology section did.

## Mission

Add semantic (embedding-based) retrieval alongside the existing SQLite FTS5
lexical search, so a query can match papers by meaning, not just shared
keywords, while keeping every result traceable back to its exact source
text.

## Principle

Restated from `docs/roadmap.md` and `docs/decisions.md`'s "Use FTS5 before
vector search": lexical search remains the transparent baseline. Semantic
search is an additional ranking/retrieval signal layered on top, never a
replacement that hides how a result was actually found. This is the same
"never decide truth, preserve traceability" boundary Phase 2 held itself to
for evidence extraction -- a semantic match is a retrieval signal, not a
scientific judgment about relevance or correctness.

## Why now

Corpus growth was intentionally stopped at 605 papers by the project owner's
decision (see `docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2
tuning" section) once that was judged large enough for Phase 2 extraction
tuning. That same corpus is a reasonable starting scale for Phase 3: large
enough to show whether semantic ranking actually improves on lexical-only
retrieval for real scientific queries, small enough that a local embedding
index (605 vectors) is trivial to build and rebuild while iterating on the
approach.

## Already reserved: `Paper.embedding_model` / `Paper.embedding_id`

Confirmed by inspection of `knowledge_engine/models.py` and ADR 0002: `Paper`
has carried `embedding_model: str | None` and `embedding_id: str | None`
columns (plus an index on the pair) since Phase 0, deliberately unused until
this phase. ADR 0002's own text: "Keep future embedding references on
`Paper`, but do not implement embeddings yet." No schema migration is needed
to start storing an embedding identity per paper -- only to decide what
`embedding_model`/`embedding_id` actually mean once populated (see Open
Questions).

## Goals (from `docs/roadmap/phase3.md`)

- Add embeddings using a pluggable vector index.
- Support local FAISS and server-backed Qdrant.
- Keep lexical search as a transparent baseline.

## Out of Scope

- Replacing or deprecating SQLite FTS5 lexical search.
- A knowledge graph or graph database (Phase 4).
- Any change to Phase 2's evidence extraction, relationship, or corpus
  ingestion semantics.
- LLM-based query understanding, summarization, or reasoning of any kind --
  embeddings here are a numeric similarity signal over existing text, not a
  generative or reasoning capability, consistent with the project-wide
  non-goal already established for Phase 2.
- A hosted/managed Qdrant deployment decision -- "server-backed Qdrant"
  support means the retrieval code can target a Qdrant instance the operator
  already runs, not that this project stands one up.

## Architecture (sketch)

```text
Parser / Extraction (existing, unchanged)
  -> Embedding Layer (new)
       deterministic, versioned embedding generation for paper text
       (embedding_model records exactly which model/version produced it,
       mirroring ADJUDICATION_RULES_VERSION / *_RULES_VERSION precedent)
  -> Vector Index Layer (new, pluggable)
       a narrow VectorIndex interface (add/search/remove) with at least
       two implementations: local FAISS (no server, matches this
       project's offline-by-default posture) and server-backed Qdrant
       (opt-in, for operators who already run one)
  -> Search Service (existing SearchService, extended)
       combines lexical (FTS5) and semantic (vector index) results;
       lexical remains the default/baseline, semantic is additive
  -> ke search / ke answer (existing commands, extended)
       a result must still show why it matched -- lexical snippet,
       semantic similarity score, or both -- never an opaque ranking
```

## What needs a real decision before any code

### Embedding generation approach (open, needs project owner decision)

Unlike Phase 2's rule-based extraction (pure Python, no dependency), turning
text into a vector embedding fundamentally requires either a machine-learning
model or an external API -- there is no dependency-free option. This is the
same class of decision Phase 2's Extraction Methodology section escalated to
the project owner (option 1 vs. 2 vs. 3), not a call this design should make
unilaterally, especially given this project's consistent offline-by-default,
supply-chain-conscious posture (see the PMC Cloud Service migration ADR for
precedent on how a dependency/infrastructure choice was evaluated here).

Three options, for the project owner to choose among:

1. **Local embedding model via `sentence-transformers`** (e.g.
   `all-MiniLM-L6-v2` or a similar small model). Fully offline, no per-query
   cost, deterministic given a fixed model version. Adds a real new
   dependency (`sentence-transformers`, and transitively PyTorch or a
   similar tensor runtime) with its own model-download and disk-footprint
   implications -- the model weights themselves (tens to hundreds of MB)
   would need to be fetched at least once, similar in kind to the spaCy
   dependency Phase 2 deliberately deferred for the same reason.
2. **External embedding API** (for example an Anthropic, OpenAI, or Cohere
   embeddings endpoint). No local model weights or heavy dependency, but
   breaks the "runs fully offline" property this project has held since
   Phase 0 (`docs/architecture.md`: "It runs fully offline"), introduces a
   real per-paper/per-query cost and a new network dependency, and sends
   corpus text to a third party -- a meaningfully different trust posture
   than the read-only NCBI/Crossref/PMC fetches already in use, since those
   never transmit the corpus's own content outward.
3. **Defer embedding generation, ship the pluggable `VectorIndex` interface
   and FAISS/Qdrant backends first**, accepting pre-computed vectors from an
   external, out-of-band process (a notebook, a one-off script) rather than
   generating them in `core` itself. This narrows Phase 3's first milestone
   to proving the retrieval-side architecture (index, search, ranking
   combination) without committing to an embedding-generation dependency yet
   -- the same "narrow the first milestone, prove correctness before
   expanding" discipline the M12 100-paper rehearsal and the M28/M29
   PICO/Relationship-Report milestones both followed.

No default is assumed here. Each has a real, different tradeoff against this
project's established offline/dependency posture, so this is presented as an
open question rather than a recommendation, unlike Phase 2's extraction
methodology (where structured-section heuristics were the clearer fit for
this project's constraints). If a strong recommendation is wanted, option 3
is the lowest-commitment starting point: it proves the FAISS/Qdrant plumbing
without answering the embedding-model question, and options 1/2 both remain
available once the retrieval architecture is validated.

### Vector index sequencing (open, smaller decision)

The roadmap names both local FAISS and server-backed Qdrant. Building both
simultaneously duplicates the M12-style "narrow first, expand later"
discipline unnecessarily. Recommendation (not yet confirmed): FAISS first,
since it requires no server/operator setup and matches this project's
default single-machine posture; Qdrant as a second, explicitly optional
backend behind the same `VectorIndex` interface once FAISS proves the
architecture.

## Testing Strategy (sketch, pending the embedding-approach decision)

Following the same pattern M14/Phase 2 established:

- Deterministic tests for the `VectorIndex` interface using small synthetic
  fixed-dimension vectors, not real embeddings -- proves add/search/remove
  correctness without depending on any specific embedding model.
- If option 1 (local model) is chosen: a model-version-pinned fixture test
  proving the same input text produces the same embedding vector, mirroring
  how `*_RULES_VERSION` constants prove determinism elsewhere.
- No test should assert that a semantic match is more "correct" than a
  lexical one -- only that the ranking/combination logic behaves as
  specified for fixed, known inputs.

## Open Questions

- **Embedding generation approach** -- see above; needs the project owner's
  decision before any embedding-generation code is written.
- **Vector index sequencing** -- FAISS first is recommended but not yet
  confirmed.
- **Result combination** -- once both lexical and semantic signals exist,
  how are they combined into one ranked result list (interleaved, semantic
  as a re-ranker over lexical candidates, separate result sections)? Not
  yet designed; depends on which embedding approach is chosen and what real
  query patterns look like once semantic search exists to observe.
- **`embedding_id` semantics** -- once an embedding approach is chosen, what
  exactly does `embedding_id` identify (a vector-index row ID, a content
  hash of the embedded text, something else)? Deferred until the approach
  decision resolves what's actually being identified.
