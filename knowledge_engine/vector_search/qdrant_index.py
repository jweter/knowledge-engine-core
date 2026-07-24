"""`VectorIndex` implementation targeting an operator-run Qdrant server.

Per `docs/phase3_design.md`'s explicit scope, "server-backed Qdrant" means
this project's retrieval code can target a Qdrant instance the operator
already runs -- not that this project stands one up. Unlike
`FaissVectorIndex`, there is no local file to save/load: the collection on
the Qdrant server itself is the persistence mechanism.

Score convention: `VectorMatch.score` must mean the same thing across every
`VectorIndex` backend (squared Euclidean/L2 distance, lower = more similar,
matching `FaissVectorIndex`). Qdrant's own Euclidean-distance score is *not*
squared -- verified empirically against `qdrant-client` 1.18.0's embedded
local-mode client (a point at Euclidean distance 5 from the query returned
a raw score of `5.0`, not `25.0`), since Qdrant's own documentation does not
state this precisely. This module squares the raw score before returning it
so callers never need backend-specific knowledge.
"""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.http.models import CollectionInfo
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams

from knowledge_engine.vector_search.index import VectorMatch, VectorSearchError

QDRANT_VECTOR_INDEX_RULES_VERSION = "m33-qdrant-vector-index-v1"


class QdrantVectorIndex:
    """`VectorIndex` backed by a collection on an operator-run Qdrant server.

    The collection is created on first use (a single unnamed vector,
    Euclidean distance) if it does not already exist. If it does exist,
    its schema is validated against `dimension` -- a mismatched or
    incompatible (for example named-vector) collection fails construction
    rather than silently being reused, mirroring
    `FaissVectorIndex.load`'s dimension check.
    """

    def __init__(
        self,
        *,
        dimension: int,
        collection_name: str,
        url: str | None = None,
        api_key: str | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        if dimension <= 0:
            raise VectorSearchError("Vector dimension must be a positive integer.")
        if not collection_name or not collection_name.strip():
            raise VectorSearchError("A Qdrant collection name is required.")
        if client is None and not url:
            raise VectorSearchError("A Qdrant url is required unless a client is injected.")
        self.dimension = dimension
        self._collection_name = collection_name
        self._client = client if client is not None else QdrantClient(url=url, api_key=api_key)

        if self._client.collection_exists(collection_name):
            existing_size, existing_distance = _vector_params(
                self._client.get_collection(collection_name)
            )
            if existing_size != dimension or existing_distance != Distance.EUCLID:
                raise VectorSearchError(
                    f"Qdrant collection {collection_name!r} has dimension "
                    f"{existing_size} and distance {existing_distance.value}; expected "
                    f"dimension {dimension} and Euclidean distance."
                )
        else:
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.EUCLID),
            )

    @property
    def size(self) -> int:
        """Number of vectors currently stored."""

        return self._client.count(self._collection_name).count

    def add(self, vector_id: int, vector: Sequence[float]) -> None:
        self._validate_vector(vector)
        self._client.upsert(
            collection_name=self._collection_name,
            points=[PointStruct(id=vector_id, vector=list(vector))],
        )

    def search(self, query_vector: Sequence[float], k: int) -> list[VectorMatch]:
        self._validate_vector(query_vector)
        if k <= 0:
            raise VectorSearchError("k must be a positive integer.")
        results = self._client.query_points(
            collection_name=self._collection_name,
            query=list(query_vector),
            limit=k,
        ).points
        return [
            VectorMatch(vector_id=int(point.id), score=float(point.score) ** 2) for point in results
        ]

    def remove(self, vector_id: int) -> None:
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=[vector_id]),
        )

    def _validate_vector(self, vector: Sequence[float]) -> None:
        if len(vector) != self.dimension:
            raise VectorSearchError(
                f"Vector has dimension {len(vector)}, expected {self.dimension}."
            )


def _vector_params(collection_info: CollectionInfo) -> tuple[int, Distance]:
    vectors_config = collection_info.config.params.vectors
    if not isinstance(vectors_config, VectorParams) or vectors_config.size is None:
        raise VectorSearchError(
            "Qdrant collection uses a named-vector schema this project does not support; "
            "expected a single unnamed vector."
        )
    return int(vectors_config.size), vectors_config.distance
