"""Executable CLI entrypoint with explicit external and reporting commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.markup import escape
from rich.table import Table

from knowledge_engine.cli import app as app
from knowledge_engine.cli import console
from knowledge_engine.config import build_settings
from knowledge_engine.corpus_library import export_corpus_library, import_corpus_library
from knowledge_engine.crossref_http import UrllibCrossrefTransport
from knowledge_engine.crossref_provider import CrossrefProvider
from knowledge_engine.database import Database, ExtractionRunRepository, PaperRepository
from knowledge_engine.extraction import (
    CLAIM_CANDIDATE_RULES_VERSION,
    CLAIM_FRAMING_RULES_VERSION,
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    PICO_EXTRACTION_RULES_VERSION,
    SECTION_DETECTION_RULES_VERSION,
    STUDY_DESIGN_RULES_VERSION,
    build_draft_evidence_items,
    classify_claim_framing,
    classify_study_type,
    detect_claim_candidates,
    detect_sections,
    extract_limitations,
    extract_pico,
)
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.reporting import render_import_run_report
from knowledge_engine.metadata_enrichment import MetadataProvider, MetadataQuery
from knowledge_engine.models import ImportRun, Paper, PaperPage
from knowledge_engine.ncbi_http import UrllibNcbiTransport
from knowledge_engine.paper_pages_backfill import backfill_paper
from knowledge_engine.parser import ParsedPage, PyMuPDFParser
from knowledge_engine.pmc_acquisition import (
    AcquisitionError,
    AcquisitionReceipt,
    AcquisitionTransport,
    PmcOaAcquisitionService,
)
from knowledge_engine.pubmed_discovery import (
    GetTransport,
    NcbiDiscoveryError,
    PubmedPmcDiscoveryService,
)
from knowledge_engine.vector_search import (
    FaissVectorIndex,
    VectorSearchError,
    load_external_vectors,
)

DoiOption = Annotated[str, typer.Option("--doi", help="DOI to query.")]
ProviderOption = Annotated[
    str,
    typer.Option("--provider", help="External metadata provider. Currently: crossref."),
]
ImportRunIdArgument = Annotated[
    str,
    typer.Argument(help="Import run UUID to report."),
]
ReportOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path for the generated Markdown report."),
]
ForceOutputOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite an existing output file."),
]
PubmedQueryOption = Annotated[
    str,
    typer.Option("--query", help="PubMed search expression."),
]
CandidateOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for reviewable candidate JSON."),
]
CandidateLimitOption = Annotated[
    int,
    typer.Option("--limit", min=1, max=100, help="Maximum candidates in this page."),
]
CandidateRetstartOption = Annotated[
    int,
    typer.Option("--retstart", min=0, help="Zero-based PubMed page offset."),
]
CandidatesPathOption = Annotated[
    Path,
    typer.Option("--candidates", help="Reviewed PubMed candidate JSON path."),
]
ApprovalsPathOption = Annotated[
    Path,
    typer.Option("--approvals", help="Explicit operator approval JSON path."),
]
PapersDirectoryOption = Annotated[
    Path,
    typer.Option("--papers-dir", help="Ignored local directory for approved PDFs."),
]
ReceiptOutputOption = Annotated[
    Path,
    typer.Option("--receipt", help="Path for the sanitized acquisition receipt."),
]
PaperIdOption = Annotated[
    int,
    typer.Option("--paper-id", help="Persisted paper's database ID."),
]
ExtractionReviewOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the JSONL draft extraction review queue."),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Report what would happen without writing anything."),
]
CorpusLibraryOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the new corpus-library snapshot file."),
]
CorpusLibraryInputOption = Annotated[
    Path,
    typer.Option("--input", help="Corpus-library snapshot file to import."),
]
EmbeddingVectorsOption = Annotated[
    Path,
    typer.Option(
        "--vectors",
        help="JSONL file of externally-generated paper embeddings.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
EmbeddingIndexPathOption = Annotated[
    Path,
    typer.Option("--index-path", help="Local FAISS index file to create or update."),
]
ExistingEmbeddingIndexPathOption = Annotated[
    Path,
    typer.Option(
        "--index-path",
        help="Local FAISS index file to search.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
QueryVectorOption = Annotated[
    Path,
    typer.Option(
        "--query-vector",
        help="JSON file containing an already-embedded query vector.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
VectorSearchLimitOption = Annotated[int, typer.Option("--limit", "-n", min=1, max=100)]


def _crossref_provider() -> MetadataProvider:
    """Build the production Crossref provider only for an explicit preview request."""

    return CrossrefProvider(transport=UrllibCrossrefTransport())


def _pubmed_discovery_service() -> PubmedPmcDiscoveryService:
    """Build the production NCBI discovery service for an explicit command."""

    transport = cast(GetTransport, UrllibNcbiTransport())
    return PubmedPmcDiscoveryService(transport)


def _pmc_acquisition_service() -> PmcOaAcquisitionService:
    """Build the production approval-gated PMC acquisition service."""

    transport = cast(AcquisitionTransport, UrllibNcbiTransport())
    return PmcOaAcquisitionService(transport)


def _local_database() -> Database:
    """Build the local database used by read-only reporting and review commands."""

    return Database(build_settings(Path.cwd()))


def _load_report_run(import_run_id: str) -> ImportRun | None:
    """Load one persisted run with its report relationships."""

    database = _local_database()
    database.initialize()
    with database.session() as session:
        return ImportRunService(
            session,
            project_root=database.settings.project_root,
        ).get_run(import_run_id)


def _load_paper_pages(paper_id: int) -> tuple[Paper, list[ParsedPage]] | None:
    """Load one persisted paper and its pages, converted for extraction.

    Returns None if the paper does not exist. The returned Paper is detached
    from its session -- only its already-loaded scalar attributes
    (id/doi/title) are safe to read afterward.
    """

    database = _local_database()
    database.initialize()
    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        if paper is None:
            return None
        pages = [ParsedPage(page_number=page.page_number, text=page.text) for page in paper.pages]
        session.expunge(paper)
        return paper, pages


def _record_extraction_run(
    *,
    paper_id: int,
    output_path: Path,
    page_count: int,
    section_count: int,
    candidate_count: int,
    draft_item_count: int,
) -> None:
    """Persist a durable record of one `extraction-review-generate` invocation.

    Never re-runs or re-triggers anything -- purely observational, so a
    paper's extraction history can be found later without re-reading every
    JSONL file the command has ever produced.
    """

    database = _local_database()
    database.initialize()
    with database.session() as session:
        ExtractionRunRepository(session).create(
            paper_id=paper_id,
            output_path=str(output_path),
            page_count=page_count,
            section_count=section_count,
            candidate_count=candidate_count,
            draft_item_count=draft_item_count,
            section_detection_rules_version=SECTION_DETECTION_RULES_VERSION,
            claim_candidate_rules_version=CLAIM_CANDIDATE_RULES_VERSION,
            claim_framing_rules_version=CLAIM_FRAMING_RULES_VERSION,
            draft_evidence_item_rules_version=DRAFT_EVIDENCE_ITEM_RULES_VERSION,
            study_design_rules_version=STUDY_DESIGN_RULES_VERSION,
            pico_extraction_rules_version=PICO_EXTRACTION_RULES_VERSION,
        )


def _validate_output(output: Path, *, force: bool) -> None:
    """Reject symbolic links and accidental overwrites before external or database access."""

    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output file already exists. Use --force to overwrite.")


def _write_output(output: Path, content: str) -> None:
    """Write text while keeping local filesystem details out of CLI errors."""

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    except OSError:
        raise typer.BadParameter("Output file could not be written.") from None


def _rollback_acquired_files(
    output_directory: Path,
    receipt: AcquisitionReceipt,
) -> None:
    """Remove files from a completed batch when its receipt cannot be persisted."""

    rollback_failed = False
    for item in receipt.items:
        try:
            (output_directory / item.filename).unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise typer.BadParameter(
            "Receipt output failed and acquired PDFs could not be fully rolled back."
        )


@app.command("metadata-preview")
def metadata_preview(
    doi: DoiOption,
    provider: ProviderOption = "crossref",
) -> None:
    """Preview external metadata candidates without persistence or promotion."""

    normalized_provider = provider.strip().casefold()
    if normalized_provider != "crossref":
        raise typer.BadParameter("Unsupported metadata provider. Expected: crossref.")
    try:
        query = MetadataQuery(doi=doi)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(
        "[yellow]Network access:[/yellow] querying Crossref over HTTPS for metadata candidates."
    )
    result = _crossref_provider().lookup(query)

    if result.candidates:
        table = Table(title="External metadata candidates")
        table.add_column("Field")
        table.add_column("Value")
        table.add_column("Normalized")
        table.add_column("Provider record")
        for candidate in result.candidates:
            table.add_row(
                candidate.field,
                escape(candidate.value),
                escape(candidate.normalized_value),
                escape(candidate.provider_record_id or "-"),
            )
        console.print(table)
        console.print(
            "[bold]Candidates are evidence only; no metadata was persisted or promoted.[/bold]"
        )
        return

    diagnostic = result.diagnostics[0] if result.diagnostics else None
    if diagnostic is None:
        console.print("[yellow]Crossref returned no metadata candidates.[/yellow]")
        return
    if diagnostic.code == "no_match":
        console.print(f"[yellow]No match:[/yellow] {escape(diagnostic.message)}")
        return

    retry_note = " Retry may succeed later." if diagnostic.retryable else ""
    console.print(
        f"[red]Provider failure ({diagnostic.code}):[/red] {escape(diagnostic.message)}{retry_note}"
    )
    raise typer.Exit(1)


@app.command("pubmed-candidate-discover")
def pubmed_candidate_discover(
    query: PubmedQueryOption,
    output: CandidateOutputOption,
    limit: CandidateLimitOption = 25,
    retstart: CandidateRetstartOption = 0,
    force: ForceOutputOption = False,
) -> None:
    """Discover reviewable PubMed candidates and PMC OA evidence without downloading PDFs."""

    _validate_output(output, force=force)
    console.print(
        "[yellow]Network access:[/yellow] querying official PubMed and PMC services over HTTPS."
    )
    try:
        result = _pubmed_discovery_service().discover(
            query,
            limit=limit,
            retstart=retstart,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except NcbiDiscoveryError as exc:
        console.print(f"[red]NCBI discovery failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, result.to_json())
    verified = sum(candidate.open_access for candidate in result.candidates)
    console.print(
        f"[green]Wrote {len(result.candidates)} candidates:[/green] {output} "
        f"({verified} PMC OA verified)."
    )
    console.print(
        "[bold]Candidates require human inclusion and license review; "
        "no PDFs were downloaded.[/bold]"
    )


@app.command("pmc-oa-acquire")
def pmc_oa_acquire(
    candidates: CandidatesPathOption,
    approvals: ApprovalsPathOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Acquire only explicitly approved PMC OA PDFs and write a sanitized receipt."""

    _validate_output(receipt, force=force)
    console.print(
        "[yellow]Network access:[/yellow] acquiring explicitly approved PDFs "
        "from official PMC OA resources."
    )
    try:
        result = _pmc_acquisition_service().acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=papers_dir,
        )
    except AcquisitionError as exc:
        console.print(f"[red]PMC OA acquisition failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    try:
        _write_output(receipt, result.to_json())
    except typer.BadParameter:
        _rollback_acquired_files(papers_dir, result)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs were rolled back."
        ) from None
    console.print(
        f"[green]Acquired {result.acquired_count} approved PMC OA PDFs.[/green] Receipt: {receipt}"
    )
    console.print(
        "[bold]Approval evidence was cross-checked exactly; no manifest rows were promoted.[/bold]"
    )


