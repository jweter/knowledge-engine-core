"""Command line interface for Knowledge Engine Core."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import PyMuPDFParser
from knowledge_engine.search import SearchService

app = typer.Typer(help="Offline scientific paper ingestion and search.")
console = Console()
PdfPathArgument = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]
KeywordOption = Annotated[
    list[str] | None,
    typer.Option("--keyword", "-k", help="Keyword to attach."),
]
SearchQueryArgument = Annotated[str, typer.Argument(help="Keyword or quoted phrase query.")]
SearchLimitOption = Annotated[int, typer.Option("--limit", "-n", min=1, max=100)]


def _database() -> Database:
    settings = build_settings(Path.cwd())
    return Database(settings)


@app.command()
def init() -> None:
    """Initialize the local Knowledge Engine database."""

    database = _database()
    database.initialize()
    console.print(f"[green]Initialized database:[/green] {database.settings.resolved_data_dir}")


@app.command("import")
def import_paper(
    pdf_path: PdfPathArgument,
    keyword: KeywordOption = None,
) -> None:
    """Import a scientific paper PDF."""

    database = _database()
    database.initialize()
    parser = PyMuPDFParser()
    parsed = parser.parse(pdf_path)

    with database.session() as session:
        repository = PaperRepository(session)
        paper = repository.add_parsed_paper(parsed, keywords=keyword or [])
        console.print(f"[green]Imported[/green] #{paper.id}: {paper.title}")
        console.print(f"Pages: {paper.page_count}  Words: {paper.word_count}")


@app.command()
def search(
    query: SearchQueryArgument,
    limit: SearchLimitOption = 10,
) -> None:
    """Search imported papers."""

    database = _database()
    database.initialize()
    with database.session() as session:
        results = SearchService(session).search(query, limit=limit)

    if not results:
        console.print("[yellow]No matching papers found.[/yellow]")
        return

    table = Table(title=f"Search results for: {query}")
    table.add_column("ID", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Title")
    table.add_column("Snippet")
    for result in results:
        table.add_row(
            str(result.paper_id),
            f"{result.score:.3f}",
            result.title,
            result.snippet,
        )
    console.print(table)


@app.command("list")
def list_papers() -> None:
    """List imported papers."""

    database = _database()
    database.initialize()
    with database.session() as session:
        papers = PaperRepository(session).list_papers()

    table = Table(title="Imported papers")
    table.add_column("ID", justify="right")
    table.add_column("Title")
    table.add_column("Authors")
    table.add_column("Pages", justify="right")
    table.add_column("Words", justify="right")
    for paper in papers:
        authors = ", ".join(link.author.name for link in paper.author_links) or "-"
        table.add_row(
            str(paper.id),
            paper.title,
            authors,
            str(paper.page_count),
            str(paper.word_count),
        )
    console.print(table)


@app.command()
def stats() -> None:
    """Show local collection statistics."""

    database = _database()
    database.initialize()
    with database.session() as session:
        collection_stats = PaperRepository(session).stats()

    table = Table(title="Knowledge Engine Core stats")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in collection_stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


if __name__ == "__main__":
    app()
