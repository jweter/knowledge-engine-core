from __future__ import annotations

import json
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper


def _database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def _add_paper(database: Database, *, pdf_name: str, page_text: str) -> None:
    parsed = ParsedPaper(
        source_path=Path(f"papers/corpora/test_corpus/{pdf_name}"),
        content_hash=pdf_name * 8,
        title="Example Paper",
        authors=["Author One"],
        abstract="An abstract.",
        doi="10.1234/example",
        page_count=1,
        word_count=len(page_text.split()),
        raw_text=page_text,
        body_text=page_text,
        pages=[ParsedPage(page_number=1, text=page_text)],
    )
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(parsed)


def _evidence_record(
    evidence_record_id: str, *, result_summary: str, source_span: dict[str, object]
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "evidence_record_id": evidence_record_id,
        "extraction_method": "manual_source_audit",
        "extraction_status": "draft_manual_prototype",
        "source_doi": "10.1234/example",
        "source_title": "Example Paper",
        "source_type": "paper",
        "study_type": "randomized_controlled_trial",
        "research_question": "Does the intervention affect the outcome?",
        "claim_text": "The intervention improved the outcome.",
        "evidence_direction": "supports",
        "population": "Adults.",
        "intervention": "Intervention.",
        "comparator": "Placebo.",
        "outcome": "Outcome.",
        "result_summary": result_summary,
        "source_span": source_span,
        "limitations": ["One bounded result."],
        "uncertainty_notes": None,
        "confidence_note": None,
        "provenance": {"created_by": "manual review", "method": "read the source PDF"},
        "created_for_milestone": "test",
        "review_status": "reviewed",
        "review_checklist": {"human_reviewed": True},
        "review_notes": "Read the source PDF directly.",
    }


def _map_payload(*record_ids: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "map_id": "test-grounding-map-v1",
        "title": "Test Grounding Map",
        "research_question": "Does the intervention affect the outcome?",
        "map_status": "provisional",
        "scope": {
            "population": "Adults.",
            "intervention": "Intervention.",
            "outcome": "Outcome.",
            "exclusions": "Other populations.",
        },
        "evidence_nodes": [
            {"evidence_record_id": record_id, "role": "landmark_trial", "inclusion_rationale": "x"}
            for record_id in record_ids
        ],
        "relationship_ids": [],
        "population_groups": [],
        "comparator_groups": [],
        "contradiction_assessment": {
            "status": "none_identified_in_bounded_map",
            "statement": "None found.",
            "evidence_record_ids": [],
        },
        "limitations": ["Test map."],
        "known_gaps": [],
        "review": {
            "method": "test",
            "status": "secondary_review_required",
            "reviewed_by": "test",
            "reviewer_type": "test",
            "review_date": "2026-08-10",
            "notes": "test",
        },
    }


def _write_jsonl(path: Path, *records: dict[str, object]) -> Path:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def test_grounding_verify_passes_when_every_number_is_in_the_source_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)
    _add_paper(
        database,
        pdf_name="PMC1.pdf",
        page_text="Response was 28.2% versus 14.3% (odds ratio 2.36, 95% CI 1.0-5.6, p=0.05).",
    )
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-1",
            result_summary="Response was higher with treatment (28.2% vs 14.3%; OR 2.36, "
            "95% CI [1.0, 5.6]).",
            source_span={"local_pdf_path": "papers/corpora/test_corpus/PMC1.pdf", "page_number": 1},
        ),
    )
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(_map_payload("ev-1")), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-grounding-verify",
            str(map_path),
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "1/1 records fully grounded" in result.output
    assert "ev-1" in result.output
    assert "grounded" in result.output


def test_grounding_verify_reports_missing_numbers_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)
    _add_paper(
        database,
        pdf_name="PMC2.pdf",
        page_text="The primary analysis found HR 0.65 (95% CI 0.61-0.71) favoring treatment.",
    )
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-2",
            result_summary="OS improved with HR 0.65 (95% CI 0.61-0.71); a secondary "
            "analysis found HR 1.26.",
            source_span={"local_pdf_path": "papers/corpora/test_corpus/PMC2.pdf", "page_number": 1},
        ),
    )
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(_map_payload("ev-2")), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-grounding-verify",
            str(map_path),
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 1
    assert "0/1 records fully grounded" in result.output
    assert "1.26" in result.output
    assert "not found in source page" in result.output


def test_grounding_verify_reports_unresolved_source_page_distinctly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-3",
            result_summary="HR 0.65 (95% CI 0.61-0.71).",
            source_span={
                "local_pdf_path": "papers/corpora/test_corpus/PMC-does-not-exist.pdf",
                "page_number": 1,
            },
        ),
    )
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(_map_payload("ev-3")), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-grounding-verify",
            str(map_path),
            "--evidence",
            str(evidence_path),
        ],
    )

    assert result.exit_code == 1
    assert "source page not resolved" in result.output


def test_grounding_verify_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)
    _add_paper(database, pdf_name="PMC4.pdf", page_text="Response was 50% in the treatment arm.")
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-4",
            result_summary="Response was 50%.",
            source_span={"local_pdf_path": "papers/corpora/test_corpus/PMC4.pdf", "page_number": 1},
        ),
    )
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(_map_payload("ev-4")), encoding="utf-8")
    output_path = tmp_path / "grounding.md"

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-grounding-verify",
            str(map_path),
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote grounding verification report" in result.output
    report = output_path.read_text(encoding="utf-8")
    assert "1/1 records fully grounded" in report
    assert "ev-4" in report


def test_grounding_verify_refuses_an_existing_output_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)
    evidence_path = _write_jsonl(
        tmp_path / "evidence.jsonl",
        _evidence_record(
            "ev-5",
            result_summary="Response was 50%.",
            source_span={"local_pdf_path": "papers/corpora/test_corpus/PMC5.pdf", "page_number": 1},
        ),
    )
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(_map_payload("ev-5")), encoding="utf-8")
    output_path = tmp_path / "grounding.md"
    output_path.write_text("keep", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-grounding-verify",
            str(map_path),
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 2
    assert "Use --force to overwrite" in unstyle(result.output)
    assert output_path.read_text(encoding="utf-8") == "keep"