@app.command("corpus-run-report")
def corpus_run_report(
    import_run_id: ImportRunIdArgument,
    output: ReportOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Render a sanitized Markdown report for a persisted import run."""

    if output:
        _validate_output(output, force=force)

    run = _load_report_run(import_run_id)
    if run is None:
        console.print(f"[red]Unknown import run:[/red] {escape(import_run_id)}")
        raise typer.Exit(1)

    try:
        report = render_import_run_report(run)
    except ValueError as exc:
        raise typer.BadParameter(f"Import run report reconciliation failed: {exc}") from exc

    if output:
        _write_output(output, report)
        console.print(f"[green]Wrote corpus run report:[/green] {output}")
        return

    console.print(report, markup=False)


@app.command("extraction-review-generate")
def extraction_review_generate(
    paper_id: PaperIdOption,
    output: ExtractionReviewOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Run deterministic claim extraction against one persisted paper and
    write a draft extraction review queue -- not validated evidence."""

    _validate_output(output, force=force)

    loaded = _load_paper_pages(paper_id)
    if loaded is None:
        console.print(f"[red]Unknown paper ID:[/red] {paper_id}")
        raise typer.Exit(1)
    paper, pages = loaded

    if not pages:
        console.print(
            f"[red]Paper {paper_id} has no persisted pages.[/red] Extraction requires "
            "page-level provenance (added in M15); this paper predates that migration "
            "or was never fully imported. No output was written."
        )
        raise typer.Exit(1)

    sections = detect_sections(pages)
    candidates = detect_claim_candidates(pages, sections)
    framings = classify_claim_framing(candidates)
    study_type = classify_study_type(pages, sections)
    limitations = extract_limitations(pages, sections)
    pico = extract_pico(pages, sections)
    paper_metadata = PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title)
    items = build_draft_evidence_items(
        paper_metadata,
        framings,
        study_type=study_type,
        limitations=limitations,
        study_design_rules_version=STUDY_DESIGN_RULES_VERSION,
        population=pico.population,
        intervention=pico.intervention,
        comparator=pico.comparator,
        outcome=pico.outcome,
        pico_extraction_rules_version=pico.rules_version,
    )

    lines = [json.dumps(item.to_dict()) for item in items]
    _write_output(output, "\n".join(lines) + ("\n" if lines else ""))

    try:
        _record_extraction_run(
            paper_id=paper.id,
            output_path=output,
            page_count=len(pages),
            section_count=len(sections),
            candidate_count=len(candidates),
            draft_item_count=len(items),
        )
    except Exception:
        output.unlink(missing_ok=True)
        console.print(
            "[red]Extraction run could not be recorded.[/red] The draft output file was "
            "removed so a retry starts cleanly, rather than leaving an unrecorded review "
            "queue behind."
        )
        raise typer.Exit(1) from None

    pico_detected = ", ".join(
        field
        for field, value in (
            ("population", pico.population),
            ("intervention", pico.intervention),
            ("comparator", pico.comparator),
            ("outcome", pico.outcome),
        )
        if value
    )
    console.print(
        f"[green]Wrote {len(items)} draft evidence item(s):[/green] {output} "
        f"({len(pages)} page(s), {len(sections)} section(s), {len(candidates)} candidate(s), "
        f"study_type: {study_type or 'not detected'}, "
        f"limitations: {'detected' if limitations else 'not detected'}, "
        f"PICO fields detected: {pico_detected or 'none'})."
    )
    console.print(
        "[bold]Draft items are a review queue, not validated evidence -- "
        "research_question and evidence_direction require human completion. "
        "study_type, limitations, and population/intervention/comparator/outcome are "
        "populated automatically when detected, never guessed.[/bold]"
    )


