from __future__ import annotations

import pytest

from knowledge_engine.vector_search import (
    DEFAULT_LOCAL_MODEL_NAME,
    LocalEmbeddingError,
    SentenceTransformerEmbeddingGenerator,
)


class _FakeEncoder:
    def __init__(self, *, dimension: int | None = 3) -> None:
        self._dimension = dimension
        self.calls: list[str] = []

    def encode(self, text: str, convert_to_numpy: bool) -> list[float]:
        self.calls.append(text)
        return [float(len(text)), 0.5, 1.5][: self._dimension or 3]

    def get_sentence_embedding_dimension(self) -> int | None:
        return self._dimension


def test_model_id_reflects_configured_model_name() -> None:
    generator = SentenceTransformerEmbeddingGenerator(
        model_name="a-model", model_loader=lambda name: _FakeEncoder()
    )

    assert generator.model_id == "local:a-model"


def test_defaults_to_default_model_name() -> None:
    seen: list[str] = []

    def loader(name: str) -> _FakeEncoder:
        seen.append(name)
        return _FakeEncoder()

    generator = SentenceTransformerEmbeddingGenerator(model_loader=loader)

    generator.generate("some text")

    assert seen == [DEFAULT_LOCAL_MODEL_NAME]


def test_generate_returns_a_tuple_of_floats() -> None:
    generator = SentenceTransformerEmbeddingGenerator(model_loader=lambda name: _FakeEncoder())

    vector = generator.generate("hello world")

    assert vector == (11.0, 0.5, 1.5)
    assert all(isinstance(component, float) for component in vector)


def test_generate_rejects_empty_text() -> None:
    generator = SentenceTransformerEmbeddingGenerator(model_loader=lambda name: _FakeEncoder())

    with pytest.raises(LocalEmbeddingError, match="empty text"):
        generator.generate("   ")


def test_dimension_returns_the_encoder_dimension() -> None:
    generator = SentenceTransformerEmbeddingGenerator(
        model_loader=lambda name: _FakeEncoder(dimension=3)
    )

    assert generator.dimension == 3


def test_dimension_rejects_a_model_with_no_fixed_dimension() -> None:
    generator = SentenceTransformerEmbeddingGenerator(
        model_loader=lambda name: _FakeEncoder(dimension=None)
    )

    with pytest.raises(LocalEmbeddingError, match="no fixed dimension"):
        _ = generator.dimension


def test_model_is_loaded_lazily_and_only_once() -> None:
    load_count = 0

    def loader(name: str) -> _FakeEncoder:
        nonlocal load_count
        load_count += 1
        return _FakeEncoder()

    generator = SentenceTransformerEmbeddingGenerator(model_loader=loader)
    assert load_count == 0

    generator.generate("first")
    generator.generate("second")
    _ = generator.dimension

    assert load_count == 1


def test_rejects_empty_model_name() -> None:
    with pytest.raises(LocalEmbeddingError, match="model name is required"):
        SentenceTransformerEmbeddingGenerator(model_name="  ")


def test_missing_dependency_raises_local_embedding_error() -> None:
    def loader(name: str) -> _FakeEncoder:
        raise LocalEmbeddingError("sentence-transformers is not installed.")

    generator = SentenceTransformerEmbeddingGenerator(model_loader=loader)

    with pytest.raises(LocalEmbeddingError, match="not installed"):
        generator.generate("text")
