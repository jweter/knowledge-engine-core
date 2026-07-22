from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.search import SearchService, build_natural_language_fts_query


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


def test_repository_persists_no_pages_when_parser_supplied_none(tmp_path: Path) -> None:
    """Existing callers that never set ParsedPaper.pages must not break."""

    database = build_database(tmp_path)

    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed_paper(tmp_path))
        paper_id = paper.id

    with database.session() as session:
        stored = PaperRepository(session).get(paper_id)
        assert stored is not None
        assert stored.pages == []


def test_repository_persists_page_boundaries(tmp_path: Path) -> None:
    parsed = parsed_paper(tmp_path)
    parsed = parsed.model_copy(
        update={
            "pages": [
                ParsedPage(page_number=1, text="Alzheimer disease appears in the body text."),
                ParsedPage(page_number=2, text="with metabolic signaling."),
            ]
        }
    )
    database = build_database(tmp_path)

    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        paper_id = paper.id

    with database.session() as session:
        stored = PaperRepository(session).get(paper_id)
        assert stored is not None
        assert [(page.page_number, page.text) for page in stored.pages] == [
            (1, "Alzheimer disease appears in the body text."),
            (2, "with metabolic signaling."),
        ]


def test_search_returns_ranked_matches(tmp_path: Path) -> None:
    database = build_database(tmp_path)

    with database.session() as session:
        PaperRepository(session).add_parsed_paper(parsed_paper(tmp_path))

    with database.session() as session:
        results = SearchService(session).search('"metabolic signaling"')

    assert len(results) == 1
    assert results[0].title == "Alzheimer Disease and Metabolic Signaling"
    assert "metabolic" in results[0].snippet.lower()


def test_answer_retrieval_accepts_natural_language_questions(tmp_path: Path) -> None:
    database = build_database(tmp_path)
    parsed = ParsedPaper(
        source_path=tmp_path / "glp1.pdf",
        content_hash="b" * 64,
        title="GLP-1 Receptor Agonists and Body Weight",
        authors=["Jane Researcher"],
        abstract="GLP-1 receptor agonists reduce body weight in adults with obesity.",
        doi="10.1234/glp1",
        page_count=4,
        word_count=24,
        raw_text="Participants receiving GLP-1 receptor agonists had reduced body weight.",
        body_text="GLP-1 receptor agonists reduce body weight compared with placebo.",
    )

    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        paper.publication_year = 2024

    with database.session() as session:
        results = SearchService(session).answer_retrieval(
            "Do GLP-1 receptor agonists reduce body weight?"
        )

    assert len(results) == 1
    assert results[0].title == "GLP-1 Receptor Agonists and Body Weight"
    assert results[0].publication_year == 2024
    assert results[0].doi == "10.1234/glp1"
    assert "body" in results[0].matched_query


def test_natural_language_query_removes_punctuation_and_stopwords() -> None:
    query = build_natural_language_fts_query("Do GLP-1 receptor agonists reduce body weight?")

    assert query == "glp OR receptor OR agonists OR reduce OR body OR weight"
