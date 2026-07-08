import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPaper


def build_cli_database(tmp_path: Path, *, doi: str = "10.1234/answer") -> Database:
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
        content_hash=f"{abs(hash(doi)):064d}"[-64:],
        title="GLP-1 Therapy Reduces Body Weight",
        authors=["Ada Scientist"],
        abstract="GLP-1 receptor agonists reduce body weight in adults with obesity.",
        doi=doi,
        page_count=5,
        word_count=30,
        raw_text="GLP-1 receptor agonists reduce body weight compared with placebo.",
        body_text="Weight reduction was observed with GLP-1 receptor agonist therapy.",
    )
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        paper.publication_year = 2023
    return database


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Offline scientific paper ingestion and search" in result.output


def test_safe_text_normalizes_pdf_ligatures() -> None:
    assert cli._safe_text("Efﬁcacy") == "Efficacy"


def test_answer_command_returns_retrieval_only_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        ["answer", "Do GLP-1 receptor agonists reduce body weight?"],
    )

    assert result.exit_code == 0
    assert "GLP-1 Therapy Reduces Body Weight" in result.output
    assert "2023" in result.output
    assert "10.1234/answer" in result.output
    assert "This is retrieval only." in result.output
    assert "No scientific synthesis has been performed." in result.output


def test_answer_command_applies_sources_overlay_by_doi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.3389/fphar.2022.935823")
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "source_id,title,authors,year,venue,doi,source_url,license_type\n"
        "source-1,Curated GLP-1 Review,"
        "Gao; Hua; Wang,2022,Frontiers in Pharmacology,"
        "10.3389/fphar.2022.935823,https://example.test/article,CC-BY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code == 0
    assert "Curated GLP-1 Review" in result.output
    assert "Metadata source: corpus sources.csv" in result.output
    assert "Gao; Hua; Wang" in result.output
    assert "Frontiers in Pharmacology" in result.output
    assert "CC-BY" in result.output
    assert "GLP-1 Therapy Reduces Body Weight" not in result.output


def test_answer_command_falls_back_when_sources_overlay_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1234/answer")
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "source_id,title,authors,year,venue,doi,source_url,license_type\n"
        "source-1,Curated Nonmatch,Curator,2022,Journal,10.9999/nope,"
        "https://example.test/article,CC-BY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code == 0
    assert "GLP-1 Therapy Reduces Body Weight" in result.output
    assert "Metadata source: corpus sources.csv" not in result.output
    assert "Curated Nonmatch" not in result.output


def test_answer_command_rejects_invalid_sources_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text("title\nCurated GLP-1 Review\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
        ],
    )

    assert result.exit_code != 0
    assert "sources CSV is missing required column" in result.output


def test_answer_command_displays_doi_matched_manual_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    records_path = write_evidence_records(
        tmp_path,
        [{"source_doi": "https://doi.org/10.1038/s41591-022-02026-4"}],
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code == 0
    assert "Reviewed evidence: available" in result.output
    assert "Evidence record ID: ev-1" in result.output
    assert "Extraction method: manual" in result.output
    assert "Review status: draft" in result.output
    assert "needs secondary review" in result.output
    assert "Evidence direction: supports" in result.output
    assert "Semaglutide provided evidence" in result.output
    assert "Percent body weight change." in result.output
    assert "No scientific synthesis has been performed." in result.output


def test_answer_command_marks_retrieved_paper_without_manual_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1234/answer")
    records_path = write_evidence_records(tmp_path, [{"source_doi": "10.9999/nonmatch"}])
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code == 0
    assert "Reviewed evidence: not available" in result.output
    assert "Evidence record ID: ev-1" not in result.output
    assert "This is retrieval only." in result.output


def test_answer_command_rejects_evidence_records_without_doi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1234/answer")
    records_path = write_evidence_records(tmp_path, [{"source_doi": ""}])
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "source_doi is required" in result.output


def test_answer_command_fails_for_missing_evidence_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(tmp_path / "missing.jsonl"),
        ],
    )

    assert result.exit_code != 0
    assert "Evidence records file does not exist" in result.output


