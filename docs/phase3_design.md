# Phase 3 Design: Search Plus Semantics

Status:
This is the Phase 3 design sketch, written before any Phase 3 implementation
milestone -- the same role `docs/m6_phase1_corpus_ingestion_plan.md` played
for Phase 1 and `docs/phase2_design.md` played for Phase 2. It turns
`docs/roadmap/phase3.md`'s three-bullet goal statement into an
implementation-ready architecture and, most importantly, surfaced the one
real open decision (embedding-generation approach) before any
embedding-*generation* code was written, the same way Phase 2's Extraction
Methodology section did. That decision did not block the retrieval-side
`VectorIndex`/FAISS/Qdrant plumbing -- option 3 below explicitly proposed
building that first against externally-supplied vectors, and M30 did
exactly that: a pluggable `VectorIndex` interface, a local FAISS
implementation, and an `EmbeddingGenerator` interface with no
implementation yet, wired into two CLI commands
(`ke embedding-index-build`, `ke vector-search`) that operate on
externally-supplied vectors only. M31 then resolved the embedding-generation
decision itself: the project owner chose "both" -- a local
`sentence-transformers` model and an external OpenAI API generator, both
implementing the same `EmbeddingGenerator` interface, wired into a new
`ke embedding-generate` command that produces the same vectors file
`ke embedding-index-build` already consumes. M32 then closed the gap those
two milestones deliberately left open: `ke vector-search` now accepts
`--query-text`, embedding a live free-text query with either generator
before searching, instead of requiring a pre-embedded vector file for
every query. See the Architecture and Vector Index Layer sections below
for what M30/M31/M32 actually implement, and Open Questions for what
remains undecided (notably, combining this with lexical FTS5 results into
one ranked list -- M32 only removes the "must pre-embed the query"
friction, it does not unify the two retrieval signals).

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

## Architecture (M30 implements the two layers marked "implemented" below)

```text
Parser / Extraction (existing, unchanged)
  -> Embedding Layer (implemented, M31)
       EmbeddingGenerator: model_id, dimension, generate(text)
       (knowledge_engine.vector_search.generator). Two implementations,
       both chosen by the project owner rather than one recommended over
       the other:
       - SentenceTransformerEmbeddingGenerator
         (knowledge_engine.vector_search.local_generator): local
         `sentence-transformers` model (default all-MiniLM-L6-v2, 384
         dimensions), CPU-only PyTorch build, fully offline once weights
         are cached, model_id "local:<model-name>".
       - OpenAiEmbeddingGenerator
         (knowledge_engine.vector_search.openai_generator): OpenAI's
         `/v1/embeddings` endpoint over stdlib urllib (no SDK, matching
         every other outbound HTTP client in this project), requires
         `KE_OPENAI_API_KEY`, sends paper text to a third party,
         model_id "openai:<model-name>".
       embedding_model records exactly which model/version produced a
       vector, mirroring ADJUDICATION_RULES_VERSION / *_RULES_VERSION
       precedent. Wired into `ke embedding-generate --generator local|openai
       --output <vectors.jsonl>`, which embeds each paper's title and
       abstract (one vector per paper -- not full body text, not chunked)
       and writes the same vectors-file format `ke embedding-index-build`
       already consumes; M30's ingestion/build/search commands did not
       change.
  -> Vector Index Layer (implemented, M30)
       knowledge_engine.vector_search.index: a narrow VectorIndex
       interface (add/search/remove) and FaissVectorIndex, a local flat
       (exact) L2 index (no server, matches this project's
       offline-by-default posture). Qdrant remains a second, not-yet-built
       backend behind the same interface. knowledge_engine.vector_search.
       index_metadata persists a small JSON sidecar recording exactly
       which embedding_model built an index -- vectors from different
       models are not comparable even at the same dimension, so mixing
       them would silently rank unrelated vector spaces together (found
       by a Codex review on PR #154); a single index is now locked to one
       model, enforced at both build time (a mismatched or
       metadata-less existing index is rejected) and search time (an
       optional embedding_model in the query file is checked against it).
       Wired into two CLI commands:
       `ke embedding-index-build --vectors <jsonl> --index-path <path>`
       (knowledge_engine.vector_search.ingestion parses and validates
       externally-supplied vectors -- including that every record in one
       file shares the same embedding_model -- referentially checks every
       paper_id against the local database, builds/updates the index, and
       persists Paper.embedding_model/embedding_id) and
       `ke vector-search --index-path <path> (--query-vector <json> |
       --query-text <text> --generator local|openai)` (M32: accepts either
       an already-embedded query vector from any external tool, or a
       free-text query embedded live with the same local/OpenAI generators
       `ke embedding-generate` uses -- exactly one of the two must be
       given. Either way the query's embedding_model is checked against
       the index's recorded embedding_model before searching, and the
       command returns ranked papers with their real metadata).
  -> Search Service (existing SearchService, unchanged)
       ke search / ke answer remain lexical-only (FTS5); `ke vector-search`
       is a separate command, not merged into them. Combining lexical and
       semantic results into one ranked list is still deferred -- see Open
       Questions' Result combination entry -- M32 only removed the
       "queries must be pre-embedded" friction, it did not unify the two
       retrieval signals.
```

