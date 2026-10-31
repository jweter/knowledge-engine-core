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


def _parsed_paper(
    tmp_path: Path,
    content_hash: str,
    *,
    title: str,
    text: str = "Results\n\nBody weight decreased by 10% with semaglutide.",
    abstract: str = "An abstract about semaglutide and weight loss.",
) -> ParsedPaper:
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title=title,
        authors=["Ada Scientist"],
        abstract=abstract,
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


def test_hybrid_search_ranks_a_paper_matched_both_ways_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        both = repository.add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Semaglutide Weight Loss Trial")
        )
        repository.add_parsed_paper(
            _parsed_paper(tmp_path, "b" * 64, title="Semaglutide Cardiac Outcomes")
        )
        both_id = both.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    # both_id is the closest vector match (score 0.0); lexical_only_id is
    # not in the vector index at all, so it is lexical-only.
    index_path = _build_index(
        tmp_path,
        vectors={both_id: [1.0, 0.0]},
        embedding_model="fake:test-v1",
        dimension=2,
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "semaglutide",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    both_position = unwrapped.index("Semaglutide Weight Loss Trial")
    lexical_only_position = unwrapped.index("Semaglutide Cardiac Outcomes")
    assert both_position < lexical_only_position
    assert "lexical=" in unwrapped
    assert "semantic=" in unwrapped
    assert fake.embedded_texts == ["semaglutide"]


def test_hybrid_search_reports_no_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = _database(tmp_path, "source")
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "an unrelated query with no lexical hits",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert "1. " in unwrapped or "No matches found" in unwrapped


def test_hybrid_search_rejects_a_mismatched_embedding_model(
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
            "hybrid-search",
            "a query",
            "--index-path",
            str(index_path),
            "--generator",
            "openai",
        ],
    )

    assert result.exit_code != 0
    unwrapped = _unwrapped(result.output)
    assert "local:all-MiniLM-L6-v2" in unwrapped
    assert "openai:text-embedding-3-small" in unwrapped


def test_hybrid_search_exits_nonzero_when_embedding_fails(
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
            "hybrid-search",
            "a query",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "Failed to embed query text" in _unwrapped(result.output)


def test_hybrid_search_handles_punctuation_in_the_query_without_crashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Crohn's Disease Outcomes")
        )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "What is Crohn's disease?",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Crohn's Disease Outcomes" in _unwrapped(result.output)


def test_hybrid_search_expands_the_candidate_pool_to_satisfy_a_larger_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        for index in range(5):
            repository.add_parsed_paper(
                _parsed_paper(tmp_path, f"{index}" * 64, title=f"Semaglutide Trial {index}")
            )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    index_path = _build_index(
        tmp_path, vectors={1: [1.0, 0.0]}, embedding_model="fake:test-v1", dimension=2
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "semaglutide",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
            "--limit",
            "5",
            "--candidate-limit",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    assert all(f"Semaglutide Trial {index}" in unwrapped for index in range(5))


def test_hybrid_search_rejects_an_index_with_no_metadata(tmp_path: Path) -> None:
    index_path = tmp_path / "index.faiss"
    FaissVectorIndex(2).save(index_path)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "a query",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code != 0
    assert "no recorded embedding_model" in _unwrapped(result.output)


def test_hybrid_search_dual_signal_match_outranks_a_closer_vector_only_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paper matched by BOTH signals should be able to outrank a paper
    that is the single CLOSEST vector match but has no lexical match at
    all -- proving the merge sums normalized scores rather than simply
    deferring to whichever signal's raw ranking is strongest."""

    database = _database(tmp_path, "source")
    with database.session() as session:
        repository = PaperRepository(session)
        dual = repository.add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Semaglutide Dual Match")
        )
        vector_only = repository.add_parsed_paper(
            _parsed_paper(
                tmp_path,
                "b" * 64,
                title="Unrelated Vector Only Paper",
                text="Results\n\nA finding about an unrelated topic entirely.",
                abstract="An abstract about an unrelated topic entirely.",
            )
        )
        dual_id, vector_only_id = dual.id, vector_only.id
    # The vector-only paper's indexed text never mentions "semaglutide",
    # so it cannot match the lexical query below -- it is vector-only by
    # construction, not merely by accident of FTS5 ranking.
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    index_path = _build_index(
        tmp_path,
        # vector_only_id is the closer vector match (smaller distance);
        # dual_id is farther but still present in BOTH signals.
        vectors={vector_only_id: [1.0, 0.0], dual_id: [0.5, 0.5]},
        embedding_model="fake:test-v1",
        dimension=2,
    )
    fake = _FakeGenerator()
    monkeypatch.setattr(entrypoint, "_build_embedding_generator", lambda generator, model: fake)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "hybrid-search",
            "semaglutide",
            "--index-path",
            str(index_path),
            "--generator",
            "local",
        ],
    )

    assert result.exit_code == 0, result.output
    unwrapped = _unwrapped(result.output)
    dual_position = unwrapped.index("Semaglutide Dual Match")
    vector_only_position = unwrapped.index("Unrelated Vector Only Paper")
    assert dual_position < vector_only_position
