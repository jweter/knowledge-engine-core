from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.vector_search import (
    FaissVectorIndex,
    LocalEmbeddingError,
    VectorIndexMetadata,
    save_index_metadata,
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _database(tmp_path: Path, name: str) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / name,
            database_url=f"sqlite:///{tmp_path / name}.sqlite3",
        )
    )
    database.initialize()
    return database


def _parsed_paper(tmp_path: Path, content_hash: str, *, title: str = "A Trial") -> ParsedPaper:
    text = "Results\n\nBody weight decreased by 10%."
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title=title,
        authors=["Ada Scientist"],
        abstract="An abstract.",
        doi=f"10.1/{content_hash[:8]}",
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def _build_index(
    tmp_path: Path,
    *,
    vectors: dict[int, list[float]],
    embedding_model: str,
    dimension: int,
) -> Path:
    index_path = tmp_path / "index.faiss"
    index = FaissVectorIndex(dimension)
    for paper_id, vector in vectors.items():
        index.add(paper_id, vector)
    index.save(index_path)
    save_index_metadata(
        index_path, VectorIndexMetadata(embedding_model=embedding_model, dimension=dimension)
    )
    return index_path


class _FakeGenerator:
    def __init__(self, *, dimension: int = 2, model_id: str = "fake:test-v1") -> None:
        self._dimension = dimension
        self._model_id = model_id
        self.embedded_texts: list[str] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate(self, text: str) -> tuple[float, ...]:
        self.embedded_texts.append(text)
        return (1.0, 0.0)


class _FailingGenerator:
    model_id = "fake:test-v1"
    dimension = 2

    def generate(self, text: str) -> tuple[float, ...]:
        raise LocalEmbeddingError("boom")


def test_query_text_embeds_live_and_returns_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        paper = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Close Match"))
        paper_id = paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    index_path = _build_index(
        tmp_path,
        vectors={paper_id: [1.0, 0.0]},
        embedding_model="fake:test-v1",
        dimension=2,
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "vector-search",
            "--index-path",
            str(index_path),
            "--query-text",
            "does body weight decrease?",
            "--generator",
            "local",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Close Match" in unwrapped
    assert "embedding_model: fake:test-v1" in unwrapped
    assert fake.embedded_texts == ["does body weight decrease?"]


def test_query_text_requires_a_generator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["vector-search", "--index-path", str(index_path), "--query-text", "a question"],
    )

    assert result.exit_code != 0
    assert "--generator is required" in _unwrapped(result.output)


def test_rejects_both_query_vector_and_query_text(tmp_path: Path) -> None:
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    query_vector_path = tmp_path / "query.json"
    query_vector_path.write_text("[1.0, 0.0]", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "vector-search",
            "--index-path",
            str(index_path),
            "--query-vector",
            str(query_vector_path),
            "--query-text",
            "a question",
            "--generator",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "exactly one of --query-vector or --query-text" in _unwrapped(result.output)


def test_rejects_neither_query_vector_nor_query_text(tmp_path: Path) -> None:
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )

    result = CliRunner().invoke(entrypoint.app, ["vector-search", "--index-path", str(index_path)])

    assert result.exit_code != 0
    assert "exactly one of --query-vector or --query-text" in _unwrapped(result.output)


def test_rejects_generator_option_with_query_vector(tmp_path: Path) -> None:
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    query_vector_path = tmp_path / "query.json"
    query_vector_path.write_text("[1.0, 0.0]", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "vector-search",
            "--index-path",
            str(index_path),
            "--query-vector",
            str(query_vector_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "only used with --query-text" in _unwrapped(result.output)


def test_query_text_rejects_a_mismatched_embedding_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="local:all-MiniLM-L6-v2", dimension=2
    )
    fake = _FakeGenerator(model_id="openai:text-embedding-3-small")
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "vector-search",
            "--index-path",
            str(index_path),
            "--query-text",
            "a question",
            "--generator",
            "openai",
        ],
    )

    assert result.exit_code != 0
    unwrapped = _unwrapped(result.output)
    assert "local:all-MiniLM-L6-v2" in unwrapped
    assert "openai:text-embedding-3-small" in unwrapped


def test_query_text_exits_nonzero_when_embedding_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    monkeypatch.setattr(
        entrypoint, "_build_embedding_generator", lambda generator, model: _FailingGenerator()
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "vector-search",
            "--index-path",
            str(index_path),
            "--query-text",
            "a question",
            "--generator",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "Failed to embed query text" in _unwrapped(result.output)
