"""Phase 3 vector-search services: pluggable index and embedding generators."""

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
from knowledge_engine.vector_search.local_generator import (
    DEFAULT_MODEL_NAME as DEFAULT_LOCAL_MODEL_NAME,
)
from knowledge_engine.vector_search.local_generator import (
    LocalEmbeddingError,
    SentenceTransformerEmbeddingGenerator,
)
from knowledge_engine.vector_search.openai_generator import (
    OpenAiEmbeddingError,
    OpenAiEmbeddingGenerator,
)
from knowledge_engine.vector_search.qdrant_index import (
    QDRANT_VECTOR_INDEX_RULES_VERSION,
    QdrantVectorIndex,
)

__all__ = [
    "DEFAULT_LOCAL_MODEL_NAME",
    "EXTERNAL_VECTOR_INGESTION_RULES_VERSION",
    "QDRANT_VECTOR_INDEX_RULES_VERSION",
    "VECTOR_INDEX_RULES_VERSION",
    "EmbeddingGenerator",
    "ExternalVectorRecord",
    "FaissVectorIndex",
    "LocalEmbeddingError",
    "OpenAiEmbeddingError",
    "OpenAiEmbeddingGenerator",
    "QdrantVectorIndex",
    "SentenceTransformerEmbeddingGenerator",
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
