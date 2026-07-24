"""Pluggable vector-index interface and a local FAISS-backed implementation.

`docs/phase3_design.md`'s Architecture sketch names this the Vector Index
Layer: a narrow `VectorIndex` interface (add/search/remove) with at least
two implementations -- local FAISS (this module, no server, matches the
project's offline-by-default posture) and server-backed Qdrant (not yet
implemented). Persistence (how an index is created, saved, loaded, or
connected to) is deliberately left out of the shared interface -- FAISS
persists to a local file, a future Qdrant backend would connect to a
running server instead -- so each backend owns its own persistence
mechanics.

This module does not generate embeddings from text. See `generator.py` for
the separate, not-yet-implemented `EmbeddingGenerator` interface that
future local-model or external-API options plug into.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np

VECTOR_INDEX_RULES_VERSION = "m30-faiss-vector-index-v1"


class VectorSearchError(ValueError):
    """A vector-index operation received malformed input."""


@dataclass(frozen=True)
class VectorMatch:
    """One nearest-neighbor result.

    `score` is squared L2 distance (`FaissVectorIndex`'s metric) -- lower
    means more similar, the opposite convention from a typical similarity
    score. Callers must not assume "higher is better."
    """

    vector_id: int
    score: float


class VectorIndex(Protocol):
    """Common interface every vector-index backend implements."""

    def add(self, vector_id: int, vector: Sequence[float]) -> None:
        """Add or replace the vector stored for `vector_id`."""

    def search(self, query_vector: Sequence[float], k: int) -> list[VectorMatch]:
        """Return up to `k` nearest neighbors to `query_vector`, best match first."""

    def remove(self, vector_id: int) -> None:
        """Remove `vector_id`'s vector, if present. A no-op if it is absent."""


class FaissVectorIndex:
    """Local FAISS-backed `VectorIndex` using a flat (exact) L2 index.

    Wrapped in `IndexIDMap2` so vector IDs are the caller's own IDs (this
    project uses `Paper.id`) rather than FAISS's default sequential
    positions -- required for `add` to replace an existing paper's vector
    by ID instead of silently duplicating it, and for `remove` to work by
    ID at all. "Flat" means exact (brute-force) nearest-neighbor search,
    not an approximate index -- correct at any scale this corpus is likely
    to reach, and simplest to reason about; an approximate index is a
    future optimization only if search latency actually requires it.
    """

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise VectorSearchError("Vector dimension must be a positive integer.")
        self.dimension = dimension
        # Typed as the `faiss.Index` base class (not `IndexIDMap2`) so `load`
        # can assign a freshly `faiss.read_index`-loaded index, whose static
        # return type is also the base class, without a type mismatch.
        self._index: faiss.Index = faiss.IndexIDMap2(faiss.IndexFlatL2(dimension))

    @property
    def size(self) -> int:
        """Number of vectors currently stored."""

        return int(self._index.ntotal)

    def add(self, vector_id: int, vector: Sequence[float]) -> None:
        self._validate_vector(vector)
        ids = np.array([vector_id], dtype="int64")
        # faiss's real Python API accepts a numpy int64 array here (verified
        # directly against the installed faiss-cpu build); its type stubs
        # incorrectly declare an `IDSelector` parameter instead.
        self._index.remove_ids(ids)  # type: ignore[arg-type]
        self._index.add_with_ids(np.array([vector], dtype="float32"), ids)

    def search(self, query_vector: Sequence[float], k: int) -> list[VectorMatch]:
        self._validate_vector(query_vector)
        if k <= 0:
            raise VectorSearchError("k must be a positive integer.")
        if self.size == 0:
            return []
        distances, ids = self._index.search(np.array([query_vector], dtype="float32"), k)
        return [
            VectorMatch(vector_id=int(vector_id), score=float(distance))
            for distance, vector_id in zip(distances[0], ids[0], strict=True)
            if vector_id != -1
        ]

    def remove(self, vector_id: int) -> None:
        self._index.remove_ids(np.array([vector_id], dtype="int64"))  # type: ignore[arg-type]

    def save(self, path: Path) -> None:
        """Persist this index to a local file."""

        faiss.write_index(self._index, str(path))

    @classmethod
    def load(cls, path: Path, *, dimension: int) -> FaissVectorIndex:
        """Load a previously saved index from a local file.

        `dimension` must be supplied by the caller (recorded separately,
        for example alongside the vectors file that built the index) and
        is verified against the loaded index's own reported dimension.
        """

        instance = cls(dimension)
        loaded = faiss.read_index(str(path))
        if loaded.d != dimension:
            raise VectorSearchError(
                f"Index at {path} has dimension {loaded.d}, expected {dimension}."
            )
        instance._index = loaded
        return instance

    def _validate_vector(self, vector: Sequence[float]) -> None:
        if len(vector) != self.dimension:
            raise VectorSearchError(
                f"Vector has dimension {len(vector)}, expected {self.dimension}."
            )
