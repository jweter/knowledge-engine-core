from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.entrypoint import app
from knowledge_engine.models import Paper
from knowledge_engine.paper_pages_backfill import backfill_paper, decide_backfill
from knowledge_engine.parser import (
    DocumentParseError,
    DocumentParser,
    ParsedPage,
    ParsedPaper,
    PyMuPDFParser,
)


def make_pdf(path: Path, text: str = "Results\n\nBody weight decreased by 12.4%.") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _paper(
    paper_id: int = 1, source_path: str = "/nonexistent.pdf", content_hash: str = "a" * 64
) -> Paper:
    paper = Paper(
        title="Example Paper",
        doi="10.1234/example",
        source_path=source_path,
        content_hash=content_hash,
    )
    paper.id = paper_id
    return paper


def _parsed(content_hash: str = "a" * 64) -> ParsedPaper:
    return ParsedPaper(
        source_path=Path("/tmp/example.pdf"),
        content_hash=content_hash,
        title="Example Paper",
        authors=[],
        abstract=None,
        doi="10.1234/example",
        page_count=1,
        word_count=5,
        raw_text="Body weight decreased.",
        body_text="Body weight decreased.",
        pages=[ParsedPage(page_number=1, text="Body weight decreased.")],
    )


class _FakeParser(DocumentParser):
    def __init__(self, result: ParsedPaper | Exception) -> None:
        self._result = result

    def parse(self, path: Path) -> ParsedPaper:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# --- Pure decision logic ---


def test_decide_backfill_accepts_matching_hash() -> None:
    paper = _paper(content_hash="a" * 64)
    parsed = _parsed(content_hash="a" * 64)

    outcome = decide_backfill(paper, parsed)

    assert outcome.status == "backfilled"


def test_decide_backfill_rejects_hash_mismatch() -> None:
    paper = _paper(content_hash="a" * 64)
    parsed = _parsed(content_hash="b" * 64)

    outcome = decide_backfill(paper, parsed)

    assert outcome.status == "hash_mismatch"
    assert outcome.detail is not None
    assert "does not match" in outcome.detail


def test_backfill_paper_reports_missing_source_file(tmp_path: Path) -> None:
    paper = _paper(source_path=str(tmp_path / "missing.pdf"))
    parser = _FakeParser(_parsed())

    outcome, parsed = backfill_paper(paper, parser)

    assert outcome.status == "missing_source_file"
    assert parsed is None


def test_backfill_paper_reports_parse_failure(tmp_path: Path) -> None:
    source_path = tmp_path / "paper.pdf"
    source_path.write_bytes(b"not a real pdf")
    paper = _paper(source_path=str(source_path))
    parser = _FakeParser(DocumentParseError("malformed"))

    outcome, parsed = backfill_paper(paper, parser)

    assert outcome.status == "parse_failed"
    assert parsed is None


def test_backfill_paper_reports_os_error_as_parse_failure_not_a_crash(tmp_path: Path) -> None:
    """A source file can pass the existence check and still become
    inaccessible (deleted mid-race, permission denied, I/O error) by the
    time it's actually opened -- PyMuPDF/the OS raise a plain OSError for
    this, not DocumentParseError or FileNotFoundError specifically. This
    must be reported per-paper, never allowed to escape and abort the
    batch."""

    source_path = tmp_path / "paper.pdf"
    source_path.write_bytes(b"placeholder")
    paper = _paper(source_path=str(source_path))
    parser = _FakeParser(PermissionError("permission denied"))

    outcome, parsed = backfill_paper(paper, parser)

    assert outcome.status == "parse_failed"
    assert parsed is None
    assert outcome.detail == "permission denied"


def test_backfill_paper_returns_parsed_on_success(tmp_path: Path) -> None:
    source_path = tmp_path / "paper.pdf"
    source_path.write_bytes(b"placeholder")
    paper = _paper(source_path=str(source_path), content_hash="a" * 64)
    parser = _FakeParser(_parsed(content_hash="a" * 64))

    outcome, parsed = backfill_paper(paper, parser)

    assert outcome.status == "backfilled"
    assert parsed is not None


