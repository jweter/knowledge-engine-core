import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from knowledge_engine.vector_search import (
    QDRANT_VECTOR_INDEX_RULES_VERSION,
    QdrantVectorIndex,
    VectorSearchError,
)

_MODEL = "test-model-v1"


def _index(
    *,
    dimension: int = 3,
    collection_name: str = "test",
    embedding_model: str = _MODEL,
    client: QdrantClient | None = None,
) -> QdrantVectorIndex:
    return QdrantVectorIndex(
        dimension=dimension,
        collection_name=collection_name,
        embedding_model=embedding_model,
        client=client or QdrantClient(":memory:"),
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
        _index(dimension=0)


def test_constructor_rejects_empty_collection_name() -> None:
    with pytest.raises(VectorSearchError, match="collection name"):
        _index(collection_name="  ")


def test_constructor_rejects_empty_embedding_model() -> None:
    with pytest.raises(VectorSearchError, match="embedding_model"):
        _index(embedding_model="  ")


def test_constructor_requires_a_url_when_no_client_is_injected() -> None:
    with pytest.raises(VectorSearchError, match="url is required"):
        QdrantVectorIndex(dimension=3, collection_name="test", embedding_model=_MODEL)


def test_reusing_an_existing_collection_with_matching_dimension_succeeds() -> None:
    client = QdrantClient(":memory:")
    first = _index(dimension=3, collection_name="reused", client=client)
    first.add(1, [1.0, 0.0, 0.0])

    second = _index(dimension=3, collection_name="reused", client=client)

    assert second.size == 1
    matches = second.search([1.0, 0.0, 0.0], k=1)
    assert matches[0].vector_id == 1


def test_reusing_an_existing_collection_with_mismatched_dimension_fails() -> None:
    client = QdrantClient(":memory:")
    _index(dimension=3, collection_name="mismatched", client=client)

    with pytest.raises(VectorSearchError, match="dimension 3.*expected dimension 4"):
        _index(dimension=4, collection_name="mismatched", client=client)


def test_reusing_an_empty_existing_collection_with_a_different_model_succeeds() -> None:
    """Nothing to conflict with yet -- see the module docstring."""

    client = QdrantClient(":memory:")
    _index(dimension=3, collection_name="empty", embedding_model="model-a", client=client)

    reused = _index(dimension=3, collection_name="empty", embedding_model="model-b", client=client)

    reused.add(1, [1.0, 0.0, 0.0])
    assert reused.size == 1


def test_reusing_a_populated_collection_with_a_different_model_fails() -> None:
    client = QdrantClient(":memory:")
    first = _index(dimension=3, collection_name="mixed", embedding_model="model-a", client=client)
    first.add(1, [1.0, 0.0, 0.0])

    with pytest.raises(VectorSearchError, match="model-a.*model-b"):
        _index(dimension=3, collection_name="mixed", embedding_model="model-b", client=client)


def test_reusing_a_populated_collection_with_unverifiable_points_fails() -> None:
    """A point inserted outside `QdrantVectorIndex.add` carries no embedding_model payload."""

    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="foreign",
        vectors_config=VectorParams(size=3, distance=Distance.EUCLID),
    )
    client.upsert(collection_name="foreign", points=[PointStruct(id=1, vector=[1.0, 0.0, 0.0])])

    with pytest.raises(VectorSearchError, match="Refusing to mix"):
        _index(dimension=3, collection_name="foreign", client=client)
