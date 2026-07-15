import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.ingestion import ImportedCorpusRun
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
    assert "corpus-validate" in result.output
    assert "corpus-import" in result.output


def test_safe_text_normalizes_pdf_ligatures() -> None:
    assert cli._safe_text("Efﬁcacy") == "Efficacy"


def test_corpus_validate_command_passes_valid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path)])

    assert result.exit_code == 0
    assert "Corpus validation" in result.output
    assert "Manifest validity: valid" in result.output
    assert "Import readiness: not evaluated" in result.output
    assert "No papers were imported." in result.output
    assert "No database writes were performed." in result.output
    assert "Validation does not constitute legal approval or scientific review." in result.output
    assert not (tmp_path / "data" / "knowledge_engine.sqlite3").exists()


def test_corpus_validate_command_reports_import_blocked_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path, usage_status="needs_legal_review")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path)])

    assert result.exit_code == 0
    assert "Manifest validity: valid" in result.output
    assert "Import readiness: blocked" in result.output
    assert "usage_status_not_importable" in result.output


def test_corpus_validate_command_fails_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path, corpus_id="Bad ID")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path)])

    assert result.exit_code == 1
    assert "Corpus validation failed" in result.output
    assert "Manifest validity: invalid" in result.output
    assert "invalid_corpus_id" in result.output
    assert "^[a-z0-9][a-z0-9_-]*$" in result.output


def test_corpus_validate_command_orders_issues_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(
        tmp_path,
        rows=[
            "b-source,,approved_open_access,included",
            "a-source,,approved_open_access,included",
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path)])

    assert result.exit_code == 1
    assert result.output.index("line 2") < result.output.index("line 3")


def test_corpus_validate_command_check_files_blocks_missing_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-validate", str(corpus_path), "--check-files"])

    assert result.exit_code == 0
    assert "Manifest validity: valid" in result.output
    assert "Import readiness: blocked" in result.output
    assert "local_file_missing" in result.output
    assert "Missing: 1" in result.output


def test_corpus_import_command_reports_successful_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)

    class StubCorpusIngestionService:
        def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
            self.session = session
            self.project_root = project_root or tmp_path

        def import_corpus(self, path: Path) -> ImportedCorpusRun:
            persisted = ImportRunService(self.session, project_root=self.project_root).create_run(
                path, check_files=True
            )
            run = ImportRunService(self.session, project_root=self.project_root).get_run(
                persisted.import_run_id
            )
            assert run is not None
            run.run_status = "succeeded"
            run.items[0].item_status = "imported"
            self.session.flush()
            return ImportedCorpusRun(
                import_run_id=run.import_run_id,
                run_status=run.run_status,
                imported_count=1,
                failed_count=0,
                skipped_count=0,
            )

    monkeypatch.setattr(cli, "CorpusIngestionService", StubCorpusIngestionService)

    result = CliRunner().invoke(app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 0
    assert "Corpus import finished" in result.output
    assert "Run status: succeeded" in result.output
    assert "Imported papers: 1" in result.output
    assert "Failed items: 0" in result.output
    assert "Skipped items: 0" in result.output
    assert "status=imported" in result.output
    assert "Paper and FTS records may have been written for successful items." in result.output
    assert "No URLs were followed and no documents were downloaded." in result.output


def test_corpus_import_command_fails_for_import_blocked_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path, usage_status="needs_legal_review")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 1
    assert "Corpus import finished" in result.output
    assert "Run status: import_blocked" in result.output
    assert "Imported papers: 0" in result.output
    assert "Failed items: 0" in result.output
    assert "Skipped items: 1" in result.output
    assert "usage_status_not_importable" in result.output


def test_corpus_import_command_fails_for_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path, corpus_id="Bad ID")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 1
    assert "Corpus import finished" in result.output
    assert "Run status: validation_failed" in result.output
    assert "invalid_corpus_id" in result.output


