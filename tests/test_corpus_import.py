import json
from pathlib import Path

import pytest
from sqlalchemy import text

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from knowledge_engine.models import ImportRun, Paper
from knowledge_engine.parser import DocumentParser, ParsedPaper


def make_database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def make_corpus(
    tmp_path: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    header: list[str] | None = None,
) -> Path:
    (tmp_path / "knowledge_engine").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    corpus_dir = tmp_path / "data" / "corpora" / "test_corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    papers_dir = tmp_path / "papers" / "corpora" / "test_corpus"
    papers_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "license_policy.md").write_text("# License\n", encoding="utf-8")
    corpus = {
        "manifest_version": 1,
        "corpus_id": "test_corpus",
        "name": "Test Corpus",
        "description": "A test corpus.",
        "scientific_domain": "test science",
        "research_question": {"question_id": "q_test", "text": "Does this import?"},
        "created_at": "2026-07-11",
        "updated_at": "2026-07-11",
        "license_policy": "license_policy.md",
        "source_manifest": "sources.csv",
        "default_local_papers_directory": "papers/corpora/test_corpus",
    }
    corpus_path = corpus_dir / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    write_sources(corpus_dir / "sources.csv", rows or [source_row()], header=header)
    return corpus_path


def write_sources(
    path: Path,
    rows: list[dict[str, str]],
    *,
    header: list[str] | None = None,
) -> None:
    columns = header or [
        "source_id",
        "title",
        "publication_year",
        "doi",
        "usage_status",
        "inclusion_status",
        "source_url",
        "access_date",
        "inclusion_reason",
        "license_type",
        "license_url",
        "local_path",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(row.get(name, "") for name in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def source_row(**overrides: str) -> dict[str, str]:
    row = {
        "source_id": "source-1",
        "title": "Manifest Title",
        "publication_year": "2024",
        "doi": "10.1234/source-1",
        "usage_status": "approved_open_access",
        "inclusion_status": "included",
        "source_url": "https://example.test/source-1",
        "access_date": "2026-07-11",
        "inclusion_reason": "Relevant.",
        "license_type": "CC-BY",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "local_path": "paper.pdf",
    }
    row.update(overrides)
    return row


def declare_pdf(tmp_path: Path, name: str) -> Path:
    path = tmp_path / "papers" / "corpora" / "test_corpus" / name
    path.write_text("placeholder", encoding="utf-8")
    return path


def parsed_paper(path: Path, *, title: str, doi: str, content_hash: str) -> ParsedPaper:
    return ParsedPaper(
        source_path=path,
        content_hash=content_hash,
        title=title,
        authors=["Ada Lovelace"],
        abstract="Abstract text.",
        doi=doi,
        page_count=1,
        word_count=4,
        raw_text="Raw text for indexing.",
        body_text="Body text for indexing.",
    )


def get_run(database: Database, run_id: str, tmp_path: Path) -> ImportRun:
    with database.session() as session:
        run = ImportRunService(session, project_root=tmp_path).get_run(run_id)
        assert run is not None
        return run


class StubParser(DocumentParser):
    def __init__(self, outcomes: dict[str, ParsedPaper | Exception]) -> None:
        self.outcomes = outcomes

    def parse(self, path: Path) -> ParsedPaper:
        outcome = self.outcomes[path.name]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_warning_only_import_finishes_succeeded(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(publication_year="", year="2024")],
        header=[
            "source_id",
            "title",
            "year",
            "doi",
            "usage_status",
            "inclusion_status",
            "source_url",
            "access_date",
            "inclusion_reason",
            "license_type",
            "license_url",
            "local_path",
        ],
    )
    pdf_path = declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser({
        "paper.pdf": parsed_paper(
            pdf_path,
            title="Imported",
            doi="10.1234/imported",
            content_hash="a" * 64,
        )
    })

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    assert result.run_status == "succeeded"
    assert result.imported_count == 1
    assert result.failed_count == 0
    assert run.run_status == "succeeded"
    assert run.warning_count == 1
    assert run.items[0].item_status == "imported"


def test_import_blocked_manifest_preserves_blocked_run_status(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(usage_status="needs_legal_review")],
    )

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    assert result.run_status == "import_blocked"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert run.run_status == "import_blocked"
    assert run.items[0].item_status == "import_blocked"