## Decisions the project owner made before any code was written

### Embedding generation approach (resolved by M31: both)

Unlike Phase 2's rule-based extraction (pure Python, no dependency), turning
text into a vector embedding fundamentally requires either a machine-learning
model or an external API -- there is no dependency-free option. This was the
same class of decision Phase 2's Extraction Methodology section escalated to
the project owner (option 1 vs. 2 vs. 3), not a call this design made
unilaterally, especially given this project's consistent offline-by-default,
supply-chain-conscious posture (see the PMC Cloud Service migration ADR for
precedent on how a dependency/infrastructure choice was evaluated here).

Three options were presented; the project owner chose **both 1 and 2**,
having already validated the retrieval side via option 3 (M30):

1. **Local embedding model via `sentence-transformers`** (default
   `all-MiniLM-L6-v2`, 384 dimensions). Fully offline, no per-query cost,
   deterministic given a fixed model version. Adds a real new dependency
   (`sentence-transformers`, and transitively PyTorch) with its own
   model-download and disk-footprint implications -- the model weights
   (tens to hundreds of MB) are fetched once from the Hugging Face Hub and
   cached locally. Implemented as `SentenceTransformerEmbeddingGenerator`;
   PyTorch is pinned to the CPU-only wheel index
   (`https://download.pytorch.org/whl/cpu`) rather than the default
   GPU/CUDA build, since this project runs single-machine and offline --
   the default build pulls in an unused multi-gigabyte NVIDIA CUDA
   toolkit.
2. **External embedding API**, specifically OpenAI's `/v1/embeddings`
   endpoint. No local model weights or heavy dependency, but breaks the
   "runs fully offline" property this project has held since Phase 0
   (`docs/architecture.md`: "It runs fully offline"), introduces a real
   per-paper/per-query cost and a new network dependency, and sends corpus
   text to a third party -- a meaningfully different trust posture than the
   read-only NCBI/Crossref/PMC fetches already in use, since those never
   transmit the corpus's own content outward. Implemented as
   `OpenAiEmbeddingGenerator` using stdlib `urllib` (no `openai` SDK,
   matching every other outbound HTTP client in this project); requires
   `KE_OPENAI_API_KEY`.
3. **Defer embedding generation, ship the pluggable `VectorIndex` interface
   and FAISS/Qdrant backends first** -- this is what M30 did, proving the
   retrieval-side architecture before the generation decision above was
   made.

Both generators implement the same `EmbeddingGenerator` interface
(`knowledge_engine.vector_search.generator`) and plug into
`ke embedding-generate --generator local|openai`, so neither `VectorIndex`
nor the ingestion/build/search commands needed to change.

### Vector index sequencing (resolved: FAISS first, Qdrant approved next)

