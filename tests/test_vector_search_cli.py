from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper


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


def _write_vectors(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_embedding_index_build_indexes_and_persists_embedding_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        paper1 = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        paper2 = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64))
        paper1_id, paper2_id = paper1.id, paper2.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(
        vectors_path,
        [
            {"paper_id": paper1_id, "vector": [1.0, 0.0], "embedding_model": "external:test-v1"},
            {"paper_id": paper2_id, "vector": [0.0, 1.0], "embedding_model": "external:test-v1"},
        ],
    )
    index_path = tmp_path / "index.faiss"

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "Indexed 2 vector(s)" in unwrapped
    assert "dimension 2, index size 2" in unwrapped
    assert index_path.exists()

    with database.session() as session:
        repository = PaperRepository(session)
        stored1 = repository.get(paper1_id)
        stored2 = repository.get(paper2_id)
        assert stored1 is not None
        assert stored1.embedding_model == "external:test-v1"
        assert stored1.embedding_id == str(paper1_id)
        assert stored2 is not None
        assert stored2.embedding_id == str(paper2_id)


def test_embedding_index_build_rejects_unknown_paper_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(vectors_path, [{"paper_id": 999, "vector": [1.0], "embedding_model": "test"}])
    index_path = tmp_path / "index.faiss"

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    assert result.exit_code != 0
    assert "unknown paper ID(s): 999" in _unwrapped(result.output)
    assert not index_path.exists()


def test_embedding_index_build_rejects_invalid_vectors_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    vectors_path.write_text("not json\n", encoding="utf-8")
    index_path = tmp_path / "index.faiss"

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    assert result.exit_code != 0
    assert "Vectors file is invalid" in _unwrapped(result.output)


def test_embedding_index_build_is_incremental_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second run against a different paper must add to, not replace, the index."""

    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        paper1 = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        paper2 = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64))
        paper1_id, paper2_id = paper1.id, paper2.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = tmp_path / "index.faiss"

    first_vectors = tmp_path / "first.jsonl"
    _write_vectors(
        first_vectors, [{"paper_id": paper1_id, "vector": [1.0, 0.0], "embedding_model": "test"}]
    )
    CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(first_vectors), "--index-path", str(index_path)],
    )

    second_vectors = tmp_path / "second.jsonl"
    _write_vectors(
        second_vectors, [{"paper_id": paper2_id, "vector": [0.0, 1.0], "embedding_model": "test"}]
    )
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "embedding-index-build",
            "--vectors",
            str(second_vectors),
            "--index-path",
            str(index_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "index size 2" in _unwrapped(result.output)


def test_vector_search_returns_ranked_results_with_paper_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        near = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Near Paper"))
        far = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64, title="Far Paper"))
        near_id, far_id = near.id, far.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(
        vectors_path,
        [
            {"paper_id": near_id, "vector": [1.0, 0.0], "embedding_model": "test"},
            {"paper_id": far_id, "vector": [0.0, 1.0], "embedding_model": "test"},
        ],
    )
    index_path = tmp_path / "index.faiss"
    CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    query_path = tmp_path / "query.json"
    query_path.write_text(json.dumps({"vector": [1.0, 0.0]}), encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["vector-search", "--index-path", str(index_path), "--query-vector", str(query_path)],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "1. Near Paper" in unwrapped
    assert f"Paper ID: {near_id}" in unwrapped
    assert "2. Far Paper" in unwrapped
    assert "vector similarity only, not lexical search" in unwrapped


def test_vector_search_accepts_bare_array_query_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        paper_id = paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(
        vectors_path, [{"paper_id": paper_id, "vector": [1.0, 0.0], "embedding_model": "test"}]
    )
    index_path = tmp_path / "index.faiss"
    CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    query_path = tmp_path / "query.json"
    query_path.write_text(json.dumps([1.0, 0.0]), encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["vector-search", "--index-path", str(index_path), "--query-vector", str(query_path)],
    )

    assert result.exit_code == 0, result.output
    assert f"Paper ID: {paper_id}" in _unwrapped(result.output)


def test_vector_search_rejects_invalid_query_vector_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        paper_id = paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(
        vectors_path, [{"paper_id": paper_id, "vector": [1.0], "embedding_model": "test"}]
    )
    index_path = tmp_path / "index.faiss"
    CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    query_path = tmp_path / "query.json"
    query_path.write_text("not json", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["vector-search", "--index-path", str(index_path), "--query-vector", str(query_path)],
    )

    assert result.exit_code != 0
    assert "not valid JSON" in _unwrapped(result.output)


def test_vector_search_rejects_dimension_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(_parsed_paper(tmp_path, "a" * 64))
        paper_id = paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    vectors_path = tmp_path / "vectors.jsonl"
    _write_vectors(
        vectors_path, [{"paper_id": paper_id, "vector": [1.0, 0.0], "embedding_model": "test"}]
    )
    index_path = tmp_path / "index.faiss"
    CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors_path), "--index-path", str(index_path)],
    )

    query_path = tmp_path / "query.json"
    query_path.write_text(json.dumps([1.0, 0.0, 0.0]), encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["vector-search", "--index-path", str(index_path), "--query-vector", str(query_path)],
    )

    assert result.exit_code != 0
    assert "dimension" in _unwrapped(result.output)
