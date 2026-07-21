"""CLI for bounded empirical PDF calibration pilots."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.corpus_readiness_cli import _write_report_atomically
from knowledge_engine.pdf_calibration import PdfCalibrationError, calibrate_pdf_sample

app = typer.Typer(help="Inspect a bounded receipt-backed PDF sample.")
ReceiptOption = Annotated[Path, typer.Option("--receipt")]
PdfDirectoryOption = Annotated[Path, typer.Option("--pdf-directory")]
OutputOption = Annotated[Path, typer.Option("--output")]
ForceOption = Annotated[bool, typer.Option("--force")]


@app.callback()
def main() -> None:
    """Expose PDF calibration inspection through an explicit command group."""


@app.command("inspect")
def inspect_command(
    receipt: ReceiptOption,
    pdf_directory: PdfDirectoryOption,
    output: OutputOption,
    force: ForceOption = False,
) -> None:
    """Inspect 1-4 acquired PDFs and persist a sanitized calibration report."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        report = calibrate_pdf_sample(receipt, pdf_directory)
    except PdfCalibrationError as exc:
        typer.echo(f"PDF calibration failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_report_atomically(output, report.to_json())
    hard_failures = sum(
        finding.severity == "hard_failure" for item in report.items for finding in item.findings
    )
    typer.echo(
        f"Inspected {report.sample_count} PDFs; hard failures: {hard_failures}. "
        "Warnings and review-required findings remain visible in the report."
    )


if __name__ == "__main__":
    app()
