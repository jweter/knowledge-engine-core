from pathlib import Path
from typing import NoReturn

import pytest
from sqlalchemy.orm import Session

import knowledge_engine.import_runs.ingestion as ingestion_module
from knowledge_engine.duplicate_resolution import DuplicateResolutionError
from knowledge_engine.duplicates import DuplicateDecision
from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from knowledge_engine.models import ImportItem
from knowledge_engine.parser import DocumentParseError, ParsedPaper
from tests.corpus_fixtures import get_run, make_database
from tests.test_corpus_import import (
    StubParser,
    declare_pdf,
    make_corpus,
    parsed_paper,
    source_row,
)


def _two_item_corpus(tmp_path: Path) -> tuple[Path, Path]:
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-1", local_path="first.pdf"),
            source_row(
                source_id="source-2",
                title="Second Row",
                doi="10.1234/source-2",
                local_path="second.pdf",
                source_url="https://example.test/source-2",
            ),
        ],
    )
    declare_pdf(tmp_path, "first.pdf")
    second_pdf = declare_pdf(tmp_path, "second.pdf")
    return corpus_path, second_pdf


def test_expected_parser_failure_is_sanitized_and_continues(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path, second_pdf = _two_item_corpus(tmp_path)
    parser = StubParser(
        {
            "first.pdf": DocumentParseError("raw parser secret"),
            "second.pdf": parsed_paper(
                second_pdf,
                title="Imported second paper",
                doi="10.1234/imported-second",
                content_hash="1" * 64,
            ),
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    issue = next(issue for issue in run.issues if issue.code == "paper_parse_failed")
    assert result.run_status == "partially_succeeded"
    assert result.imported_count == 1
    assert result.failed_count == 1
    assert issue.message == "The declared local file could not be parsed as a supported paper."
    assert "raw parser secret" not in issue.message


def test_unexpected_parser_exception_propagates_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser({"paper.pdf": TypeError("raw parser defect")})

    with pytest.raises(TypeError, match="raw parser defect"):
        with database.session() as session:
            CorpusIngestionService(session, project_root=tmp_path, parser=parser).import_corpus(
                corpus_path
            )

    captured = capsys.readouterr()
    assert "raw parser defect" not in captured.out
    assert "raw parser defect" not in captured.err


def test_expected_duplicate_resolution_failure_is_sanitized_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = make_database(tmp_path)
    corpus_path, second_pdf = _two_item_corpus(tmp_path)
    first_pdf = tmp_path / "papers" / "corpora" / "test_corpus" / "first.pdf"
    parser = StubParser(
        {
            "first.pdf": parsed_paper(
                first_pdf,
                title="First paper",
                doi="10.1234/first",
                content_hash="2" * 64,
            ),
            "second.pdf": parsed_paper(
                second_pdf,
                title="Second paper",
                doi="10.1234/second",
                content_hash="3" * 64,
            ),
        }
    )
    original = ingestion_module.resolve_duplicate_before_persistence
    calls = 0

    def fail_first(session: Session, *, item: ImportItem, parsed: ParsedPaper) -> DuplicateDecision:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise DuplicateResolutionError("raw duplicate secret")
        return original(session, item=item, parsed=parsed)

    monkeypatch.setattr(ingestion_module, "resolve_duplicate_before_persistence", fail_first)

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    issue = next(issue for issue in run.issues if issue.code == "duplicate_resolution_failed")
    assert result.run_status == "partially_succeeded"
    assert result.imported_count == 1
    assert result.failed_count == 1
    assert issue.message == "Duplicate identity evidence could not be resolved safely."
    assert "raw duplicate secret" not in issue.message


def test_unexpected_duplicate_resolution_exception_propagates_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(tmp_path)
    pdf_path = declare_pdf(tmp_path, "paper.pdf")
    parser = StubParser(
        {
            "paper.pdf": parsed_paper(
                pdf_path,
                title="Paper",
                doi="10.1234/paper",
                content_hash="4" * 64,
            )
        }
    )

    def fail_systemically(_session: Session, *, item: ImportItem, parsed: ParsedPaper) -> NoReturn:
        del item, parsed
        raise TypeError("raw duplicate defect")

    monkeypatch.setattr(ingestion_module, "resolve_duplicate_before_persistence", fail_systemically)

    with pytest.raises(TypeError, match="raw duplicate defect"):
        with database.session() as session:
            CorpusIngestionService(session, project_root=tmp_path, parser=parser).import_corpus(
                corpus_path
            )

    captured = capsys.readouterr()
    assert "raw duplicate defect" not in captured.out
    assert "raw duplicate defect" not in captured.err
