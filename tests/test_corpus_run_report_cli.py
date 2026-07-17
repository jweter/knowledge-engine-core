from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.models import ImportItem, ImportRun, ManifestSnapshot


def test_corpus_run_report_prints_sanitized_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run()
    monkeypatch.setattr(entrypoint, "_load_report_run", lambda import_run_id: run)

    result = CliRunner().invoke(entrypoint.app, ["corpus-run-report", "run-1"])

    assert result.exit_code == 0
    assert "# Corpus Import Run Report" in result.output
    assert "Persisted import items: 1" in result.output
    assert "source=`source-1`" in result.output
    assert "Network access:" not in result.output


def test_corpus_run_report_rejects_unknown_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoint, "_load_report_run", lambda import_run_id: None)

    result = CliRunner().invoke(entrypoint.app, ["corpus-run-report", "missing-run"])

    assert result.exit_code == 1
    assert "Unknown import run:" in result.output
    assert "missing-run" in result.output


def test_corpus_run_report_protects_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "report.md"
    output.write_text("existing", encoding="utf-8")
    called = False

    def load_run(import_run_id: str) -> ImportRun:
        nonlocal called
        called = True
        return _run()

    monkeypatch.setattr(entrypoint, "_load_report_run", load_run)

    result = CliRunner().invoke(
        entrypoint.app,
        ["corpus-run-report", "run-1", "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "Output file already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"
    assert called is False


def test_corpus_run_report_force_overwrites_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "reports" / "report.md"
    monkeypatch.setattr(entrypoint, "_load_report_run", lambda import_run_id: _run())

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "corpus-run-report",
            "run-1",
            "--output",
            str(output),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "Wrote corpus run report:" in result.output
    assert output.read_text(encoding="utf-8").startswith("# Corpus Import Run Report")


def test_corpus_run_report_surfaces_reconciliation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run()
    run.total_source_rows = 2
    monkeypatch.setattr(entrypoint, "_load_report_run", lambda import_run_id: run)

    result = CliRunner().invoke(entrypoint.app, ["corpus-run-report", "run-1"])

    assert result.exit_code != 0
    assert "Import run report reconciliation failed" in result.output
    assert "Declared source rows do not reconcile" in result.output


def _run() -> ImportRun:
    snapshot = ManifestSnapshot(
        snapshot_id="snapshot-1",
        corpus_path="data/corpora/m12/corpus.json",
        source_manifest_path="data/corpora/m12/sources.csv",
        corpus_json_bytes=b"{}",
        source_csv_bytes=b"source_id\n",
        corpus_json_text="{}",
        source_csv_text="source_id\n",
        corpus_json_sha256="a" * 64,
        source_csv_sha256="b" * 64,
        combined_sha256="c" * 64,
        captured_at="2026-07-18T00:00:00Z",
    )
    run = ImportRun(
        import_run_id="run-1",
        corpus_id="m12",
        corpus_name="M12 Test Corpus",
        manifest_version=1,
        validation_mode="check_files",
        run_mode="fresh",
        run_status="succeeded",
        review_status="clear",
        manifest_validity="valid",
        import_readiness="ready",
        total_source_rows=1,
        valid_source_rows=1,
        warning_count=0,
        structural_error_count=0,
        import_blocker_count=0,
        created_at="2026-07-18T00:00:00Z",
        completed_at="2026-07-18T00:01:00Z",
        source_manifest_path="data/corpora/m12/sources.csv",
        license_policy_path="data/corpora/m12/license_policy.md",
        corpus_path="data/corpora/m12/corpus.json",
        parent_import_run_id=None,
        manifest_snapshot_id="snapshot-1",
    )
    run.manifest_snapshot = snapshot
    run.items = [
        ImportItem(
            import_item_id="item-1",
            import_run_id="run-1",
            source_id="source-1",
            csv_line_number=2,
            title="Test Paper",
            normalized_doi="10.1000/test",
            inclusion_status="included",
            usage_status="approved_open_access",
            local_path="paper.pdf",
            item_status="imported",
            duplicate_outcome=None,
            matched_paper_id=1,
            matched_import_item_id=None,
            computed_content_hash="d" * 64,
            duplicate_evidence_json=None,
            retry_of_import_item_id=None,
            blocks_manifest=False,
            blocks_import=False,
            warning_count=0,
            structural_error_count=0,
            import_blocker_count=0,
            created_at="2026-07-18T00:00:00Z",
            completed_at="2026-07-18T00:01:00Z",
        )
    ]
    run.issues = []
    return run
