"""Standalone CLI for M14 corpus-readiness validation."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.corpus_readiness import CorpusReadinessError, validate_corpus_readiness

app = typer.Typer(help="Validate a curated corpus before the controlled M14 import.")

ManifestOption = Annotated[
    Path,
    typer.Option("--manifest", help="Curated sources.csv manifest path."),
]
ReceiptOption = Annotated[
    list[Path],
    typer.Option("--receipt", help="Sanitized acquisition receipt; repeat as needed."),
]
PapersDirectoryOption = Annotated[
    Path,
    typer.Option("--papers-dir", help="Local ignored directory containing corpus PDFs."),
]
ExpectedCountOption = Annotated[
    int,
    typer.Option("--expected-count", min=1, help="Required accepted corpus size."),
]
OutputOption = Annotated[
    Path,
    typer.Option("--output", help="Sanitized readiness report path."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite an existing readiness report."),
]


@app.callback()
def main() -> None:
    """Expose readiness validation through an explicit command group."""


@app.command("validate")
def validate_command(
    manifest: ManifestOption,
    receipt: ReceiptOption,
    papers_dir: PapersDirectoryOption,
    output: OutputOption,
    expected_count: ExpectedCountOption = 500,
    force: ForceOption = False,
) -> None:
    """Reconcile manifest rows, receipts, and local PDF evidence exactly."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        report = validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=tuple(receipt),
            papers_directory=papers_dir,
            expected_count=expected_count,
        )
    except CorpusReadinessError as exc:
        typer.echo(f"Corpus readiness failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    _write_report_atomically(output, report.to_json())
    typer.echo(
        f"Corpus ready: {report.accepted_count} manifest rows, "
        f"{report.receipt_count} receipts, {report.file_count} PDFs."
    )


def _write_report_atomically(output: Path, payload: str) -> None:
    """Persist a complete report without exposing partial final evidence."""

    stage = output.with_name(f".{output.name}.tmp")
    stage_created = False
    try:
        if output.parent.is_symlink():
            raise OSError
        output.parent.mkdir(parents=True, exist_ok=True)
        if stage.is_symlink() or stage.exists():
            raise OSError
        with stage.open("x", encoding="utf-8", newline="\n") as handle:
            stage_created = True
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, output)
    except OSError:
        if stage_created:
            with contextlib.suppress(OSError):
                stage.unlink(missing_ok=True)
        raise typer.BadParameter("Readiness report could not be written.") from None


if __name__ == "__main__":
    app()