# --- CLI end-to-end, against a real database and real PDF ---


def _build_database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def _add_pre_m15_paper(database: Database, pdf_path: Path, doi: str = "10.1234/pre-m15") -> int:
    """Persist a paper with zero pages, mirroring pre-M15 state, using the
    real content hash of the given PDF file."""

    real_parse = PyMuPDFParser().parse(pdf_path)
    parsed = ParsedPaper(
        source_path=pdf_path,
        content_hash=real_parse.content_hash,
        title=real_parse.title,
        authors=[],
        abstract=None,
        doi=doi,
        page_count=real_parse.page_count,
        word_count=real_parse.word_count,
        raw_text=real_parse.raw_text,
        body_text=real_parse.body_text,
        pages=[],
    )
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        return paper.id


def test_backfill_cli_backfills_pre_m15_style_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    paper_id = _add_pre_m15_paper(database, pdf_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill"])

    assert result.exit_code == 0, result.output
    assert "Backfilled: 1" in result.output

    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        assert paper is not None
        assert len(paper.pages) == 1
        assert "12.4%" in paper.pages[0].text


def test_backfill_cli_skips_already_paged_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    real_parse = PyMuPDFParser().parse(pdf_path)
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(real_parse)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill"])

    assert result.exit_code == 0, result.output
    assert "No papers need backfilling." in result.output


def test_backfill_cli_reports_missing_source_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    paper_id = _add_pre_m15_paper(database, pdf_path)
    pdf_path.unlink()
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill"])

    assert result.exit_code == 1
    assert "missing source file: 1" in result.output

    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        assert paper is not None
        assert paper.pages == []


def test_backfill_cli_reports_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    real_parse = PyMuPDFParser().parse(pdf_path)
    parsed = real_parse.model_copy(update={"content_hash": "0" * 64, "pages": []})
    with database.session() as session:
        added_paper = PaperRepository(session).add_parsed_paper(parsed)
        paper_id = added_paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill"])

    assert result.exit_code == 1
    assert "hash mismatch: 1" in result.output

    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        assert paper is not None
        assert paper.pages == []


def test_backfill_cli_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    paper_id = _add_pre_m15_paper(database, pdf_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Backfilled: 1" in result.output
    assert "Dry run" in result.output

    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        assert paper is not None
        assert paper.pages == []

    real_result = CliRunner().invoke(app, ["paper-pages-backfill"])
    assert real_result.exit_code == 0, real_result.output
    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        assert paper is not None
        assert len(paper.pages) == 1


def test_backfill_cli_continues_past_one_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_pdf = tmp_path / "good.pdf"
    make_pdf(good_pdf, text="Results\n\nGood paper text.")
    bad_pdf = tmp_path / "bad.pdf"
    make_pdf(bad_pdf, text="Results\n\nBad paper text.")

    database = _build_database(tmp_path)
    good_id = _add_pre_m15_paper(database, good_pdf)
    bad_id = _add_pre_m15_paper(database, bad_pdf, doi="10.1234/pre-m15-bad")
    bad_pdf.unlink()
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    result = CliRunner().invoke(app, ["paper-pages-backfill"])

    assert result.exit_code == 1
    assert "Backfilled: 1" in result.output
    assert "missing source file: 1" in result.output

    with database.session() as session:
        good_paper = PaperRepository(session).get(good_id)
        bad_paper = PaperRepository(session).get(bad_id)
        assert good_paper is not None and len(good_paper.pages) == 1
        assert bad_paper is not None and bad_paper.pages == []


def test_backfill_cli_idempotent_on_rerun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    database = _build_database(tmp_path)
    _add_pre_m15_paper(database, pdf_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    runner = CliRunner()

    first = runner.invoke(app, ["paper-pages-backfill"])
    second = runner.invoke(app, ["paper-pages-backfill"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert "No papers need backfilling." in second.output
