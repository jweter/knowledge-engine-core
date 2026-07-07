"""Command line interface for Knowledge Engine Core."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import PyMuPDFParser
from knowledge_engine.search import SearchResult, SearchService, build_natural_language_fts_query

app = typer.Typer(help="Offline scientific paper ingestion and search.")
console = Console()
PdfPathArgument = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]
KeywordOption = Annotated[
    list[str] | None,
    typer.Option("--keyword", "-k", help="Keyword to attach."),
]
SearchQueryArgument = Annotated[str, typer.Argument(help="Keyword or quoted phrase query.")]
QuestionArgument = Annotated[str, typer.Argument(help="Natural-language scientific question.")]
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
            _safe_text(result.title),
            _safe_text(result.snippet),
        )
    console.print(table)


@app.command()
def answer(
    question: QuestionArgument,
    limit: SearchLimitOption = 5,
) -> None:
    """Retrieve papers relevant to a scientific question."""

    database = _database()
    database.initialize()
    fts_query = build_natural_language_fts_query(question)

    with database.session() as session:
        results = SearchService(session).answer_retrieval(question, limit=limit)

    console.print(f"[bold]Question:[/bold] {_safe_text(question)}")
    if fts_query:
        console.print(f"[bold]Retrieval query:[/bold] {fts_query}")

    if not results:
        console.print("[yellow]No relevant papers found in the indexed corpus.[/yellow]")
        _print_retrieval_disclaimer()
        return

    console.print()
    console.print("[bold]Relevant papers[/bold]")
    for rank, result in enumerate(results, start=1):
        console.print()
        console.print(f"[bold]{rank}. {_safe_text(result.title)}[/bold]")
        console.print(f"Publication year: {result.publication_year or 'Unknown'}")
        console.print(f"Matching abstract/snippet: {_safe_text(_best_snippet(result))}")
        console.print(f"Why it matched: {_safe_text(_why_matched(result))}")
        console.print(f"Citation: {_safe_text(_citation(result))}")

    _print_retrieval_disclaimer()


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
            _safe_text(paper.title),
            _safe_text(authors),
            str(paper.page_count),
            str(paper.word_count),
        )
    console.print(table)


def _best_snippet(result: SearchResult) -> str:
    """Return the best available short evidence snippet for display."""

    if result.snippet:
        return result.snippet
    if result.abstract:
        return _truncate(result.abstract, max_length=280)
    return "No abstract or snippet available."


def _why_matched(result: SearchResult) -> str:
    """Explain why a paper appeared in answer retrieval."""

    return f"Matched indexed title, abstract, or body text using: {result.matched_query}"


def _citation(result: SearchResult) -> str:
    """Create a simple citation from currently available metadata."""

    year = str(result.publication_year) if result.publication_year else "n.d."
    doi = f" DOI: {result.doi}." if result.doi else ""
    return f"{result.title} ({year}).{doi}"


def _truncate(value: str, max_length: int) -> str:
    """Truncate long text for CLI display."""

    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def _safe_text(value: str) -> str:
    """Normalize extracted PDF text for reliable CLI display."""

    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _print_retrieval_disclaimer() -> None:
    """Print the required retrieval-only disclaimer."""

    console.print()
    console.print("[bold]This is retrieval only.[/bold]")
    console.print("[bold]No scientific synthesis has been performed.[/bold]")


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