@app.command("paper-pages-backfill")
def paper_pages_backfill(dry_run: DryRunOption = False) -> None:
    """Backfill paper_pages rows for papers imported before M15.

    Only papers whose original local PDF is still present, and whose
    freshly re-parsed content hash matches the persisted one, are
    backfilled. A missing or changed source file is reported, never
    silently skipped.
    """

    database = _local_database()
    database.initialize()
    parser = PyMuPDFParser()

    counts: dict[str, int] = {}
    with database.session() as session:
        repository = PaperRepository(session)
        papers = repository.list_papers_without_pages()

        if not papers:
            console.print("[green]No papers need backfilling.[/green]")
            return

        for paper in papers:
            outcome, parsed = backfill_paper(paper, parser)
            counts[outcome.status] = counts.get(outcome.status, 0) + 1

            if outcome.status == "backfilled" and parsed is not None:
                if not dry_run:
                    paper.pages = [
                        PaperPage(page_number=page.page_number, text=page.text)
                        for page in parsed.pages
                    ]
                console.print(f"[green]Backfilled paper {paper.id}:[/green] {escape(paper.title)}")
            else:
                console.print(
                    f"[yellow]Skipped paper {paper.id} ({outcome.status}):[/yellow] "
                    f"{escape(outcome.detail or '')}"
                )

    prefix = "[bold]Dry run --[/bold] no changes were written. " if dry_run else ""
    console.print(
        f"{prefix}Backfilled: {counts.get('backfilled', 0)}, "
        f"missing source file: {counts.get('missing_source_file', 0)}, "
        f"hash mismatch: {counts.get('hash_mismatch', 0)}, "
        f"parse failed: {counts.get('parse_failed', 0)}."
    )
    if counts.get("backfilled", 0) < len(papers):
        raise typer.Exit(1)