def test_answer_command_fails_for_invalid_evidence_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("{not-json}\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "Line 1: invalid JSON." in result.output


def test_answer_command_fails_for_empty_evidence_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code != 0
    assert "contains no evidence records" in result.output


def test_evidence_report_prints_markdown_without_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(
        tmp_path,
        [{"source_doi": "10.1038/s41591-022-02026-4"}],
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code == 0
    assert "# Knowledge Engine Evidence Report" in result.output
    assert "## Research Question" in result.output
    assert "Do GLP-1 receptor agonists reduce body weight?" in result.output
    assert "Curated STEP 5 Trial" in result.output
    assert "Reviewed evidence: available" in result.output
    assert "Evidence record ID: ev-1" in result.output
    assert "Review status: draft" in result.output
    assert "No scientific synthesis has been performed." in result.output


def test_evidence_report_writes_markdown_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(
        tmp_path,
        [{"source_doi": "10.1038/s41591-022-02026-4"}],
    )
    output_path = tmp_path / "reports" / "report.md"
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote evidence report" in result.output
    report = output_path.read_text(encoding="utf-8")
    assert "Curated STEP 5 Trial" in report
    assert "Greater body-weight reduction with semaglutide." in report
    assert "Metadata source: corpus sources.csv" in report
    assert "Review status: draft" in report


def test_evidence_report_marks_paper_without_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1234/answer")
    sources_csv = write_sources_csv(tmp_path, doi="10.1234/answer")
    records_path = write_evidence_records(tmp_path, [{"source_doi": "10.9999/nonmatch"}])
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code == 0
    assert "Reviewed evidence: not available" in result.output


def test_evidence_report_fails_when_output_exists_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(tmp_path, [{"source_doi": "10.9999/nonmatch"}])
    output_path = tmp_path / "report.md"
    output_path.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "Output file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_evidence_report_overwrites_output_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(tmp_path, [{"source_doi": "10.9999/nonmatch"}])
    output_path = tmp_path / "report.md"
    output_path.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "# Knowledge Engine Evidence Report" in output_path.read_text(encoding="utf-8")


def test_evidence_report_fails_for_missing_evidence_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    sources_csv = write_sources_csv(tmp_path)
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(tmp_path / "missing.jsonl"),
        ],
    )

    assert result.exit_code != 0
    assert "Evidence records file does not exist" in result.output


def test_evidence_report_fails_for_invalid_evidence_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = build_cli_database(tmp_path)
    sources_csv = write_sources_csv(tmp_path)
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("{not-json}\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        [
            "evidence-report",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
        ],
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "Line 1: invalid JSON." in result.output


def test_evidence_validate_passes_valid_jsonl(tmp_path: Path) -> None:
    records_path = write_evidence_records(
        tmp_path,
        [{"review_status": "draft"}, {"review_status": "reviewed"}],
    )

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code == 0
    assert "Evidence validation passed." in result.output
    assert "Records: 2" in result.output
    assert "Draft: 1" in result.output
    assert "Reviewed: 1" in result.output
    assert "Needs revision: 0" in result.output
    assert "Rejected: 0" in result.output


def test_evidence_validate_fails_for_missing_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["evidence-validate", str(tmp_path / "missing.jsonl")])

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "Evidence records file does not exist" in result.output


def test_evidence_validate_fails_for_empty_file(tmp_path: Path) -> None:
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "contains no evidence records" in result.output


