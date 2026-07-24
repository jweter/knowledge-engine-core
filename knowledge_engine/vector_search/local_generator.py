"""Local `EmbeddingGenerator` backed by a `sentence-transformers` model.

Runs fully offline once the model weights are cached on disk, matching this
project's "runs fully offline" property (`docs/architecture.md`) -- the
first call to `generate` downloads and caches the named model from the
Hugging Face Hub if it is not already present locally, the same one-time
cost any local ML model incurs for its weights. This is option 1 from
`docs/phase3_design.md`'s embedding-generation decision: no per-query cost
or third-party data transfer, at the cost of a real new dependency
(`sentence-transformers`, and transitively a CPU-only PyTorch build).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, cast

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class LocalEmbeddingError(RuntimeError):
    """Raised when the local embedding model cannot be loaded or run."""


class SentenceEncoder(Protocol):
    """The subset of `sentence_transformers.SentenceTransformer` this module uses.

    Naming the contract lets tests inject a fake encoder instead of
    downloading and running a real model, matching the dependency-injected
    transport pattern used for every network client in this project
    (`ncbi_http.UrllibNcbiTransport`, `google_drive_http.GoogleDriveHttpTransport`).
    """

    def encode(self, text: str, convert_to_numpy: bool) -> Sequence[float]: ...

    def get_sentence_embedding_dimension(self) -> int | None: ...


ModelLoader = Callable[[str], SentenceEncoder]


def _load_sentence_transformer(model_name: str) -> SentenceEncoder:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise LocalEmbeddingError("sentence-transformers is not installed.") from error
    try:
        return cast(SentenceEncoder, SentenceTransformer(model_name))
    except Exception as error:
        raise LocalEmbeddingError(
            f"Failed to load local embedding model {model_name!r}."
        ) from error


class SentenceTransformerEmbeddingGenerator:
    """`EmbeddingGenerator` backed by a local `sentence-transformers` model."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
        model_loader: ModelLoader | None = None,
    ) -> None:
        if not model_name or not model_name.strip():
            raise LocalEmbeddingError("A model name is required.")
        self._model_name = model_name
        self._model_loader = model_loader or _load_sentence_transformer
        self._model: SentenceEncoder | None = None

    @property
    def model_id(self) -> str:
        return f"local:{self._model_name}"

    @property
    def dimension(self) -> int:
        dimension = self._loaded_model().get_sentence_embedding_dimension()
        if dimension is None:
            raise LocalEmbeddingError(
                f"Local embedding model {self._model_name!r} has no fixed dimension."
            )
        return int(dimension)

    def generate(self, text: str) -> tuple[float, ...]:
        if not text or not text.strip():
            raise LocalEmbeddingError("Cannot generate an embedding for empty text.")
        vector = self._loaded_model().encode(text, convert_to_numpy=True)
        return tuple(float(component) for component in vector)

    def _loaded_model(self) -> SentenceEncoder:
        if self._model is None:
            self._model = self._model_loader(self._model_name)
        return self._model
