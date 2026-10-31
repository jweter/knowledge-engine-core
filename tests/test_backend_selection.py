from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from knowledge_engine.vector_search.backend_selection import resolve_vector_index
from knowledge_engine.vector_search.index import FaissVectorIndex
from knowledge_engine.vector_search.qdrant_index import QdrantVectorIndex

_MODEL = "test-model-v1"


def test_faiss_with_a_nonexistent_path_returns_a_fresh_index(tmp_path: Path) -> None:
    index = resolve_vector_index(
        "faiss",
        dimension=3,
        embedding_model=_MODEL,
        index_path=tmp_path / "missing.faiss",
    )
    assert isinstance(index, FaissVectorIndex)
    assert index.dimension == 3
    assert index.size == 0


def test_faiss_with_an_existing_saved_file_returns_the_loaded_index(tmp_path: Path) -> None:
    index_path = tmp_path / "saved.faiss"
    original = FaissVectorIndex(3)
    original.add(1, [1.0, 0.0, 0.0])
    original.add(2, [0.0, 1.0, 0.0])
    original.save(index_path)

    loaded = resolve_vector_index(
        "faiss",
        dimension=3,
        embedding_model=_MODEL,
        index_path=index_path,
    )
    assert isinstance(loaded, FaissVectorIndex)
    assert loaded.size == 2
    matches = loaded.search([1.0, 0.0, 0.0], k=1)
    assert matches[0].vector_id == 1


def test_faiss_without_index_path_raises() -> None:
    with pytest.raises(ValueError, match="FAISS backend requires index_path"):
        resolve_vector_index("faiss", dimension=3, embedding_model=_MODEL)


def test_qdrant_with_an_injected_in_memory_client_returns_a_working_index() -> None:
    index = resolve_vector_index(
        "qdrant",
        dimension=3,
        embedding_model=_MODEL,
        qdrant_collection_name="test-collection",
        qdrant_client=QdrantClient(":memory:"),
    )
    assert isinstance(index, QdrantVectorIndex)
    index.add(1, [1.0, 0.0, 0.0])
    matches = index.search([1.0, 0.0, 0.0], k=1)
    assert matches[0].vector_id == 1


def test_qdrant_without_collection_name_raises() -> None:
    with pytest.raises(ValueError, match="Qdrant backend requires qdrant_collection_name"):
        resolve_vector_index(
            "qdrant",
            dimension=3,
            embedding_model=_MODEL,
            qdrant_client=QdrantClient(":memory:"),
        )


def test_qdrant_without_url_or_client_raises() -> None:
    with pytest.raises(
        ValueError,
        match="Qdrant backend requires qdrant_url unless qdrant_client is supplied",
    ):
        resolve_vector_index(
            "qdrant",
            dimension=3,
            embedding_model=_MODEL,
            qdrant_collection_name="test-collection",
        )


def test_unknown_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown vector index backend: 'bogus'"):
        resolve_vector_index("bogus", dimension=3, embedding_model=_MODEL)