def test_evidence_validate_fails_for_invalid_jsonl(tmp_path: Path) -> None:
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("{not-json}\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "Line 1: invalid JSON." in result.output


def test_evidence_validate_fails_for_duplicate_evidence_record_id(tmp_path: Path) -> None:
    records_path = write_evidence_records(
        tmp_path,
        [{"evidence_record_id": "duplicate"}, {"evidence_record_id": "duplicate"}],
    )

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "duplicate evidence_record_id: duplicate" in result.output


def test_evidence_validate_fails_for_missing_required_field(tmp_path: Path) -> None:
    records_path = write_evidence_records(tmp_path, [{}])
    record = json.loads(records_path.read_text(encoding="utf-8"))
    del record["schema_version"]
    records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "missing required field(s): schema_version" in result.output


def test_evidence_validate_fails_for_missing_source_doi(tmp_path: Path) -> None:
    records_path = write_evidence_records(tmp_path, [{"source_doi": ""}])

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "source_doi is required" in result.output


def test_evidence_validate_fails_for_invalid_review_status(tmp_path: Path) -> None:
    records_path = write_evidence_records(tmp_path, [{"review_status": "approved"}])

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "invalid review_status 'approved'" in result.output


def test_evidence_validate_fails_for_malformed_review_checklist(tmp_path: Path) -> None:
    records_path = write_evidence_records(tmp_path, [{"review_checklist": "yes"}])

    result = CliRunner().invoke(app, ["evidence-validate", str(records_path)])

    assert result.exit_code != 0
    assert "review_checklist must be an object" in result.output


@pytest.mark.parametrize("command_name", ["evidence", "answer", "evidence-report"])
def test_evidence_consuming_commands_reject_duplicate_evidence_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command_name: str
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(
        tmp_path,
        [{"evidence_record_id": "duplicate"}, {"evidence_record_id": "duplicate"}],
    )
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        evidence_consumer_args(command_name, tmp_path, sources_csv, records_path),
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "duplicate evidence_record_id: duplicate" in result.output


@pytest.mark.parametrize("command_name", ["evidence", "answer", "evidence-report"])
def test_evidence_consuming_commands_reject_invalid_review_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command_name: str
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(tmp_path, [{"review_status": "approved"}])
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        evidence_consumer_args(command_name, tmp_path, sources_csv, records_path),
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "invalid review_status 'approved'" in result.output


@pytest.mark.parametrize("command_name", ["evidence", "answer", "evidence-report"])
def test_evidence_consuming_commands_reject_malformed_review_checklist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command_name: str
) -> None:
    database = build_cli_database(tmp_path, doi="10.1038/s41591-022-02026-4")
    sources_csv = write_sources_csv(tmp_path)
    records_path = write_evidence_records(tmp_path, [{"review_checklist": "yes"}])
    monkeypatch.setattr(cli, "_database", lambda: database)

    result = CliRunner().invoke(
        app,
        evidence_consumer_args(command_name, tmp_path, sources_csv, records_path),
    )

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "review_checklist must be an object" in result.output


def test_evidence_command_displays_manual_evidence_record(tmp_path: Path) -> None:
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text(
        (
            '{"evidence_record_id":"ev-1",'
            '"schema_version":"0.1",'
            '"extraction_status":"draft_manual_prototype",'
            '"research_question":"Do GLP-1 receptor agonists reduce body weight?",'
            '"source_title":"STEP 5 trial",'
            '"source_doi":"10.1038/s41591-022-02026-4",'
            '"source_type":"paper",'
            '"study_type":"randomized_controlled_trial",'
            '"review_status":"draft",'
            '"review_checklist":{'
            '"source_verified":true,'
            '"doi_verified":true,'
            '"manual_extraction_labeled":true,'
            '"source_span_present":true,'
            '"limitations_recorded":true,'
            '"uncertainty_recorded":true,'
            '"no_synthesis_language":true,'
            '"ready_for_secondary_review":false},'
            '"review_notes":"Prototype record awaiting secondary review.",'
            '"claim_text":"Semaglutide provided evidence of greater weight reduction.",'
            '"evidence_direction":"supports",'
            '"population":"Adults with overweight or obesity without diabetes.",'
            '"intervention":"Semaglutide 2.4 mg.",'
            '"comparator":"Placebo.",'
            '"outcome":"Percent body weight change.",'
            '"result_summary":"Greater body-weight reduction with semaglutide.",'
            '"limitations":["Manual extraction only."],'
            '"uncertainty_notes":"One paper only.",'
            '"confidence_note":"Source-linked manual record.",'
            '"source_span":{"page_number":2,"section":"Results"},'
            '"provenance":{"created_by":"manual review"},'
            '"created_for_milestone":"test",'
            '"extraction_method":"manual_human_review"}\n'
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["evidence", str(records_path)])

    assert result.exit_code == 0
    assert "Evidence record: ev-1" in result.output
    assert "STEP 5 trial" in result.output
    assert "Review status: draft" in result.output
    assert "Review notes: Prototype record awaiting secondary review." in result.output
    assert "Extraction method: manual_human_review (manual)" in result.output
    assert "This is manually extracted evidence." in result.output
    assert "No scientific synthesis has been performed." in result.output


def test_evidence_command_falls_back_when_review_status_missing(tmp_path: Path) -> None:
    records_path = write_evidence_records(
        tmp_path,
        [{"review_status": None, "review_checklist": None, "review_notes": None}],
    )

    result = CliRunner().invoke(app, ["evidence", str(records_path)])

    assert result.exit_code == 0
    assert "Review status: unspecified" in result.output
    assert "Review checklist: not recorded" in result.output


def test_evidence_command_fails_for_missing_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["evidence", str(tmp_path / "missing.jsonl")])

    assert result.exit_code != 0
    assert "Evidence records file does not exist" in result.output


