from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPaper
from knowledge_engine.search import SearchService


def build_database(tmp_path: Path) -> Database:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
    )
    database = Database(settings)
    database.initialize()
    return database


def parsed_paper(tmp_path: Path) -> ParsedPaper:
    return ParsedPaper(
        source_path=tmp_path / "paper.pdf",
        content_hash="a" * 64,
        title="Alzheimer Disease and Metabolic Signaling",
        authors=["Ada Lovelace", "Grace Hopper"],
        abstract="A study of alzheimer disease signals.",
        doi="10.1234/test",
        page_count=2,
        word_count=12,
        raw_text="Alzheimer disease appears in the body text with metabolic signaling.",
        body_text="Metabolic signaling and alzheimer disease are discussed.",
    )


def test_repository_stores_paper_and_stats(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        repository = PaperRepository(session)
        paper = repository.add_parsed_paper(parsed_paper(tmp_path), keywords=["neuroscience"])
        assert paper.id is not None

    with database.session() as session:
        repository = PaperRepository(session)
        stats = repository.stats()
        papers = repository.list_papers()

    assert stats["papers"] == 1
    assert stats["authors"] == 2
    assert stats["keywords"] == 1
    assert len(papers) == 1
    assert papers[0].title == "Alzheimer Disease and Metabolic Signaling"


def test_search_returns_ranked_matches(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        PaperRepository(session).add_parsed_paper(parsed_paper(tmp_path))

    with database.session() as session:
        results = SearchService(session).search('"metabolic signaling"')

    assert len(results) == 1
    assert results[0].title == "Alzheimer Disease and Metabolic Signaling"
    assert "metabolic" in results[0].snippet.lower()
