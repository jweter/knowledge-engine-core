"""Deterministic, sanitized reporting for persisted corpus import runs."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from knowledge_engine.models import ImportItem, ImportRun


@dataclass(frozen=True)
class ImportRunReportSummary:
    """Reconciled aggregate values derived from one persisted import run."""

    item_count: int
    item_status_counts: tuple[tuple[str, int], ...]
    duplicate_outcome_counts: tuple[tuple[str, int], ...]
    issue_code_counts: tuple[tuple[str, int], ...]
    issue_severity_counts: tuple[tuple[str, int], ...]
    issue_category_counts: tuple[tuple[str, int], ...]
    matched_paper_count: int
    matched_import_item_count: int
    retry_link_count: int
    blocking_manifest_issue_count: int
    blocking_import_issue_count: int
    warning_issue_count: int


def summarize_import_run(run: ImportRun) -> ImportRunReportSummary:
    """Build and reconcile deterministic aggregate counts for an import run."""

    item_status_counts = _sorted_counts(item.item_status for item in run.items)
    duplicate_outcome_counts = _sorted_counts(
        item.duplicate_outcome for item in run.items if item.duplicate_outcome
    )
    issue_code_counts = _sorted_counts(issue.code for issue in run.issues)
    issue_severity_counts = _sorted_counts(issue.severity for issue in run.issues)
    issue_category_counts = _sorted_counts(issue.category for issue in run.issues)

    summary = ImportRunReportSummary(
        item_count=len(run.items),
        item_status_counts=item_status_counts,
        duplicate_outcome_counts=duplicate_outcome_counts,
        issue_code_counts=issue_code_counts,
        issue_severity_counts=issue_severity_counts,
        issue_category_counts=issue_category_counts,
        matched_paper_count=sum(item.matched_paper_id is not None for item in run.items),
        matched_import_item_count=sum(
            item.matched_import_item_id is not None for item in run.items
        ),
        retry_link_count=sum(item.retry_of_import_item_id is not None for item in run.items),
        blocking_manifest_issue_count=sum(issue.blocks_manifest for issue in run.issues),
        blocking_import_issue_count=sum(issue.blocks_import for issue in run.issues),
        warning_issue_count=sum(issue.severity == "warning" for issue in run.issues),
    )
    _validate_reconciliation(run, summary)
    return summary


def render_import_run_report(run: ImportRun) -> str:
    """Render a sanitized Markdown report from persisted run state."""

    summary = summarize_import_run(run)
    snapshot = run.manifest_snapshot
    manifest_version = run.manifest_version if run.manifest_version is not None else "unknown"
    lines = [
        "# Corpus Import Run Report",
        "",
        "## Run identity",
        "",
        f"- Import run ID: `{_safe_code(run.import_run_id)}`",
        f"- Run mode: `{_safe_code(run.run_mode)}`",
        f"- Parent import run ID: `{_safe_code(run.parent_import_run_id or 'none')}`",
        f"- Run status: `{_safe_code(run.run_status)}`",
        f"- Review status: `{_safe_code(run.review_status)}`",
        f"- Validation mode: `{_safe_code(run.validation_mode)}`",
        f"- Created at: `{_safe_code(run.created_at)}`",
        f"- Completed at: `{_safe_code(run.completed_at)}`",
        "",
        "## Corpus and manifest",
        "",
        f"- Corpus ID: `{_safe_code(run.corpus_id or 'unknown')}`",
        f"- Corpus name: {_safe_text(run.corpus_name or 'Unknown')}",
        f"- Manifest version: `{manifest_version}`",
        f"- Manifest validity: `{_safe_code(run.manifest_validity)}`",
        f"- Import readiness: `{_safe_code(run.import_readiness)}`",
        f"- Manifest snapshot ID: `{_safe_code(run.manifest_snapshot_id)}`",
        f"- Combined manifest SHA-256: `{_safe_code(snapshot.combined_sha256)}`",
        f"- Corpus path: `{_safe_path(run.corpus_path)}`",
        f"- Source manifest path: `{_safe_path(run.source_manifest_path or 'unknown')}`",
        "",
        "## Reconciled outcomes",
        "",
        f"- Declared source rows: {run.total_source_rows}",
        f"- Persisted import items: {summary.item_count}",
        f"- Valid source rows: {run.valid_source_rows}",
        f"- Matched paper records: {summary.matched_paper_count}",
        f"- Matched prior import items: {summary.matched_import_item_count}",
        f"- Retry-linked items: {summary.retry_link_count}",
        "",
        "### Item statuses",
        "",
        *_count_lines(summary.item_status_counts),
        "",
        "### Duplicate outcomes",
        "",
        *_count_lines(
            summary.duplicate_outcome_counts, empty_label="No duplicate outcomes recorded."
        ),
        "",
        "## Persisted issues",
        "",
        f"- Warning issues: {summary.warning_issue_count}",
        f"- Manifest-blocking issues: {summary.blocking_manifest_issue_count}",
        f"- Import-blocking issues: {summary.blocking_import_issue_count}",
        "",
        "### Issue codes",
        "",
        *_count_lines(summary.issue_code_counts, empty_label="No persisted issues."),
        "",
        "### Issue severities",
        "",
        *_count_lines(summary.issue_severity_counts, empty_label="No persisted issues."),
        "",
        "### Issue categories",
        "",
        *_count_lines(summary.issue_category_counts, empty_label="No persisted issues."),
        "",
        "## Item lineage",
        "",
        *_item_lines(run.items),
        "",
        "## Measurement boundaries",
        "",
        (
            "- Counts in this report are derived from persisted import-run, item, "
            "issue, and manifest-snapshot state."
        ),
        (
            "- The current schema does not store high-resolution stage timing, CPU, "
            "memory, or disk telemetry."
        ),
        (
            "- Wall-clock duration and environment measurements must be recorded "
            "separately by the rehearsal operator."
        ),
        (
            "- M11 external metadata candidates and metadata-conflict counts are not "
            "persisted in the current schema."
        ),
        (
            "- This report does not contain extracted full text and does not provide "
            "scientific validation or synthesis."
        ),
        "",
    ]
    return "\n".join(lines)


def _validate_reconciliation(run: ImportRun, summary: ImportRunReportSummary) -> None:
    if sum(count for _, count in summary.item_status_counts) != summary.item_count:
        raise ValueError("Import item status counts do not reconcile with persisted items.")
    if sum(count for _, count in summary.duplicate_outcome_counts) > summary.item_count:
        raise ValueError("Duplicate outcome counts exceed persisted import items.")
    if run.warning_count != summary.warning_issue_count:
        raise ValueError("Run warning count does not reconcile with persisted warning issues.")
    if run.structural_error_count != summary.blocking_manifest_issue_count:
        raise ValueError(
            "Run structural error count does not reconcile with manifest-blocking issues."
        )
    if run.import_blocker_count != summary.blocking_import_issue_count:
        raise ValueError("Run import blocker count does not reconcile with import-blocking issues.")
    if run.total_source_rows != summary.item_count:
        raise ValueError("Declared source rows do not reconcile with persisted import items.")


def _sorted_counts(values: Iterable[object]) -> tuple[tuple[str, int], ...]:
    counts = Counter(str(value) for value in values)
    return tuple(sorted(counts.items()))


def _count_lines(
    counts: tuple[tuple[str, int], ...],
    *,
    empty_label: str = "No values recorded.",
) -> list[str]:
    if not counts:
        return [empty_label]
    return [f"- `{_safe_code(value)}`: {count}" for value, count in counts]


def _item_lines(items: list[ImportItem]) -> list[str]:
    if not items:
        return ["No import items recorded."]
    return [_item_line(item) for item in items]


def _item_line(item: ImportItem) -> str:
    parts = [
        f"source=`{_safe_code(item.source_id or 'unknown')}`",
        f"status=`{_safe_code(item.item_status)}`",
        f"duplicate=`{_safe_code(item.duplicate_outcome or 'none')}`",
        f"paper_id=`{item.matched_paper_id if item.matched_paper_id is not None else 'none'}`",
        f"matched_item=`{_safe_code(item.matched_import_item_id or 'none')}`",
        f"retry_of=`{_safe_code(item.retry_of_import_item_id or 'none')}`",
    ]
    return "- " + "; ".join(parts)


def _safe_path(value: str) -> str:
    normalized = _safe_code(value)
    if normalized.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", normalized):
        return "[redacted absolute path]"
    if ".." in normalized.replace("\\", "/").split("/"):
        return "[redacted unsafe path]"
    return normalized


def _safe_code(value: str) -> str:
    """Keep persisted values inside one bounded Markdown code span."""

    return " ".join(value.replace("`", "'").split())[:1024]


def _safe_text(value: str) -> str:
    """Escape bounded persisted text that is rendered outside a code span."""

    normalized = " ".join(value.split())[:1024]
    return re.sub(r"([\\`*_[\]{}()#+.!<>|~-])", r"\\\1", normalized)


__all__ = ["ImportRunReportSummary", "render_import_run_report", "summarize_import_run"]
