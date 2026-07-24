from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.vector_search import LocalEmbeddingError, OpenAiEmbeddingError
from knowledge_engine.vector_search.generator import EmbeddingGenerator


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


class _FakeGenerator:
    def __init__(self, *, dimension: int = 3, model_id: str = "fake:test-v1") -> None:
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
        return tuple(float(len(text) + component) for component in range(self._dimension))


class _FailingGenerator:
    model_id = "fake:test-v1"
    dimension = 3

    def generate(self, text: str) -> tuple[float, ...]:
        raise LocalEmbeddingError("boom")


def test_embedding_generate_writes_a_vectors_file_for_every_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        paper1 = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Paper One"))
        paper2 = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64, title="Paper Two"))
        paper1_id, paper2_id = paper1.id, paper2.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    fake = _FakeGenerator()
    monkeypatch.setattr(
        entrypoint,
        "_build_embedding_generator",
        lambda generator, model: fake,
    )

    output_path = tmp_path / "vectors.jsonl"
    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-generate", "--output", str(output_path), "--generator", "local"],
    )

    assert result.exit_code == 0, result.output
    assert "Generated 2 embedding(s)" in _unwrapped(result.output)
    assert "fake:test-v1" in _unwrapped(result.output)

    lines = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert {record["paper_id"] for record in lines} == {paper1_id, paper2_id}
    assert all(record["embedding_model"] == "fake:test-v1" for record in lines)
    assert all(len(record["vector"]) == 3 for record in lines)
    assert any("Paper One" in text for text in fake.embedded_texts)
    assert any("An abstract." in text for text in fake.embedded_texts)


def test_embedding_generate_restricts_to_requested_paper_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        paper1 = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64))
        paper1_id = paper1.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(
        entrypoint, "_build_embedding_generator", lambda generator, model: _FakeGenerator()
    )

    output_path = tmp_path / "vectors.jsonl"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-generate",
            "--output",
            str(output_path),
            "--generator",
            "local",
            "--paper-id",
            str(paper1_id),
        ],
    )

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [record["paper_id"] for record in lines] == [paper1_id]


def test_embedding_generate_reports_when_no_papers_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(
        entrypoint, "_build_embedding_generator", lambda generator, model: _FakeGenerator()
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-generate", "--output", str(tmp_path / "vectors.jsonl"), "--generator", "local"],
    )

    assert result.exit_code == 0, result.output
    assert "No papers found" in _unwrapped(result.output)


def test_embedding_generate_exits_nonzero_when_generation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(
        entrypoint, "_build_embedding_generator", lambda generator, model: _FailingGenerator()
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-generate", "--output", str(tmp_path / "vectors.jsonl"), "--generator", "local"],
    )

    assert result.exit_code != 0
    assert "Failed to embed paper" in _unwrapped(result.output)


def test_build_embedding_generator_rejects_unknown_generator_name() -> None:
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-generate",
            "--output",
            "/tmp/does-not-matter.jsonl",
            "--generator",
            "not-a-real-generator",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown generator" in _unwrapped(result.output)


def test_build_embedding_generator_openai_requires_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KE_OPENAI_API_KEY", raising=False)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-generate",
            "--output",
            "/tmp/does-not-matter.jsonl",
            "--generator",
            "openai",
        ],
    )

    assert result.exit_code != 0
    assert "KE_OPENAI_API_KEY is not set" in _unwrapped(result.output)


def test_build_embedding_generator_returns_a_real_embedding_generator() -> None:
    generator: EmbeddingGenerator = entrypoint._build_embedding_generator("local", None)

    assert generator.model_id == "local:all-MiniLM-L6-v2"


def test_embedding_generate_reports_an_unknown_openai_model_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad --model must not crash with an unhandled exception (Codex finding, PR #156).

    `_build_embedding_generator` constructs the generator before any
    try/except in the caller; an invalid model previously propagated as
    an unhandled OpenAiEmbeddingError instead of the sanitized CLI error
    every other failure path in this command uses.
    """

    monkeypatch.setenv("KE_OPENAI_API_KEY", "sk-test")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-generate",
            "--output",
            "/tmp/does-not-matter.jsonl",
            "--generator",
            "openai",
            "--model",
            "not-a-real-model",
        ],
    )

    assert not isinstance(result.exception, LocalEmbeddingError | OpenAiEmbeddingError)
    assert result.exit_code != 0
    assert "Unknown OpenAI embedding model" in _unwrapped(result.output)


def test_embedding_generate_reports_an_empty_local_model_name_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-generate",
            "--output",
            str(tmp_path / "vectors.jsonl"),
            "--generator",
            "local",
            "--model",
            "   ",
        ],
    )

    assert not isinstance(result.exception, LocalEmbeddingError | OpenAiEmbeddingError)
    assert result.exit_code != 0
    assert "model name is required" in _unwrapped(result.output)
