"""CLI for exporting manifest-shaped curation drafts."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.corpus_readiness_cli import _write_report_atomically
from knowledge_engine.manifest_curation import ManifestCurationError, export_manifest_curation_draft

app = typer.Typer(help="Export reconciled M14 manifest curation drafts.")
WorksheetOption = Annotated[Path, typer.Option("--worksheet")]
ReceiptOption = Annotated[Path, typer.Option("--receipt")]
OutputOption = Annotated[Path, typer.Option("--output")]
ForceOption = Annotated[bool, typer.Option("--force")]


@app.command("export")
def export_command(
    worksheet: WorksheetOption,
    receipt: ReceiptOption,
    output: OutputOption,
    force: ForceOption = False,
) -> None:
    """Export a draft for curation without modifying sources.csv."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        draft = export_manifest_curation_draft(worksheet, receipt)
    except ManifestCurationError as exc:
        typer.echo(f"Manifest curation export failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_report_atomically(output, draft.to_csv())
    typer.echo(
        f"Exported {len(draft.rows)} manifest curation rows. "
        "No sources.csv file was modified."
    )


if __name__ == "__main__":
    app()
