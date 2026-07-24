import pytest
from qdrant_client import QdrantClient

from knowledge_engine.vector_search import (
    QDRANT_VECTOR_INDEX_RULES_VERSION,
    QdrantVectorIndex,
    VectorSearchError,
)


def _index(*, dimension: int = 3, collection_name: str = "test") -> QdrantVectorIndex:
    return QdrantVectorIndex(
        dimension=dimension, collection_name=collection_name, client=QdrantClient(":memory:")
    )


def test_qdrant_vector_index_rules_version_is_stable() -> None:
    assert QDRANT_VECTOR_INDEX_RULES_VERSION == "m33-qdrant-vector-index-v1"


def test_add_and_search_returns_nearest_neighbor_first() -> None:
    index = _index()
    index.add(1, [1.0, 0.0, 0.0])
    index.add(2, [0.0, 1.0, 0.0])
    index.add(3, [0.9, 0.1, 0.0])

    matches = index.search([1.0, 0.0, 0.0], k=3)

    assert [match.vector_id for match in matches] == [1, 3, 2]
    assert matches[0].score == pytest.approx(0.0)


def test_search_score_is_squared_euclidean_distance() -> None:
    index = _index(dimension=2)
    index.add(1, [0.0, 0.0])
    index.add(2, [3.0, 4.0])

    matches = index.search([0.0, 0.0], k=2)

    scores = {match.vector_id: match.score for match in matches}
    assert scores[1] == pytest.approx(0.0)
    assert scores[2] == pytest.approx(25.0)


def test_search_returns_fewer_than_k_when_index_smaller() -> None:
    index = _index(dimension=2)
    index.add(1, [1.0, 1.0])

    matches = index.search([1.0, 1.0], k=5)

    assert len(matches) == 1
    assert matches[0].vector_id == 1


def test_search_on_empty_index_returns_no_matches() -> None:
    index = _index(dimension=2)

    assert index.search([1.0, 1.0], k=5) == []


def test_add_replaces_existing_vector_for_same_id() -> None:
    index = _index(dimension=2)
    index.add(1, [1.0, 0.0])
    index.add(1, [0.0, 1.0])

    assert index.size == 1
    matches = index.search([0.0, 1.0], k=1)
    assert matches[0].vector_id == 1
    assert matches[0].score == pytest.approx(0.0)


def test_remove_deletes_a_vector() -> None:
    index = _index(dimension=2)
    index.add(1, [1.0, 0.0])
    index.add(2, [0.0, 1.0])

    index.remove(1)

    assert index.size == 1
    matches = index.search([1.0, 0.0], k=2)
    assert [match.vector_id for match in matches] == [2]


def test_remove_on_absent_id_is_a_no_op() -> None:
    index = _index(dimension=2)
    index.add(1, [1.0, 0.0])

    index.remove(999)

    assert index.size == 1


def test_add_rejects_wrong_dimension_vector() -> None:
    index = _index(dimension=3)

    with pytest.raises(VectorSearchError, match="dimension"):
        index.add(1, [1.0, 0.0])


def test_search_rejects_wrong_dimension_vector() -> None:
    index = _index(dimension=3)
    index.add(1, [1.0, 0.0, 0.0])

    with pytest.raises(VectorSearchError, match="dimension"):
        index.search([1.0, 0.0], k=1)


def test_search_rejects_non_positive_k() -> None:
    index = _index(dimension=2)
    index.add(1, [1.0, 0.0])

    with pytest.raises(VectorSearchError, match="k must be"):
        index.search([1.0, 0.0], k=0)


def test_constructor_rejects_non_positive_dimension() -> None:
    with pytest.raises(VectorSearchError, match="dimension"):
        QdrantVectorIndex(dimension=0, collection_name="test", client=QdrantClient(":memory:"))


def test_constructor_rejects_empty_collection_name() -> None:
    with pytest.raises(VectorSearchError, match="collection name"):
        QdrantVectorIndex(dimension=3, collection_name="  ", client=QdrantClient(":memory:"))


def test_constructor_requires_a_url_when_no_client_is_injected() -> None:
    with pytest.raises(VectorSearchError, match="url is required"):
        QdrantVectorIndex(dimension=3, collection_name="test")


def test_reusing_an_existing_collection_with_matching_dimension_succeeds() -> None:
    client = QdrantClient(":memory:")
    first = QdrantVectorIndex(dimension=3, collection_name="reused", client=client)
    first.add(1, [1.0, 0.0, 0.0])

    second = QdrantVectorIndex(dimension=3, collection_name="reused", client=client)

    assert second.size == 1
    matches = second.search([1.0, 0.0, 0.0], k=1)
    assert matches[0].vector_id == 1


def test_reusing_an_existing_collection_with_mismatched_dimension_fails() -> None:
    client = QdrantClient(":memory:")
    QdrantVectorIndex(dimension=3, collection_name="mismatched", client=client)

    with pytest.raises(VectorSearchError, match="dimension 3.*expected dimension 4"):
        QdrantVectorIndex(dimension=4, collection_name="mismatched", client=client)
