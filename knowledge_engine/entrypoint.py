"""Executable CLI entrypoint with explicit external and reporting commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.markup import escape
from rich.table import Table

from knowledge_engine.cli import app as app
from knowledge_engine.cli import console
from knowledge_engine.config import build_settings
from knowledge_engine.core_candidate_review import (
    CoreCandidateReviewError,
    prepare_core_candidate_review,
)
from knowledge_engine.core_discovery import CoreDiscoveryError, CoreDiscoveryService
from knowledge_engine.core_discovery import GetTransport as CoreGetTransport
from knowledge_engine.core_http import UrllibCoreTransport
from knowledge_engine.corpus_library import (
    export_corpus_library,
    export_corpus_library_compressed,
    import_corpus_library,
    import_corpus_library_compressed,
)
from knowledge_engine.crossref_http import UrllibCrossrefTransport
from knowledge_engine.crossref_provider import CrossrefProvider
from knowledge_engine.database import Database, ExtractionRunRepository, PaperRepository
from knowledge_engine.europepmc_acquisition import (
    AcquisitionTransport as EuropePmcAcquisitionTransport,
)
from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionError,
    EuropePmcAcquisitionReceipt,
    EuropePmcOaAcquisitionService,
)
from knowledge_engine.europepmc_candidate_review import (
    EuropePmcCandidateReviewError,
    prepare_europepmc_candidate_review,
)
from knowledge_engine.europepmc_discovery import (
    EuropePmcDiscoveryError,
    EuropePmcDiscoveryService,
)
from knowledge_engine.europepmc_discovery import GetTransport as EuropePmcGetTransport
from knowledge_engine.europepmc_http import UrllibEuropePmcTransport
from knowledge_engine.extraction import (
    CLAIM_CANDIDATE_RULES_VERSION,
    CLAIM_FRAMING_RULES_VERSION,
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    PICO_EXTRACTION_RULES_VERSION,
    SECTION_DETECTION_RULES_VERSION,
    STUDY_DESIGN_RULES_VERSION,
)
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_annotate import annotate_draft_items
from knowledge_engine.extraction_review_batch import (
    run_batch_extraction_review,
    run_extraction_review_for_paper,
)
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.reporting import render_import_run_report
from knowledge_engine.manual_pdf_preview import (
    ManualPdfPreviewError,
    export_manual_pdf_manifest_draft,
    prepare_manual_pdf_preview,
)
from knowledge_engine.mesh_lookup import GetTransport as MeshLookupGetTransport
from knowledge_engine.mesh_lookup import MeshLookupError, MeshLookupService
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
from knowledge_engine.pubchem_http import UrllibPubchemTransport
from knowledge_engine.pubchem_lookup import GetTransport as PubchemLookupGetTransport
from knowledge_engine.pubchem_lookup import (
    PubchemLookupError,
    PubchemLookupService,
)
from knowledge_engine.pubmed_discovery import (
    GetTransport,
    NcbiDiscoveryError,
    PubmedPmcDiscoveryService,
)
from knowledge_engine.reference_lookup import GetTransport as ReferenceLookupGetTransport
from knowledge_engine.reference_lookup import (
    ReferenceLookupError,
    ReferenceLookupService,
)
from knowledge_engine.reference_lookup_http import UrllibWikipediaTransport
from knowledge_engine.rxnorm_http import UrllibRxNavTransport
from knowledge_engine.rxnorm_lookup import GetTransport as RxNormLookupGetTransport
from knowledge_engine.rxnorm_lookup import (
    RxNormLookupError,
    RxNormLookupService,
)
from knowledge_engine.search import SearchService
from knowledge_engine.search_fusion import fuse_rankings
from knowledge_engine.unpaywall_http import UrllibUnpaywallTransport
from knowledge_engine.unpaywall_lookup import GetTransport as UnpaywallGetTransport
from knowledge_engine.unpaywall_lookup import (
    UnpaywallLookupError,
    UnpaywallLookupService,
    parse_dois_file,
)
from knowledge_engine.vector_search import (
    DEFAULT_LOCAL_MODEL_NAME,
    EmbeddingGenerator,
    FaissVectorIndex,
    LocalEmbeddingError,
    OpenAiEmbeddingError,
    OpenAiEmbeddingGenerator,
    SentenceTransformerEmbeddingGenerator,
    VectorIndexMetadata,
    VectorSearchError,
    load_external_vectors,
    load_index_metadata,
    save_index_metadata,
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
EuropePmcQueryOption = Annotated[
    str,
    typer.Option("--query", help="Europe PMC search expression."),
]
EuropePmcCursorMarkOption = Annotated[
    str,
    typer.Option("--cursor-mark", help="Europe PMC pagination cursor ('*' for the first page)."),
]
EuropePmcReviewCandidatesOption = Annotated[
    Path,
    typer.Option(
        "--candidates",
        help="Europe PMC discovery JSON path.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
CoreQueryOption = Annotated[
    str,
    typer.Option("--query", help="CORE search expression."),
]
CoreOffsetOption = Annotated[
    int,
    typer.Option("--offset", min=0, help="Zero-based CORE page offset."),
]
CoreReviewCandidatesOption = Annotated[
    Path,
    typer.Option(
        "--candidates",
        help="CORE discovery JSON path.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
UnpaywallDoiOption = Annotated[
    str,
    typer.Option("--doi", help="DOI to look up (e.g. from a held candidate)."),
]
UnpaywallDoisFileOption = Annotated[
    Path,
    typer.Option(
        "--dois-file",
        help='JSON file: {"dois": ["10.x/...", ...]} (max 100).',
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
ReferenceLookupTermArgument = Annotated[
    str, typer.Argument(help="A term or mechanism to look up (e.g. 'semaglutide').")
]
ReferenceLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
RxNormLookupTermArgument = Annotated[
    str, typer.Argument(help="A drug name to look up (e.g. 'semaglutide', 'Ozempic').")
]
RxNormLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
MeshLookupTermArgument = Annotated[
    str, typer.Argument(help="A medical term to look up (e.g. 'obesity', 'type 2 diabetes').")
]
MeshLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
PubchemLookupTermArgument = Annotated[
    str, typer.Argument(help="A compound name to look up (e.g. 'metformin', 'empagliflozin').")
]
PubchemLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
ManualPdfPathOption = Annotated[
    Path,
    typer.Option(
        "--pdf",
        help="Local PDF file to preview.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
ManualPdfDoiLookupOption = Annotated[
    bool,
    typer.Option(
        "--doi-lookup",
        help="If a DOI is found, look it up on Unpaywall for OA/license evidence.",
    ),
]
ManualPdfPreviewInputOption = Annotated[
    Path,
    typer.Option(
        "--preview",
        help="Manual PDF preview JSON path.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
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
EuropePmcCandidatesPathOption = Annotated[
    Path,
    typer.Option("--candidates", help="Reviewed Europe PMC candidate JSON path."),
]
EuropePmcApprovalsPathOption = Annotated[
    Path,
    typer.Option("--approvals", help="Explicit operator Europe PMC approval JSON path."),
]
PaperIdOption = Annotated[
    int,
    typer.Option("--paper-id", help="Persisted paper's database ID."),
]
ExtractionReviewOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the JSONL draft extraction review queue."),
]
ExtractionReviewBatchPaperIdsOption = Annotated[
    list[int] | None,
    typer.Option(
        "--paper-id",
        help="Restrict the batch to this paper ID (repeatable; default: every persisted paper).",
    ),
]
ExtractionReviewAnnotateInputOption = Annotated[
    Path,
    typer.Option(
        "--input", help="Draft extraction review JSONL file (from extraction-review-generate)."
    ),
]
ExtractionReviewAnnotateOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the annotated draft extraction review JSONL file."),
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
    Path | None,
    typer.Option(
        "--query-vector",
        help="JSON file containing an already-embedded query vector. Mutually exclusive "
        "with --query-text.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
QueryTextOption = Annotated[
    str | None,
    typer.Option(
        "--query-text",
        help="A free-text query to embed live (via --generator) and search with. "
        "Mutually exclusive with --query-vector.",
    ),
]
VectorSearchGeneratorOption = Annotated[
    str | None,
    typer.Option("--generator", help="Embedding generator for --query-text: 'local' or 'openai'."),
]
VectorSearchModelOption = Annotated[
    str | None,
    typer.Option(
        "--model", help="Override the generator's default model name (used with --query-text)."
    ),
]
VectorSearchLimitOption = Annotated[int, typer.Option("--limit", "-n", min=1, max=100)]
EmbeddingGenerateOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the generated vectors JSONL file."),
]
EmbeddingGeneratorNameOption = Annotated[
    str,
    typer.Option("--generator", help="Embedding generator to use: 'local' or 'openai'."),
]
EmbeddingGenerateModelOption = Annotated[
    str | None,
    typer.Option("--model", help="Override the generator's default model name."),
]
EmbeddingGeneratePaperIdsOption = Annotated[
    list[int] | None,
    typer.Option(
        "--paper-id", help="Restrict generation to this paper ID (repeatable; default: all)."
    ),
]
FusedSearchQueryTextArgument = Annotated[
    str, typer.Argument(help="Free-text query used for both lexical and semantic retrieval.")
]
FusedSearchGeneratorOption = Annotated[
    str,
    typer.Option(
        "--generator", help="Embedding generator for the semantic side: 'local' or 'openai'."
    ),
]
FusedSearchCandidateLimitOption = Annotated[
    int,
    typer.Option(
        "--candidate-limit",
        help="How many results to pull from each of the lexical and semantic rankings "
        "before fusing them.",
        min=1,
        max=200,
    ),
]


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


def _europepmc_acquisition_service() -> EuropePmcOaAcquisitionService:
    """Build the production approval-gated Europe PMC acquisition service."""

    transport = cast(EuropePmcAcquisitionTransport, UrllibEuropePmcTransport())
    return EuropePmcOaAcquisitionService(transport)


def _europepmc_discovery_service() -> EuropePmcDiscoveryService:
    """Build the production Europe PMC discovery service for an explicit command."""

    transport = cast(EuropePmcGetTransport, UrllibEuropePmcTransport())
    return EuropePmcDiscoveryService(transport)


def _core_discovery_service() -> CoreDiscoveryService:
    """Build the production CORE discovery service for an explicit command.

    `KE_CORE_API_KEY` is optional -- CORE's public API works unauthenticated
    at a low rate limit and only raises that limit with a bearer token; see
    `core_discovery.py`'s module docstring.
    """

    transport = cast(CoreGetTransport, UrllibCoreTransport())
    api_key = build_settings(Path.cwd()).core_api_key
    return CoreDiscoveryService(transport, api_key=api_key)


def _unpaywall_lookup_service() -> UnpaywallLookupService:
    """Build the production Unpaywall lookup service for an explicit command.

    Raises `ValueError` if `KE_UNPAYWALL_EMAIL` is unset -- Unpaywall's
    usage policy requires a contact email on every request, and this
    project does not bake in a default contact for every installation.
    """

    email = build_settings(Path.cwd()).unpaywall_email
    if not email:
        raise ValueError(
            "KE_UNPAYWALL_EMAIL is not set. Unpaywall requires a contact email in every request."
        )
    transport = cast(UnpaywallGetTransport, UrllibUnpaywallTransport())
    return UnpaywallLookupService(transport, email=email)


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


def _rollback_europepmc_acquired_files(
    output_directory: Path,
    receipt: EuropePmcAcquisitionReceipt,
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


@app.command("europepmc-candidate-discover")
def europepmc_candidate_discover(
    query: EuropePmcQueryOption,
    output: CandidateOutputOption,
    limit: CandidateLimitOption = 25,
    cursor_mark: EuropePmcCursorMarkOption = "*",
    force: ForceOutputOption = False,
) -> None:
    """Discover reviewable Europe PMC candidates without downloading PDFs.

    The second automated discovery source (M34), alongside
    `pubmed-candidate-discover`. Deliberately scoped to what Europe PMC adds
    beyond PMC: candidates already in PMC are still discovered and reported
    here (never silently dropped), but `europepmc-candidate-review-prepare`
    rejects them as out of this pipeline's scope, since PMC content is
    already reachable through the PubMed/PMC pipeline via NCBI's own
    official S3 bucket.
    """

    _validate_output(output, force=force)
    console.print("[yellow]Network access:[/yellow] querying the official Europe PMC REST API.")
    try:
        result = _europepmc_discovery_service().discover(
            query,
            limit=limit,
            cursor_mark=cursor_mark,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except EuropePmcDiscoveryError as exc:
        console.print(f"[red]Europe PMC discovery failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, result.to_json())
    verified = sum(candidate.open_access for candidate in result.candidates)
    console.print(
        f"[green]Wrote {len(result.candidates)} candidates:[/green] {output} "
        f"({verified} open access)."
    )
    if result.next_cursor_mark is not None:
        console.print(f"Next page: --cursor-mark {result.next_cursor_mark!r}")
    console.print(
        "[bold]Candidates require human inclusion and license review; "
        "no PDFs were downloaded.[/bold]"
    )


@app.command("europepmc-candidate-review-prepare")
def europepmc_candidate_review_prepare(
    candidates: EuropePmcReviewCandidatesOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Create a deterministic Europe PMC adjudication worksheet.

    Never approves or promotes a candidate -- mirrors
    `candidate_review_cli.py`'s "prepare" step for the PubMed/PMC pipeline,
    but as a `ke` subcommand for discoverability.
    """

    _validate_output(output, force=force)
    try:
        worksheet = prepare_europepmc_candidate_review(candidates)
    except EuropePmcCandidateReviewError as exc:
        console.print(
            f"[red]Europe PMC candidate review preparation failed:[/red] {escape(str(exc))}"
        )
        raise typer.Exit(1) from exc

    _write_output(output, worksheet.to_json())
    console.print(
        f"[green]Prepared {worksheet.candidate_count} pending candidate reviews:[/green] {output}. "
        "No candidates were approved or promoted."
    )


