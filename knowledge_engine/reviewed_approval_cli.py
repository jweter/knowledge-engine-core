"""Standalone CLI for exporting automated adjudications to acquisition approvals."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.corpus_readiness_cli import _write_report_atomically
from knowledge_engine.reviewed_approval import ReviewedApprovalError, export_reviewed_approvals

app = typer.Typer(help="Export accepted M14 adjudications to acquisition approvals.")

WorksheetOption = Annotated[
    Path,
    typer.Option("--worksheet", help="Completed candidate adjudication worksheet JSON path."),
]
OutputOption = Annotated[
    Path,
    typer.Option("--output", help="PMC acquisition approval JSON path."),
]
LimitOption = Annotated[
    int,
    typer.Option(
        "--limit",
        min=1,
        help="Select exactly this many validated accepted records in worksheet order.",
    ),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Replace an existing approval file atomically."),
]


@app.callback()
def main() -> None:
    """Expose approval export through an explicit command group."""


@app.command("export")
def export_command(
    worksheet: WorksheetOption,
    output: OutputOption,
    limit: LimitOption = 500,
    force: ForceOption = False,
) -> None:
    """Export an exact deterministic subset of accepted automated adjudications."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        batch = export_reviewed_approvals(worksheet, selection_limit=limit)
    except ReviewedApprovalError as exc:
        typer.echo(f"Adjudicated approval export failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    _write_report_atomically(output, batch.to_json())
    typer.echo(
        f"Selected {batch.selected_count} of {batch.source_accepted_count} validated accepted "
        "records for automated acquisition. Held and rejected records were excluded."
    )


if __name__ == "__main__":
    app()