@app.command("corpus-library-export")
def corpus_library_export(output: CorpusLibraryOutputOption) -> None:
    """Export the local database's corpus content to a standalone snapshot.

    Only paper-intrinsic content is copied (papers, their extracted pages
    and text, journals, authors, keywords) -- never operational history like
    import runs or extraction runs. The output file must not already exist.
    """

    database = _local_database()
    database.initialize()
    try:
        summary = export_corpus_library(database.engine, output)
    except FileExistsError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Exported corpus library:[/green] {output} "
        f"({summary.paper_count} paper(s), {summary.journal_count} journal(s), "
        f"{summary.author_count} author(s), {summary.keyword_count} keyword(s))."
    )


@app.command("corpus-library-import")
def corpus_library_import(input_path: CorpusLibraryInputOption) -> None:
    """Hydrate the local database's corpus content from a snapshot.

    A paper whose content hash already exists locally is skipped, so
    importing the same or an overlapping snapshot twice is idempotent.
    """

    database = _local_database()
    database.initialize()
    try:
        with database.session() as session:
            summary = import_corpus_library(session, input_path)
    except FileNotFoundError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Imported corpus library:[/green] {summary.imported_paper_count} paper(s) "
        f"imported, {summary.skipped_existing_paper_count} already present and skipped."
    )