def test_structurally_invalid_manifest_preserves_validation_failed_status(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["corpus_id"] = "Bad ID"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    assert result.run_status == "validation_failed"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert run.run_status == "validation_failed"
    assert run.items[0].item_status == "import_blocked"


def test_parse_failure_is_sanitized_and_later_items_continue(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", doi="10.1234/source-1", local_path="bad.pdf"),
            source_row(
                source_id="source-2",
                title="Good Row",
                doi="10.1234/source-2",
                local_path="good.pdf",
                source_url="https://example.test/source-2",
            ),
        ],
    )
    declare_pdf(tmp_path, "bad.pdf")
    good_pdf = declare_pdf(tmp_path, "good.pdf")
    parser = StubParser(
        {
            "bad.pdf": ValueError("sensitive parse detail"),
            "good.pdf": parsed_paper(
                good_pdf, title="Good Import", doi="10.1234/good", content_hash="b" * 64
            ),
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    item_statuses = {item.source_id: item.item_status for item in run.items}
    ingestion_issue = next(issue for issue in run.issues if issue.category == "ingestion")
    assert result.run_status == "partially_succeeded"
    assert result.imported_count == 1
    assert result.failed_count == 1
    assert item_statuses == {"source-1": "failed", "source-2": "imported"}
    assert ingestion_issue.code == "paper_parse_failed"
    assert (
        ingestion_issue.message
        == "The declared local file could not be parsed as a supported paper."
    )
    assert "sensitive parse detail" not in ingestion_issue.message


def test_persistence_failure_rolls_back_failed_paper_completely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", doi="10.1234/source-1", local_path="fail.pdf"),
            source_row(
                source_id="source-2",
                title="Good Row",
                doi="10.1234/source-2",
                local_path="good.pdf",
                source_url="https://example.test/source-2",
            ),
        ],
    )
    fail_pdf = declare_pdf(tmp_path, "fail.pdf")
    good_pdf = declare_pdf(tmp_path, "good.pdf")
    parser = StubParser(
        {
            "fail.pdf": parsed_paper(
                fail_pdf, title="Fail Me", doi="10.1234/fail", content_hash="c" * 64
            ),
            "good.pdf": parsed_paper(
                good_pdf, title="Good Import", doi="10.1234/good", content_hash="d" * 64
            ),
        }
    )
    original_upsert = PaperRepository.upsert_search_index

    def fail_one_index(self: PaperRepository, paper: Paper) -> None:
        if paper.title == "Fail Me":
            raise RuntimeError("sensitive sqlite failure")
        original_upsert(self, paper)

    monkeypatch.setattr(PaperRepository, "upsert_search_index", fail_one_index)

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    with database.engine.connect() as connection:
        paper_count = connection.execute(text("SELECT count(*) FROM papers")).scalar()
        text_count = connection.execute(text("SELECT count(*) FROM paper_texts")).scalar()
        fts_count = connection.execute(text("SELECT count(*) FROM paper_search")).scalar()
        source_paths = list(connection.execute(text("SELECT source_path FROM papers")).scalars())

    assert result.run_status == "partially_succeeded"
    assert paper_count == 1
    assert text_count == 1
    assert fts_count == 1
    assert source_paths == [str(good_pdf.resolve())]
    assert any(issue.code == "paper_persistence_failed" for issue in run.issues)
    assert all("sensitive sqlite failure" not in issue.message for issue in run.issues)


def test_all_item_failures_finish_failed(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path, rows=[source_row(local_path="bad.pdf")])
    declare_pdf(tmp_path, "bad.pdf")
    parser = StubParser({"bad.pdf": ValueError("sensitive parse detail")})

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id, tmp_path)
    with database.engine.connect() as connection:
        paper_count = connection.execute(text("SELECT count(*) FROM papers")).scalar()
        text_count = connection.execute(text("SELECT count(*) FROM paper_texts")).scalar()
        fts_count = connection.execute(text("SELECT count(*) FROM paper_search")).scalar()

    assert result.run_status == "failed"
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert run.run_status == "failed"
    assert run.items[0].item_status == "failed"
    assert paper_count == 0
    assert text_count == 0
    assert fts_count == 0
