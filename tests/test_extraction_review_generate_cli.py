from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, ExtractionRunRepository, PaperRepository
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper


def _paper(paper_id: int = 1, doi: str | None = "10.1234/example") -> Paper:
    paper = Paper(
        title="Example Trial of a GLP-1 Agonist",
        doi=doi,
        source_path="papers/example.pdf",
        content_hash="a" * 64,
    )
    paper.id = paper_id
    return paper


def _pages_with_results_section() -> list[ParsedPage]:
    text = (
        "Methods\n\nParticipants were randomized to treatment or placebo.\n\n"
        "Results\n\nThe primary endpoint was body weight change. "
        "Body weight decreased by 12.4% relative to baseline."
    )
    return [ParsedPage(page_number=1, text=text)]


def test_extraction_review_generate_writes_draft_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "review.jsonl"
    monkeypatch.setattr(
        entrypoint, "_load_paper_pages", lambda paper_id: (_paper(), _pages_with_results_section())
    )
    recorded: dict[str, object] = {}
    monkeypatch.setattr(
        entrypoint, "_record_extraction_run", lambda **kwargs: recorded.update(kwargs)
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "1", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert recorded["paper_id"] == 1
    assert recorded["output_path"] == output
    assert recorded["page_count"] == 1
    assert recorded["section_count"] == 2
    assert recorded["candidate_count"] == 1
    assert recorded["draft_item_count"] == 1
    assert "Wrote 1 draft evidence item(s):" in result.output
    assert "review queue, not validated evidence" in result.output

    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["claim_text"] == "Body weight decreased by 12.4% relative to baseline."
    assert record["result_summary"] == record["claim_text"]
    assert record["source_doi"] == "10.1234/example"
    assert record["source_title"] == "Example Trial of a GLP-1 Agonist"
    assert record["source_type"] == "paper"
    assert record["source_span"]["paper_id"] == 1
    assert record["research_question"] is None
    assert record["evidence_direction"] is None
    assert record["provenance"] is None
    assert record["extraction_context"]["matched_signal"] == "percentage"
    assert record["extraction_context"]["section_type"] == "results"


def test_extraction_review_generate_removes_output_when_run_cannot_be_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persistence failure after a successful write must not leave an
    unrecorded review queue behind -- the output is rolled back so a plain
    retry (without --force) starts cleanly."""

    output = tmp_path / "review.jsonl"
    monkeypatch.setattr(
        entrypoint, "_load_paper_pages", lambda paper_id: (_paper(), _pages_with_results_section())
    )

    def _raise(**kwargs: object) -> None:
        raise RuntimeError("database is locked")

    monkeypatch.setattr(entrypoint, "_record_extraction_run", _raise)

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "1", "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "Extraction run could not be recorded" in result.output
    assert not output.exists()


def test_extraction_review_generate_rejects_unknown_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "review.jsonl"
    monkeypatch.setattr(entrypoint, "_load_paper_pages", lambda paper_id: None)

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "999", "--output", str(output)],
    )

    assert result.exit_code == 1
    assert "Unknown paper ID:" in result.output
    assert "999" in result.output
    assert not output.exists()


def test_extraction_review_generate_rejects_paper_without_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "review.jsonl"
    monkeypatch.setattr(entrypoint, "_load_paper_pages", lambda paper_id: (_paper(), []))

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "1", "--output", str(output)],
    )

    assert result.exit_code == 1
    assert "has no persisted pages" in result.output
    assert not output.exists()


def test_extraction_review_generate_zero_candidates_is_a_successful_empty_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "review.jsonl"
    pages = [ParsedPage(page_number=1, text="Participants attended their scheduled visits.")]
    monkeypatch.setattr(entrypoint, "_load_paper_pages", lambda paper_id: (_paper(), pages))
    monkeypatch.setattr(entrypoint, "_record_extraction_run", lambda **kwargs: None)

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "1", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote 0 draft evidence item(s):" in result.output
    assert output.read_text(encoding="utf-8") == ""


def test_extraction_review_generate_protects_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "review.jsonl"
    output.write_text("existing", encoding="utf-8")
    called = False

    def load_pages(paper_id: int) -> tuple[Paper, list[ParsedPage]]:
        nonlocal called
        called = True
        return _paper(), _pages_with_results_section()

    monkeypatch.setattr(entrypoint, "_load_paper_pages", load_pages)

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", "1", "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "Output file already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"
    assert called is False


def test_extraction_review_generate_force_overwrites_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "reviews" / "review.jsonl"
    monkeypatch.setattr(
        entrypoint, "_load_paper_pages", lambda paper_id: (_paper(), _pages_with_results_section())
    )
    monkeypatch.setattr(entrypoint, "_record_extraction_run", lambda **kwargs: None)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-generate",
            "--paper-id",
            "1",
            "--output",
            str(output),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()


def test_extraction_review_generate_end_to_end_against_real_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real Database/PaperRepository round trip, proving the PaperPage ->
    ParsedPage conversion and full pipeline wiring, not just the CLI layer."""

    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    parsed = ParsedPaper(
        source_path=tmp_path / "glp1.pdf",
        content_hash="b" * 64,
        title="GLP-1 Therapy Reduces Body Weight",
        authors=["Ada Scientist"],
        abstract="GLP-1 receptor agonists reduce body weight in adults with obesity.",
        doi="10.1234/glp1",
        page_count=1,
        word_count=30,
        raw_text=(
            "Results\n\nThe primary endpoint was body weight change. "
            "Body weight decreased by 12.4% relative to baseline."
        ),
        body_text=(
            "Results\n\nThe primary endpoint was body weight change. "
            "Body weight decreased by 12.4% relative to baseline."
        ),
        pages=[
            ParsedPage(
                page_number=1,
                text=(
                    "Results\n\nThe primary endpoint was body weight change. "
                    "Body weight decreased by 12.4% relative to baseline."
                ),
            )
        ],
    )
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        paper_id = paper.id

    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    output = tmp_path / "review.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-generate", "--paper-id", str(paper_id), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["claim_text"] == "Body weight decreased by 12.4% relative to baseline."
    assert record["source_doi"] == "10.1234/glp1"

    with database.session() as session:
        runs = ExtractionRunRepository(session).list_for_paper(paper_id)
    assert len(runs) == 1
    run = runs[0]
    assert run.paper_id == paper_id
    assert run.output_path == str(output)
    assert run.page_count == 1
    assert run.section_count == 1
    assert run.candidate_count == 1
    assert run.draft_item_count == 1
    assert run.section_detection_rules_version
    assert run.claim_candidate_rules_version
    assert run.claim_framing_rules_version
    assert run.draft_evidence_item_rules_version