@app.command("embedding-index-build")
def embedding_index_build(
    vectors: EmbeddingVectorsOption,
    index_path: EmbeddingIndexPathOption,
) -> None:
    """Build or update a local FAISS vector index from externally-generated embeddings.

    Phase 3's option 3 (see docs/phase3_design.md's Open Questions): no
    embedding-generation code exists in this project yet, so this command
    ingests vectors an external tool already computed rather than
    generating them itself. Every referenced paper_id must already exist
    in the local database; a dangling reference is reported, never
    silently skipped. Re-running against the same paper_id replaces its
    vector rather than duplicating it.
    """

    result = load_external_vectors(vectors)
    if result.errors:
        console.print(f"[red]Vectors file is invalid:[/red] {vectors}")
        for error in result.errors:
            console.print(f"- {escape(error)}")
        raise typer.Exit(1)

    requested_ids = [record.paper_id for record in result.records]
    database = _local_database()
    database.initialize()
    with database.session() as session:
        repository = PaperRepository(session)
        found_ids = {paper.id for paper in repository.get_many(requested_ids)}
        missing_ids = sorted(set(requested_ids) - found_ids)
        if missing_ids:
            missing = ", ".join(str(paper_id) for paper_id in missing_ids)
            console.print(f"[red]Vectors reference unknown paper ID(s):[/red] {missing}")
            raise typer.Exit(1)

        assert result.dimension is not None  # non-empty records guarantee a dimension
        try:
            index = (
                FaissVectorIndex.load(index_path, dimension=result.dimension)
                if index_path.exists()
                else FaissVectorIndex(result.dimension)
            )
        except VectorSearchError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(1) from None

        for record in result.records:
            index.add(record.paper_id, record.vector)
            repository.set_embedding(
                record.paper_id,
                embedding_model=record.embedding_model,
                embedding_id=str(record.paper_id),
            )

        index.save(index_path)

    console.print(
        f"[green]Indexed {len(result.records)} vector(s):[/green] {index_path} "
        f"(dimension {result.dimension}, index size {index.size})."
    )


