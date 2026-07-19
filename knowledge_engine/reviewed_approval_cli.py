"""Standalone CLI for exporting completed reviews to acquisition approvals."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.corpus_readiness_cli import _write_report_atomically
from knowledge_engine.reviewed_approval import ReviewedApprovalError, export_reviewed_approvals

app = typer.Typer(help="Export fully reviewed M14 candidates to acquisition approvals.")

WorksheetOption = Annotated[
    Path,
    typer.Option("--worksheet", help="Completed candidate review worksheet JSON path."),
]
OutputOption = Annotated[
    Path,
    typer.Option("--output", help="PMC acquisition approval JSON path."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Replace an existing approval file atomically."),
]


@app.command("export")
def export_command(
    worksheet: WorksheetOption,
    output: OutputOption,
    force: ForceOption = False,
) -> None:
    """Export accepted completed reviews without making approval decisions."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        batch = export_reviewed_approvals(worksheet)
    except ReviewedApprovalError as exc:
        typer.echo(f"Reviewed approval export failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    _write_report_atomically(output, batch.to_json())
    typer.echo(
        f"Exported {len(batch.approvals)} reviewed acquisition approvals. "
        "No review decisions were created or changed."
    )


if __name__ == "__main__":
    app()
