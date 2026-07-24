from pathlib import Path

from knowledge_engine.vector_search import (
    VectorIndexMetadata,
    load_index_metadata,
    metadata_path_for,
    save_index_metadata,
)


def test_metadata_path_for_appends_meta_json_suffix() -> None:
    index_path = Path("/tmp/index.faiss")

    assert metadata_path_for(index_path) == Path("/tmp/index.faiss.meta.json")


def test_load_index_metadata_returns_none_when_no_sidecar_exists(tmp_path: Path) -> None:
    assert load_index_metadata(tmp_path / "index.faiss") is None


def test_save_and_load_index_metadata_round_trip(tmp_path: Path) -> None:
    index_path = tmp_path / "index.faiss"
    metadata = VectorIndexMetadata(embedding_model="external:test-v1", dimension=3)

    save_index_metadata(index_path, metadata)
    loaded = load_index_metadata(index_path)

    assert loaded == metadata