def test_evidence_command_fails_for_invalid_jsonl(tmp_path: Path) -> None:
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("{not-json}\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["evidence", str(records_path)])

    assert result.exit_code != 0
    assert "Evidence validation failed." in result.output
    assert "Line 1: invalid JSON." in result.output


def test_evidence_command_fails_for_empty_jsonl(tmp_path: Path) -> None:
    records_path = tmp_path / "evidence_records.jsonl"
    records_path.write_text("\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["evidence", str(records_path)])

    assert result.exit_code != 0
    assert "contains no evidence records" in result.output


def write_evidence_records(tmp_path: Path, overrides: list[dict[str, object]]) -> Path:
    records_path = tmp_path / "evidence_records.jsonl"
    records = []
    for index, override in enumerate(overrides, start=1):
        record: dict[str, object] = {
            "schema_version": "0.1",
            "evidence_record_id": f"ev-{index}",
            "extraction_method": "manual_human_review",
            "extraction_status": "draft_manual_prototype",
            "source_doi": "10.1038/s41591-022-02026-4",
            "source_title": "STEP 5 trial",
            "source_type": "paper",
            "study_type": "randomized_controlled_trial",
            "research_question": "Do GLP-1 receptor agonists reduce body weight?",
            "review_status": "draft",
            "review_checklist": {
                "source_verified": True,
                "doi_verified": True,
                "manual_extraction_labeled": True,
                "source_span_present": True,
                "limitations_recorded": True,
                "uncertainty_recorded": True,
                "no_synthesis_language": True,
                "ready_for_secondary_review": False,
            },
            "review_notes": "Prototype manual record awaiting secondary review.",
            "claim_text": "Semaglutide provided evidence of greater weight reduction.",
            "evidence_direction": "supports",
            "population": "Adults with overweight or obesity without diabetes.",
            "intervention": "Semaglutide 2.4 mg.",
            "comparator": "Placebo.",
            "outcome": "Percent body weight change.",
            "result_summary": "Greater body-weight reduction with semaglutide.",
            "limitations": ["Manual extraction only."],
            "uncertainty_notes": "One paper only.",
            "confidence_note": "Source-linked manual record.",
            "source_span": {"page_number": 2, "section": "Results"},
            "provenance": {"created_by": "manual review"},
            "created_for_milestone": "test",
        }
        record.update(override)
        records.append(record)

    records_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    return records_path


def write_sources_csv(
    tmp_path: Path,
    *,
    doi: str = "10.1038/s41591-022-02026-4",
) -> Path:
    sources_csv = tmp_path / "sources.csv"
    sources_csv.write_text(
        "source_id,title,authors,year,venue,doi,source_url,license_type\n"
        "source-1,Curated STEP 5 Trial,"
        "Garvey; Batterham,2022,Nature Medicine,"
        f"{doi},https://example.test/step-5,CC-BY\n",
        encoding="utf-8",
    )
    return sources_csv


def evidence_consumer_args(
    command_name: str,
    tmp_path: Path,
    sources_csv: Path,
    records_path: Path,
) -> list[str]:
    if command_name == "evidence":
        return ["evidence", str(records_path)]
    if command_name == "answer":
        return [
            "answer",
            "Do GLP-1 receptor agonists reduce body weight?",
            "--sources",
            str(sources_csv),
            "--evidence",
            str(records_path),
        ]
    return [
        "evidence-report",
        "Do GLP-1 receptor agonists reduce body weight?",
        "--sources",
        str(sources_csv),
        "--evidence",
        str(records_path),
        "--output",
        str(tmp_path / "report.md"),
    ]
