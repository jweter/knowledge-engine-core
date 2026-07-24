from pathlib import Path

import pytest

from knowledge_engine.vector_search import (
    VECTOR_INDEX_RULES_VERSION,
    FaissVectorIndex,
    VectorSearchError,
)


def test_vector_index_rules_version_is_stable() -> None:
    assert VECTOR_INDEX_RULES_VERSION == "m30-faiss-vector-index-v1"


def test_add_and_search_returns_nearest_neighbor_first() -> None:
    index = FaissVectorIndex(dimension=3)
    index.add(1, [1.0, 0.0, 0.0])
    index.add(2, [0.0, 1.0, 0.0])
    index.add(3, [0.9, 0.1, 0.0])

    matches = index.search([1.0, 0.0, 0.0], k=3)

    assert [match.vector_id for match in matches] == [1, 3, 2]
    assert matches[0].score == pytest.approx(0.0)


def test_search_returns_fewer_than_k_when_index_smaller() -> None:
    index = FaissVectorIndex(dimension=2)
    index.add(1, [1.0, 1.0])

    matches = index.search([1.0, 1.0], k=5)

    assert len(matches) == 1
    assert matches[0].vector_id == 1


def test_search_on_empty_index_returns_no_matches() -> None:
    index = FaissVectorIndex(dimension=2)

    assert index.search([1.0, 1.0], k=5) == []


def test_add_replaces_existing_vector_for_same_id() -> None:
    index = FaissVectorIndex(dimension=2)
    index.add(1, [1.0, 0.0])
    index.add(1, [0.0, 1.0])

    assert index.size == 1
    matches = index.search([0.0, 1.0], k=1)
    assert matches[0].vector_id == 1
    assert matches[0].score == pytest.approx(0.0)


def test_remove_deletes_a_vector() -> None:
    index = FaissVectorIndex(dimension=2)
    index.add(1, [1.0, 0.0])
    index.add(2, [0.0, 1.0])

    index.remove(1)

    assert index.size == 1
    matches = index.search([1.0, 0.0], k=2)
    assert [match.vector_id for match in matches] == [2]


def test_remove_on_absent_id_is_a_no_op() -> None:
    index = FaissVectorIndex(dimension=2)
    index.add(1, [1.0, 0.0])

    index.remove(999)

    assert index.size == 1


def test_add_rejects_wrong_dimension_vector() -> None:
    index = FaissVectorIndex(dimension=3)

    with pytest.raises(VectorSearchError, match="dimension"):
        index.add(1, [1.0, 0.0])


def test_search_rejects_wrong_dimension_vector() -> None:
    index = FaissVectorIndex(dimension=3)
    index.add(1, [1.0, 0.0, 0.0])

    with pytest.raises(VectorSearchError, match="dimension"):
        index.search([1.0, 0.0], k=1)


def test_search_rejects_non_positive_k() -> None:
    index = FaissVectorIndex(dimension=2)
    index.add(1, [1.0, 0.0])

    with pytest.raises(VectorSearchError, match="k must be"):
        index.search([1.0, 0.0], k=0)


def test_constructor_rejects_non_positive_dimension() -> None:
    with pytest.raises(VectorSearchError, match="dimension"):
        FaissVectorIndex(dimension=0)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    index = FaissVectorIndex(dimension=3)
    index.add(1, [1.0, 0.0, 0.0])
    index.add(2, [0.0, 1.0, 0.0])
    index_path = tmp_path / "index.faiss"

    index.save(index_path)
    loaded = FaissVectorIndex.load(index_path, dimension=3)

    assert loaded.size == 2
    matches = loaded.search([1.0, 0.0, 0.0], k=1)
    assert matches[0].vector_id == 1


def test_load_rejects_dimension_mismatch(tmp_path: Path) -> None:
    index = FaissVectorIndex(dimension=3)
    index.add(1, [1.0, 0.0, 0.0])
    index_path = tmp_path / "index.faiss"
    index.save(index_path)

    with pytest.raises(VectorSearchError, match="dimension"):
        FaissVectorIndex.load(index_path, dimension=4)
