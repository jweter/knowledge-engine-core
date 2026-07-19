"""Standalone CLI for preparing human-review candidate worksheets."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from knowledge_engine.candidate_review import CandidateReviewError, prepare_candidate_review
from knowledge_engine.corpus_readiness_cli import _write_report_atomically

app = typer.Typer(help="Prepare pending-only M14 candidate review worksheets.")

CandidatesOption = Annotated[
    Path,
    typer.Option("--candidates", help="PubMed/PMC discovery JSON path."),
]
OutputOption = Annotated[
    Path,
    typer.Option("--output", help="Pending human-review worksheet JSON path."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Replace an existing worksheet atomically."),
]


@app.command("prepare")
def prepare_command(
    candidates: CandidatesOption,
    output: OutputOption,
    force: ForceOption = False,
) -> None:
    """Create a deterministic worksheet without approving any candidate."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")
    try:
        worksheet = prepare_candidate_review(candidates)
    except CandidateReviewError as exc:
        typer.echo(f"Candidate review preparation failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    _write_report_atomically(output, worksheet.to_json())
    typer.echo(
        f"Prepared {worksheet.candidate_count} pending candidate reviews. "
        "No candidates were approved or promoted."
    )


if __name__ == "__main__":
    app()
