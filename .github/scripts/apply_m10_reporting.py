"""Apply the final guarded M10 CLI reporting edits."""

from pathlib import Path

path = Path("knowledge_engine/cli.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        """    console.print(f"Import run ID: {_display_cli_text(run.import_run_id)}")
    console.print(f"Run status: {_display_cli_text(run.run_status)}")
    console.print(f"Validation mode: {_display_cli_text(run.validation_mode)}")
""",
        """    console.print(f"Import run ID: {_display_cli_text(run.import_run_id)}")
    console.print(f"Run status: {_display_cli_text(run.run_status)}")
    console.print(f"Run mode: {_display_cli_text(run.run_mode)}")
    console.print(
        f"Parent import run ID: {_display_cli_text(run.parent_import_run_id or 'None')}"
    )
    console.print(f"Validation mode: {_display_cli_text(run.validation_mode)}")
""",
    ),
    (
        """    completed_m9_statuses = {"succeeded", "partially_succeeded", "failed"}
    completed_ingestion_summary = (
        _import_run_item_summary(run) if run.run_status in completed_m9_statuses else None
    )
""",
        """    completed_ingestion_statuses = {
        "succeeded",
        "partially_succeeded",
        "failed",
        "needs_review",
    }
    completed_ingestion_summary = (
        _import_run_item_summary(run)
        if run.run_status in completed_ingestion_statuses
        else None
    )
""",
    ),
    (
        """        console.print(f"Imported papers: {completed_ingestion_summary['imported']}")
        console.print(f"Failed items: {completed_ingestion_summary['failed']}")
        console.print(f"Skipped items: {completed_ingestion_summary['skipped']}")
    elif import_result is not None:
        console.print(f"Imported papers: {import_result.imported_count}")
        console.print(f"Failed items: {import_result.failed_count}")
        console.print(f"Skipped items: {import_result.skipped_count}")
""",
        """        console.print(f"Imported papers: {completed_ingestion_summary['imported']}")
        console.print(f"Failed items: {completed_ingestion_summary['failed']}")
        console.print(f"Skipped items: {completed_ingestion_summary['skipped']}")
        console.print(f"Needs review items: {completed_ingestion_summary['needs_review']}")
    elif import_result is not None:
        console.print(f"Imported papers: {import_result.imported_count}")
        console.print(f"Failed items: {import_result.failed_count}")
        console.print(f"Skipped items: {import_result.skipped_count}")
        console.print(f"Needs review items: {import_result.needs_review_count}")
""",
    ),
    (
        """            f"status={_display_cli_text(item.item_status)} "
            f"warnings={item.warning_count} "
            f"structural_errors={item.structural_error_count} "
            f"import_blockers={item.import_blocker_count}"
""",
        """            f"status={_display_cli_text(item.item_status)} "
            f"duplicate_outcome={_display_cli_text(item.duplicate_outcome or 'None')} "
            f"matched_paper_id={item.matched_paper_id or 'None'} "
            f"matched_import_item_id={_display_cli_text(item.matched_import_item_id or 'None')} "
            f"retry_of_import_item_id={_display_cli_text(item.retry_of_import_item_id or 'None')} "
            f"warnings={item.warning_count} "
            f"structural_errors={item.structural_error_count} "
            f"import_blockers={item.import_blocker_count}"
""",
    ),
    (
        """        "imported": sum(1 for item in run.items if item.item_status in imported_statuses),
        "failed": sum(1 for item in run.items if item.item_status == "failed"),
        "skipped": sum(1 for item in run.items if item.item_status == "skipped"),
    }
""",
        """        "imported": sum(1 for item in run.items if item.item_status in imported_statuses),
        "failed": sum(1 for item in run.items if item.item_status == "failed"),
        "skipped": sum(1 for item in run.items if item.item_status == "skipped"),
        "needs_review": sum(
            1 for item in run.items if item.item_status == "needs_review"
        ),
    }
""",
    ),
    (
        """    skipped = summary["skipped"]
    console.print(
        f"Ingestion completed with {imported} imported, {failed} failed, {skipped} skipped."
    )
""",
        """    skipped = summary["skipped"]
    needs_review = summary["needs_review"]
    console.print(
        f"Ingestion completed with {imported} imported, {failed} failed, {skipped} skipped."
    )
    console.print(f"Needs review items: {needs_review}")
""",
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"expected CLI reporting block not found:\n{old}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
