"""The embedding-generation interface, implemented by two pluggable backends.

`docs/phase3_design.md`'s Open Questions section escalated the actual
embedding-generation approach (a local model, an external API, or neither
yet) to the project owner -- the same class of new-dependency,
offline-posture decision Phase 2's extraction methodology was escalated for
before any extraction code existed. The project owner chose "both": this
module defines the interface, and `knowledge_engine.vector_search.
local_generator.SentenceTransformerEmbeddingGenerator` /
`knowledge_engine.vector_search.openai_generator.OpenAiEmbeddingGenerator`
implement it. `VectorIndex` and the ingestion/search commands built against
externally-supplied vectors never needed to change -- either implementation
plugs in here without touching the rest of the vector-search stack.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingGenerator(Protocol):
    """Turns text into a fixed-dimension embedding vector."""

    @property
    def model_id(self) -> str:
        """A stable identifier for exactly which model/version produced a vector.

        Recorded as `Paper.embedding_model`, mirroring how
        `ADJUDICATION_RULES_VERSION`/`*_RULES_VERSION` constants elsewhere in
        this project version deterministic rule output -- a reviewer must
        always be able to tell which model produced a given embedding.
        """

    @property
    def dimension(self) -> int:
        """The fixed vector length every call to `generate` returns."""

    def generate(self, text: str) -> tuple[float, ...]:
        """Return a `dimension`-length embedding vector for `text`."""
