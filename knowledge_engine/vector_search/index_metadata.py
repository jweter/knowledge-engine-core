"""Tracks which embedding model an on-disk `FaissVectorIndex` was built from.

`FaissVectorIndex.save`/`load` only persist the raw vector data -- they have
no concept of which embedding model produced those vectors, since that is
not a `VectorIndex`-interface concern (a future Qdrant backend might record
this differently, for example as collection metadata already). But mixing
vectors from different embedding models into one index is a real
correctness hazard: L2 distance between vectors from different models is
meaningless even when their dimensions happen to coincide, so an index must
never silently accept a second model's vectors. This module persists a
small JSON sidecar next to the index file recording exactly which model
built it, so `embedding-index-build` can refuse to mix models and
`vector-search` can report which model a result actually came from.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class VectorIndexMetadata:
    """Which embedding model and dimension one on-disk vector index was built from."""

    embedding_model: str
    dimension: int


def metadata_path_for(index_path: Path) -> Path:
    """Return the sidecar metadata path for a given FAISS index file."""

    return index_path.with_name(index_path.name + ".meta.json")


def save_index_metadata(index_path: Path, metadata: VectorIndexMetadata) -> None:
    """Persist `metadata` as the sidecar for `index_path`."""

    metadata_path_for(index_path).write_text(json.dumps(asdict(metadata)), encoding="utf-8")


def load_index_metadata(index_path: Path) -> VectorIndexMetadata | None:
    """Load `index_path`'s sidecar metadata, or `None` if it has none."""

    metadata_path = metadata_path_for(index_path)
    if not metadata_path.exists():
        return None
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return VectorIndexMetadata(
        embedding_model=payload["embedding_model"], dimension=payload["dimension"]
    )