@app.command("vector-search")
def vector_search(
    index_path: ExistingEmbeddingIndexPathOption,
    query_vector: QueryVectorOption,
    limit: VectorSearchLimitOption = 10,
) -> None:
    """Search a local FAISS vector index by an already-embedded query vector.

    Does not accept a free-text query -- no EmbeddingGenerator exists yet
    (see docs/phase3_design.md's Open Questions). The caller supplies an
    already-embedded query vector, for example from any external
    embedding tool, as a JSON file (`{"vector": [...]}` or a bare array).
    Lexical search remains available via `ke search`; this command is an
    additional, separate retrieval signal, not a replacement.
    """

    try:
        payload = json.loads(query_vector.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        console.print(f"[red]Query vector file is not valid JSON:[/red] {query_vector}")
        raise typer.Exit(1) from None

    vector = payload.get("vector") if isinstance(payload, dict) else payload
    if (
        not isinstance(vector, list)
        or not vector
        or not all(
            isinstance(component, int | float) and not isinstance(component, bool)
            for component in vector
        )
    ):
        console.print(
            "[red]Query vector file must contain a non-empty array of numbers "
            '(a bare array or {"vector": [...]}).[/red]'
        )
        raise typer.Exit(1)

    try:
        index = FaissVectorIndex.load(index_path, dimension=len(vector))
    except VectorSearchError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    matches = index.search([float(component) for component in vector], k=limit)
    if not matches:
        console.print("[yellow]No matches found in the vector index.[/yellow]")
        return

    database = _local_database()
    database.initialize()
    with database.session() as session:
        repository = PaperRepository(session)
        papers_by_id = {
            paper.id: paper for paper in repository.get_many([match.vector_id for match in matches])
        }

    console.print(f"[bold]Vector search results:[/bold] {index_path}")
    for rank, match in enumerate(matches, start=1):
        paper = papers_by_id.get(match.vector_id)
        title = escape(paper.title) if paper else "Unknown paper (not in local database)"
        console.print()
        console.print(f"[bold]{rank}. {title}[/bold]")
        console.print(f"Paper ID: {match.vector_id}")
        console.print(f"Score (squared L2 distance, lower = more similar): {match.score:.4f}")
        if paper:
            console.print(f"DOI: {escape(paper.doi or 'Unknown')}")

    console.print()
    console.print(
        "[bold]This is vector similarity only, not lexical search and not scientific "
        "synthesis.[/bold]"
    )
