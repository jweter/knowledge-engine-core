"""Phase 3 vector-search services: pluggable index, not-yet-implemented generator."""

from knowledge_engine.vector_search.generator import EmbeddingGenerator
from knowledge_engine.vector_search.index import (
    VECTOR_INDEX_RULES_VERSION,
    FaissVectorIndex,
    VectorIndex,
    VectorMatch,
    VectorSearchError,
)
from knowledge_engine.vector_search.index_metadata import (
    VectorIndexMetadata,
    load_index_metadata,
    metadata_path_for,
    save_index_metadata,
)
from knowledge_engine.vector_search.ingestion import (
    EXTERNAL_VECTOR_INGESTION_RULES_VERSION,
    ExternalVectorRecord,
    VectorIngestionResult,
    load_external_vectors,
)

__all__ = [
    "EXTERNAL_VECTOR_INGESTION_RULES_VERSION",
    "VECTOR_INDEX_RULES_VERSION",
    "EmbeddingGenerator",
    "ExternalVectorRecord",
    "FaissVectorIndex",
    "VectorIndex",
    "VectorIndexMetadata",
    "VectorIngestionResult",
    "VectorMatch",
    "VectorSearchError",
    "load_external_vectors",
    "load_index_metadata",
    "metadata_path_for",
    "save_index_metadata",
]
