from __future__ import annotations

from knowledge_engine.import_runs.reporting import render_import_run_report, summarize_import_run
from knowledge_engine.models import ImportIssue, ImportItem, ImportRun, ManifestSnapshot


def test_reconciles_and_renders_synthetic_100_item_rehearsal() -> None:
    run = _synthetic_run()

    summary = summarize_import_run(run)
    report = render_import_run_report(run)

    assert summary.item_count == 100
    assert summary.item_status_counts == (
        ("duplicate", 10),
        ("failed", 5),
        ("imported", 80),
        ("needs_review", 2),
        ("skipped", 3),
    )
    assert summary.duplicate_outcome_counts == (("same_paper_same_file", 10),)
    assert summary.matched_paper_count == 90
    assert summary.matched_import_item_count == 10
    assert summary.retry_link_count == 5
    assert "Persisted import items: 100" in report
    assert "`imported`: 80" in report
    assert "`same_paper_same_file`: 10" in report
    assert (
        "M11 external metadata candidates and metadata-conflict counts are not persisted" in report
    )
    assert "scientific validation or synthesis" in report


def test_report_redacts_absolute_and_traversal_paths() -> None:
    run = _synthetic_run()
    run.corpus_path = "/Users/example/private/corpus.json"
    run.source_manifest_path = "../private/sources.csv"

    report = render_import_run_report(run)

    assert "/Users/example" not in report
    assert "../private" not in report
    assert "[redacted absolute path]" in report
    assert "[redacted unsafe path]" in report


def test_report_rejects_source_row_item_count_mismatch() -> None:
    run = _synthetic_run()
    run.total_source_rows = 101

    try:
        summarize_import_run(run)
    except ValueError as error:
        assert str(error) == "Declared source rows do not reconcile with persisted import items."
    else:
        raise AssertionError("Expected reconciliation failure.")


def test_report_rejects_warning_count_mismatch() -> None:
    run = _synthetic_run()
    run.warning_count = 4

    try:
        summarize_import_run(run)
    except ValueError as error:
        assert str(error) == "Run warning count does not reconcile with persisted warning issues."
    else:
        raise AssertionError("Expected reconciliation failure.")


def _synthetic_run() -> ImportRun:
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
        import_run_id="run-100",
        corpus_id="m12_rehearsal",
        corpus_name="M12 Synthetic Rehearsal",
        manifest_version=1,
        validation_mode="check_files",
        run_mode="fresh",
        run_status="partially_succeeded",
        review_status="needs_review",
        manifest_validity="valid",
        import_readiness="ready",
        total_source_rows=100,
        valid_source_rows=100,
        warning_count=3,
        structural_error_count=0,
        import_blocker_count=2,
        created_at="2026-07-18T00:00:00Z",
        completed_at="2026-07-18T00:05:00Z",
        source_manifest_path="data/corpora/m12/sources.csv",
        license_policy_path="data/corpora/m12/license_policy.md",
        corpus_path="data/corpora/m12/corpus.json",
        parent_import_run_id=None,
        manifest_snapshot_id="snapshot-1",
    )
    run.manifest_snapshot = snapshot
    run.items = _items()
    run.issues = _issues()
    return run


def _items() -> list[ImportItem]:
    statuses = (
        ["imported"] * 80
        + ["duplicate"] * 10
        + ["failed"] * 5
        + ["skipped"] * 3
        + ["needs_review"] * 2
    )
    items: list[ImportItem] = []
    for index, status in enumerate(statuses, start=1):
        is_duplicate = status == "duplicate"
        is_failed = status == "failed"
        items.append(
            ImportItem(
                import_item_id=f"item-{index}",
                import_run_id="run-100",
                source_id=f"source-{index:03d}",
                csv_line_number=index + 1,
                title=f"Synthetic Paper {index}",
                normalized_doi=f"10.1000/{index}",
                inclusion_status="included",
                usage_status="approved_open_access",
                local_path=f"paper-{index:03d}.pdf",
                item_status=status,
                duplicate_outcome="same_paper_same_file" if is_duplicate else None,
                matched_paper_id=index if status in {"imported", "duplicate"} else None,
                matched_import_item_id=f"prior-{index}" if is_duplicate else None,
                computed_content_hash=f"{index:064x}"[-64:],
                duplicate_evidence_json="{}" if is_duplicate else None,
                retry_of_import_item_id=f"failed-prior-{index}" if is_failed else None,
                blocks_manifest=False,
                blocks_import=False,
                warning_count=0,
                structural_error_count=0,
                import_blocker_count=0,
                created_at="2026-07-18T00:00:00Z",
                completed_at="2026-07-18T00:05:00Z",
            )
        )
    return items


def _issues() -> list[ImportIssue]:
    return [
        _issue(1, "missing_doi", "warning", "metadata", blocks_import=False),
        _issue(2, "duplicate_candidate", "warning", "duplicate", blocks_import=False),
        _issue(3, "parser_warning", "warning", "parser", blocks_import=False),
        _issue(4, "unreadable_pdf", "error", "parser", blocks_import=True),
        _issue(5, "legal_status_not_approved", "error", "legal", blocks_import=True),
    ]


def _issue(
    sequence: int,
    code: str,
    severity: str,
    category: str,
    *,
    blocks_import: bool,
) -> ImportIssue:
    return ImportIssue(
        issue_id=f"issue-{sequence}",
        import_run_id="run-100",
        import_item_id=f"item-{sequence}",
        code=code,
        severity=severity,
        category=category,
        message=f"Synthetic {code}",
        source_id=f"source-{sequence:03d}",
        field=None,
        csv_line_number=sequence + 1,
        blocks_manifest=False,
        blocks_import=blocks_import,
        sequence=sequence,
        created_at="2026-07-18T00:05:00Z",
    )