The roadmap names both local FAISS and server-backed Qdrant. Building both
simultaneously would have duplicated the M12-style "narrow first, expand
later" discipline unnecessarily, so FAISS shipped first in M30 -- no
server/operator setup, matching this project's default single-machine
posture. The project owner has approved Qdrant as the second, explicitly
optional backend behind the same `VectorIndex` interface (M33, not yet
built as of this writing).

## Testing Strategy

Following the same pattern M14/Phase 2 established:

- Deterministic tests for the `VectorIndex` interface using small synthetic
  fixed-dimension vectors, not real embeddings -- proves add/search/remove
  correctness without depending on any specific embedding model.
  Implemented in `tests/test_vector_index.py` and
  `tests/test_vector_ingestion.py`, plus `tests/test_vector_search_cli.py`
  for the two CLI commands end-to-end against a real (test) database.
- For both generators (M31): the model/API client is injected as a
  dependency (`model_loader` for the local generator, `opener` for the
  OpenAI generator), matching this project's transport-testing pattern
  (`ncbi_http.UrllibNcbiTransport`, `google_drive_http.
  GoogleDriveHttpTransport`) -- tests inject a fake encoder/opener rather
  than downloading a real model or calling the real API, so the suite
  stays fast and deterministic. Implemented in `tests/test_local_generator.py`,
  `tests/test_openai_generator.py`, and `tests/test_embedding_generate_cli.py`.
  One test (`test_build_embedding_generator_returns_a_real_embedding_generator`)
  does construct the real `SentenceTransformerEmbeddingGenerator` to prove
  the CLI wiring is correct, but only reads `model_id`, which requires no
  model download (the model loads lazily on first `generate`/`dimension`
  call).
- For `ke vector-search --query-text` (M32): `tests/test_free_text_vector_search_cli.py`
  monkeypatches `_build_embedding_generator` with a fake generator (same
  seam `test_embedding_generate_cli.py` uses), proving the live-embed path,
  the `--query-vector`/`--query-text` mutual-exclusion validation, and the
  embedding-model mismatch rejection without downloading a real model or
  calling a real API.
- No test should assert that a semantic match is more "correct" than a
  lexical one -- only that the ranking/combination logic behaves as
  specified for fixed, known inputs.

## Open Questions

- **Embedding generation approach** -- resolved by M31: both local
  (`sentence-transformers`) and external-API (OpenAI) generators are
  implemented behind the same `EmbeddingGenerator` interface. See above.
- **Vector index sequencing** -- resolved by M30: FAISS first, implemented.
  Qdrant remains a second, not-yet-built backend behind the same
  `VectorIndex` interface, to be added only if a real operator need for a
  server-backed index appears.
- **Result combination** -- partially unblocked by M32: `ke vector-search
  --query-text` now accepts a free-text query directly, so "what real
  query patterns look like" is no longer blocked on an embedding approach
  existing. Still undesigned: how lexical (`ke search`/`ke answer`, FTS5)
  and semantic (`ke vector-search`) results get combined into one ranked
  list (interleaved, semantic as a re-ranker over lexical candidates,
  separate result sections) -- they remain two separate commands today,
  not merged.
- **`embedding_id` semantics** -- resolved for M30's own mechanism:
  `embedding_id` is the paper's own `Paper.id` (as a string), matching the
  ID `FaissVectorIndex` itself is keyed by. This may need revisiting if a
  future embedding approach naturally produces vectors identified some
  other way (for example versioned per re-embedding), but is not
  speculative for the mechanism M30 actually implements. A real
  consequence of this choice, found by a Codex review on PR #154:
  `Paper.id` is only unique *within* one database, not portable across
  one, so `ke corpus-library-import` (M27) now clears
  `embedding_model`/`embedding_id` on every imported paper rather than
  copying them verbatim -- the source database's ID would otherwise
  collide with an unrelated paper's ID in the target database, or point
  at nothing. An operator must re-run `ke embedding-index-build` for
  papers after importing a corpus-library snapshot; the FAISS index file
  itself was never part of the snapshot's portable content to begin with
  (only paper-intrinsic content is -- see `docs/m27_corpus_library.md`).
