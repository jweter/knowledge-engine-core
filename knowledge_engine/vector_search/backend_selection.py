"""Select and construct a `VectorIndex` for a named backend.

Closes the gap `docs/roadmap.md`'s Phase 3 section names explicitly:
"Qdrant M33 (QdrantVectorIndex, not yet wired into the CLI commands --
no operator need for that has appeared)." This module is the single
factory a future, separately-scoped CLI change would call once a
--backend option exists; wiring it into the CLI is out of scope here.
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from knowledge_engine.vector_search.index import FaissVectorIndex, VectorIndex
from knowledge_engine.vector_search.qdrant_index import QdrantVectorIndex


def resolve_vector_index(
    backend: str,
    *,
    dimension: int,
    embedding_model: str,
    index_path: Path | None = None,
    qdrant_collection_name: str | None = None,
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    qdrant_client: QdrantClient | None = None,
) -> VectorIndex:
    """Construct the `VectorIndex` for `backend`.

    backend="faiss": `index_path` is required. Reproduces the exact
    load-if-exists-else-construct-fresh pattern already used inline in
    `knowledge_engine/entrypoint.py`'s `embedding_generate` command.

    backend="qdrant": `qdrant_collection_name` is required, and either
    `qdrant_client` or `qdrant_url` must be supplied. Constructs
    `QdrantVectorIndex` directly; no validation is added beyond what
    its own constructor already performs.
    """
    if backend == "faiss":
        if index_path is None:
            raise ValueError("FAISS backend requires index_path")
        return (
            FaissVectorIndex.load(index_path, dimension=dimension)
            if index_path.exists()
            else FaissVectorIndex(dimension)
        )
    if backend == "qdrant":
        if not qdrant_collection_name:
            raise ValueError("Qdrant backend requires qdrant_collection_name")
        if qdrant_client is None and qdrant_url is None:
            raise ValueError("Qdrant backend requires qdrant_url unless qdrant_client is supplied")
        return QdrantVectorIndex(
            dimension=dimension,
            collection_name=qdrant_collection_name,
            embedding_model=embedding_model,
            url=qdrant_url,
            api_key=qdrant_api_key,
            client=qdrant_client,
        )
    raise ValueError(f"Unknown vector index backend: {backend!r}")
