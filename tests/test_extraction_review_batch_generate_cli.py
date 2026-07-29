from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, ExtractionRunRepository, PaperRepository
from knowledge_engine.models import ExtractionRun
from knowledge_engine.parser import ParsedPage, ParsedPaper


def _database(tmp_path: Path, name: str = "source") -> Database:
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
    tmp_path: Path, content_hash: str, *, title: str, with_results: bool = True
) -> ParsedPaper:
    text = (
        "Results\n\nBody weight decreased by 10% with semaglutide."
        if with_results
        else "This is an unstructured document with no recognizable headings at all."
    )
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title=title,
        authors=["Ada Scientist"],
        abstract="An abstract about semaglutide and weight loss.",
        doi=f"10.1/{content_hash[:8]}",
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def test_batch_generate_writes_a_combined_queue_across_multiple_papers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        repository = PaperRepository(session)
        first = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Paper A"))
        second = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64, title="Paper B"))
        first_id, second_id = first.id, second.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output = tmp_path / "batch.jsonl"
    result = CliRunner().invoke(
        entrypoint.app, ["extraction-review-batch-generate", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert "Wrote 2 draft evidence item(s) across 2 paper(s)" in " ".join(result.output.split())

    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    paper_ids = {record["source_span"]["paper_id"] for record in records}
    assert paper_ids == {first_id, second_id}


def test_batch_generate_restricts_to_requested_paper_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        repository = PaperRepository(session)
        first = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Paper A"))
        repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64, title="Paper B"))
        first_id = first.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output = tmp_path / "batch.jsonl"
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-batch-generate",
            "--output",
            str(output),
            "--paper-id",
            str(first_id),
        ],
    )

    assert result.exit_code == 0, result.output
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_span"]["paper_id"] == first_id


def test_batch_generate_skips_papers_with_no_results_section_without_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        repository = PaperRepository(session)
        repository.add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Sparse Paper", with_results=False)
        )
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output = tmp_path / "batch.jsonl"
    result = CliRunner().invoke(
        entrypoint.app, ["extraction-review-batch-generate", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = " ".join(result.output.split())
    assert "Wrote 0 draft evidence item(s) across 1 paper(s)" in unwrapped
    assert "papers with zero draft items: 1" in unwrapped


def test_batch_generate_reports_no_papers_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    output = tmp_path / "batch.jsonl"
    result = CliRunner().invoke(
        entrypoint.app, ["extraction-review-batch-generate", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert "No papers found to process" in result.output
    assert not output.exists()


def test_batch_generate_excludes_a_paper_whose_run_cannot_be_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB-recording failure for one paper must not abort the whole batch --
    the other papers' items still get written, and the failed paper is
    reported by ID rather than silently dropped."""

    database = _database(tmp_path)
    with database.session() as session:
        repository = PaperRepository(session)
        first = repository.add_parsed_paper(_parsed_paper(tmp_path, "a" * 64, title="Paper A"))
        second = repository.add_parsed_paper(_parsed_paper(tmp_path, "b" * 64, title="Paper B"))
        first_id, second_id = first.id, second.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)

    original_create = ExtractionRunRepository.create

    def _flaky_create(
        self: ExtractionRunRepository,
        *,
        paper_id: int,
        output_path: str,
        page_count: int,
        section_count: int,
        candidate_count: int,
        draft_item_count: int,
        section_detection_rules_version: str,
        claim_candidate_rules_version: str,
        claim_framing_rules_version: str,
        draft_evidence_item_rules_version: str,
        study_design_rules_version: str,
        pico_extraction_rules_version: str,
    ) -> ExtractionRun:
        if paper_id == first_id:
            raise RuntimeError("database is locked")
        return original_create(
            self,
            paper_id=paper_id,
            output_path=output_path,
            page_count=page_count,
            section_count=section_count,
            candidate_count=candidate_count,
            draft_item_count=draft_item_count,
            section_detection_rules_version=section_detection_rules_version,
            claim_candidate_rules_version=claim_candidate_rules_version,
            claim_framing_rules_version=claim_framing_rules_version,
            draft_evidence_item_rules_version=draft_evidence_item_rules_version,
            study_design_rules_version=study_design_rules_version,
            pico_extraction_rules_version=pico_extraction_rules_version,
        )

    monkeypatch.setattr(ExtractionRunRepository, "create", _flaky_create)

    output = tmp_path / "batch.jsonl"
    result = CliRunner().invoke(
        entrypoint.app, ["extraction-review-batch-generate", "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    unwrapped = " ".join(result.output.split())
    assert "could not have their extraction run recorded" in unwrapped
    assert str(first_id) in unwrapped
    assert "Wrote 1 draft evidence item(s) across 1 paper(s)" in unwrapped

    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_span"]["paper_id"] == second_id
