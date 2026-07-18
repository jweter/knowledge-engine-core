import json
from pathlib import Path

import pytest
from sqlalchemy import text

import knowledge_engine.import_runs.ingestion as ingestion_module
from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from knowledge_engine.models import Paper
from knowledge_engine.paper_persistence import ClassifiedPaperRepository
from knowledge_engine.parser import DocumentParseError, DocumentParser, ParsedPaper
from knowledge_engine.persistence_errors import SearchIndexWriteError
from tests.corpus_fixtures import (
    get_run,
    make_database,
    prepare_corpus_layout,
    write_corpus_manifest,
    write_sources,
)


def make_corpus(
    tmp_path: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    header: list[str] | None = None,
) -> Path:
    corpus_dir, _ = prepare_corpus_layout(tmp_path)
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
    write_corpus_manifest(corpus_path, corpus)
    write_sources(corpus_dir / "sources.csv", rows or [source_row()], header=header)
    return corpus_path


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
    parser = StubParser(
        {
            "paper.pdf": parsed_paper(
                pdf_path,
                title="Imported",
                doi="10.1234/imported",
                content_hash="a" * 64,
            )
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
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

    run = get_run(database, result.import_run_id)
    assert result.run_status == "import_blocked"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert run.run_status == "import_blocked"
    assert run.items[0].item_status == "import_blocked"


def test_import_blocked_manifest_marks_other_valid_items_skipped(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", usage_status="needs_legal_review"),
            source_row(
                source_id="source-2",
                title="Would Have Imported",
                doi="10.1234/source-2",
                local_path="good.pdf",
                source_url="https://example.test/source-2",
            ),
        ],
    )
    declare_pdf(tmp_path, "good.pdf")

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    item_statuses = {item.source_id: item.item_status for item in run.items}

    assert result.run_status == "import_blocked"
    assert result.skipped_count == 2
    assert item_statuses == {"source-1": "import_blocked", "source-2": "skipped"}


def test_structurally_invalid_manifest_preserves_validation_failed_status(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["corpus_id"] = "Bad ID"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    assert result.run_status == "validation_failed"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert run.run_status == "validation_failed"
    assert run.items[0].item_status == "import_blocked"


def test_run_level_ingestion_failure_marks_valid_items_skipped(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1"),
            source_row(
                source_id="source-2",
                title="Second Importable Row",
                doi="10.1234/source-2",
                local_path="second.pdf",
                source_url="https://example.test/source-2",
            ),
        ],
    )
    declare_pdf(tmp_path, "paper.pdf")
    declare_pdf(tmp_path, "second.pdf")

    original_papers_directory = ingestion_module._papers_directory

    def fail_once(*args: object, **kwargs: object) -> Path:
        raise ingestion_module._PapersDirectoryError("sensitive filesystem detail")

    ingestion_module._papers_directory = fail_once
    try:
        with database.session() as session:
            result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(
                corpus_path
            )
    finally:
        ingestion_module._papers_directory = original_papers_directory

    run = get_run(database, result.import_run_id)

    assert result.run_status == "failed"
    assert result.skipped_count == 2
    assert [item.item_status for item in run.items] == ["skipped", "skipped"]


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
            "bad.pdf": DocumentParseError("sensitive parse detail"),
            "good.pdf": parsed_paper(
                good_pdf, title="Good Import", doi="10.1234/good", content_hash="b" * 64
            ),
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
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


def test_papers_directory_failure_preserves_failed_run_with_sanitized_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    declare_pdf(tmp_path, "paper.pdf")

    def fail_papers_directory(*_args: object, **_kwargs: object) -> Path:
        raise ingestion_module._PapersDirectoryError("sensitive filesystem detail")

    monkeypatch.setattr(ingestion_module, "_papers_directory", fail_papers_directory)

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    issue = next(issue for issue in run.issues if issue.category == "ingestion")

    assert result.run_status == "failed"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert run.run_status == "failed"
    assert run.import_blocker_count == 1
    assert issue.import_item_id is None
    assert issue.code == "persisted_papers_directory_invalid"
    assert issue.field == "default_local_papers_directory"
    assert issue.message == "The persisted local papers directory could not be resolved safely."
    assert "sensitive filesystem detail" not in issue.message


def test_missing_local_file_during_import_is_sanitized(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser({"paper.pdf": FileNotFoundError("sensitive missing detail")})

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    issue = next(issue for issue in run.issues if issue.category == "ingestion")

    assert result.run_status == "failed"
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert issue.code == "local_file_missing_during_import"
    assert issue.message == "The declared local file was missing when import started."
    assert "sensitive missing detail" not in issue.message


def test_unreadable_local_file_during_import_is_sanitized(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser({"paper.pdf": OSError("sensitive unreadable detail")})

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    issue = next(issue for issue in run.issues if issue.category == "ingestion")

    assert result.run_status == "failed"
    assert result.imported_count == 0
    assert result.failed_count == 1
    assert issue.code == "local_file_unreadable"
    assert issue.message == "The declared local file could not be read during import."
    assert "sensitive unreadable detail" not in issue.message


def test_all_skipped_items_finish_run_succeeded(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", inclusion_status="excluded", local_path="skip-1.pdf"),
            source_row(source_id="source-2", inclusion_status="excluded", local_path="skip-2.pdf"),
        ],
    )
    declare_pdf(tmp_path, "skip-1.pdf")
    declare_pdf(tmp_path, "skip-2.pdf")

    with database.session() as session:
        result = CorpusIngestionService(session, project_root=tmp_path).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)

    assert result.run_status == "succeeded"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 2
    assert run.run_status == "succeeded"
    assert [item.item_status for item in run.items] == ["skipped", "skipped"]


def test_ingestion_updates_run_import_blocker_count(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", local_path="missing.pdf"),
            source_row(source_id="source-2", local_path="unreadable.pdf"),
        ],
    )
    declare_pdf(tmp_path, "missing.pdf")
    declare_pdf(tmp_path, "unreadable.pdf")
    parser = StubParser(
        {
            "missing.pdf": FileNotFoundError("missing during import"),
            "unreadable.pdf": OSError("unreadable during import"),
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)

    assert result.run_status == "failed"
    assert result.failed_count == 2
    assert run.import_blocker_count == 2
    assert run.import_blocker_count == sum(1 for issue in run.issues if issue.blocks_import)
    assert [item.import_blocker_count for item in run.items] == [1, 1]


def test_expected_search_index_failure_rolls_back_item_and_continues(
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
    original_upsert = ClassifiedPaperRepository.upsert_search_index

    def fail_one_index(self: ClassifiedPaperRepository, paper: Paper) -> None:
        if paper.title == "Fail Me":
            raise SearchIndexWriteError("sensitive sqlite failure")
        original_upsert(self, paper)

    monkeypatch.setattr(ClassifiedPaperRepository, "upsert_search_index", fail_one_index)

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    with database.engine.connect() as connection:
        paper_count = connection.execute(text("SELECT count(*) FROM papers")).scalar()
        text_count = connection.execute(text("SELECT count(*) FROM paper_texts")).scalar()
        fts_count = connection.execute(text("SELECT count(*) FROM paper_search")).scalar()
        source_paths = list(connection.execute(text("SELECT source_path FROM papers")).scalars())

    assert result.run_status == "partially_succeeded"
    assert result.failed_count == 1
    assert paper_count == 1
    assert text_count == 1
    assert fts_count == 1
    assert source_paths == [str(good_pdf.resolve())]
    issue = next(issue for issue in run.issues if issue.code == "paper_search_index_write_failed")
    assert issue.message == "The parsed paper could not be added to the search index."
    assert "sensitive sqlite failure" not in issue.message


def test_unexpected_repository_defect_propagates_and_rolls_back_outer_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    pdf_path = declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser(
        {
            "paper.pdf": parsed_paper(
                pdf_path,
                title="Unexpected Failure",
                doi="10.1234/unexpected",
                content_hash="e" * 64,
            )
        }
    )

    def fail_unexpectedly(self: ClassifiedPaperRepository, paper: Paper) -> None:
        del self, paper
        raise TypeError("sensitive programming defect")

    monkeypatch.setattr(ClassifiedPaperRepository, "upsert_search_index", fail_unexpectedly)

    with pytest.raises(TypeError, match="sensitive programming defect"):
        with database.session() as session:
            CorpusIngestionService(session, project_root=tmp_path, parser=parser).import_corpus(
                corpus_path
            )

    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM papers")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM paper_texts")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM paper_search")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM import_runs")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM import_issues")).scalar() == 0


def test_all_item_failures_finish_failed(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path, rows=[source_row(local_path="bad.pdf")])
    declare_pdf(tmp_path, "bad.pdf")
    parser = StubParser({"bad.pdf": DocumentParseError("sensitive parse detail")})

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
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