def test_corpus_import_command_sanitizes_internal_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)

    class StubCorpusIngestionService:
        def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
            self.session = session
            self.project_root = project_root or tmp_path

        def import_corpus(self, path: Path) -> ImportedCorpusRun:
            raise RuntimeError("sensitive absolute path /private/tmp/example.pdf")

    monkeypatch.setattr(cli, "CorpusIngestionService", StubCorpusIngestionService)

    result = CliRunner().invoke(app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 2
    assert "Corpus import did not complete due to an internal error." in result.output
    assert "sensitive absolute path" not in result.output


def test_corpus_import_command_sanitizes_other_sensitive_internal_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)

    class StubCorpusIngestionService:
        def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
            self.session = session
            self.project_root = project_root or tmp_path

        def import_corpus(self, path: Path) -> ImportedCorpusRun:
            raise RuntimeError(
                'postgresql://user:secret-token@example.test/ke'
            )

    monkeypatch.setattr(cli, "CorpusIngestionService", StubCorpusIngestionService)

    result = CliRunner().invoke(app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 2
    assert "Corpus import did not complete due to an internal error." in result.output
    assert "secret-token" not in result.output
    assert "postgresql://" not in result.output


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
    assert "Evidence Review Status Summary" in result.output
    assert "Evidence records: 1" in result.output
    assert "Draft: 1" in result.output
    assert "Evidence readiness: draft only; secondary review needed." in result.output
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
    assert "## Evidence Review Status Summary" in result.output
    assert "Evidence records: 1" in result.output
    assert "Evidence readiness: draft only; secondary review needed." in result.output
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
    assert "## Evidence Review Status Summary" in report
    assert "Evidence records: 1" in report
    assert "Evidence readiness: draft only; secondary review needed." in report
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
    assert "Evidence Review Status Summary" in result.output
    assert "Evidence records: 2" in result.output
    assert "Draft: 1" in result.output
    assert "Reviewed: 1" in result.output
    assert "Needs revision: 0" in result.output
    assert "Rejected: 0" in result.output
    assert "Evidence readiness: mixed review status." in result.output


def test_evidence_status_summary_counts_all_statuses() -> None:
    summary = cli._evidence_status_summary(
        [
            {"review_status": "draft"},
            {"review_status": "reviewed"},
            {"review_status": "needs_revision"},
            {"review_status": "rejected"},
            {},
        ]
    )

    assert summary.total == 5
    assert summary.draft == 1
    assert summary.reviewed == 1
    assert summary.needs_revision == 1
    assert summary.rejected == 1
    assert summary.unspecified == 1
    assert summary.readiness_note == "revision needed before use."


def test_evidence_status_summary_all_reviewed_readiness() -> None:
    summary = cli._evidence_status_summary(
        [{"review_status": "reviewed"}, {"review_status": "reviewed"}]
    )

    assert summary.readiness_note == "reviewed evidence available."


def test_evidence_status_summary_rejected_readiness() -> None:
    summary = cli._evidence_status_summary(
        [{"review_status": "reviewed"}, {"review_status": "rejected"}]
    )

    assert summary.readiness_note == "contains rejected records; review before reporting."


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
    assert "Evidence Review Status Summary" in result.output
    assert "Evidence records: 1" in result.output
    assert "Evidence readiness: draft only; secondary review needed." in result.output
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


def write_cli_corpus(
    tmp_path: Path,
    *,
    corpus_id: str = "cli_corpus",
    usage_status: str = "approved_open_access",
    rows: list[str] | None = None,
) -> Path:
    (tmp_path / "knowledge_engine").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    corpus_dir = tmp_path / "data" / "corpora" / "cli_corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "license_policy.md").write_text("# License\n", encoding="utf-8")
    (tmp_path / "papers" / "corpora" / "cli_corpus").mkdir(parents=True)
    corpus = {
        "manifest_version": 1,
        "corpus_id": corpus_id,
        "name": "CLI Corpus",
        "description": "A CLI test corpus.",
        "scientific_domain": "test science",
        "research_question": {"question_id": "q_cli", "text": "Does the CLI validate?"},
        "created_at": "2026-07-11",
        "updated_at": "2026-07-11",
        "license_policy": "license_policy.md",
        "source_manifest": "sources.csv",
        "default_local_papers_directory": "papers/corpora/cli_corpus",
    }
    (corpus_dir / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")
    source_rows = rows or [f"source-1,Valid Paper,{usage_status},included"]
    (corpus_dir / "sources.csv").write_text(
        "source_id,title,usage_status,inclusion_status,source_url,access_date,"
        "inclusion_reason,license_type,license_url,local_path\n"
        + "\n".join(
            f"{row},https://example.test/paper,2026-07-11,Relevant,CC-BY,"
            "https://creativecommons.org/licenses/by/4.0/,paper.pdf"
            for row in source_rows
        )
        + "\n",
        encoding="utf-8",
    )
    return corpus_dir / "corpus.json"


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
