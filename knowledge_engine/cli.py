"""Command line interface for Knowledge Engine Core."""

from __future__ import annotations

import csv
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Annotated, Any

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
EvidenceRecordsArgument = Annotated[
    Path,
    typer.Argument(help="JSONL file containing manual evidence records."),
]
SearchLimitOption = Annotated[int, typer.Option("--limit", "-n", min=1, max=100)]
SourcesCsvOption = Annotated[
    Path | None,
    typer.Option(
        "--sources",
        help="Optional corpus sources.csv metadata overlay for display only.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
EvidenceRecordsOption = Annotated[
    Path | None,
    typer.Option(
        "--evidence",
        help="Optional manual evidence JSONL records to preview by DOI.",
    ),
]
RequiredSourcesCsvOption = Annotated[
    Path,
    typer.Option(
        "--sources",
        help="Corpus sources.csv metadata overlay.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
RequiredEvidenceRecordsOption = Annotated[
    Path,
    typer.Option("--evidence", help="Manual evidence JSONL records."),
]
OutputMarkdownOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path for the generated Markdown report."),
]
ForceOutputOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite an existing output file."),
]
ALLOWED_REVIEW_STATUSES = {"draft", "reviewed", "needs_revision", "rejected"}
REQUIRED_EVIDENCE_FIELDS = {
    "schema_version",
    "evidence_record_id",
    "extraction_method",
    "extraction_status",
    "source_doi",
    "source_title",
    "source_type",
    "study_type",
    "research_question",
    "claim_text",
    "evidence_direction",
    "population",
    "intervention",
    "comparator",
    "outcome",
    "result_summary",
    "source_span",
    "limitations",
    "uncertainty_notes",
    "confidence_note",
    "provenance",
    "created_for_milestone",
}
REVIEW_EVIDENCE_FIELDS = {"review_status", "review_checklist", "review_notes"}


@dataclass(frozen=True)
class CorpusSourceMetadata:
    """Curated display metadata loaded from a corpus sources CSV."""

    title: str
    authors: str
    year: str
    journal: str
    doi: str
    source_url: str
    license_type: str


@dataclass(frozen=True)
class EvidenceValidationResult:
    """Result of validating an evidence records JSONL file."""

    records: list[dict[str, Any]]
    errors: list[str]


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
    sources: SourcesCsvOption = None,
    evidence: EvidenceRecordsOption = None,
) -> None:
    """Retrieve papers relevant to a scientific question."""

    database = _database()
    database.initialize()
    fts_query = build_natural_language_fts_query(question)
    metadata_overlay = _load_sources_overlay(sources) if sources else {}
    evidence_by_doi = _load_evidence_records_by_doi(evidence) if evidence else {}

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
        curated = _find_curated_metadata(result, metadata_overlay)
        console.print()
        console.print(f"[bold]{rank}. {_safe_text(_display_title(result, curated))}[/bold]")
        if curated:
            console.print("Metadata source: corpus sources.csv")
            console.print(f"Authors: {_safe_text(curated.authors or 'Unknown')}")
            console.print(f"Journal: {_safe_text(curated.journal or 'Unknown')}")
            console.print(f"Source URL: {_safe_text(curated.source_url or 'Unknown')}")
            console.print(f"License: {_safe_text(curated.license_type or 'Unknown')}")
        console.print(f"Publication year: {_display_year(result, curated)}")
        console.print(f"Matching abstract/snippet: {_safe_text(_best_snippet(result))}")
        console.print(f"Why it matched: {_safe_text(_why_matched(result))}")
        console.print(f"Citation: {_safe_text(_citation(result, curated))}")
        if evidence:
            matched_evidence = _find_evidence_records(result, evidence_by_doi)
            _print_evidence_preview(matched_evidence)

    _print_retrieval_disclaimer()


@app.command()
def evidence(records_path: EvidenceRecordsArgument) -> None:
    """Display manual evidence records from a JSONL file."""

    records = _load_evidence_records(records_path)
    console.print(f"[bold]Evidence records:[/bold] {_safe_text(str(records_path))}")

    for index, record in enumerate(records, start=1):
        record_id = _safe_text(_record_value(record, "evidence_record_id"))
        console.print()
        console.print(f"[bold]{index}. Evidence record: {record_id}[/bold]")
        console.print(
            f"Research question: {_safe_text(_record_value(record, 'research_question'))}"
        )
        console.print(f"Source title: {_safe_text(_record_value(record, 'source_title'))}")
        console.print(f"DOI: {_safe_text(_record_value(record, 'source_doi'))}")
        console.print(f"Study type: {_safe_text(_record_value(record, 'study_type'))}")
        console.print(f"Review status: {_safe_text(_review_status(record))}")
        console.print(f"Review checklist: {_safe_text(_review_checklist_summary(record))}")
        review_notes = _review_notes(record)
        if review_notes:
            console.print(f"Review notes: {_safe_text(review_notes)}")
        console.print(f"Claim text: {_safe_text(_record_value(record, 'claim_text'))}")
        console.print(
            f"Evidence direction: {_safe_text(_record_value(record, 'evidence_direction'))}"
        )
        console.print(f"Population: {_safe_text(_record_value(record, 'population'))}")
        console.print(f"Intervention: {_safe_text(_record_value(record, 'intervention'))}")
        console.print(f"Comparator: {_safe_text(_record_value(record, 'comparator'))}")
        console.print(f"Outcome: {_safe_text(_record_value(record, 'outcome'))}")
        console.print(f"Result summary: {_safe_text(_record_value(record, 'result_summary'))}")
        console.print(f"Limitations: {_safe_text(_format_record_value(record.get('limitations')))}")
        console.print(
            f"Uncertainty notes: {_safe_text(_record_value(record, 'uncertainty_notes'))}"
        )
        console.print(f"Confidence note: {_safe_text(_record_value(record, 'confidence_note'))}")
        console.print(f"Source span: {_safe_text(_format_record_value(record.get('source_span')))}")
        console.print(f"Provenance: {_safe_text(_format_record_value(record.get('provenance')))}")
        console.print(
            f"Extraction method: {_safe_text(_record_value(record, 'extraction_method'))} (manual)"
        )

    console.print()
    console.print("[bold]This is manually extracted evidence.[/bold]")
    console.print("[bold]No scientific synthesis has been performed.[/bold]")


@app.command("evidence-validate")
def evidence_validate(records_path: EvidenceRecordsArgument) -> None:
    """Validate manual evidence records in a JSONL file."""

    result = _validate_evidence_records(records_path, require_review_fields=True)
    if result.errors:
        console.print("[red]Evidence validation failed.[/red]")
        for error in result.errors:
            console.print(f"- {error}")
        raise typer.Exit(1)

    status_counts = Counter(_review_status(record) for record in result.records)
    console.print("[green]Evidence validation passed.[/green]")
    console.print(f"Records: {len(result.records)}")
    console.print(f"Draft: {status_counts['draft']}")
    console.print(f"Reviewed: {status_counts['reviewed']}")
    console.print(f"Needs revision: {status_counts['needs_revision']}")
    console.print(f"Rejected: {status_counts['rejected']}")


@app.command("evidence-report")
def evidence_report(
    question: QuestionArgument,
    sources: RequiredSourcesCsvOption,
    evidence: RequiredEvidenceRecordsOption,
    output: OutputMarkdownOption = None,
    force: ForceOutputOption = False,
    limit: SearchLimitOption = 5,
) -> None:
    """Generate a Markdown retrieval and manual evidence report."""

    if output and output.exists() and not force:
        raise typer.BadParameter(f"Output file already exists: {output}. Use --force to overwrite.")

    database = _database()
    database.initialize()
    metadata_overlay = _load_sources_overlay(sources)
    evidence_by_doi = _load_evidence_records_by_doi(evidence)

    with database.session() as session:
        results = SearchService(session).answer_retrieval(question, limit=limit)

    if not results:
        raise typer.BadParameter("No relevant papers found in the indexed corpus.")

    report = _build_evidence_report(
        question=question,
        results=results,
        metadata_overlay=metadata_overlay,
        evidence_by_doi=evidence_by_doi,
        sources_path=sources,
        evidence_path=evidence,
    )

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        console.print(f"[green]Wrote evidence report:[/green] {output}")
        return

    console.print(report, markup=False)


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


def _display_title(result: SearchResult, curated: CorpusSourceMetadata | None) -> str:
    """Return the title to display for an answer result."""

    return curated.title if curated and curated.title else result.title


def _display_year(result: SearchResult, curated: CorpusSourceMetadata | None) -> str:
    """Return the publication year to display for an answer result."""

    if curated and curated.year:
        return curated.year
    return str(result.publication_year or "Unknown")


def _citation(result: SearchResult, curated: CorpusSourceMetadata | None = None) -> str:
    """Create a simple citation from currently available metadata."""

    title = _display_title(result, curated)
    year = _display_year(result, curated)
    if year == "Unknown":
        year = "n.d."
    doi_value = curated.doi if curated and curated.doi else result.doi
    doi = f" DOI: {doi_value}." if doi_value else ""
    return f"{title} ({year}).{doi}"


def _load_sources_overlay(path: Path) -> dict[str, CorpusSourceMetadata]:
    """Load curated metadata keyed by DOI from a corpus sources CSV."""

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise typer.BadParameter("sources CSV is empty.")
        required_columns = {"doi", "title"}
        missing_columns = sorted(required_columns.difference(reader.fieldnames))
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise typer.BadParameter(f"sources CSV is missing required column(s): {missing}.")

        overlay: dict[str, CorpusSourceMetadata] = {}
        for row in reader:
            doi = (row.get("doi") or "").strip()
            if not doi:
                continue
            overlay[_normalize_doi(doi)] = CorpusSourceMetadata(
                title=(row.get("title") or "").strip(),
                authors=(row.get("authors") or "").strip(),
                year=(row.get("year") or "").strip(),
                journal=(row.get("venue") or "").strip(),
                doi=doi,
                source_url=(row.get("source_url") or "").strip(),
                license_type=(row.get("license_type") or "").strip(),
            )
    return overlay


def _find_curated_metadata(
    result: SearchResult, metadata_overlay: dict[str, CorpusSourceMetadata]
) -> CorpusSourceMetadata | None:
    """Find curated display metadata for a search result."""

    if not result.doi:
        return None
    return metadata_overlay.get(_normalize_doi(result.doi))


def _normalize_doi(doi: str) -> str:
    """Normalize a DOI for metadata overlay matching."""

    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def _load_evidence_records(path: Path) -> list[dict[str, Any]]:
    """Load manual evidence records from a JSONL file."""

    return _load_valid_evidence_records(path, require_review_fields=False)


def _load_valid_evidence_records(
    path: Path, *, require_review_fields: bool
) -> list[dict[str, Any]]:
    """Load evidence records after shared structural validation."""

    result = _validate_evidence_records(path, require_review_fields=require_review_fields)
    if result.errors:
        message = "Evidence validation failed.\n" + "\n".join(result.errors)
        raise typer.BadParameter(message)
    return result.records


def _validate_evidence_records(
    path: Path, *, require_review_fields: bool
) -> EvidenceValidationResult:
    """Validate evidence records for the vertical slice prototype."""

    errors: list[str] = []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if not path.exists():
        return EvidenceValidationResult(
            records=[],
            errors=[f"Evidence records file does not exist: {path}"],
        )

    lines = path.read_text(encoding="utf-8").splitlines()
    if not any(line.strip() for line in lines):
        return EvidenceValidationResult(
            records=[],
            errors=["Evidence records file contains no evidence records."],
        )

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        try:
            record = json.loads(stripped)
        except JSONDecodeError:
            errors.append(f"Line {line_number}: invalid JSON.")
            continue

        if not isinstance(record, dict):
            errors.append(f"Line {line_number}: evidence record must be a JSON object.")
            continue

        records.append(record)
        _validate_evidence_record(
            record,
            line_number,
            seen_ids,
            errors,
            require_review_fields=require_review_fields,
        )

    return EvidenceValidationResult(records=records, errors=errors)


def _validate_evidence_record(
    record: dict[str, Any],
    line_number: int,
    seen_ids: set[str],
    errors: list[str],
    *,
    require_review_fields: bool,
) -> None:
    """Validate one evidence record and append errors."""

    required_fields = REQUIRED_EVIDENCE_FIELDS.copy()
    if require_review_fields:
        required_fields.update(REVIEW_EVIDENCE_FIELDS)
    missing_fields = sorted(required_fields - record.keys())
    if missing_fields:
        missing = ", ".join(missing_fields)
        errors.append(f"Line {line_number}: missing required field(s): {missing}.")

    evidence_id = record.get("evidence_record_id")
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        errors.append(f"Line {line_number}: evidence_record_id is required.")
    elif evidence_id in seen_ids:
        errors.append(f"Line {line_number}: duplicate evidence_record_id: {evidence_id}.")
    else:
        seen_ids.add(evidence_id)

    for field in (
        "source_doi",
        "source_title",
        "research_question",
        "claim_text",
        "evidence_direction",
        "result_summary",
        "extraction_method",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Line {line_number}: {field} is required.")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        errors.append(f"Line {line_number}: provenance must be a non-empty object.")

    review_status = record.get("review_status")
    if require_review_fields and (not isinstance(review_status, str) or not review_status.strip()):
        errors.append(f"Line {line_number}: review_status is required.")
    elif (
        isinstance(review_status, str)
        and review_status
        and review_status not in ALLOWED_REVIEW_STATUSES
    ):
        allowed = ", ".join(sorted(ALLOWED_REVIEW_STATUSES))
        errors.append(
            f"Line {line_number}: invalid review_status '{review_status}'. "
            f"Allowed values: {allowed}."
        )

    review_checklist = record.get("review_checklist")
    if (require_review_fields or review_checklist is not None) and not isinstance(
        review_checklist, dict
    ):
        errors.append(f"Line {line_number}: review_checklist must be an object.")

    review_notes = record.get("review_notes")
    if (require_review_fields or review_notes is not None) and not isinstance(review_notes, str):
        errors.append(f"Line {line_number}: review_notes must be a string.")


def _load_evidence_records_by_doi(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load manual evidence records keyed by normalized source DOI."""

    records_by_doi: dict[str, list[dict[str, Any]]] = {}
    for record in _load_evidence_records(path):
        doi = _record_value(record, "source_doi")
        if doi == "Unknown":
            continue
        records_by_doi.setdefault(_normalize_doi(doi), []).append(record)
    return records_by_doi


def _find_evidence_records(
    result: SearchResult, records_by_doi: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Find manual evidence records for a search result by DOI."""

    if not result.doi:
        return []
    return records_by_doi.get(_normalize_doi(result.doi), [])


def _print_evidence_preview(records: list[dict[str, Any]]) -> None:
    """Print compact manual evidence previews for an answer result."""

    if not records:
        console.print("Reviewed evidence: not available")
        return

    console.print("Reviewed evidence: available")
    for record in records:
        console.print(
            f"  Evidence record ID: {_safe_text(_record_value(record, 'evidence_record_id'))}"
        )
        console.print("  Extraction method: manual")
        console.print(f"  Review status: {_safe_text(_review_status(record))}")
        console.print(f"  Review checklist: {_safe_text(_review_checklist_summary(record))}")
        review_notes = _review_notes(record)
        if review_notes:
            console.print(f"  Review notes: {_safe_text(review_notes)}")
        console.print(
            f"  Evidence direction: {_safe_text(_record_value(record, 'evidence_direction'))}"
        )
        console.print(f"  Claim text: {_safe_text(_record_value(record, 'claim_text'))}")
        console.print(f"  Outcome: {_safe_text(_record_value(record, 'outcome'))}")
        console.print(f"  Result summary: {_safe_text(_record_value(record, 'result_summary'))}")
        limitations = _safe_text(_format_record_value(record.get("limitations")))
        console.print(f"  Limitations: {limitations}")
        console.print(
            f"  Uncertainty notes: {_safe_text(_record_value(record, 'uncertainty_notes'))}"
        )
        console.print(f"  Confidence note: {_safe_text(_record_value(record, 'confidence_note'))}")
        source_span = _safe_text(_format_record_value(record.get("source_span")))
        console.print(f"  Source span: {source_span}")


def _build_evidence_report(
    *,
    question: str,
    results: list[SearchResult],
    metadata_overlay: dict[str, CorpusSourceMetadata],
    evidence_by_doi: dict[str, list[dict[str, Any]]],
    sources_path: Path,
    evidence_path: Path,
) -> str:
    """Build a Markdown report from retrieval results and manual evidence."""

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Knowledge Engine Evidence Report",
        "",
        f"Generated: {generated_at}",
        "",
        "## Research Question",
        "",
        question,
        "",
        "## Inputs",
        "",
        f"- Corpus source file: `{sources_path}`",
        f"- Evidence file: `{evidence_path}`",
        "",
        "## Scope",
        "",
        "This report combines retrieval results with curated corpus metadata and "
        "manual evidence records. It is intended for human review.",
        "",
        "This is retrieval plus manually extracted evidence only.",
        "No scientific synthesis has been performed.",
        "",
        "## Retrieved Papers",
        "",
    ]

    for rank, result in enumerate(results, start=1):
        curated = _find_curated_metadata(result, metadata_overlay)
        records = _find_evidence_records(result, evidence_by_doi)
        lines.extend(_report_paper_lines(rank, result, curated, records))

    lines.extend(
        [
            "## Final Disclaimer",
            "",
            "This report is retrieval plus manually extracted evidence only.",
            "No scientific synthesis has been performed.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_paper_lines(
    rank: int,
    result: SearchResult,
    curated: CorpusSourceMetadata | None,
    records: list[dict[str, Any]],
) -> list[str]:
    """Build Markdown lines for one retrieved paper."""

    lines = [
        f"### {rank}. {_report_text(_display_title(result, curated))}",
        "",
        f"- Rank: {rank}",
        f"- Title: {_report_text(_display_title(result, curated))}",
        f"- Authors: {_report_text(_report_authors(curated))}",
        f"- Year: {_report_text(_display_year(result, curated))}",
        f"- Journal: {_report_text(_report_journal(curated))}",
        f"- DOI: {_report_text(_report_doi(result, curated))}",
        f"- Source URL: {_report_text(_report_source_url(curated))}",
        f"- License type: {_report_text(_report_license(curated))}",
        f"- Metadata source: {_report_metadata_source(curated)}",
        f"- Retrieval snippet: {_report_text(_best_snippet(result))}",
        f"- Citation: {_report_text(_citation(result, curated))}",
        f"- Reviewed evidence: {'available' if records else 'not available'}",
        "",
    ]

    for record in records:
        lines.extend(_report_evidence_lines(record))

    return lines


def _report_evidence_lines(record: dict[str, Any]) -> list[str]:
    """Build Markdown lines for one manual evidence record."""

    return [
        "#### Manual Evidence Record",
        "",
        f"- Evidence record ID: {_report_record_value(record, 'evidence_record_id')}",
        f"- Extraction method: {_report_record_value(record, 'extraction_method')} (manual)",
        f"- Review status: {_report_text(_review_status(record))}",
        f"- Review checklist: {_report_text(_review_checklist_summary(record))}",
        f"- Review notes: {_report_text(_review_notes(record) or 'None')}",
        f"- Evidence direction: {_report_record_value(record, 'evidence_direction')}",
        f"- Claim text: {_report_record_value(record, 'claim_text')}",
        f"- Population: {_report_record_value(record, 'population')}",
        f"- Intervention: {_report_record_value(record, 'intervention')}",
        f"- Comparator: {_report_record_value(record, 'comparator')}",
        f"- Outcome: {_report_record_value(record, 'outcome')}",
        f"- Result summary: {_report_record_value(record, 'result_summary')}",
        f"- Limitations: {_report_text(_format_record_value(record.get('limitations')))}",
        f"- Uncertainty notes: {_report_record_value(record, 'uncertainty_notes')}",
        f"- Confidence note: {_report_record_value(record, 'confidence_note')}",
        f"- Source span: {_report_text(_format_record_value(record.get('source_span')))}",
        f"- Provenance summary: {_report_text(_format_record_value(record.get('provenance')))}",
        "",
    ]


def _report_text(value: str) -> str:
    """Normalize text for Markdown report output."""

    return _safe_text(value)


def _report_record_value(record: dict[str, Any], key: str) -> str:
    """Return a normalized evidence record value for Markdown report output."""

    return _report_text(_record_value(record, key))


def _review_status(record: dict[str, Any]) -> str:
    """Return the manual review status for an evidence record."""

    value = record.get("review_status")
    if not isinstance(value, str) or not value.strip():
        return "unspecified"
    return value.strip()


def _review_checklist_summary(record: dict[str, Any]) -> str:
    """Summarize the manual review checklist for display."""

    checklist = record.get("review_checklist")
    if not isinstance(checklist, dict) or not checklist:
        return "not recorded"

    labels = {
        "source_verified": "source verified",
        "doi_verified": "DOI verified",
        "manual_extraction_labeled": "manual extraction labeled",
        "source_span_present": "source span present",
        "limitations_recorded": "limitations recorded",
        "uncertainty_recorded": "uncertainty recorded",
        "no_synthesis_language": "no synthesis language",
        "ready_for_secondary_review": "secondary review",
    }
    completed = [
        labels.get(key, key.replace("_", " "))
        for key, value in checklist.items()
        if isinstance(value, bool) and value
    ]
    incomplete = [
        labels.get(key, key.replace("_", " "))
        for key, value in checklist.items()
        if isinstance(value, bool) and not value
    ]

    parts: list[str] = []
    if completed:
        parts.append(", ".join(completed))
    if incomplete:
        parts.append(f"needs {', '.join(incomplete)}")
    return "; ".join(parts) if parts else "not recorded"


def _review_notes(record: dict[str, Any]) -> str | None:
    """Return optional manual review notes."""

    value = record.get("review_notes")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _report_authors(curated: CorpusSourceMetadata | None) -> str:
    return curated.authors if curated and curated.authors else "Unknown"


def _report_journal(curated: CorpusSourceMetadata | None) -> str:
    return curated.journal if curated and curated.journal else "Unknown"


def _report_doi(result: SearchResult, curated: CorpusSourceMetadata | None) -> str:
    if curated and curated.doi:
        return curated.doi
    return result.doi or "Unknown"


def _report_source_url(curated: CorpusSourceMetadata | None) -> str:
    return curated.source_url if curated and curated.source_url else "Unknown"


def _report_license(curated: CorpusSourceMetadata | None) -> str:
    return curated.license_type if curated and curated.license_type else "Unknown"


def _report_metadata_source(curated: CorpusSourceMetadata | None) -> str:
    return "corpus sources.csv" if curated else "database record"


def _record_value(record: dict[str, Any], key: str) -> str:
    """Return a string value from an evidence record."""

    return _format_record_value(record.get(key))


def _format_record_value(value: Any) -> str:
    """Format evidence record values for CLI display."""

    if value is None or value == "":
        return "Unknown"
    if isinstance(value, list):
        return "; ".join(_format_record_value(item) for item in value)
    if isinstance(value, dict):
        parts = [f"{key}: {_format_record_value(item)}" for key, item in value.items()]
        return "; ".join(parts)
    return str(value)


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