@app.command("core-candidate-discover")
def core_candidate_discover(
    query: CoreQueryOption,
    output: CandidateOutputOption,
    limit: CandidateLimitOption = 25,
    offset: CoreOffsetOption = 0,
    force: ForceOutputOption = False,
) -> None:
    """Discover reviewable CORE candidates without downloading PDFs.

    The third automated discovery source (M35), alongside
    `pubmed-candidate-discover` and `europepmc-candidate-discover`. CORE
    aggregates open-access content broadly, well beyond biomedical
    literature. An optional `KE_CORE_API_KEY` raises CORE's low
    unauthenticated rate limit; discovery still works without one.
    """

    _validate_output(output, force=force)
    console.print("[yellow]Network access:[/yellow] querying the official CORE API.")
    try:
        result = _core_discovery_service().discover(
            query,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except CoreDiscoveryError as exc:
        console.print(f"[red]CORE discovery failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, result.to_json())
    console.print(
        f"[green]Wrote {len(result.candidates)} candidates:[/green] {output} "
        f"(of {result.total_hits} total hits)."
    )
    if result.next_offset is not None:
        console.print(f"Next page: --offset {result.next_offset}")
    console.print(
        "[bold]Candidates require human inclusion and license review; "
        "no PDFs were downloaded.[/bold]"
    )


@app.command("core-candidate-review-prepare")
def core_candidate_review_prepare(
    candidates: CoreReviewCandidatesOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Create a deterministic CORE adjudication worksheet.

    Never approves or promotes a candidate. Note: CORE never supplies a
    license field, so every candidate's license rule is
    `"incomplete_missing_license"` and no CORE candidate can auto-accept --
    see `core_candidate_review.py`'s module docstring.
    """

    _validate_output(output, force=force)
    try:
        worksheet = prepare_core_candidate_review(candidates)
    except CoreCandidateReviewError as exc:
        console.print(f"[red]CORE candidate review preparation failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, worksheet.to_json())
    console.print(
        f"[green]Prepared {worksheet.candidate_count} pending candidate reviews:[/green] {output}. "
        "No candidates were approved or promoted."
    )


@app.command("unpaywall-doi-lookup")
def unpaywall_doi_lookup(
    doi: UnpaywallDoiOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Look up one DOI's OA-location/license evidence via the official Unpaywall API.

    Evidence lookup only -- not a discovery-and-adjudication pipeline like
    `pubmed-candidate-discover`/`europepmc-candidate-discover`/
    `core-candidate-discover`. Unpaywall's topic-search endpoint was
    confirmed broken (HTTP 500) at build time, and even its working per-DOI
    endpoint carries no scientific-scope signal, so this command makes no
    accept/reject/hold decision. Intended to enrich a DOI already surfaced
    by another pipeline (e.g. a `held` candidate) with Unpaywall's own view
    of its best OA location and license. Requires `KE_UNPAYWALL_EMAIL`.
    """

    _validate_output(output, force=force)
    try:
        service = _unpaywall_lookup_service()
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    console.print("[yellow]Network access:[/yellow] querying the official Unpaywall API.")
    try:
        result = service.lookup(doi)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except UnpaywallLookupError as exc:
        console.print(f"[red]Unpaywall lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, result.to_json())
    if result.found and result.record is not None:
        console.print(
            f"[green]Wrote OA evidence for {result.doi}:[/green] {output} "
            f"(is_oa={result.record.is_oa})."
        )
    else:
        console.print(
            f"[yellow]DOI not found in Unpaywall's index:[/yellow] {result.doi}. Wrote {output}."
        )
    console.print(
        "[bold]Evidence only; no adjudication decision was made and no PDFs were downloaded.[/bold]"
    )


@app.command("unpaywall-batch-lookup")
def unpaywall_batch_lookup(
    dois_file: UnpaywallDoisFileOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Look up a bounded batch (max 100) of DOIs' OA-location/license evidence.

    See `unpaywall-doi-lookup` for the design rationale. Requires
    `KE_UNPAYWALL_EMAIL`.
    """

    _validate_output(output, force=force)
    try:
        dois = parse_dois_file(dois_file)
    except UnpaywallLookupError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    try:
        service = _unpaywall_lookup_service()
    except ValueError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    console.print(
        f"[yellow]Network access:[/yellow] querying the official Unpaywall API for "
        f"{len(dois)} DOI(s)."
    )
    try:
        result = service.lookup_many(dois)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except UnpaywallLookupError as exc:
        console.print(f"[red]Unpaywall lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, result.to_json())
    found = sum(1 for item in result.results if item.found)
    console.print(
        f"[green]Wrote OA evidence for {len(dois)} DOI(s):[/green] {output} "
        f"({found} found, {len(dois) - found} not found)."
    )
    console.print(
        "[bold]Evidence only; no adjudication decision was made and no PDFs were downloaded.[/bold]"
    )


@app.command("reference-lookup")
def reference_lookup(
    term: ReferenceLookupTermArgument,
    output: ReferenceLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Look up a term's plain-language grounding via Wikipedia's public REST API.

    M41's first slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`): background context for a
    term or mechanism a paper's claim text names (e.g. "GLP-1 receptor
    agonist", "SGLT2 inhibitor"), not primary-research evidence. Never
    routed through `EvidenceRecord` promotion, and never merged with the
    evidence corpus's own search commands (`ke search`/`ke answer`/
    `ke vector-search`/`ke fused-search`) -- this is a separate, explicitly
    non-evidentiary lookup. A term with no Wikipedia article returns
    `found: false` rather than a guess.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying Wikipedia's public REST API.")
    transport = cast(ReferenceLookupGetTransport, UrllibWikipediaTransport())
    service = ReferenceLookupService(transport)
    try:
        result = service.lookup(term)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ReferenceLookupError as exc:
        console.print(f"[red]Reference lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No Wikipedia article found for:[/yellow] {escape(term)}")
    else:
        console.print(f"[bold]{escape(result.title or term)}[/bold]")
        if result.description:
            console.print(escape(result.description))
        if result.page_type and result.page_type != "standard":
            console.print(f"[yellow]Page type: {escape(result.page_type)}[/yellow]")
        if result.extract:
            console.print()
            console.print(escape(result.extract))
        console.print()
        console.print(
            f"Source: {escape(result.source_url or 'unknown')}  "
            f"License: {escape(result.license or 'unknown')}"
        )
        if result.permanent_url:
            console.print(f"Permanent link (this exact revision): {escape(result.permanent_url)}")

    console.print()
    console.print(
        "[bold]This is background reference context from Wikipedia, not evidence -- "
        "no scientific synthesis has been performed.[/bold]"
    )


@app.command("rxnorm-lookup")
def rxnorm_lookup(
    term: RxNormLookupTermArgument,
    output: RxNormLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Resolve a drug name to its RxNorm normalized concept via NLM's public RxNav API.

    M42's second slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`), alongside M41's Wikipedia
    lookup: background context for a drug name a paper's claim text uses
    (e.g. "semaglutide", "Ozempic"), not primary-research evidence. Never
    routed through `EvidenceRecord` promotion, and never merged with the
    evidence corpus's own search commands (`ke search`/`ke answer`/
    `ke vector-search`/`ke fused-search`) -- this is a separate, explicitly
    non-evidentiary lookup. A term RxNorm does not recognize returns
    `found: false` rather than a guess.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying NLM's public RxNav API.")
    transport = cast(RxNormLookupGetTransport, UrllibRxNavTransport())
    service = RxNormLookupService(transport)
    try:
        result = service.lookup(term)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RxNormLookupError as exc:
        console.print(f"[red]RxNorm lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No RxNorm concept found for:[/yellow] {escape(term)}")
    else:
        console.print(f"[bold]{escape(result.name or term)}[/bold]")
        if result.term_type:
            console.print(f"Term type: {escape(result.term_type)}")
        if result.synonym:
            console.print(f"Synonym: {escape(result.synonym)}")
        if result.ingredients:
            ingredient_list = ", ".join(
                f"{ingredient.name} (RXCUI {ingredient.rxcui})" for ingredient in result.ingredients
            )
            console.print(f"Ingredient(s): {escape(ingredient_list)}")
        console.print()
        console.print(
            f"RxCUI: {escape(result.rxcui or 'unknown')}  "
            f"Source: {escape(result.source_url or 'unknown')}  "
            f"License: {escape(result.license or 'unknown')}"
        )

    console.print()
    console.print(
        "[bold]This is background reference context from RxNorm, not evidence -- "
        "no scientific synthesis has been performed.[/bold]"
    )


@app.command("mesh-lookup")
def mesh_lookup(
    term: MeshLookupTermArgument,
    output: MeshLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Resolve a medical term to its NLM MeSH descriptor via NCBI's public E-utilities API.

    M43's third slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`), alongside M41's Wikipedia
    lookup and M42's RxNorm lookup: background context for a disease,
    procedure, or mechanism term a paper's claim text uses (e.g.
    "obesity", "type 2 diabetes"), not primary-research evidence. Never
    routed through `EvidenceRecord` promotion, and never merged with the
    evidence corpus's own search commands (`ke search`/`ke answer`/
    `ke vector-search`/`ke fused-search`) -- this is a separate, explicitly
    non-evidentiary lookup. MeSH is a controlled vocabulary, not a fuzzy
    search: a term with no exact matching MeSH entry term returns
    `found: false` rather than guessing the closest candidate.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying NCBI's public E-utilities API.")
    transport = cast(MeshLookupGetTransport, UrllibNcbiTransport())
    service = MeshLookupService(transport)
    try:
        result = service.lookup(term)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MeshLookupError as exc:
        console.print(f"[red]MeSH lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No exact MeSH descriptor found for:[/yellow] {escape(term)}")
    else:
        console.print(f"[bold]{escape(result.heading or term)}[/bold]")
        if result.scope_note:
            console.print(escape(result.scope_note))
        if result.synonyms:
            console.print(f"Synonyms: {escape(', '.join(result.synonyms))}")
        console.print()
        console.print(
            f"MeSH ID: {escape(result.mesh_id or 'unknown')}  "
            f"Source: {escape(result.source_url or 'unknown')}  "
            f"License: {escape(result.license or 'unknown')}"
        )

    console.print()
    console.print(
        "[bold]This is background reference context from MeSH, not evidence -- "
        "no scientific synthesis has been performed.[/bold]"
    )


@app.command("pubchem-lookup")
def pubchem_lookup(
    term: PubchemLookupTermArgument,
    output: PubchemLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Resolve a compound name to its PubChem record via NLM/NCBI's public PUG REST API.

    M44's fourth slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`), alongside M41's
    Wikipedia lookup, M42's RxNorm lookup, and M43's MeSH lookup:
    background context for a compound name a paper's claim text uses
    (e.g. "metformin", "empagliflozin"), not primary-research evidence.
    Never routed through `EvidenceRecord` promotion, and never merged
    with the evidence corpus's own search commands (`ke search`/
    `ke answer`/`ke vector-search`/`ke fused-search`) -- this is a
    separate, explicitly non-evidentiary lookup. A name PubChem does not
    recognize returns `found: false` rather than a guess.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying PubChem's public PUG REST API.")
    transport = cast(PubchemLookupGetTransport, UrllibPubchemTransport())
    service = PubchemLookupService(transport)
    try:
        result = service.lookup(term)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except PubchemLookupError as exc:
        console.print(f"[red]PubChem lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No PubChem compound found for:[/yellow] {escape(term)}")
    else:
        console.print(f"[bold]{escape(result.title or term)}[/bold]")
        if result.molecular_formula:
            console.print(f"Molecular formula: {escape(result.molecular_formula)}")
        if result.molecular_weight:
            console.print(f"Molecular weight: {escape(result.molecular_weight)}")
        if result.iupac_name:
            console.print(f"IUPAC name: {escape(result.iupac_name)}")
        if result.smiles:
            console.print(f"SMILES: {escape(result.smiles)}")
        console.print()
        console.print(
            f"CID: {escape(result.cid or 'unknown')}  "
            f"Source: {escape(result.source_url or 'unknown')}  "
            f"License: {escape(result.license or 'unknown')}"
        )

    console.print()
    console.print(
        "[bold]This is background reference context from PubChem, not evidence -- "
        "no scientific synthesis has been performed.[/bold]"
    )


@app.command("manual-pdf-preview")
def manual_pdf_preview(
    pdf: ManualPdfPathOption,
    output: CandidateOutputOption,
    doi_lookup: ManualPdfDoiLookupOption = False,
    force: ForceOutputOption = False,
) -> None:
    """Preview a manually-supplied local PDF without importing it.

    Parses the PDF locally (title, authors, abstract, DOI, page/word
    count) with the same parser `ke import` itself uses -- no manifest row
    needs to be hand-typed to see this evidence. Fully offline unless
    `--doi-lookup` is passed and a DOI is found, in which case Unpaywall
    (M36) is queried for OA/license evidence over the network, requiring
    `KE_UNPAYWALL_EMAIL`. Never writes to the corpus manifest or database;
    see `manual-pdf-manifest-draft` for the next, explicit step.
    """

    _validate_output(output, force=force)
    unpaywall_service = None
    if doi_lookup:
        try:
            unpaywall_service = _unpaywall_lookup_service()
        except ValueError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(1) from None
        console.print(
            "[yellow]Network access:[/yellow] querying the official Unpaywall API "
            "if a DOI is found."
        )
    try:
        preview = prepare_manual_pdf_preview(pdf, unpaywall_service=unpaywall_service)
    except ManualPdfPreviewError as exc:
        console.print(f"[red]Manual PDF preview failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc
    except UnpaywallLookupError as exc:
        console.print(f"[red]Unpaywall lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, preview.to_json())
    console.print(f"[green]Wrote preview evidence:[/green] {output} (title: {preview.title!r}).")
    if preview.doi is None:
        console.print("[yellow]No DOI was found in the PDF.[/yellow]")
    elif not preview.doi_lookup_performed:
        console.print("DOI found but not looked up; re-run with --doi-lookup to check Unpaywall.")
    console.print(
        "[bold]Evidence only; no manifest row was written and nothing was imported.[/bold]"
    )


@app.command("manual-pdf-manifest-draft")
def manual_pdf_manifest_draft(
    preview: ManualPdfPreviewInputOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Draft one manifest-ready CSV row from a reviewed, license-verified preview.

    Refuses unless the preview's license evidence already passed (an
    Unpaywall-verified reusable license) -- never guesses. Running this
    command against a preview you have reviewed and accepted is itself
    the approval act. Never modifies `sources.csv` directly, matching
    `manifest_curation_cli.py`'s existing draft-only contract for the
    automated pipelines.
    """

    _validate_output(output, force=force)
    try:
        draft = export_manual_pdf_manifest_draft(preview)
    except ManualPdfPreviewError as exc:
        console.print(f"[red]Manual PDF manifest draft failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, draft.to_csv())
    console.print(
        f"[green]Wrote 1 manifest curation row:[/green] {output}. No sources.csv file was modified."
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


@app.command("europepmc-oa-acquire")
def europepmc_oa_acquire(
    candidates: EuropePmcCandidatesPathOption,
    approvals: EuropePmcApprovalsPathOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Acquire only explicitly approved Europe PMC OA PDFs and write a sanitized receipt.

    Mirrors `pmc-oa-acquire`'s approval-gated, all-or-nothing acquisition
    contract for M34's Europe PMC pipeline (see
    `docs/m34_europepmc_discovery.md`). Only fetches from `europepmc.org`
    (Europe PMC's own hosted full-text repository) -- never a third-party OA
    mirror -- and only for candidates `europepmc-candidate-review-prepare`
    marked `accepted`.
    """

    _validate_output(receipt, force=force)
    console.print(
        "[yellow]Network access:[/yellow] acquiring explicitly approved PDFs "
        "from Europe PMC's own hosted full-text repository."
    )
    try:
        result = _europepmc_acquisition_service().acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=papers_dir,
        )
    except EuropePmcAcquisitionError as exc:
        console.print(f"[red]Europe PMC OA acquisition failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    try:
        _write_output(receipt, result.to_json())
    except typer.BadParameter:
        _rollback_europepmc_acquired_files(papers_dir, result)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs were rolled back."
        ) from None
    console.print(
        f"[green]Acquired {result.acquired_count} approved Europe PMC OA PDFs.[/green] "
        f"Receipt: {receipt}"
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

    paper_metadata = PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title)
    result = run_extraction_review_for_paper(paper_metadata, pages)
    items = result.draft_items

    lines = [json.dumps(item.to_dict()) for item in items]
    _write_output(output, "\n".join(lines) + ("\n" if lines else ""))

    try:
        _record_extraction_run(
            paper_id=paper.id,
            output_path=output,
            page_count=result.page_count,
            section_count=result.section_count,
            candidate_count=result.candidate_count,
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
            ("population", result.pico.population),
            ("intervention", result.pico.intervention),
            ("comparator", result.pico.comparator),
            ("outcome", result.pico.outcome),
        )
        if value
    )
    console.print(
        f"[green]Wrote {len(items)} draft evidence item(s):[/green] {output} "
        f"({result.page_count} page(s), {result.section_count} section(s), "
        f"{result.candidate_count} candidate(s), "
        f"study_type: {result.study_type or 'not detected'}, "
        f"limitations: {'detected' if result.limitations else 'not detected'}, "
        f"PICO fields detected: {pico_detected or 'none'})."
    )
    console.print(
        "[bold]Draft items are a review queue, not validated evidence -- "
        "research_question and evidence_direction require human completion. "
        "study_type, limitations, and population/intervention/comparator/outcome are "
        "populated automatically when detected, never guessed.[/bold]"
    )


@app.command("extraction-review-batch-generate")
def extraction_review_batch_generate(
    output: ExtractionReviewOutputOption,
    paper_id: ExtractionReviewBatchPaperIdsOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Run `ke extraction-review-generate`'s pipeline across many papers at once.

    Writes one combined JSONL draft-evidence-item review queue -- every item
    already carries its own `source_span.paper_id`, so a reviewer can trace
    any item back to its paper without needing per-paper files. Exactly the
    same pipeline as the single-paper command; this only removes the
    one-paper-at-a-time friction of generating the queue a reviewer works
    from. Still not validated evidence: `ke extraction-review-promote`
    remains the only path from a draft item to a real `EvidenceRecord`, and
    it still refuses any item missing a human-supplied
    `research_question`/`evidence_direction`. A paper with no persisted
    pages is skipped and counted, not a hard failure, so one incomplete
    paper cannot abort the whole batch. An unknown `--paper-id` is rejected
    outright, matching `ke embedding-index-build`'s existing dangling-ID
    behavior -- an explicit request naming a paper that doesn't exist is
    reported, never silently dropped from the batch.
    """

    _validate_output(output, force=force)

    database = _local_database()
    database.initialize()
    lines: list[str] = []
    recorded_paper_count = 0
    unrecorded_paper_ids: list[int] = []
    with database.session() as session:
        repository = PaperRepository(session)
        if paper_id:
            papers = repository.get_many(paper_id)
            missing_ids = sorted(set(paper_id) - {paper.id for paper in papers})
            if missing_ids:
                console.print(
                    f"[red]Unknown paper ID(s):[/red] "
                    f"{', '.join(str(missing_id) for missing_id in missing_ids)}"
                )
                raise typer.Exit(1)
        else:
            papers = repository.list_papers()
        if not papers:
            console.print("[yellow]No papers found to process.[/yellow]")
            return
        paper_pages = [
            (
                PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title),
                [ParsedPage(page_number=page.page_number, text=page.text) for page in paper.pages],
            )
            for paper in sorted(papers, key=lambda paper: paper.id)
        ]

        summary = run_batch_extraction_review(paper_pages)

        run_repository = ExtractionRunRepository(session)
        for result in summary.results:
            try:
                with session.begin_nested():
                    run_repository.create(
                        paper_id=result.paper_id,
                        output_path=str(output),
                        page_count=result.page_count,
                        section_count=result.section_count,
                        candidate_count=result.candidate_count,
                        draft_item_count=len(result.draft_items),
                        section_detection_rules_version=SECTION_DETECTION_RULES_VERSION,
                        claim_candidate_rules_version=CLAIM_CANDIDATE_RULES_VERSION,
                        claim_framing_rules_version=CLAIM_FRAMING_RULES_VERSION,
                        draft_evidence_item_rules_version=DRAFT_EVIDENCE_ITEM_RULES_VERSION,
                        study_design_rules_version=STUDY_DESIGN_RULES_VERSION,
                        pico_extraction_rules_version=PICO_EXTRACTION_RULES_VERSION,
                    )
            except Exception:
                unrecorded_paper_ids.append(result.paper_id)
                continue
            recorded_paper_count += 1
            lines.extend(json.dumps(item.to_dict()) for item in result.draft_items)

        _write_output(output, "\n".join(lines) + ("\n" if lines else ""))

    if unrecorded_paper_ids:
        console.print(
            f"[red]{len(unrecorded_paper_ids)} paper(s) could not have their extraction run "
            "recorded and were excluded from the output:[/red] "
            f"{', '.join(str(paper_id) for paper_id in unrecorded_paper_ids)}"
        )

    console.print(
        f"[green]Wrote {len(lines)} draft evidence item(s) across {recorded_paper_count} "
        f"paper(s):[/green] {output}"
    )
    console.print(
        f"Papers skipped (no persisted pages): {summary.papers_with_zero_pages}; "
        f"papers with zero draft items: {summary.papers_with_zero_candidates}."
    )
    console.print(
        "[bold]Draft items are a review queue, not validated evidence -- "
        "research_question and evidence_direction require human completion before "
        "ke extraction-review-promote will accept any of them.[/bold]"
    )


@app.command("extraction-review-annotate")
def extraction_review_annotate(
    input_path: ExtractionReviewAnnotateInputOption,
    output: ExtractionReviewAnnotateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Attach reference-layer context (RxNorm/MeSH) to a draft review queue.

    Reads `ke extraction-review-generate`/`extraction-review-batch-generate`'s
    JSONL output and writes an annotated copy where each draft item carries a
    new `reference_context` object: `intervention`/`comparator` looked up
    against M42's RxNorm (both name a drug or treatment), `population`/
    `outcome` against M43's MeSH (both describe a medical concept). Builds
    three of `docs/reference_knowledge_layer_design.md`'s Addendum items at
    once: a coverage-gap flag when a term has no reference-layer match
    (`found: false`, never silently omitted), full provenance on every
    embedded result (`source_url`/`license`/`retrieved_at`), and background
    definitions inline for the human deciding `research_question`/
    `evidence_direction` before running `ke extraction-review-promote`.

    Never touches `research_question`, `evidence_direction`, or any other
    field `ke extraction-review-promote` requires -- purely additive context
    a reviewer can read or ignore. A separate, opt-in step from generation:
    run it by hand against the paper(s) you are about to review, not
    automatically across the whole corpus -- generating the review queue
    itself must stay network-free even at the corpus's real scale (M40:
    13,588 draft items across 943 papers).
    """

    if not input_path.exists():
        console.print(f"[red]Input file does not exist:[/red] {input_path}")
        raise typer.Exit(1)
    _validate_output(output, force=force)

    items: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Line {line_number}: invalid JSON.[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(record, dict):
            console.print(f"[red]Line {line_number}: record must be a JSON object.[/red]")
            raise typer.Exit(1)
        items.append(record)

    if not items:
        console.print("[yellow]No draft items found in input file.[/yellow]")
        return

    console.print(
        "[yellow]Network access:[/yellow] querying NLM's public RxNav and E-utilities APIs."
    )
    rxnorm_transport = cast(RxNormLookupGetTransport, UrllibRxNavTransport())
    mesh_transport = cast(MeshLookupGetTransport, UrllibNcbiTransport())
    rxnorm_service = RxNormLookupService(rxnorm_transport)
    mesh_service = MeshLookupService(mesh_transport)
    try:
        annotated, summary = annotate_draft_items(
            items, rxnorm_service=rxnorm_service, mesh_service=mesh_service
        )
    except (RxNormLookupError, MeshLookupError) as exc:
        console.print(f"[red]Reference-layer annotation failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    lines = "\n".join(json.dumps(item) for item in annotated) + "\n"
    _write_output(output, lines)

    console.print(
        f"[green]Annotated {summary.item_count} draft item(s):[/green] {output} "
        f"({summary.rxnorm_terms_looked_up} distinct RxNorm term(s), "
        f"{summary.mesh_terms_looked_up} distinct MeSH term(s) looked up)."
    )
    console.print(
        "[bold]reference_context is background context, not evidence -- "
        "research_question and evidence_direction still require human completion "
        "before ke extraction-review-promote will accept any item.[/bold]"
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
    A `.gz` suffix (e.g. `snapshot.sqlite3.gz`) writes a gzip-compressed
    snapshot instead of a plain one -- GitHub caps individual pushed files
    at 100MB, and this corpus's page-level text compresses well enough to
    stay committable for much longer than the raw SQLite file would.
    """

    database = _local_database()
    database.initialize()
    try:
        if output.suffix == ".gz":
            summary = export_corpus_library_compressed(database.engine, output)
        else:
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
    importing the same or an overlapping snapshot twice is idempotent. A
    `.gz` suffix is read as a gzip-compressed snapshot.
    """

    database = _local_database()
    database.initialize()
    try:
        with database.session() as session:
            if input_path.suffix == ".gz":
                summary = import_corpus_library_compressed(session, input_path)
            else:
                summary = import_corpus_library(session, input_path)
    except FileNotFoundError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None
    console.print(
        f"[green]Imported corpus library:[/green] {summary.imported_paper_count} paper(s) "
        f"imported, {summary.skipped_existing_paper_count} already present and skipped."
    )


def _build_embedding_generator(generator: str, model: str | None) -> EmbeddingGenerator:
    """Construct the requested `EmbeddingGenerator`.

    Both options from `docs/phase3_design.md`'s embedding-generation
    decision are implemented behind this one switch: 'local' (fully
    offline, no per-query cost, a real new dependency) and 'openai' (no
    local model weights, but sends paper text to a third party and
    requires a `KE_OPENAI_API_KEY`).
    """

    if generator == "local":
        try:
            return SentenceTransformerEmbeddingGenerator(
                model_name=model or DEFAULT_LOCAL_MODEL_NAME
            )
        except LocalEmbeddingError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(1) from None
    if generator == "openai":
        api_key = build_settings(Path.cwd()).openai_api_key
        if not api_key:
            console.print(
                "[red]KE_OPENAI_API_KEY is not set.[/red] The openai generator requires an "
                "API key; corpus text is sent to OpenAI over the network."
            )
            raise typer.Exit(1)
        try:
            if model:
                return OpenAiEmbeddingGenerator(api_key=api_key, model=model)
            return OpenAiEmbeddingGenerator(api_key=api_key)
        except OpenAiEmbeddingError as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            raise typer.Exit(1) from None
    console.print(f"[red]Unknown generator {generator!r}.[/red] Expected 'local' or 'openai'.")
    raise typer.Exit(1)


def _paper_embedding_text(paper: Paper) -> str:
    """Return the text embedded for one paper: title, plus abstract if present.

    Deliberately not the full body text -- one vector per paper, matching
    `embedding_id`'s existing "the paper's own Paper.id" semantics
    (docs/phase3_design.md). Chunking a paper into multiple vectors is a
    separate, not-yet-made decision.
    """

    if paper.abstract:
        return f"{paper.title}\n\n{paper.abstract}"
    return paper.title


@app.command("embedding-generate")
def embedding_generate(
    output: EmbeddingGenerateOutputOption,
    generator: EmbeddingGeneratorNameOption,
    model: EmbeddingGenerateModelOption = None,
    paper_id: EmbeddingGeneratePaperIdsOption = None,
) -> None:
    """Generate embedding vectors for local papers into an externally-supplied-vectors JSONL file.

    Writes the same `{"paper_id", "vector", "embedding_model"}` JSONL
    format `ke embedding-index-build` already consumes -- this command
    generates that file locally (via `--generator local` or
    `--generator openai`) instead of via an out-of-band process, but does
    not change how the index is built or searched; run
    `ke embedding-index-build` on the output afterward. Embeds each
    paper's title and abstract only (see `_paper_embedding_text`).
    """

    embedding_generator = _build_embedding_generator(generator, model)

    database = _local_database()
    database.initialize()
    with database.session() as session:
        repository = PaperRepository(session)
        papers = repository.get_many(paper_id) if paper_id else repository.list_papers()
        if not papers:
            console.print("[yellow]No papers found to embed.[/yellow]")
            return

        records: list[dict[str, object]] = []
        for paper in papers:
            try:
                vector = embedding_generator.generate(_paper_embedding_text(paper))
            except (LocalEmbeddingError, OpenAiEmbeddingError) as exc:
                console.print(f"[red]Failed to embed paper {paper.id}:[/red] {escape(str(exc))}")
                raise typer.Exit(1) from None
            records.append(
                {
                    "paper_id": paper.id,
                    "vector": list(vector),
                    "embedding_model": embedding_generator.model_id,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    console.print(
        f"[green]Generated {len(records)} embedding(s):[/green] {output} "
        f"(embedding_model {embedding_generator.model_id})."
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
    vector rather than duplicating it. Every vector in the file, and every
    incremental update to an existing index, must come from the same
    embedding_model -- vectors from different models are not comparable
    even at the same dimension, so a mismatch is rejected rather than
    silently mixed into one index.
    """

    result = load_external_vectors(vectors)
    if result.errors:
        console.print(f"[red]Vectors file is invalid:[/red] {vectors}")
        for error in result.errors:
            console.print(f"- {escape(error)}")
        raise typer.Exit(1)

    assert result.dimension is not None  # non-empty records guarantee a dimension
    assert result.embedding_model is not None  # non-empty records guarantee a model

    if index_path.exists():
        existing_metadata = load_index_metadata(index_path)
        if existing_metadata is None:
            console.print(
                f"[red]Index at {index_path} has no recorded embedding_model "
                "metadata.[/red] Refusing to update an index whose embedding model "
                "cannot be verified."
            )
            raise typer.Exit(1)
        if existing_metadata.embedding_model != result.embedding_model:
            console.print(
                f"[red]Index was built with embedding_model "
                f"'{escape(existing_metadata.embedding_model)}'; this vectors file uses "
                f"'{escape(result.embedding_model)}'.[/red] Refusing to mix incompatible "
                "embedding models in one index."
            )
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
        save_index_metadata(
            index_path,
            VectorIndexMetadata(embedding_model=result.embedding_model, dimension=result.dimension),
        )

    console.print(
        f"[green]Indexed {len(result.records)} vector(s):[/green] {index_path} "
        f"(embedding_model {result.embedding_model}, dimension {result.dimension}, "
        f"index size {index.size})."
    )


@app.command("vector-search")
def vector_search(
    index_path: ExistingEmbeddingIndexPathOption,
    query_vector: QueryVectorOption = None,
    query_text: QueryTextOption = None,
    generator: VectorSearchGeneratorOption = None,
    model: VectorSearchModelOption = None,
    limit: VectorSearchLimitOption = 10,
) -> None:
    """Search a local FAISS vector index by a free-text query or an already-embedded vector.

    Exactly one of `--query-text` (embedded live via `--generator local|openai`,
    the same generators `ke embedding-generate` uses) or `--query-vector` (a JSON
    file from any external embedding tool -- `{"vector": [...]}`, optionally with
    `"embedding_model"`; or a bare array) must be given. Either way the query's
    embedding_model, once known, is checked against the index's recorded
    embedding_model -- vectors from different models are not comparable even at
    the same dimension. Lexical search remains available via `ke search`; this
    command is an additional, separate retrieval signal, not a replacement, and
    combining the two into one ranked list is not yet implemented.
    """

    index_metadata = load_index_metadata(index_path)
    if index_metadata is None:
        console.print(
            f"[red]Index at {index_path} has no recorded embedding_model "
            "metadata.[/red] Refusing to search an index whose embedding model cannot "
            "be verified."
        )
        raise typer.Exit(1)

    if (query_vector is None) == (query_text is None):
        console.print("[red]Provide exactly one of --query-vector or --query-text.[/red]")
        raise typer.Exit(1)

    query_embedding_model: str | None
    if query_text is not None:
        if generator is None:
            console.print("[red]--generator is required with --query-text (local or openai).[/red]")
            raise typer.Exit(1)
        embedding_generator = _build_embedding_generator(generator, model)
        try:
            vector: list[float] = list(embedding_generator.generate(query_text))
        except (LocalEmbeddingError, OpenAiEmbeddingError) as exc:
            console.print(f"[red]Failed to embed query text:[/red] {escape(str(exc))}")
            raise typer.Exit(1) from None
        query_embedding_model = embedding_generator.model_id
    else:
        assert query_vector is not None
        if generator is not None or model is not None:
            console.print("[red]--generator/--model are only used with --query-text.[/red]")
            raise typer.Exit(1)
        try:
            payload = json.loads(query_vector.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            console.print(f"[red]Query vector file is not valid JSON:[/red] {query_vector}")
            raise typer.Exit(1) from None

        raw_vector = payload.get("vector") if isinstance(payload, dict) else payload
        if (
            not isinstance(raw_vector, list)
            or not raw_vector
            or not all(
                isinstance(component, int | float) and not isinstance(component, bool)
                for component in raw_vector
            )
        ):
            console.print(
                "[red]Query vector file must contain a non-empty array of numbers "
                '(a bare array or {"vector": [...]}).[/red]'
            )
            raise typer.Exit(1)
        vector = [float(component) for component in raw_vector]
        query_embedding_model = (
            payload.get("embedding_model") if isinstance(payload, dict) else None
        )

    if (
        query_embedding_model is not None
        and query_embedding_model != index_metadata.embedding_model
    ):
        console.print(
            f"[red]Query vector was embedded with '{escape(str(query_embedding_model))}'; "
            f"this index was built with '{escape(index_metadata.embedding_model)}'.[/red] "
            "Refusing to compare vectors from different embedding models."
        )
        raise typer.Exit(1)

    try:
        index = FaissVectorIndex.load(index_path, dimension=len(vector))
    except VectorSearchError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    matches = index.search(vector, k=limit)
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

    console.print(
        f"[bold]Vector search results:[/bold] {index_path} "
        f"(embedding_model: {index_metadata.embedding_model})"
    )
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


@app.command("fused-search")
def fused_search(
    query_text: FusedSearchQueryTextArgument,
    index_path: ExistingEmbeddingIndexPathOption,
    generator: FusedSearchGeneratorOption,
    model: VectorSearchModelOption = None,
    limit: VectorSearchLimitOption = 10,
    candidate_limit: FusedSearchCandidateLimitOption = 25,
) -> None:
    """Combine lexical (`ke search`) and semantic (`ke vector-search`) retrieval.

    Resolves `docs/phase3_design.md`'s last open Phase 3 design question:
    the two retrieval signals have run as separate commands since M30/M32,
    with no combined ranking. This runs both against the same free-text
    query -- lexical via `SearchService.answer_retrieval` (the same
    natural-language-safe FTS5 tokenizer `ke answer` uses, so punctuation
    like "Crohn's disease" or "heart-failure" cannot raise a raw FTS5 syntax
    error), semantic by embedding the query live (via `--generator`, the
    same generators `ke vector-search --query-text` uses) and searching the
    local FAISS index -- and fuses the two ranked paper_id lists with
    Reciprocal Rank Fusion (see `knowledge_engine.search_fusion`): a paper
    appearing in both rankings outranks one appearing in only one.
    `--candidate-limit` controls how many results are pulled from each
    individual ranking before fusing; the effective candidate pool is never
    narrower than `--limit` itself, so a requested result count can always
    be satisfied when enough matches exist.
    """

    index_metadata = load_index_metadata(index_path)
    if index_metadata is None:
        console.print(
            f"[red]Index at {index_path} has no recorded embedding_model "
            "metadata.[/red] Refusing to search an index whose embedding model cannot "
            "be verified."
        )
        raise typer.Exit(1)

    embedding_generator = _build_embedding_generator(generator, model)
    try:
        vector: list[float] = list(embedding_generator.generate(query_text))
    except (LocalEmbeddingError, OpenAiEmbeddingError) as exc:
        console.print(f"[red]Failed to embed query text:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from None

    if embedding_generator.model_id != index_metadata.embedding_model:
        console.print(
            f"[red]Query was embedded with '{escape(embedding_generator.model_id)}'; "
            f"this index was built with '{escape(index_metadata.embedding_model)}'.[/red] "
            "Refusing to compare vectors from different embedding models."
        )
        raise typer.Exit(1)

    try:
        index = FaissVectorIndex.load(index_path, dimension=len(vector))
    except VectorSearchError as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from None

    effective_candidate_limit = max(candidate_limit, limit)
    semantic_paper_ids = [
        match.vector_id for match in index.search(vector, k=effective_candidate_limit)
    ]

    database = _local_database()
    database.initialize()
    with database.session() as session:
        lexical_paper_ids = [
            result.paper_id
            for result in SearchService(session).answer_retrieval(
                query_text, limit=effective_candidate_limit
            )
        ]
        fused = fuse_rankings(lexical_paper_ids, semantic_paper_ids)[:limit]
        repository = PaperRepository(session)
        papers_by_id = {
            paper.id: paper for paper in repository.get_many([result.paper_id for result in fused])
        }

    if not fused:
        console.print("[yellow]No matches found in either lexical or semantic search.[/yellow]")
        return

    console.print(f"[bold]Fused search results for:[/bold] {escape(query_text)}")
    console.print(
        f"(lexical: SQLite FTS5; semantic: {index_path}, "
        f"embedding_model: {index_metadata.embedding_model})"
    )
    for rank, result in enumerate(fused, start=1):
        paper = papers_by_id.get(result.paper_id)
        title = escape(paper.title) if paper else "Unknown paper (not in local database)"
        matched_via = []
        if result.lexical_rank is not None:
            matched_via.append(f"lexical #{result.lexical_rank}")
        if result.semantic_rank is not None:
            matched_via.append(f"semantic #{result.semantic_rank}")
        console.print()
        console.print(f"[bold]{rank}. {title}[/bold]")
        console.print(f"Paper ID: {result.paper_id}")
        console.print(f"Fused score: {result.fused_score:.4f} (matched: {', '.join(matched_via)})")
        if paper:
            console.print(f"DOI: {escape(paper.doi or 'Unknown')}")

    console.print()
    console.print(
        "[bold]This is combined lexical and semantic retrieval only, not scientific "
        "synthesis.[/bold]"
    )
