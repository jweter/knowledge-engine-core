"""Executable CLI entrypoint with explicit external and reporting commands."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.markup import escape
from rich.table import Table
from sqlalchemy.exc import OperationalError

from knowledge_engine.arxiv_http import UrllibArxivTransport
from knowledge_engine.arxiv_provider import ArxivProvider
from knowledge_engine.candidate_review import (
    CandidateReviewError,
    prepare_candidate_review,
)
from knowledge_engine.citation_extraction import find_cited_dois
from knowledge_engine.citation_snowball import (
    CitationSnowballDiscovery,
    CitationSnowballPlan,
    CitationSnowballResult,
    CitationTraversalProvider,
)
from knowledge_engine.citation_snowball_ledger import CitationSnowballLedger
from knowledge_engine.citation_traversal import CitationDirection
from knowledge_engine.cli import ReportFormatOption, console
from knowledge_engine.cli import app as app
from knowledge_engine.clinicaltrials_http import UrllibClinicalTrialsTransport
from knowledge_engine.clinicaltrials_lookup import (
    ClinicalTrialsLookupError,
    ClinicalTrialsLookupService,
)
from knowledge_engine.clinicaltrials_lookup import (
    GetTransport as ClinicalTrialsLookupGetTransport,
)
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
from knowledge_engine.crossref_federated_adapter import CrossrefFederatedAdapter
from knowledge_engine.crossref_http import UrllibCrossrefTransport
from knowledge_engine.crossref_provider import CrossrefProvider
from knowledge_engine.database import (
    CURRENT_SCHEMA_VERSION,
    Database,
    ExtractionRunRepository,
    GraphRepository,
    PaperRepository,
)
from knowledge_engine.discovery_broker import DiscoveryProvider
from knowledge_engine.discovery_cycle import (
    DISCOVERY_CYCLE_RULES_VERSION,
    DiscoveryCycleError,
    advance_discovery_cycle_state,
    candidate_review_item_to_dict,
    load_discovery_cycle_state,
    save_discovery_cycle_state,
)
from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
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
from knowledge_engine.evidence_intelligence import (
    ClaimConfidence,
    EvidenceConsensus,
    EvidenceCoverage,
    EvidenceQuality,
    compute_claim_confidence,
    compute_evidence_consensus,
    compute_evidence_coverage,
    compute_evidence_quality,
    extraction_tier_label,
    render_synthesis,
)
from knowledge_engine.evidence_review_automate import automate_review_for_record
from knowledge_engine.extraction import (
    CLAIM_CANDIDATE_RULES_VERSION,
    CLAIM_FRAMING_RULES_VERSION,
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    EVIDENCE_CLASSIFICATION_RULES_VERSION,
    LLM_GROUNDED_PICO_RULES_VERSIONS,
    PICO_EXTRACTION_RULES_VERSION,
    SECTION_DETECTION_RULES_VERSION,
    STUDY_DESIGN_RULES_VERSION,
    build_automated_evidence_record,
)
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_annotate import annotate_draft_items
from knowledge_engine.extraction_review_batch import (
    run_batch_extraction_review,
    run_extraction_review_for_paper,
)
from knowledge_engine.federated_discovery import DiscoveryQuery
from knowledge_engine.federated_result_snapshot import build_public_federated_result_payload
from knowledge_engine.federated_search_ledger import (
    FederatedSearchLedger,
    SearchCoverageReport,
    build_search_coverage_report,
)
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
    GeneralQuestionAcquisitionPlan,
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.general_question_pmc_acquisition import (
    GeneralQuestionPmcAcquisitionError,
    execute_pmc_acquisition_plan,
    persist_pmc_acquisition_execution,
)
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.reporting import render_import_run_report
from knowledge_engine.llm import LocalLLMError, OllamaLLM
from knowledge_engine.manual_pdf_preview import (
    ManualPdfPreviewError,
    export_manual_pdf_manifest_draft,
    prepare_manual_pdf_preview,
)
from knowledge_engine.mesh_lookup import GetTransport as MeshLookupGetTransport
from knowledge_engine.mesh_lookup import MeshLookupError, MeshLookupService
from knowledge_engine.metadata_enrichment import MetadataProvider, MetadataQuery
from knowledge_engine.models import GraphCitation, ImportRun, Paper, PaperPage
from knowledge_engine.ncbi_http import UrllibNcbiTransport
from knowledge_engine.openalex_citation_adapter import OpenAlexCitationAdapter
from knowledge_engine.openalex_citations import OpenAlexCitationProvider
from knowledge_engine.openalex_http import UrllibOpenAlexTransport
from knowledge_engine.openalex_provider import OpenAlexProvider
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
from knowledge_engine.pubmed_federated_adapter import PubmedFederatedAdapter
from knowledge_engine.reference_lookup import (
    GetTransport as ReferenceLookupGetTransport,
)
from knowledge_engine.reference_lookup import (
    ReferenceLookupError,
    ReferenceLookupService,
)
from knowledge_engine.reference_lookup_http import UrllibWikipediaTransport
from knowledge_engine.rejected_candidates import (
    REJECTED_LEDGER_RULES_VERSION,
    RejectedCandidatesError,
    append_rejected_candidates,
    check_candidates_against_ledger,
    extract_candidates,
    load_rejected_ledger,
    parse_rejected_candidate,
)
from knowledge_engine.relationship_candidate_ranking import (
    RankedCandidate,
    rank_candidates_by_similarity,
)
from knowledge_engine.relationship_classification import classify_relationship
from knowledge_engine.rxnorm_http import UrllibRxNavTransport
from knowledge_engine.rxnorm_lookup import GetTransport as RxNormLookupGetTransport
from knowledge_engine.rxnorm_lookup import (
    RxNormLookupError,
    RxNormLookupService,
)
from knowledge_engine.scientific_scope import (
    GLP1_METABOLIC_SCOPE,
    resolve_scope_vocabulary,
)
from knowledge_engine.search import SearchService
from knowledge_engine.search_fusion import fuse_rankings
from knowledge_engine.semantic_scholar_http import UrllibSemanticScholarTransport
from knowledge_engine.semantic_scholar_provider import SemanticScholarProvider
from knowledge_engine.uniprot_http import UrllibUniProtTransport
from knowledge_engine.uniprot_lookup import GetTransport as UniProtLookupGetTransport
from knowledge_engine.uniprot_lookup import (
    UniProtLookupError,
    UniProtLookupService,
)
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
CorpusScopeOption = Annotated[
    str,
    typer.Option(
        "--corpus",
        help=(
            "Which corpus's scope vocabulary to adjudicate candidates against. "
            "See knowledge_engine.scientific_scope for known corpus ids."
        ),
    ),
]
GraphCorpusIdOption = Annotated[
    str | None,
    typer.Option(
        "--corpus",
        help=(
            "Corpus id to record on (`graph-build`) or filter to (the "
            "candidate-surfacing commands). Optional and unset by default -- "
            "the graph is corpus-agnostic unless a caller opts in. See "
            "knowledge_engine.scientific_scope for known corpus ids."
        ),
    ),
]
DiscoveryCycleStateOption = Annotated[
    Path,
    typer.Option(
        "--state",
        help="Discovery-cycle pagination state JSON file (created on first run).",
    ),
]
DiscoveryCycleOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for this cycle's ready-for-review worksheet JSON."),
]
RejectedLedgerOption = Annotated[
    Path,
    typer.Option("--ledger", help="Rejected-PMID ledger CSV file (created if it doesn't exist)."),
]
FederatedQueryOption = Annotated[
    str,
    typer.Option("--query", help="Provider-neutral free-text discovery query."),
]
FederatedLimitOption = Annotated[
    int,
    typer.Option("--limit", min=1, max=100, help="Maximum candidates requested per provider."),
]
FederatedYearFromOption = Annotated[
    int | None,
    typer.Option("--year-from", help="Optional earliest publication year filter."),
]
FederatedYearToOption = Annotated[
    int | None,
    typer.Option("--year-to", help="Optional latest publication year filter."),
]
FederatedProvidersOption = Annotated[
    str | None,
    typer.Option(
        "--providers",
        help=(
            "Comma-separated provider subset (e.g. 'pubmed,openalex'). "
            "Defaults to every configured provider."
        ),
    ),
]
FederatedLedgerRootOption = Annotated[
    Path,
    typer.Option(
        "--ledger-root",
        help="Directory the federated search-run ledger persists JSON run records to.",
    ),
]
FederatedOpenAlexApiKeyOption = Annotated[
    str | None,
    typer.Option(
        "--openalex-api-key",
        envvar="KE_OPENALEX_API_KEY",
        help=(
            "OpenAlex API key. OpenAlex reports itself 'disabled' without one -- "
            "see OpenAlexProvider; no other provider here requires a credential."
        ),
    ),
]
FederatedSemanticScholarApiKeyOption = Annotated[
    str | None,
    typer.Option(
        "--semantic-scholar-api-key",
        envvar="KE_SEMANTIC_SCHOLAR_API_KEY",
        help=(
            "Optional Semantic Scholar API key, sent as an x-api-key header. "
            "Unlike OpenAlex, Semantic Scholar's public Academic Graph search "
            "works without one -- a key only raises the rate limit."
        ),
    ),
]
FederatedInitiatedByOption = Annotated[
    str | None,
    typer.Option("--initiated-by", help="Optional free-text label recorded on the persisted run."),
]
FederatedProjectIdOption = Annotated[
    str | None,
    typer.Option(
        "--project-id",
        help=(
            "Optional project identifier recorded on the persisted run. Internal run "
            "context, not part of the public coverage payload -- see SearchCoverageReport."
        ),
    ),
]
FederatedResearchQuestionIdOption = Annotated[
    str | None,
    typer.Option(
        "--research-question-id",
        help=(
            "Optional caller-supplied identifier tying this run to a tracked research "
            "question, so later runs for the same question can be listed together via "
            "`ke federated-discover-history`. Internal run context, not part of the "
            "public coverage payload -- see SearchCoverageReport."
        ),
    ),
]
FederatedDiscoverOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        help=(
            "Optional path to also save the full result (query, coverage, "
            "deduplicated candidates with per-provider observations) as JSON, "
            "for a programmatic caller -- e.g. knowledge-engine-web -- rather "
            "than parsing the console table."
        ),
    ),
]
FederatedSearchRunIdArgument = Annotated[
    str,
    typer.Argument(help="Search-run UUID returned by `federated-discover`."),
]
FederatedHistoryResearchQuestionIdArgument = Annotated[
    str,
    typer.Argument(
        help=(
            "The research_question_id previously supplied to `federated-discover "
            "--research-question-id` -- lists every run tagged with it, newest first."
        )
    ),
]
FederatedHistoryOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        help=(
            "Optional path to also save the full history (research_question_id, run "
            "count, and each matched run's public coverage record) as JSON, for a "
            "programmatic caller -- e.g. knowledge-engine-web -- rather than parsing "
            "the console table."
        ),
    ),
]
FederatedCoverageReportOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        help=(
            "Optional path to also save this run's public coverage record plus its "
            "full deduplicated candidate list (with per-provider observations) as "
            "JSON, for a programmatic caller -- e.g. knowledge-engine-web's "
            "freshness-history view -- rather than parsing the console table. Runs "
            "persisted before this option existed have no candidate snapshot; "
            "`candidates` is an empty list for those, never fabricated."
        ),
    ),
]
GeneralQuestionAcquisitionRequestArgument = Annotated[
    Path,
    typer.Argument(
        help=(
            "JSON acquisition request file (schema_version, search_run_id, "
            "research_question_id, candidate_ids, budget fields -- see "
            "GeneralQuestionAcquisitionRequest.from_json)."
        ),
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
GeneralQuestionAcquisitionOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        help=(
            "Optional path to also save the full acquisition plan (per-candidate "
            "disposition, identity, and budget reconciliation) as JSON, for a "
            "programmatic caller -- e.g. knowledge-engine-ai -- rather than "
            "parsing the console table."
        ),
    ),
]
GeneralQuestionAcquisitionNoDatabaseOption = Annotated[
    bool,
    typer.Option(
        "--no-database",
        help=(
            "Skip the local already-indexed lookup (DOI/PMID/arXiv ID against the "
            "persisted corpus) and report every resolved candidate purely against "
            "the search-run snapshot, ignoring what Core has already acquired."
        ),
    ),
]
SnowballSeedsOption = Annotated[
    str,
    typer.Option(
        "--seeds",
        help=(
            "Comma-separated seed identifiers (Semantic Scholar paper ID, DOI, "
            "arXiv ID, or PMID -- anything the provider's own lookup accepts)."
        ),
    ),
]
SnowballDirectionsOption = Annotated[
    str,
    typer.Option(
        "--directions",
        help=(
            "Comma-separated traversal directions: 'references', 'citations', "
            "or both. Defaults to both."
        ),
    ),
]
SnowballMaxDepthOption = Annotated[
    int,
    typer.Option("--max-depth", min=1, max=3, help="Breadth-first expansion depth from the seeds."),
]
SnowballLimitPerTraversalOption = Annotated[
    int,
    typer.Option(
        "--limit-per-traversal",
        min=1,
        max=1000,
        help="Maximum works requested per single provider traversal call.",
    ),
]
SnowballMaxCandidatesOption = Annotated[
    int,
    typer.Option(
        "--max-candidates",
        min=1,
        help="Hard cap on total newly discovered candidates before the run truncates.",
    ),
]
SnowballLedgerRootOption = Annotated[
    Path,
    typer.Option(
        "--ledger-root",
        help="Directory the citation-snowball ledger persists JSON run records to.",
    ),
]
SnowballProviderOption = Annotated[
    str,
    typer.Option(
        "--provider",
        help=(
            "Which citation-graph provider to traverse: 'semantic_scholar' "
            "(default, no credential required) or 'openalex' (requires "
            "--openalex-api-key/KE_OPENALEX_API_KEY; reports itself "
            "'disabled' -- not an error -- without one, matching "
            "OpenAlexProvider's existing federated-discover behavior)."
        ),
    ),
]
SnowballOutputOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        help=(
            "Optional path to also save the full result (plan, traversal outcomes, "
            "discovered candidates, and edge provenance) as JSON, for a programmatic "
            "caller rather than parsing the console table."
        ),
    ),
]
SnowballRunIdArgument = Annotated[
    str,
    typer.Argument(help="Snowball-run UUID returned by `citation-snowball`."),
]
RejectedCandidatesInputOption = Annotated[
    Path,
    typer.Option(
        "--input",
        help="JSONL file of rejection records (pmid, title, reason_category, batch_label, "
        "optional doi/rejected_date/notes).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
RejectedCandidatesCandidatesOption = Annotated[
    Path,
    typer.Option(
        "--candidates",
        help="Discovery JSON or adjudication worksheet JSON to check against the ledger.",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
RejectedCandidatesCheckOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path for the generated Markdown report."),
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
    str,
    typer.Argument(help="A medical term to look up (e.g. 'obesity', 'type 2 diabetes')."),
]
MeshLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
PubchemLookupTermArgument = Annotated[
    str,
    typer.Argument(help="A compound name to look up (e.g. 'metformin', 'empagliflozin')."),
]
PubchemLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
ClinicalTrialsLookupNctIdArgument = Annotated[
    str,
    typer.Argument(help="A ClinicalTrials.gov NCT ID to look up (e.g. 'NCT03652870')."),
]
ClinicalTrialsLookupOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to also save the lookup result as JSON."),
]
UniProtLookupTermArgument = Annotated[
    str,
    typer.Argument(help="A protein or gene name to look up (e.g. 'PD-1', 'GLP-1 receptor')."),
]
UniProtLookupOutputOption = Annotated[
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
        "--input",
        help="Draft extraction review JSONL file (from extraction-review-generate).",
    ),
]
ExtractionReviewAnnotateOutputOption = Annotated[
    Path,
    typer.Option("--output", help="Path for the annotated draft extraction review JSONL file."),
]
GraphBuildEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="Validated EvidenceRecord JSONL file (already passed `ke evidence-validate`).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
GraphBuildRelationshipsOption = Annotated[
    Path | None,
    typer.Option(
        "--relationships",
        help=(
            "Optional validated RelationshipRecord JSONL file "
            "(already passed `ke relationship-validate`)."
        ),
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
GraphBuildOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path to save the population summary as JSON."),
]
GraphReportEvidenceRecordIdOption = Annotated[
    str | None,
    typer.Option(
        "--evidence-record-id",
        help="Report one claim's linked concepts and relationships, by EvidenceRecord ID.",
    ),
]
GraphReportPaperIdOption = Annotated[
    int | None,
    typer.Option("--paper-id", help="Report one paper's citation edges, by database ID."),
]
GraphReportOutputOption = Annotated[
    Path | None,
    typer.Option("--output", help="Optional path for the generated Markdown report."),
]
GraphRelationshipCandidatesMinimumSharedConceptsOption = Annotated[
    int,
    typer.Option(
        "--min-shared-concepts",
        min=1,
        help="Only surface claim pairs sharing at least this many concepts.",
    ),
]
EvidenceIntelligenceEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="Validated EvidenceRecord JSONL file (already passed `ke evidence-validate`).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
EvidenceIntelligenceEvidenceRecordIdOption = Annotated[
    str,
    typer.Option(
        "--evidence-record-id",
        help="Compute Evidence Intelligence for this claim, by EvidenceRecord ID.",
    ),
]
RelationshipReviewWorksheetEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="Validated EvidenceRecord JSONL file (already passed `ke evidence-validate`).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
RelationshipReviewWorksheetLimitOption = Annotated[
    int,
    typer.Option(
        "--limit",
        min=1,
        help="Maximum candidate pairs to include in one worksheet -- a review-session batch size.",
    ),
]
RelationshipReviewWorksheetOffsetOption = Annotated[
    int,
    typer.Option(
        "--offset",
        min=0,
        help="Skip this many candidate pairs before starting -- page through a large list.",
    ),
]
RelationshipReviewWorksheetRankBySimilarityOption = Annotated[
    bool,
    typer.Option(
        "--rank-by-similarity",
        help=(
            "Re-sort candidates by outcome/result_summary text similarity "
            "(local, offline embedding model) instead of shared-concept count."
        ),
    ),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Report what would happen without writing anything."),
]
EvidenceReviewQueueEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="Validated EvidenceRecord JSONL file (already passed `ke evidence-validate`).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
EvidenceReviewQueueLimitOption = Annotated[
    int,
    typer.Option("--limit", min=1, help="Maximum records to include in the queue."),
]
EvidenceReviewAutomateLimitOption = Annotated[
    int,
    typer.Option(
        "--limit",
        min=1,
        help="Maximum still-automated records to process this run.",
    ),
]
EvidenceReviewAutomateModelOption = Annotated[
    str | None,
    typer.Option(
        "--model",
        help="Ollama model name (e.g. qwen2.5:1.5b). Defaults to KE_LLM_MODEL.",
    ),
]
EvidenceReviewAutomateRecordIdOption = Annotated[
    str | None,
    typer.Option(
        "--evidence-record-id",
        help="Process only this one evidence_record_id, ignoring --limit.",
    ),
]
RelationshipClassifyAutomateEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="Validated EvidenceRecord JSONL file (already passed `ke evidence-validate`).",
        exists=True,
        dir_okay=False,
        readable=True,
    ),
]
RelationshipClassifyAutomateRelationshipsOption = Annotated[
    Path,
    typer.Option(
        "--relationships",
        help="RelationshipRecord JSONL file to append accepted classifications to.",
        exists=True,
        dir_okay=False,
        readable=True,
        writable=True,
    ),
]
RelationshipClassifyAutomateLimitOption = Annotated[
    int,
    typer.Option(
        "--limit",
        min=1,
        help="Maximum candidate pairs to classify this run.",
    ),
]
EvidenceRecordReviewPromoteEvidenceOption = Annotated[
    Path,
    typer.Option(
        "--evidence",
        help="EvidenceRecord JSONL file to promote review_status in place.",
        exists=True,
        dir_okay=False,
        readable=True,
        writable=True,
    ),
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
        "--model",
        help="Override the generator's default model name (used with --query-text).",
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
        "--paper-id",
        help="Restrict generation to this paper ID (repeatable; default: all).",
    ),
]
FusedSearchQueryTextArgument = Annotated[
    str,
    typer.Argument(help="Free-text query used for both lexical and semantic retrieval."),
]
FusedSearchGeneratorOption = Annotated[
    str,
    typer.Option(
        "--generator",
        help="Embedding generator for the semantic side: 'local' or 'openai'.",
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
        pages = [
            ParsedPage(page_number=page.page_number, text=page.text, table_text=page.table_text)
            for page in paper.pages
        ]
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


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into a list of JSON object records.

    Exits with a clear per-line error on malformed JSON or a non-object
    record, rather than skipping or guessing.
    """

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            console.print(f"[red]{path}, line {line_number}: invalid JSON.[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(record, dict):
            console.print(f"[red]{path}, line {line_number}: record must be a JSON object.[/red]")
            raise typer.Exit(1)
        records.append(record)
    return records


def _rxnorm_definition(payload: dict[str, Any]) -> str | None:
    """Join a resolved RxNorm result's structured facts into `graph_concepts.definition`.

    Per `docs/phase4_design.md`'s Architecture section: RxNorm has no
    single free-text definition field like MeSH's `scope_note`, so
    `name`/`term_type`/`synonym` are joined into one string instead --
    the same content a `graph_concepts` row is documented as the only
    durable home for, once linked into the graph.
    """

    parts = [payload.get("name"), payload.get("term_type"), payload.get("synonym")]
    joined = "; ".join(str(part) for part in parts if part)
    return joined or None


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
        "[bold]Candidates require an AI/automated inclusion and license review "
        "(no human review required); no PDFs were downloaded.[/bold]"
    )


@app.command("discovery-cycle-run")
def discovery_cycle_run(
    query: PubmedQueryOption,
    state: DiscoveryCycleStateOption,
    ledger: RejectedLedgerOption,
    output: DiscoveryCycleOutputOption,
    limit: CandidateLimitOption = 25,
    force: ForceOutputOption = False,
    corpus: CorpusScopeOption = GLP1_METABOLIC_SCOPE.corpus_id,
) -> None:
    """Run one cycle of automated discovery: discover, adjudicate, ledger-check (M55).

    Intended to be invoked on a schedule (cron, a systemd timer, or
    anything else that runs a command periodically) for continuous
    discovery -- see `docs/roadmap/long_term_vision.md`'s live,
    connected end state. Each run:

    1. Discovers the next page of PubMed/PMC OA candidates at
       `--state`'s persisted `retstart` offset (0 on a first run).
    2. Deterministically adjudicates each candidate with M14's existing
       scope/identity/license/full-text rules
       (`ke pubmed-candidate-discover`'s adjudication worksheet logic,
       reused unchanged).
    3. Cross-checks every deterministically "accepted" candidate
       against the M53 rejected-PMID ledger, dropping any this project
       has already reviewed and rejected.
    4. Advances `--state`'s `retstart` offset by `--limit` for the next
       cycle.

    Deliberately stops here, before acquisition -- see this module's
    own docstring (`knowledge_engine.discovery_cycle`) for why
    deterministic adjudication alone is not sufficient to admit a paper
    unattended. Writes a bounded "ready for review" worksheet of
    net-new accepted candidates to `--output`, for an AI agent to give
    the same automated scope screen this project has always required
    before running `ke pmc-oa-acquire` -- no human review is required
    or expected (see `docs/roadmap/long_term_vision.md`'s automated-review
    decision).
    """

    try:
        vocabulary = resolve_scope_vocabulary(corpus)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _validate_output(output, force=force)
    try:
        cycle_state = load_discovery_cycle_state(state, query=query, limit=limit)
    except DiscoveryCycleError as exc:
        console.print(f"[red]Discovery-cycle state error:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    console.print(
        "[yellow]Network access:[/yellow] querying official PubMed and PMC services over HTTPS."
    )
    try:
        discovery_result = _pubmed_discovery_service().discover(
            query, limit=limit, retstart=cycle_state.next_retstart
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except NcbiDiscoveryError as exc:
        console.print(f"[red]NCBI discovery failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    with tempfile.TemporaryDirectory() as tmpdir:
        discovery_path = Path(tmpdir) / "discovery.json"
        discovery_path.write_text(discovery_result.to_json(), encoding="utf-8")
        try:
            worksheet = prepare_candidate_review(discovery_path, vocabulary=vocabulary)
        except CandidateReviewError as exc:
            console.print(f"[red]Candidate adjudication failed:[/red] {escape(str(exc))}")
            raise typer.Exit(1) from exc

    accepted_items = [item for item in worksheet.items if item.decision == "accepted"]
    held_count = sum(1 for item in worksheet.items if item.decision == "held")
    rejected_by_adjudication_count = sum(
        1 for item in worksheet.items if item.decision == "rejected"
    )

    rejected_ledger = load_rejected_ledger(ledger)
    accepted_dicts = [candidate_review_item_to_dict(item) for item in accepted_items]
    net_new, already_in_ledger = check_candidates_against_ledger(accepted_dicts, rejected_ledger)

    new_state = advance_discovery_cycle_state(cycle_state)
    save_discovery_cycle_state(state, new_state)

    payload = {
        "rules_version": DISCOVERY_CYCLE_RULES_VERSION,
        "query": query,
        "retstart_used": cycle_state.next_retstart,
        "next_retstart": new_state.next_retstart,
        "cycle_number": new_state.cycles_run,
        "candidates_discovered": len(worksheet.items),
        "deterministically_accepted": len(accepted_items),
        "held_for_manual_review": held_count,
        "rejected_by_adjudication": rejected_by_adjudication_count,
        "already_in_rejected_ledger": len(already_in_ledger),
        "ready_for_scope_review": net_new,
    }
    _write_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    console.print(
        f"[green]Discovery cycle {new_state.cycles_run} complete[/green] "
        f"(retstart {cycle_state.next_retstart} -> next {new_state.next_retstart}): "
        f"{len(worksheet.items)} candidate(s) discovered, {len(accepted_items)} "
        f"deterministically accepted, {len(already_in_ledger)} already in the rejected "
        f"ledger, {len(net_new)} ready for scope review."
    )
    console.print(
        "[bold]Not evidence, not acquired -- ready_for_scope_review still needs the same "
        "human/AI title-and-abstract scope screen this project has always required before "
        "running ke pmc-oa-acquire.[/bold]"
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
        "[bold]Candidates require an AI/automated inclusion and license review "
        "(no human review required); no PDFs were downloaded.[/bold]"
    )


@app.command("europepmc-candidate-review-prepare")
def europepmc_candidate_review_prepare(
    candidates: EuropePmcReviewCandidatesOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
    corpus: CorpusScopeOption = GLP1_METABOLIC_SCOPE.corpus_id,
) -> None:
    """Create a deterministic Europe PMC adjudication worksheet.

    Never approves or promotes a candidate -- mirrors
    `candidate_review_cli.py`'s "prepare" step for the PubMed/PMC pipeline,
    but as a `ke` subcommand for discoverability.
    """

    try:
        vocabulary = resolve_scope_vocabulary(corpus)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _validate_output(output, force=force)
    try:
        worksheet = prepare_europepmc_candidate_review(candidates, vocabulary=vocabulary)
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
        "[bold]Candidates require an AI/automated inclusion and license review "
        "(no human review required); no PDFs were downloaded.[/bold]"
    )


@app.command("core-candidate-review-prepare")
def core_candidate_review_prepare(
    candidates: CoreReviewCandidatesOption,
    output: CandidateOutputOption,
    force: ForceOutputOption = False,
    corpus: CorpusScopeOption = GLP1_METABOLIC_SCOPE.corpus_id,
) -> None:
    """Create a deterministic CORE adjudication worksheet.

    Never approves or promotes a candidate. Note: CORE never supplies a
    license field, so every candidate's license rule is
    `"incomplete_missing_license"` and no CORE candidate can auto-accept --
    see `core_candidate_review.py`'s module docstring.
    """

    try:
        vocabulary = resolve_scope_vocabulary(corpus)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _validate_output(output, force=force)
    try:
        worksheet = prepare_core_candidate_review(candidates, vocabulary=vocabulary)
    except CoreCandidateReviewError as exc:
        console.print(f"[red]CORE candidate review preparation failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    _write_output(output, worksheet.to_json())
    console.print(
        f"[green]Prepared {worksheet.candidate_count} pending candidate reviews:[/green] {output}. "
        "No candidates were approved or promoted."
    )


@app.command("rejected-candidates-add")
def rejected_candidates_add(
    input_path: RejectedCandidatesInputOption,
    ledger: RejectedLedgerOption,
) -> None:
    """Append durable rejection records to the rejected-PMID ledger (M53).

    Reads a JSONL file of already-decided rejections (a human or agent
    reviewer's own judgment, not inferred here) -- each line an object
    with `pmid`, `title`, `reason_category` (one of
    `knowledge_engine.rejected_candidates.REJECTED_REASON_CATEGORIES`),
    and `batch_label`; `doi`/`rejected_date`/`notes` are optional.
    `rejected_date` defaults to today (UTC) when omitted.

    Never overwrites an existing `pmid`'s row: the first recorded
    rejection reason for a given PMID wins, and a duplicate is reported
    as skipped, not silently merged. This closes the exact gap
    `docs/roadmap.md` documents -- `sources.csv` records only what a
    corpus currently includes, not a durable record of what has already
    been reviewed and rejected -- see `ke rejected-candidates-check` for
    the other half: checking a fresh discovery batch against this ledger
    before spending any review time on an already-decided PMID.
    """

    lines = input_path.read_text(encoding="utf-8").splitlines()
    records = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Line {line_number}: invalid JSON.[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(payload, dict):
            console.print(f"[red]Line {line_number}: record must be a JSON object.[/red]")
            raise typer.Exit(1)
        try:
            records.append(parse_rejected_candidate(payload))
        except RejectedCandidatesError as exc:
            console.print(f"[red]Line {line_number}:[/red] {escape(str(exc))}")
            raise typer.Exit(1) from exc

    if not records:
        console.print("[yellow]No rejection records found in input file.[/yellow]")
        return

    appended, skipped = append_rejected_candidates(ledger, records)
    console.print(
        f"[green]Appended {len(appended)} rejection record(s) "
        f"({REJECTED_LEDGER_RULES_VERSION}):[/green] {ledger}"
    )
    if skipped:
        console.print(
            f"[yellow]Skipped {len(skipped)} pmid(s) already in the ledger:[/yellow] "
            f"{', '.join(skipped)}"
        )


@app.command("rejected-candidates-check")
def rejected_candidates_check(
    candidates: RejectedCandidatesCandidatesOption,
    ledger: RejectedLedgerOption,
    output: RejectedCandidatesCheckOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Split a discovery batch into net-new versus already-rejected PMIDs (M53).

    Reads a discovery JSON (`ke pubmed-candidate-discover` and siblings'
    `"candidates"` list) or an adjudication worksheet's `"items"` list,
    and reports which PMIDs the ledger already has a rejection record
    for -- so a reviewer never spends time re-deciding a PMID this
    project has already reviewed and rejected under a different
    `retstart` offset, the exact real failure mode `docs/roadmap.md`
    documents happening twice. Purely a display layer: never writes to
    the ledger, never re-decides a rejection.
    """

    if output and output.exists() and not force:
        raise typer.BadParameter(f"Output file already exists: {output}. Use --force to overwrite.")

    try:
        payload = json.loads(candidates.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print("[red]Candidates file is not valid JSON.[/red]")
        raise typer.Exit(1) from exc
    if not isinstance(payload, dict):
        console.print("[red]Candidates file must be a JSON object.[/red]")
        raise typer.Exit(1)

    candidate_items = extract_candidates(payload)
    if not candidate_items:
        console.print(
            "[yellow]No candidates found (expected a top-level "
            '"candidates" or "items" list).[/yellow]'
        )
        return

    rejected_ledger = load_rejected_ledger(ledger)
    net_new, already_rejected = check_candidates_against_ledger(candidate_items, rejected_ledger)

    lines = [
        "# Rejected-Candidates Check",
        "",
        f"Ledger: `{ledger}` ({len(rejected_ledger)} recorded rejection(s))",
        f"Candidates checked: {len(candidate_items)}",
        f"Net-new: {len(net_new)}",
        f"Already rejected: {len(already_rejected)}",
        "",
    ]
    if already_rejected:
        lines.append("## Already rejected -- drop before review")
        lines.append("")
        for record in already_rejected:
            lines.append(
                f"- PMID {record.pmid} ({record.reason_category}, "
                f"rejected in {record.batch_label} on {record.rejected_date}): "
                f"{record.title}"
            )
        lines.append("")

    report = "\n".join(lines) + "\n"
    if output is not None:
        _write_output(output, report)
        console.print(f"[green]Wrote rejected-candidates check:[/green] {output}")
    else:
        console.print(report, markup=False)

    console.print(
        f"[bold]{len(already_rejected)} of {len(candidate_items)} candidate(s) already "
        "rejected -- drop them before spending review time on this batch.[/bold]"
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


@app.command("clinicaltrials-lookup")
def clinicaltrials_lookup(
    nct_id: ClinicalTrialsLookupNctIdArgument,
    output: ClinicalTrialsLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Resolve an NCT ID to its registry record via NLM/NIH's public ClinicalTrials.gov API v2.

    M71's fifth slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`), alongside M41's
    Wikipedia lookup, M42's RxNorm lookup, M43's MeSH lookup, and M44's
    PubChem lookup: background trial-registration context for an NCT ID
    a paper cites (e.g. "NCT03652870"), not primary-research evidence.
    Never routed through `EvidenceRecord` promotion, and never merged
    with the evidence corpus's own search commands (`ke search`/
    `ke answer`/`ke vector-search`/`ke fused-search`) -- this is a
    separate, explicitly non-evidentiary lookup. An ID ClinicalTrials.gov
    does not recognize (malformed or simply unregistered) returns
    `found: false` rather than a guess.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying ClinicalTrials.gov's public API v2.")
    transport = cast(ClinicalTrialsLookupGetTransport, UrllibClinicalTrialsTransport())
    service = ClinicalTrialsLookupService(transport)
    try:
        result = service.lookup(nct_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ClinicalTrialsLookupError as exc:
        console.print(f"[red]ClinicalTrials.gov lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No ClinicalTrials.gov study found for:[/yellow] {escape(nct_id)}")
    else:
        console.print(f"[bold]{escape(result.brief_title or result.nct_id)}[/bold]")
        if result.overall_status:
            console.print(f"Status: {escape(result.overall_status)}")
        if result.phases:
            console.print(f"Phase: {escape(', '.join(result.phases))}")
        if result.conditions:
            console.print(f"Conditions: {escape(', '.join(result.conditions))}")
        if result.interventions:
            console.print(f"Interventions: {escape(', '.join(result.interventions))}")
        if result.enrollment_count is not None:
            console.print(f"Enrollment: {result.enrollment_count}")
        if result.lead_sponsor:
            console.print(f"Lead sponsor: {escape(result.lead_sponsor)}")
        console.print()
        console.print(
            f"NCT ID: {escape(result.nct_id)}  Source: {escape(result.source_url or 'unknown')}"
        )

    console.print()
    console.print(
        "[bold]This is background reference context from ClinicalTrials.gov, not evidence -- "
        "no scientific synthesis has been performed.[/bold]"
    )


@app.command("uniprot-lookup")
def uniprot_lookup(
    term: UniProtLookupTermArgument,
    output: UniProtLookupOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Resolve a protein/gene name to its top-ranked entry via UniProt's public REST API.

    M73's sixth slice of the reference knowledge layer
    (`docs/reference_knowledge_layer_design.md`), alongside M41's
    Wikipedia lookup, M42's RxNorm lookup, M43's MeSH lookup, M44's
    PubChem lookup, and M71's ClinicalTrials.gov lookup: background
    protein/gene-target context for a term a paper assumes its reader
    already knows (e.g. "PD-1", "GLP-1 receptor"), not primary-research
    evidence. Restricted to reviewed (Swiss-Prot) human entries. Never
    routed through `EvidenceRecord` promotion, and never merged with
    the evidence corpus's own search commands (`ke search`/`ke answer`/
    `ke vector-search`/`ke fused-search`) -- this is a separate,
    explicitly non-evidentiary lookup. A term UniProt does not
    recognize returns `found: false` rather than a guess.
    """

    if output is not None:
        _validate_output(output, force=force)

    console.print("[yellow]Network access:[/yellow] querying UniProt's public REST API.")
    transport = cast(UniProtLookupGetTransport, UrllibUniProtTransport())
    service = UniProtLookupService(transport)
    try:
        result = service.lookup(term)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except UniProtLookupError as exc:
        console.print(f"[red]UniProt lookup failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, result.to_json())

    if not result.found:
        console.print(f"[yellow]No UniProt entry found for:[/yellow] {escape(term)}")
    else:
        console.print(f"[bold]{escape(result.protein_name or result.term)}[/bold]")
        if result.gene_name:
            console.print(f"Gene: {escape(result.gene_name)}")
        if result.organism:
            console.print(f"Organism: {escape(result.organism)}")
        if result.function:
            console.print(f"Function: {escape(result.function)}")
        if result.sequence_length is not None:
            console.print(f"Sequence length: {result.sequence_length}")
        console.print()
        console.print(
            f"UniProt ID: {escape(result.accession or 'unknown')}  "
            f"Source: {escape(result.source_url or 'unknown')}"
        )

    console.print()
    console.print(
        "[bold]This is background reference context from UniProt, not evidence -- "
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
    `docs/history/milestones/m34_europepmc_discovery.md`). Only fetches from `europepmc.org`
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
        "research_question and evidence_direction still need to be filled before "
        "ke extraction-review-promote will accept them. Run ke "
        "extraction-review-autoclassify (M52's deterministic, automated classifier) "
        "to fill them -- no human completion is required. "
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
    already carries its own `source_span.paper_id`, so it can be traced back
    to its paper without needing per-paper files. Exactly the same pipeline
    as the single-paper command; this only removes the one-paper-at-a-time
    friction of generating the queue. Still not validated evidence: `ke
    extraction-review-promote` remains the only path from a draft item to a
    real `EvidenceRecord`, and it still refuses any item missing
    `research_question`/`evidence_direction` -- run `ke
    extraction-review-autoclassify` (M52's deterministic, automated
    classifier) to fill them; no human completion is required. A paper with
    no persisted
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
                [
                    ParsedPage(
                        page_number=page.page_number,
                        text=page.text,
                        table_text=page.table_text,
                    )
                    for page in paper.pages
                ],
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
        "research_question and evidence_direction still need to be filled before "
        "ke extraction-review-promote will accept them. Run ke "
        "extraction-review-autoclassify (M52's deterministic, automated classifier) "
        "to fill them -- no human completion is required.[/bold]"
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
    definitions inline for whatever fills `research_question`/
    `evidence_direction` (typically `ke extraction-review-autoclassify`,
    M52's automated classifier) before running `ke
    extraction-review-promote`.

    Never touches `research_question`, `evidence_direction`, or any other
    field `ke extraction-review-promote` requires -- purely additive context
    that can be read or ignored. A separate, opt-in step from generation:
    run it against the paper(s) being processed next, not automatically
    across the whole corpus -- generating the review queue itself must stay
    network-free even at the corpus's real scale (M40:
    13,588 draft items across 943 papers). Live-verified against real
    papers: expect on the order of a minute or more of network calls for
    one paper's full draft-item set, not a near-instant operation -- see
    `knowledge_engine/extraction_review_annotate.py` for the measured
    numbers. An input file with no draft items still overwrites an
    existing `--output` (clearing any stale prior run's results) rather
    than leaving it untouched.
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
        _write_output(output, "")
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
        "research_question and evidence_direction still need to be filled "
        "(run ke extraction-review-autoclassify, M52's automated classifier -- "
        "no human completion required) before ke extraction-review-promote "
        "will accept any item.[/bold]"
    )


@app.command("extraction-review-autoclassify")
def extraction_review_autoclassify(
    input_path: ExtractionReviewAnnotateInputOption,
    output: ExtractionReviewAnnotateOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Automatically fill research_question/evidence_direction for a draft queue.

    M52. Reads `ke extraction-review-generate`/`-batch-generate`'s JSONL
    output (network-free; run `ke extraction-review-annotate` first if you
    want `reference_context` carried through, though this command does not
    read it) and writes one record per *eligible* draft item, ready for `ke
    extraction-review-promote`.

    See `knowledge_engine.extraction.evidence_classification` for the
    ruleset: `research_question` is a deterministic template over the
    item's own already-extracted population/intervention/comparator/
    outcome fields (M28), and `evidence_direction` is a deterministic
    cue-pattern classification of `claim_text`, defaulting to `supports`
    when no contrast/hedge/null-result cue is present. A draft item missing
    a PICO field, `claim_text`, or `result_summary`, or with an unusually
    long PICO field, is skipped (not guessed) -- see the module's own
    docstring for why.

    Every record this command writes is honestly labeled: `extraction_method`
    names this ruleset's version, never `manual_human_review`, and
    `review_notes` states plainly that no human read or confirmed it. This
    is `core`'s own automated classification path, not the future
    `knowledge-engine-ai` layer's -- see `docs/core_interface_contract.md`'s
    "The seam" section for the real, deliberate decision behind removing
    the human-confirmation step this command used to require.
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
        _write_output(output, "")
        console.print("[yellow]No draft items found in input file.[/yellow]")
        return

    classified: list[dict[str, Any]] = []
    for item in items:
        record = build_automated_evidence_record(item)
        if record is not None:
            classified.append(record)

    lines = "\n".join(json.dumps(record) for record in classified) + "\n" if classified else ""
    _write_output(output, lines)

    console.print(
        f"[green]Automatically classified {len(classified)} / {len(items)} draft item(s) "
        f"({EVIDENCE_CLASSIFICATION_RULES_VERSION}):[/green] {output}"
    )
    console.print(
        f"Skipped {len(items) - len(classified)} item(s) ineligible for automated "
        "classification (a missing/overlong PICO field, or missing claim_text/"
        "result_summary)."
    )
    console.print(
        "[bold]Automated classification, no human review -- run ke "
        "extraction-review-promote against this file's output next.[/bold]"
    )


@app.command("graph-build")
def graph_build(
    evidence: GraphBuildEvidenceOption,
    relationships: GraphBuildRelationshipsOption = None,
    output: GraphBuildOutputOption = None,
    force: ForceOutputOption = False,
    corpus: GraphCorpusIdOption = None,
) -> None:
    """Populate the Phase 4 knowledge graph from validated evidence and relationship records.

    See `docs/phase4_design.md`. Reads an `--evidence` JSONL file (already
    passed `ke evidence-validate`) and creates one `graph_claims` row per
    record. Reuses M45's `annotate_draft_items` unchanged to resolve each
    *new* record's `population`/`intervention`/`comparator`/`outcome` PICO
    field against RxNorm/MeSH -- the same live-network reference-layer
    lookup `extraction-review-annotate` already runs, so the same "expect
    on the order of a minute or more of network calls, not a near-instant
    operation" cost applies here too, for whatever fraction of `--evidence`
    is new. A field that has no confident reference-layer match
    (`found: false`) contributes no concept node -- unlike
    `extraction-review-annotate`'s output, this command does not keep the
    miss on record, since nothing else here reads it back.

    **M54: incremental by design.** An `evidence_record_id` that already
    has a `graph_claims` row is skipped entirely -- no re-annotation, no
    re-lookup -- since that row only ever exists inside a prior,
    fully-committed `graph-build` run, meaning its concept links were
    already resolved too. Re-running this command against a growing
    `--evidence` file costs network calls only for the records added since
    the last run, not the whole file every time; the console output
    reports exactly how many were skipped versus newly looked up. This
    was a real, measured bottleneck at real corpus scale (42 minutes for
    156 records, all re-looked-up on every run) before M54, and matters
    for a continuously-growing evidence base -- see `docs/roadmap.md`'s
    Long-Term Vision section on the live, connected end state this project
    is building toward.

    An optional `--relationships` JSONL file (already passed `ke
    relationship-validate`) adds one `graph_claim_relationships` row per
    record, projecting M24's typed `supports`/`contradicts`/`qualifies`/
    `contextualizes`/`supersedes` (M50) edges into the graph unchanged --
    this command never infers or computes a relationship. A relationship
    whose endpoint is not among the records in `--evidence` is skipped
    with a clear message, never silently dropped or a hard failure of the
    whole run.

    Every method this command calls stays on the same side of the seam
    `docs/roadmap/long_term_vision.md` establishes: it stores and links
    already-authored signals, never computes, defaults, or infers a
    confidence rating. `graph_citations` is out of scope here -- see the
    design doc's Open Questions.

    An optional `--corpus <id>` records which corpus every claim in this
    `--evidence` file belongs to (`graph_claims.corpus_id`), so
    `graph-relationship-candidates`/`relationship-review-worksheet` can
    later be scoped to one corpus instead of the whole (otherwise
    corpus-agnostic) graph. Applied to *every* claim referenced by this
    run's `--evidence` file, not just newly-created ones -- an
    already-existing claim with no `corpus_id` yet gets backfilled, but
    one that already has a `corpus_id` is never overwritten (see
    `GraphRepository.backfill_claim_corpus_id`). Omitting `--corpus`
    leaves every claim's `corpus_id` exactly as it was, preserving this
    command's pre-`--corpus` behavior unchanged.
    """

    if output is not None:
        _validate_output(output, force=force)

    evidence_records = _read_jsonl_records(evidence)
    if not evidence_records:
        console.print("[yellow]No evidence records found in --evidence file.[/yellow]")
        return

    relationship_records = _read_jsonl_records(relationships) if relationships is not None else []

    database = _local_database()
    database.initialize()

    concepts_linked = 0
    relationships_created = 0
    relationships_skipped: list[str] = []

    with database.session() as session:
        repository = GraphRepository(session)

        # M54: a claim row only ever exists inside a fully-committed
        # graph-build transaction (this whole command is one transaction;
        # see Database.session()'s commit-at-exit/rollback-on-exception
        # behavior), so its existence here is a reliable signal its concept
        # links were already resolved too. Skipping annotation for these
        # avoids re-doing every prior run's RxNorm/MeSH network calls on
        # every subsequent run -- the real bottleneck this command had at
        # real corpus scale (42 minutes for 156 records, all re-looked-up
        # every time).
        record_ids = (record.get("evidence_record_id") for record in evidence_records)
        candidate_ids = [
            evidence_record_id
            for evidence_record_id in record_ids
            if isinstance(evidence_record_id, str) and evidence_record_id.strip()
        ]
        existing_claim_ids = repository.find_claim_ids_by_evidence_ids(candidate_ids)
        claims_by_evidence_id: dict[str, int] = dict(existing_claim_ids)
        records_to_annotate = [
            record
            for record in evidence_records
            if str(record.get("evidence_record_id")) not in existing_claim_ids
        ]

        if records_to_annotate:
            console.print(
                "[yellow]Network access:[/yellow] querying NLM's public RxNav and "
                f"E-utilities APIs to resolve PICO fields for {len(records_to_annotate)} "
                f"new record(s) ({len(existing_claim_ids)} already in the graph, skipped)."
            )
            rxnorm_transport = cast(RxNormLookupGetTransport, UrllibRxNavTransport())
            mesh_transport = cast(MeshLookupGetTransport, UrllibNcbiTransport())
            rxnorm_service = RxNormLookupService(rxnorm_transport)
            mesh_service = MeshLookupService(mesh_transport)
            try:
                annotated, _summary = annotate_draft_items(
                    records_to_annotate,
                    rxnorm_service=rxnorm_service,
                    mesh_service=mesh_service,
                )
            except (RxNormLookupError, MeshLookupError) as exc:
                console.print(f"[red]Reference-layer annotation failed:[/red] {escape(str(exc))}")
                raise typer.Exit(1) from exc
        else:
            annotated = []
            console.print(
                f"[green]All {len(existing_claim_ids)} evidence record(s) already in the "
                "graph -- no new network lookups needed.[/green]"
            )

        for item in annotated:
            evidence_record_id = item.get("evidence_record_id")
            if not isinstance(evidence_record_id, str) or not evidence_record_id.strip():
                console.print(
                    "[yellow]Skipped an evidence record with no evidence_record_id.[/yellow]"
                )
                continue

            claim = repository.get_or_create_claim(evidence_record_id, corpus_id=corpus)
            claims_by_evidence_id[evidence_record_id] = claim.id

            reference_context = item.get("reference_context") or {}
            for field, payload in reference_context.items():
                if not isinstance(payload, dict) or not payload.get("found"):
                    continue
                source = payload.get("source")
                if source == "rxnorm":
                    label = payload.get("name") or payload.get("term")
                    source_reference_id = payload.get("rxcui")
                    definition = _rxnorm_definition(payload)
                elif source == "mesh":
                    label = payload.get("heading") or payload.get("term")
                    source_reference_id = payload.get("mesh_id")
                    definition = payload.get("scope_note")
                else:
                    continue
                if not label or not source_reference_id:
                    continue

                concept = repository.get_or_create_concept(
                    label=str(label),
                    source=source,
                    source_reference_id=str(source_reference_id),
                    definition=definition,
                    source_url=payload.get("source_url"),
                    license=payload.get("license"),
                    retrieved_at=str(payload.get("retrieved_at")),
                )
                repository.link_claim_concept(claim.id, concept.id, field)
                concepts_linked += 1

        for record in relationship_records:
            relationship_id = record.get("relationship_id")
            source_evidence_record_id = record.get("source_evidence_record_id")
            target_evidence_record_id = record.get("target_evidence_record_id")
            source_claim_id = claims_by_evidence_id.get(str(source_evidence_record_id))
            target_claim_id = claims_by_evidence_id.get(str(target_evidence_record_id))
            if (
                not isinstance(relationship_id, str)
                or source_claim_id is None
                or target_claim_id is None
            ):
                relationships_skipped.append(str(relationship_id or "<missing relationship_id>"))
                continue

            repository.get_or_create_relationship_edge(
                relationship_id,
                source_claim_id=source_claim_id,
                target_claim_id=target_claim_id,
                relationship_type=str(record.get("relationship_type")),
                rationale=str(record.get("rationale")),
            )
            relationships_created += 1

        claims_backfilled = 0
        if corpus is not None:
            claims_backfilled = repository.backfill_claim_corpus_id(candidate_ids, corpus)

        counts = repository.population_counts()

    console.print(
        f"[green]Graph build complete:[/green] {len(claims_by_evidence_id)} claim(s) processed, "
        f"{concepts_linked} claim-concept link(s) created, "
        f"{relationships_created} relationship edge(s) created."
    )
    if corpus is not None:
        console.print(
            f"Corpus scoping: backfilled corpus_id=[cyan]{escape(corpus)}[/cyan] on "
            f"{claims_backfilled} previously-unscoped claim(s)."
        )
    if relationships_skipped:
        console.print(
            f"[yellow]Skipped {len(relationships_skipped)} relationship(s) with a missing "
            f"relationship_id or an endpoint outside --evidence:[/yellow] "
            f"{', '.join(relationships_skipped)}"
        )
    console.print(
        f"Graph totals -- concepts: {counts['concepts']} {counts['concepts_by_source']}, "
        f"claims: {counts['claims']}, claim-concept edges: {counts['claim_concept_edges']}, "
        f"relationship edges: {counts['relationship_edges']}, "
        f"citation edges: {counts['citation_edges']}."
    )

    if output is not None:
        _write_output(output, json.dumps(counts, indent=2) + "\n")


@app.command("graph-citations-build")
def graph_citations_build(
    output: GraphBuildOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Populate `graph_citations` from every persisted paper's own reference list.

    See `knowledge_engine/citation_extraction.py`'s module docstring for
    the real-corpus measurement (M47) that scoped this to DOI-substring
    matching against the *last* `References`/`Bibliography` heading match
    in each paper's raw text, rather than a structured, multi-format
    entry parser: only 5 intra-corpus citation edges exist across the
    real 960-paper corpus, which does not justify the larger build.

    An edge is only created when a reference-list DOI matches a paper
    already persisted in this database (`graph_citations.cited_paper_id`
    is a real foreign key into `papers`, per `docs/phase4_design.md`) --
    an external DOI with no corresponding row is never stored. Operates
    directly on every persisted paper's own text; unlike `ke graph-build`,
    no input file and no network access are involved.
    """

    if output is not None:
        _validate_output(output, force=force)

    database = _local_database()
    database.initialize()

    papers_scanned = 0

    with database.session() as session:
        papers = PaperRepository(session).list_papers()
        doi_index: dict[str, int] = {
            paper.doi.strip().rstrip(".").casefold(): paper.id for paper in papers if paper.doi
        }

        graph_repository = GraphRepository(session)
        citation_edges_before = graph_repository.population_counts()["citation_edges"]

        for paper in papers:
            if paper.text is None:
                continue
            papers_scanned += 1
            for candidate in find_cited_dois(paper.text.raw_text):
                cited_paper_id = doi_index.get(candidate.doi)
                if cited_paper_id is None or cited_paper_id == paper.id:
                    continue
                graph_repository.add_citation_edge(
                    citing_paper_id=paper.id,
                    cited_paper_id=cited_paper_id,
                    raw_citation_text=candidate.raw_snippet,
                )

        counts = graph_repository.population_counts()
        edges_created = counts["citation_edges"] - citation_edges_before

    console.print(
        f"[green]Citation build complete:[/green] {papers_scanned} paper(s) scanned, "
        f"{edges_created} new citation edge(s) created."
    )
    console.print(
        f"Graph totals -- concepts: {counts['concepts']} {counts['concepts_by_source']}, "
        f"claims: {counts['claims']}, claim-concept edges: {counts['claim_concept_edges']}, "
        f"relationship edges: {counts['relationship_edges']}, "
        f"citation edges: {counts['citation_edges']}."
    )

    if output is not None:
        _write_output(output, json.dumps(counts, indent=2) + "\n")


_GRAPH_REPORT_MARKDOWN_SPECIAL_CHARS = re.compile(r"([\\`*_\[\]<~])")


def _graph_report_text(value: object) -> str:
    """Normalize a graph field for `ke graph-report`'s Markdown output.

    Mirrors `knowledge_engine.cli`'s own `_report_text` (shared by
    `evidence-report`/`relationship-report`, hardened against a real Codex
    finding on the original `relationship-report` addition) exactly:
    collapses embedded whitespace and escapes Markdown-structural
    characters, so a concept label, citation snippet, or relationship
    rationale can never forge a report heading or alter inline formatting.
    A local equivalent, not an independent rediscovery of the same
    escaping rule -- entrypoint.py does not import `cli.py`'s private
    helpers (see `_read_jsonl_records`'s own precedent).
    """

    collapsed = " ".join(str(value).split())
    return _GRAPH_REPORT_MARKDOWN_SPECIAL_CHARS.sub(r"\\\1", collapsed)


def _build_graph_summary_report(graph_repository: GraphRepository) -> str:
    """Build a Markdown report of the graph's current, actual population counts."""

    counts = graph_repository.population_counts()
    by_source = (
        ", ".join(
            f"{source}: {count}" for source, count in sorted(counts["concepts_by_source"].items())
        )
        or "none"
    )
    return "\n".join(
        [
            "# Knowledge Engine Graph Report",
            "",
            f"Generated: {_utc_now_iso_for_report()}",
            "",
            "## Corpus Totals",
            "",
            f"- Concepts: {counts['concepts']} ({by_source})",
            f"- Claims: {counts['claims']}",
            f"- Claim-concept edges: {counts['claim_concept_edges']}",
            f"- Relationship edges: {counts['relationship_edges']}",
            f"- Citation edges: {counts['citation_edges']}",
            "",
            "## Scope",
            "",
            "This report displays the graph's current, actual row counts only "
            "-- nothing here is inferred or synthesized. Run with "
            "`--evidence-record-id` or `--paper-id` for one claim's or "
            "paper's own detail.",
            "",
        ]
    )


def _build_claim_graph_report(graph_repository: GraphRepository, evidence_record_id: str) -> str:
    """Build a Markdown report of one claim's linked concepts and relationships."""

    claim = graph_repository.find_claim_by_evidence_id(evidence_record_id)
    if claim is None:
        console.print(
            f"[red]No graph claim found for evidence_record_id:[/red] {evidence_record_id}"
        )
        console.print("Run `ke graph-build --evidence <file>` first.")
        raise typer.Exit(1)

    lines = [
        "# Knowledge Engine Graph Report",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        "## Claim",
        "",
        f"- Evidence record ID: {_graph_report_text(claim.evidence_record_id)}",
        f"- Graph claim ID: {claim.id}",
        f"- Created: {_graph_report_text(claim.created_at)}",
        "",
        "## Concepts",
        "",
    ]
    concept_edges = graph_repository.concept_edges_for_claim(claim.id)
    if not concept_edges:
        lines.extend(["No concepts are linked to this claim.", ""])
    for edge_role, concept in concept_edges:
        lines.extend(
            [
                f"### {_graph_report_text(edge_role)}: {_graph_report_text(concept.label)}",
                "",
                f"- Source: {_graph_report_text(concept.source)}",
                "- Source reference ID: "
                f"{_graph_report_text(concept.source_reference_id or 'n/a')}",
                f"- Definition: {_graph_report_text(concept.definition or 'n/a')}",
                "",
            ]
        )

    lines.extend(["## Relationships", ""])
    relationships = graph_repository.relationships_for_claim(claim.id)
    if not relationships:
        lines.extend(["No relationship edges are linked to this claim.", ""])
    for relationship in relationships:
        direction = "source" if relationship.source_claim_id == claim.id else "target"
        other_claim_id = (
            relationship.target_claim_id if direction == "source" else relationship.source_claim_id
        )
        other_claim = graph_repository.get_claim(other_claim_id)
        other_evidence_id = other_claim.evidence_record_id if other_claim else "unknown"
        lines.extend(
            [
                f"### {_graph_report_text(relationship.relationship_type)} ({direction})",
                "",
                f"- Relationship ID: {_graph_report_text(relationship.relationship_id)}",
                f"- Other evidence record ID: {_graph_report_text(other_evidence_id)}",
                f"- Rationale: {_graph_report_text(relationship.rationale)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Scope",
            "",
            "This report displays stored graph rows only -- nothing here is "
            "inferred or synthesized.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_paper_citation_report(
    graph_repository: GraphRepository, paper_repository: PaperRepository, paper_id: int
) -> str:
    """Build a Markdown report of one paper's citation edges, as citer and as cited."""

    paper = paper_repository.get(paper_id)
    if paper is None:
        console.print(f"[red]No paper found with database ID:[/red] {paper_id}")
        raise typer.Exit(1)

    citations = graph_repository.citations_for_paper(paper_id)
    cites = [edge for edge in citations if edge.citing_paper_id == paper_id]
    cited_by = [edge for edge in citations if edge.cited_paper_id == paper_id]

    lines = [
        "# Knowledge Engine Graph Report",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        "## Paper",
        "",
        f"- Paper ID: {paper.id}",
        f"- Title: {_graph_report_text(paper.title)}",
        f"- DOI: {_graph_report_text(paper.doi or 'n/a')}",
        "",
        f"## Cites ({len(cites)})",
        "",
    ]
    if not cites:
        lines.extend(["This paper cites no other corpus paper in the graph yet.", ""])
    for edge in cites:
        cited_paper = paper_repository.get(edge.cited_paper_id)
        lines.extend(_graph_report_citation_lines(edge, cited_paper))

    lines.extend([f"## Cited By ({len(cited_by)})", ""])
    if not cited_by:
        lines.extend(["No other corpus paper cites this paper in the graph yet.", ""])
    for edge in cited_by:
        citing_paper = paper_repository.get(edge.citing_paper_id)
        lines.extend(_graph_report_citation_lines(edge, citing_paper))

    lines.extend(
        [
            "## Scope",
            "",
            "This report displays stored citation edges only, from "
            "`ke graph-citations-build`'s DOI-identity matching -- nothing "
            "here is inferred or synthesized.",
            "",
        ]
    )
    return "\n".join(lines)


def _graph_report_citation_lines(edge: GraphCitation, other_paper: Paper | None) -> list[str]:
    """Build Markdown lines for one citation edge and the paper on its other side."""

    other_title = _graph_report_text(other_paper.title) if other_paper else "unknown"
    other_doi = _graph_report_text(other_paper.doi or "n/a") if other_paper else "n/a"
    other_id = other_paper.id if other_paper else "unknown"
    return [
        f"### {other_title}",
        "",
        f"- Paper ID: {other_id}",
        f"- DOI: {other_doi}",
        f"- Raw citation text: {_graph_report_text(edge.raw_citation_text)}",
        "",
    ]


def _utc_now_iso_for_report() -> str:
    """Return the current UTC time as an ISO string, for a report's own generated-at line."""

    return datetime.now(UTC).isoformat(timespec="seconds")


@app.command("graph-report")
def graph_report(
    evidence_record_id: GraphReportEvidenceRecordIdOption = None,
    paper_id: GraphReportPaperIdOption = None,
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Render a Markdown report of the Phase 4 knowledge graph.

    Three modes:

    - No filter: the graph's current corpus-wide population counts.
    - `--evidence-record-id`: one claim's linked concepts (grouped by PICO
      edge role) and relationship edges, as source or target.
    - `--paper-id`: one paper's citation edges, as citer and as cited.

    Purely a display layer over `GraphRepository`'s existing read methods
    -- never writes to the graph, never infers or computes anything the
    graph does not already store.
    """

    if evidence_record_id is not None and paper_id is not None:
        raise typer.BadParameter("Use --evidence-record-id or --paper-id, not both.")
    if output is not None:
        _validate_output(output, force=force)

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        if evidence_record_id is not None:
            report = _build_claim_graph_report(graph_repository, evidence_record_id)
        elif paper_id is not None:
            report = _build_paper_citation_report(
                graph_repository, PaperRepository(session), paper_id
            )
        else:
            report = _build_graph_summary_report(graph_repository)

    if output is not None:
        _write_output(output, report)
        console.print(f"[green]Wrote graph report:[/green] {output}")
        return

    console.print(report, markup=False)


def _build_relationship_candidates_report(
    graph_repository: GraphRepository,
    minimum_shared_concepts: int,
    *,
    corpus_id: str | None = None,
) -> str:
    """Build a Markdown report of claim pairs sharing PICO-resolved concepts.

    Structural overlap only, exactly as `GraphRepository.relationship_candidates`
    computes it -- lists which concepts two claims share, never a
    relationship type or rationale itself. This report is candidate
    surfacing, not classification: `ke relationship-classify-automate`
    (M72) is what actually decides whether, and how, two claims relate,
    running an LLM proposal through deterministic grounding verification
    before writing a `RelationshipRecord`; authoring one by hand and
    checking it with `ke relationship-validate` remains available too.

    An optional `corpus_id` scopes candidates to claims backfilled with
    that `graph_claims.corpus_id` (via `ke graph-build --corpus`); `None`
    preserves this report's original corpus-agnostic behavior unchanged.
    """

    candidates = graph_repository.relationship_candidates(
        minimum_shared_concepts=minimum_shared_concepts, corpus_id=corpus_id
    )

    lines = [
        "# Knowledge Engine Graph Relationship Candidates",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        f"Minimum shared concepts: {minimum_shared_concepts}",
        f"Corpus: {corpus_id if corpus_id else '(all corpora -- unscoped)'}",
        f"Candidate pairs found: {len(candidates)}",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No claim pairs share the minimum number of concepts yet.",
                "",
            ]
        )
    for claim_a, claim_b, shared_concepts in candidates:
        concept_labels = ", ".join(_graph_report_text(concept.label) for concept in shared_concepts)
        lines.extend(
            [
                f"## {_graph_report_text(claim_a.evidence_record_id)} <-> "
                f"{_graph_report_text(claim_b.evidence_record_id)}",
                "",
                f"- Shared concepts ({len(shared_concepts)}): {concept_labels}",
                "",
            ]
        )

    lines.extend(
        [
            "## Scope",
            "",
            "This report surfaces structural overlap only -- which claims "
            "share a PICO-resolved concept. It never infers, detects, or "
            "suggests a relationship type or rationale itself; run `ke "
            "relationship-classify-automate` (M72) to propose and "
            "grounding-verify a relationship for these candidates, or "
            "author one by hand and check it with `ke "
            "relationship-validate`.",
            "",
        ]
    )
    return "\n".join(lines)


@app.command("graph-relationship-candidates")
def graph_relationship_candidates(
    minimum_shared_concepts: GraphRelationshipCandidatesMinimumSharedConceptsOption = 1,
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
    corpus: GraphCorpusIdOption = None,
) -> None:
    """Surface claim pairs sharing PICO-resolved concepts, ready for classification.

    Structural overlap only: lists which claims share a concept and which
    concepts they share, so `ke relationship-classify-automate` (M72) or
    a reviewer authoring a `RelationshipRecord` by hand does not have to
    compose candidate pairs from scratch. Never infers, detects, or
    suggests a `supports`/`contradicts`/`qualifies`/`contextualizes`/
    `supersedes` relationship or its rationale itself -- that is this
    command's own scope boundary, not a statement about who or what
    decides it downstream. A pair already linked by a validated
    relationship edge (any type, `supersedes` included) is excluded,
    since that call has already been made for it, by an automated
    classification or a hand-authored one.

    An optional `--corpus <id>` restricts candidates to claims backfilled
    with that `graph_claims.corpus_id` (see `ke graph-build --corpus`).
    Omitting it preserves this command's original behavior: candidates
    span every corpus in the (corpus-agnostic by default) graph.
    """

    if output is not None:
        _validate_output(output, force=force)

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        report = _build_relationship_candidates_report(
            graph_repository, minimum_shared_concepts, corpus_id=corpus
        )

    if output is not None:
        _write_output(output, report)
        console.print(f"[green]Wrote relationship candidates report:[/green] {output}")
        return

    console.print(report, markup=False)


_WORKSHEET_PICO_FIELDS: tuple[tuple[str, str], ...] = (
    ("study_type", "Study type"),
    ("population", "Population"),
    ("intervention", "Intervention"),
    ("comparator", "Comparator"),
    ("outcome", "Outcome"),
    ("result_summary", "Result summary"),
    ("short_source_excerpt", "Source excerpt"),
)


def _worksheet_claim_lines(evidence_record_id: str, record: dict[str, Any] | None) -> list[str]:
    """Build Markdown lines for one claim's full evidence-record fields, for the review worksheet.

    A record missing from `--evidence` (e.g. it exists in the graph but
    was pruned from the current evidence file) is reported plainly rather
    than silently skipped or guessed at.
    """

    if record is None:
        return [
            f"### {_graph_report_text(evidence_record_id)}",
            "",
            "**Not found in `--evidence` file** -- cannot show fields for this claim.",
            "",
        ]

    source = record.get("source_title") or "(untitled)"
    doi = record.get("source_doi")
    header = f"### {_graph_report_text(evidence_record_id)} -- {_graph_report_text(source)}"
    if doi:
        header += f" (DOI: {_graph_report_text(doi)})"

    lines = [header, ""]
    for field, label in _WORKSHEET_PICO_FIELDS:
        value = record.get(field)
        lines.append(f"- **{label}:** {_graph_report_text(value) if value else '(not recorded)'}")
    lines.append("")
    return lines


def _worksheet_relationship_template(claim_a_id: str, claim_b_id: str) -> list[str]:
    """Build a fill-in-the-blank `RelationshipRecord` JSON block for one candidate pair.

    A template only -- never a suggested or pre-filled relationship type
    or rationale. Reduces the mechanical work of typing the schema's
    boilerplate fields by hand for every relationship authored, exactly
    as M56/M59 required; deciding whether a relationship exists at all,
    and what it says, remains entirely the reviewer's own judgment call.
    """

    return [
        "If you decide these relate, fill in and append this to `relationship_records.jsonl`:",
        "",
        "```json",
        "{",
        '  "schema_version": "0.1",',
        '  "relationship_id": "rel-<fill-in>",',
        f'  "source_evidence_record_id": "{claim_a_id}",',
        f'  "target_evidence_record_id": "{claim_b_id}",',
        '  "relationship_type": "<supports|contradicts|qualifies|contextualizes|supersedes>",',
        '  "rationale": "<why -- cite the specific PICO/result fields above>",',
        '  "provenance": {"created_by": "manual review", '
        '"method": "reviewed via ke relationship-review-worksheet"},',
        '  "created_for_milestone": "<fill-in>"',
        "}",
        "```",
        "",
        "(Swap `source`/`target` if the relationship reads more naturally "
        "the other way -- direction only affects the rationale's wording, "
        "not the relationship's validity.)",
        "",
    ]


def _build_relationship_review_worksheet(
    ranked_candidates: list[RankedCandidate],
    evidence_records_by_id: dict[str, dict[str, Any]],
    *,
    minimum_shared_concepts: int,
    offset: int,
    limit: int,
    ranked_by_similarity: bool,
    corpus_id: str | None = None,
) -> str:
    """Build a Markdown worksheet assembling full field detail for a batch of candidate pairs.

    Candidate selection is exactly `GraphRepository.relationship_candidates`
    unchanged -- this command adds no new candidate-selection logic of
    its own, only removes the busywork of looking up each claim's full
    fields separately once a pair is already surfaced. `ranked_candidates`
    is either that method's own output (shared-concept order) or M61's
    semantic-similarity re-ranking of it, sliced by the caller as needed;
    this function only renders whatever order it is handed. Never infers,
    scores, or suggests a relationship; see `ke relationship-validate`
    for the only thing that ever writes one.
    """

    batch = ranked_candidates[offset : offset + limit]

    lines = [
        "# Knowledge Engine Relationship Review Worksheet",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        f"Minimum shared concepts: {minimum_shared_concepts}",
        f"Corpus: {corpus_id if corpus_id else '(all corpora -- unscoped)'}",
        f"Candidate pairs total: {len(ranked_candidates)}",
        (
            f"This worksheet: pairs {offset + 1}-{offset + len(batch)} of {len(ranked_candidates)}"
            if batch
            else "This worksheet: no pairs at this offset."
        ),
        "Ordering: "
        + ("semantic similarity (M61)" if ranked_by_similarity else "shared-concept count")
        + ", descending",
        "",
        "This worksheet assembles both claims' full evidence-record fields "
        "side by side, and a fill-in-the-blank `RelationshipRecord` "
        "template, for the hand-authoring path -- reviewing a batch of "
        "candidates doesn't require opening each evidence record "
        "separately. It never infers, scores, or suggests a relationship "
        "itself; `ke relationship-classify-automate` (M72) is the "
        "grounding-verified automated path for these same candidates, "
        "checked the same way with `ke relationship-validate` either way.",
        "",
    ]

    for index, ranked in enumerate(batch, start=offset + 1):
        claim_a, claim_b, shared_concepts = (
            ranked.claim_a,
            ranked.claim_b,
            ranked.shared_concepts,
        )
        concept_labels = ", ".join(_graph_report_text(concept.label) for concept in shared_concepts)
        similarity_line = (
            f"Semantic similarity: {ranked.similarity:.2f}"
            if ranked.similarity is not None
            else "Semantic similarity: not available (missing text or record)"
        )
        lines.extend(
            [
                f"## Pair {index} of {len(ranked_candidates)}: "
                f"{_graph_report_text(claim_a.evidence_record_id)} <-> "
                f"{_graph_report_text(claim_b.evidence_record_id)}",
                "",
                f"Shared concepts ({len(shared_concepts)}): {concept_labels}",
            ]
        )
        if ranked_by_similarity:
            lines.append(similarity_line)
        lines.append("")
        lines.extend(
            _worksheet_claim_lines(
                claim_a.evidence_record_id,
                evidence_records_by_id.get(claim_a.evidence_record_id),
            )
        )
        lines.extend(
            _worksheet_claim_lines(
                claim_b.evidence_record_id,
                evidence_records_by_id.get(claim_b.evidence_record_id),
            )
        )
        lines.extend(
            _worksheet_relationship_template(claim_a.evidence_record_id, claim_b.evidence_record_id)
        )
        lines.append("---")
        lines.append("")

    if not batch:
        lines.extend(["No candidate pairs at this offset.", ""])

    lines.extend(
        [
            "## Scope",
            "",
            "This worksheet surfaces structural overlap and stored field "
            "content only -- nothing here is inferred or synthesized. "
            "Candidate selection is exactly `ke graph-relationship-candidates`'s "
            "own; ordering is either that command's own shared-concept "
            "count or M61's semantic-similarity ranking, never a "
            "relationship judgment of any kind.",
            "",
        ]
    )
    return "\n".join(lines)


@app.command("relationship-review-worksheet")
def relationship_review_worksheet(
    evidence: RelationshipReviewWorksheetEvidenceOption,
    minimum_shared_concepts: GraphRelationshipCandidatesMinimumSharedConceptsOption = 1,
    limit: RelationshipReviewWorksheetLimitOption = 10,
    offset: RelationshipReviewWorksheetOffsetOption = 0,
    rank_by_similarity: RelationshipReviewWorksheetRankBySimilarityOption = False,
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
    corpus: GraphCorpusIdOption = None,
) -> None:
    """Assemble a batch of relationship candidates into one side-by-side review worksheet.

    Reuses `ke graph-relationship-candidates`'s exact candidate list, then
    looks up each claim's full evidence-record fields (PICO,
    `result_summary`, `short_source_excerpt`) from `--evidence` so a
    reviewer doesn't have to open every record separately -- the same
    manual assembly work done by hand for every relationship in M56/M59.
    Also includes a fill-in-the-blank `RelationshipRecord` JSON template
    per pair. This worksheet itself never infers, scores, or suggests a
    relationship -- it is the optional hand-authoring path, for a
    reviewer who wants to write one by hand and validate it afterward
    with `ke relationship-validate`. It is not the default: `ke
    relationship-classify-automate` (M72) is the automated,
    grounding-verified path most `RelationshipRecord`s in this project
    now come from, and runs over this same candidate list.

    `--rank-by-similarity` (M61) re-sorts the candidate list by cosine
    similarity of each pair's `outcome`/`result_summary` text, using a
    local, offline `sentence-transformers` model -- no network access, no
    API key. Useful once the 2+-shared-concept tier is exhausted (as it
    is for the real GLP-1 corpus after M56/M59) and remaining candidates
    only share a weak, near-universal concept like `placebo`: ranking by
    actual text similarity surfaces the pairs most likely to be real
    relationships first, without ever deciding one exists. `--limit`/
    `--offset` page through a large candidate list in batches across
    multiple review sessions; a pair already linked by a validated
    relationship edge stops appearing automatically, exactly as `ke
    graph-relationship-candidates` already excludes it.

    An optional `--corpus <id>` restricts candidates to claims backfilled
    with that `graph_claims.corpus_id` (see `ke graph-build --corpus`),
    identically to `ke graph-relationship-candidates --corpus`.
    """

    if output is not None:
        _validate_output(output, force=force)

    evidence_records = _read_jsonl_records(evidence)
    evidence_records_by_id = {
        str(record["evidence_record_id"]): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
        and record["evidence_record_id"].strip()
    }

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        raw_candidates = graph_repository.relationship_candidates(
            minimum_shared_concepts=minimum_shared_concepts, corpus_id=corpus
        )

        if rank_by_similarity:
            generator = _build_embedding_generator("local", None)
            ranked_candidates = rank_candidates_by_similarity(
                raw_candidates, evidence_records_by_id, generator
            )
        else:
            ranked_candidates = [
                RankedCandidate(
                    claim_a=claim_a,
                    claim_b=claim_b,
                    shared_concepts=shared_concepts,
                    similarity=None,
                )
                for claim_a, claim_b, shared_concepts in raw_candidates
            ]

        worksheet = _build_relationship_review_worksheet(
            ranked_candidates,
            evidence_records_by_id,
            minimum_shared_concepts=minimum_shared_concepts,
            offset=offset,
            limit=limit,
            ranked_by_similarity=rank_by_similarity,
            corpus_id=corpus,
        )

    if output is not None:
        _write_output(output, worksheet)
        console.print(f"[green]Wrote relationship review worksheet:[/green] {output}")
        return

    console.print(worksheet, markup=False)


@app.command("relationship-classify-automate")
def relationship_classify_automate(
    evidence: RelationshipClassifyAutomateEvidenceOption,
    relationships: RelationshipClassifyAutomateRelationshipsOption,
    minimum_shared_concepts: GraphRelationshipCandidatesMinimumSharedConceptsOption = 1,
    limit: RelationshipClassifyAutomateLimitOption = 5,
    model: EvidenceReviewAutomateModelOption = None,
    rank_by_similarity: RelationshipReviewWorksheetRankBySimilarityOption = False,
    corpus: GraphCorpusIdOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """M72: propose and grounding-verify relationships for candidate pairs, automatically.

    This is the default path for deciding whether, and how, two claims
    relate -- the same architecture M69 already established for
    evidence-record review: an LLM proposes a `relationship_type`, a
    short `quoted_evidence` phrase, and a `rationale` for each candidate
    pair (`ke graph-relationship-candidates`'s own list, optionally M61
    similarity-ranked via `--rank-by-similarity`). The proposal is
    accepted only when `relationship_type` is schema-valid and
    `quoted_evidence` -- not the free-text `rationale` -- is verified,
    via `verify_grounding`, against both claims' own
    `claim_text`/`result_summary`/`outcome` fields. A pair the model
    cannot confidently classify is skipped, never guessed.
    `relationship-review-worksheet`/`relationship-validate` remain
    available for hand-authoring a relationship instead. Requires a
    running `ollama serve` with the model at `--model`/`KE_LLM_MODEL`
    already pulled.

    Appends each accepted classification to `--relationships` as a new
    `RelationshipRecord` (`provenance.created_by="automated (M72
    relationship classification)"`) -- never rewrites or removes an
    existing relationship. Does **not** rebuild the graph; run `ke
    graph-build` afterward to pick up the new edge(s), the same reminder
    `ke evidence-review-automate` already prints for its own writes.
    """

    llm_model = model or build_settings(Path.cwd()).llm_model
    if not llm_model:
        console.print("[red]No model given.[/red] Pass --model or set KE_LLM_MODEL.")
        raise typer.Exit(1)

    settings = build_settings(Path.cwd())
    llm = OllamaLLM(model=llm_model, host=settings.ollama_host)

    evidence_records = _read_jsonl_records(evidence)
    evidence_records_by_id = {
        str(record["evidence_record_id"]): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
        and record["evidence_record_id"].strip()
    }

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        raw_candidates = graph_repository.relationship_candidates(
            minimum_shared_concepts=minimum_shared_concepts, corpus_id=corpus
        )

        if rank_by_similarity:
            generator = _build_embedding_generator("local", None)
            ranked_candidates = rank_candidates_by_similarity(
                raw_candidates, evidence_records_by_id, generator
            )
        else:
            ranked_candidates = [
                RankedCandidate(
                    claim_a=claim_a,
                    claim_b=claim_b,
                    shared_concepts=shared_concepts,
                    similarity=None,
                )
                for claim_a, claim_b, shared_concepts in raw_candidates
            ]

    batch = ranked_candidates[:limit]
    accepted_records: list[dict[str, Any]] = []
    skipped: list[tuple[str, str, str]] = []

    for ranked in batch:
        claim_a_id = ranked.claim_a.evidence_record_id
        claim_b_id = ranked.claim_b.evidence_record_id
        claim_a = evidence_records_by_id.get(claim_a_id)
        claim_b = evidence_records_by_id.get(claim_b_id)
        if claim_a is None or claim_b is None:
            skipped.append(
                (claim_a_id, claim_b_id, "referenced evidence record not found in --evidence")
            )
            continue

        result = classify_relationship(llm, claim_a, claim_b)
        if not result.accepted:
            skipped.append((claim_a_id, claim_b_id, result.skipped_reason or "unknown"))
            console.print(
                f"[yellow]{claim_a_id} <-> {claim_b_id}:[/yellow] skipped ({result.skipped_reason})"
            )
            continue

        accepted_records.append(
            {
                "schema_version": "0.1",
                "relationship_id": f"rel-m72-{claim_a_id}-{claim_b_id}",
                "source_evidence_record_id": claim_a_id,
                "target_evidence_record_id": claim_b_id,
                "relationship_type": result.relationship_type,
                "rationale": result.rationale,
                "provenance": {
                    "created_by": "automated (M72 relationship classification)",
                    "method": (
                        "LLM-proposed relationship_type and rationale, accepted only after "
                        "the rationale passed deterministic grounding verification against "
                        "both claims' own claim_text/result_summary/outcome text "
                        "(knowledge_engine.extraction.grounding.verify_grounding). "
                        "No human read this pair."
                    ),
                },
                "created_for_milestone": "M72",
            }
        )
        console.print(f"[green]{claim_a_id} <-> {claim_b_id}:[/green] {result.relationship_type}")

    if dry_run:
        console.print(
            f"[yellow]Dry run:[/yellow] {len(accepted_records)} relationship(s) would be "
            "appended; nothing written."
        )
        return

    if accepted_records:
        with relationships.open("a", encoding="utf-8") as handle:
            for record in accepted_records:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    console.print(
        f"[green]Appended {len(accepted_records)} relationship(s), skipped {len(skipped)}.[/green]"
    )
    if accepted_records:
        console.print(
            "[yellow]Graph not rebuilt.[/yellow] Run `ke graph-build` to pick up the "
            "new relationship edge(s)."
        )


def _build_unconfirmed_claims_report(graph_repository: GraphRepository) -> str:
    """Build a Markdown report of claims with zero relationship edges of any type.

    M50's Tracking the Unknown decision
    (`docs/stability_and_tracking_design.md`): the only "gap" this report
    can honestly surface without guessing is a real, structural fact the
    graph already stores -- a claim no `supports`/`contradicts`/
    `qualifies`/`contextualizes`/`supersedes` edge touches yet. It means
    exactly one thing, stated precisely in the report's own Scope section
    below: no second claim has been reviewed and explicitly related to
    this one yet, not that the underlying finding is weak, wrong, or
    under-researched.
    """

    claims = graph_repository.unconfirmed_claims()

    lines = [
        "# Knowledge Engine Graph Unconfirmed Claims",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        f"Unconfirmed claims found: {len(claims)}",
        "",
    ]
    if not claims:
        lines.extend(
            [
                "Every claim in the graph has at least one relationship edge.",
                "",
            ]
        )
    for claim in claims:
        lines.extend(
            [
                f"## {_graph_report_text(claim.evidence_record_id)}",
                "",
                f"- Graph claim ID: {claim.id}",
                f"- Created: {_graph_report_text(claim.created_at)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Scope",
            "",
            "A claim listed here has no `supports`/`contradicts`/`qualifies`/"
            "`contextualizes`/`supersedes` edge yet -- meaning no second "
            "claim has been classified and explicitly related to it, "
            "nothing more. This is a fact about `core`'s own relationship "
            "coverage, not a judgment about the underlying science; run "
            "`ke graph-relationship-candidates` to see which of these "
            "claims already share a PICO-resolved concept with another "
            "claim, then `ke relationship-classify-automate` (M72) to "
            "classify them automatically.",
            "",
        ]
    )
    return "\n".join(lines)


@app.command("graph-unconfirmed-claims")
def graph_unconfirmed_claims(
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Surface claims with zero relationship edges of any type.

    M50's Tracking the Unknown first slice
    (`docs/stability_and_tracking_design.md`): the only honest, non-inferred
    "gap" `core` can report is a claim no relationship edge touches yet --
    a real structural fact the graph already stores, not a guess about
    weak or missing evidence in the underlying science. Purely a display
    layer over `GraphRepository.unconfirmed_claims`; never infers, ranks,
    or judges scientific importance.
    """

    if output is not None:
        _validate_output(output, force=force)

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        report = _build_unconfirmed_claims_report(graph_repository)

    if output is not None:
        _write_output(output, report)
        console.print(f"[green]Wrote unconfirmed claims report:[/green] {output}")
        return

    console.print(report, markup=False)


@dataclass(frozen=True)
class _ComputedEvidenceIntelligence:
    """One claim's fully computed Evidence Intelligence numbers, shared by Markdown/JSON output."""

    claim_id: int
    quality: EvidenceQuality
    consensus: EvidenceConsensus
    confidence: ClaimConfidence
    coverage: EvidenceCoverage


def _compute_evidence_intelligence(
    graph_repository: GraphRepository,
    evidence_records_by_id: dict[str, dict[str, Any]],
    evidence_record_id: str,
) -> _ComputedEvidenceIntelligence:
    """Compute Evidence Quality, Consensus, Claim Confidence, and Coverage for one claim.

    See `docs/evidence_intelligence_design.md`. Deterministic from already-stored
    `EvidenceRecord`/`RelationshipRecord` fields -- no LLM, nothing invented.
    Exits with an error (never a guessed/partial result) if the evidence
    record or its graph claim cannot be found.
    """

    record = evidence_records_by_id.get(evidence_record_id)
    if record is None:
        console.print(
            f"[red]No evidence record found for evidence_record_id:[/red] {evidence_record_id}"
        )
        raise typer.Exit(1)

    claim = graph_repository.find_claim_by_evidence_id(evidence_record_id)
    if claim is None:
        console.print(
            f"[red]No graph claim found for evidence_record_id:[/red] {evidence_record_id}"
        )
        console.print("Run `ke graph-build --evidence <file>` first.")
        raise typer.Exit(1)

    relationships = graph_repository.relationships_for_claim(claim.id)
    relationship_types = [relationship.relationship_type for relationship in relationships]

    quality = compute_evidence_quality(record)
    consensus = compute_evidence_consensus(relationship_types)

    participating_qualities = [quality]
    seen_other_claim_ids: set[int] = set()
    for relationship in relationships:
        if relationship.relationship_type not in ("supports", "contradicts"):
            continue
        other_claim_id = (
            relationship.target_claim_id
            if relationship.source_claim_id == claim.id
            else relationship.source_claim_id
        )
        if other_claim_id in seen_other_claim_ids or other_claim_id == claim.id:
            continue
        seen_other_claim_ids.add(other_claim_id)
        other_claim = graph_repository.get_claim(other_claim_id)
        other_record = (
            evidence_records_by_id.get(other_claim.evidence_record_id) if other_claim else None
        )
        if other_record is not None:
            participating_qualities.append(compute_evidence_quality(other_record))

    confidence = compute_claim_confidence(participating_qualities, consensus)

    total_records = len(evidence_records_by_id)
    graph_counts = graph_repository.population_counts()
    records_in_relationship = graph_counts["claims"] - len(graph_repository.unconfirmed_claims())
    coverage = compute_evidence_coverage(
        total_records=total_records, records_in_relationship=records_in_relationship
    )

    return _ComputedEvidenceIntelligence(
        claim_id=claim.id,
        quality=quality,
        consensus=consensus,
        confidence=confidence,
        coverage=coverage,
    )


def _build_evidence_intelligence_report(
    graph_repository: GraphRepository,
    evidence_records_by_id: dict[str, dict[str, Any]],
    evidence_record_id: str,
) -> str:
    """Build a Markdown Evidence Intelligence report for one claim.

    See `docs/evidence_intelligence_design.md`. The three confidence
    numbers are always rendered as three separate fields, never collapsed
    into one, per that document's explicit requirement.
    """

    computed = _compute_evidence_intelligence(
        graph_repository, evidence_records_by_id, evidence_record_id
    )
    claim_id = computed.claim_id
    quality = computed.quality
    consensus = computed.consensus
    confidence = computed.confidence
    coverage = computed.coverage

    lines = [
        "# Knowledge Engine Evidence Intelligence Report",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        "## Claim",
        "",
        f"- Evidence record ID: {_graph_report_text(evidence_record_id)}",
        f"- Graph claim ID: {claim_id}",
        "",
        "## Evidence Quality",
        "",
        f"- Score: {quality.score}/100",
        f"- Study design tier: {_graph_report_text(quality.study_design_tier)}",
        f"- Extraction tier: {extraction_tier_label(quality.extraction_tier)}",
        "",
        "## Evidence Consensus",
        "",
        f"- Relationship edges: {consensus.relationship_edge_count} "
        f"({consensus.supports_count} supports, {consensus.contradicts_count} contradicts)",
        (
            f"- Score: {consensus.score}/100"
            if consensus.score is not None
            else "- Score: not yet assessable"
        ),
        f"- Reliability: {consensus.reliability}",
        "",
        "## Claim Confidence",
        "",
        (
            f"- Score: {confidence.score}/100"
            if confidence.score is not None
            else "- Score: not yet assessable"
        ),
        f"- Reliability: {confidence.reliability}",
        "",
        "## Evidence Coverage",
        "",
        f"- {coverage.records_in_relationship} of {coverage.total_records} corpus records "
        f"({coverage.percentage}%) participate in a confirmed relationship.",
        "",
        "## Synthesis",
        "",
        *[
            _graph_report_text(line)
            for line in render_synthesis(
                consensus=consensus,
                quality=quality,
                confidence=confidence,
                coverage=coverage,
            )
        ],
        "",
        "## Scope",
        "",
        "Every number above is computed deterministically from already-stored "
        "`EvidenceRecord`/`RelationshipRecord` fields -- no LLM, nothing "
        "invented or inferred beyond what is already stored. See "
        "`docs/evidence_intelligence_design.md`. Evidence Quality, Evidence "
        "Consensus, and Claim Confidence are three separate numbers and "
        "must never be read as one collapsed score.",
        "",
    ]
    return "\n".join(lines)


def _build_evidence_intelligence_json(
    graph_repository: GraphRepository,
    evidence_records_by_id: dict[str, dict[str, Any]],
    evidence_record_id: str,
) -> dict[str, Any]:
    """Build a structured JSON Evidence Intelligence report for one claim.

    Same computation as `_build_evidence_intelligence_report`'s Markdown
    output, as a JSON object instead of prose -- for a consumer that needs
    to parse results programmatically (e.g. `knowledge-engine-ai`), the
    same reasoning `ke evidence-report --format json` was added for. Fields
    match the Markdown report's sections; nothing here is computed
    differently or invented.
    """

    computed = _compute_evidence_intelligence(
        graph_repository, evidence_records_by_id, evidence_record_id
    )
    quality = computed.quality
    consensus = computed.consensus
    confidence = computed.confidence
    coverage = computed.coverage

    return {
        "schema_version": 1,
        "evidence_record_id": evidence_record_id,
        "claim_id": computed.claim_id,
        "evidence_quality": {
            "score": quality.score,
            "study_design_tier": quality.study_design_tier,
            "manually_reviewed": quality.manually_reviewed,
            "extraction_tier": quality.extraction_tier,
        },
        "evidence_consensus": {
            "relationship_edge_count": consensus.relationship_edge_count,
            "supports_count": consensus.supports_count,
            "contradicts_count": consensus.contradicts_count,
            "agreement_total": consensus.agreement_total,
            "score": consensus.score,
            "reliability": consensus.reliability,
        },
        "claim_confidence": {
            "score": confidence.score,
            "reliability": confidence.reliability,
        },
        "evidence_coverage": {
            "records_in_relationship": coverage.records_in_relationship,
            "total_records": coverage.total_records,
            "percentage": coverage.percentage,
        },
        "synthesis": render_synthesis(
            consensus=consensus,
            quality=quality,
            confidence=confidence,
            coverage=coverage,
        ),
        "scope_note": (
            "Every number above is computed deterministically from already-stored "
            "EvidenceRecord/RelationshipRecord fields -- no LLM, nothing invented or "
            "inferred beyond what is already stored. evidence_quality, "
            "evidence_consensus, and claim_confidence are three separate numbers and "
            "must never be read as one collapsed score."
        ),
    }


@app.command("evidence-intelligence")
def evidence_intelligence(
    evidence: EvidenceIntelligenceEvidenceOption,
    evidence_record_id: EvidenceIntelligenceEvidenceRecordIdOption,
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
    report_format: ReportFormatOption = "markdown",
) -> None:
    """Compute deterministic Evidence Quality, Consensus, and Claim Confidence for one claim.

    See `docs/evidence_intelligence_design.md`. Reads an `--evidence` JSONL
    file (already passed `ke evidence-validate`) for the record's own
    fields (`study_type`, `extraction_method`, `review_checklist`,
    `limitations`, `uncertainty_notes`) and the graph (already populated by
    `ke graph-build`) for its relationship edges. No LLM is used and no
    number is invented -- a claim with fewer than 2 eligible relationship
    edges (`supports`/`contradicts`/`qualifies`/`contextualizes`) honestly
    shows Evidence Consensus and Claim Confidence as "not yet assessable"
    rather than a guessed score. Scoped to exactly the
    `clinical_medicine_v1` profile. `--format json` is the structured,
    machine-readable sibling of the default Markdown report, for a
    consumer (e.g. `knowledge-engine-ai`) that needs to parse results
    programmatically rather than scrape prose.
    """

    if report_format not in ("markdown", "json"):
        raise typer.BadParameter("--format must be 'markdown' or 'json'.")

    if output is not None:
        _validate_output(output, force=force)

    evidence_records = _read_jsonl_records(evidence)
    evidence_records_by_id = {
        str(record["evidence_record_id"]): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
        and record["evidence_record_id"].strip()
    }

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        if report_format == "json":
            report = (
                json.dumps(
                    _build_evidence_intelligence_json(
                        graph_repository, evidence_records_by_id, evidence_record_id
                    ),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        else:
            report = _build_evidence_intelligence_report(
                graph_repository, evidence_records_by_id, evidence_record_id
            )

    if output is not None:
        _write_output(output, report)
        console.print(f"[green]Wrote evidence intelligence report:[/green] {output}")
        return

    if report_format == "json":
        # Avoid Rich's word-wrapping corrupting JSON output with inserted
        # newlines, matching `ke evidence-report --format json`'s same fix.
        sys.stdout.write(report)
        return

    console.print(report, markup=False)


_MANUAL_EXTRACTION_METHODS = frozenset({"manual_human_review", "manual"})


def _evidence_review_tier(
    evidence_record_id: str,
    evidence_id_to_claim_id: dict[str, int],
    claim_ids_with_edges: set[int],
    claim_ids_in_candidates: set[int],
) -> tuple[int, str]:
    """Return (tier, reason) for one automated evidence record -- lower tier reviews first."""

    claim_id = evidence_id_to_claim_id.get(evidence_record_id)
    if claim_id is None:
        return 3, "not yet in the graph"
    if claim_id in claim_ids_with_edges:
        return 1, "already touches a relationship edge"
    if claim_id in claim_ids_in_candidates:
        return 2, "appears in a relationship candidate pair"
    return 3, "no relationship signal yet"


def _build_evidence_review_queue(
    graph_repository: GraphRepository,
    evidence_records: list[dict[str, Any]],
    *,
    limit: int,
) -> str:
    """Build a Markdown report prioritizing automated evidence records for the next review pass.

    M62: "automated" means `extraction_method` is not `manual_human_review`/
    `manual` (M52's automated classification pass) and
    `review_checklist.human_reviewed` is not already `true` -- a record
    keeps its M52 `extraction_method` as provenance even after a human
    confirms it, so `human_reviewed` is what actually distinguishes
    still-pending from already-reviewed. Priority is real, structural
    signal only: tier 1 (already touches a relationship edge -- reviewing
    it directly firms up a number already shown in reports/pages), tier 2
    (appears in a relationship candidate pair -- structurally likely to
    matter soon), tier 3 (everything else, including records not yet
    graph-built). Never a quality judgment about the record's own
    content; that is what the review itself is for.
    """

    automated_records = [
        record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
        and record.get("extraction_method") not in _MANUAL_EXTRACTION_METHODS
        and not (record.get("review_checklist") or {}).get("human_reviewed")
    ]

    evidence_id_to_claim_id: dict[str, int] = {}
    claim_ids_with_edges: set[int] = set()
    for record in automated_records:
        evidence_record_id = str(record["evidence_record_id"])
        claim = graph_repository.find_claim_by_evidence_id(evidence_record_id)
        if claim is None:
            continue
        evidence_id_to_claim_id[evidence_record_id] = claim.id
        if graph_repository.relationships_for_claim(claim.id):
            claim_ids_with_edges.add(claim.id)

    claim_ids_in_candidates: set[int] = set()
    for claim_a, claim_b, _shared in graph_repository.relationship_candidates(
        minimum_shared_concepts=1
    ):
        claim_ids_in_candidates.add(claim_a.id)
        claim_ids_in_candidates.add(claim_b.id)

    ranked = sorted(
        automated_records,
        key=lambda record: (
            _evidence_review_tier(
                str(record["evidence_record_id"]),
                evidence_id_to_claim_id,
                claim_ids_with_edges,
                claim_ids_in_candidates,
            )[0],
            str(record["evidence_record_id"]),
        ),
    )
    batch = ranked[:limit]

    lines = [
        "# Knowledge Engine Evidence Review Queue",
        "",
        f"Generated: {_utc_now_iso_for_report()}",
        "",
        f"Automated (unreviewed) records total: {len(automated_records)}",
        f"This queue: {len(batch)} of {len(automated_records)}",
        "",
        "Prioritizes automated (M52) evidence records for manual review by "
        "real structural signal only -- whether a record already touches a "
        "relationship edge or a relationship candidate pair, both real "
        "facts the graph already stores. Never a quality judgment about "
        "the record's own content; that is what the review itself is for.",
        "",
    ]

    for index, record in enumerate(batch, start=1):
        evidence_record_id = str(record["evidence_record_id"])
        tier_rank, tier_reason = _evidence_review_tier(
            evidence_record_id,
            evidence_id_to_claim_id,
            claim_ids_with_edges,
            claim_ids_in_candidates,
        )
        source_title = record.get("source_title") or "(untitled)"
        doi = record.get("source_doi")
        study_type = record.get("study_type") or "unspecified type"
        lines.extend(
            [
                f"## {index}. {_graph_report_text(evidence_record_id)} -- "
                f"{_graph_report_text(source_title)}",
                "",
                f"- Priority: tier {tier_rank} ({tier_reason})",
                f"- Study type: {_graph_report_text(study_type)}",
                f"- Extraction method: "
                f"{_graph_report_text(record.get('extraction_method') or 'unknown')}",
            ]
        )
        if doi:
            lines.append(f"- DOI: {_graph_report_text(doi)}")
        lines.append("")

    if not batch:
        lines.extend(["No automated records found.", ""])

    lines.extend(
        [
            "## Scope",
            "",
            "This queue surfaces stored field content and real graph "
            "structure only -- nothing here is inferred or synthesized, "
            "and no record's underlying accuracy is judged. Reviewing a "
            "record means reading its source and confirming its fields, "
            "the same as `ke extraction-review-promote` already requires.",
            "",
        ]
    )
    return "\n".join(lines)


@app.command("evidence-review-queue")
def evidence_review_queue(
    evidence: EvidenceReviewQueueEvidenceOption,
    limit: EvidenceReviewQueueLimitOption = 20,
    output: GraphReportOutputOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Prioritize automated (M52) evidence records for the next review pass.

    M62: of the corpus's automated (`m52-evidence-classification-v1`)
    records, prioritizes which to feed to `ke evidence-review-automate`
    (M69's automated, grounding-verified LLM review -- no human review
    required) first, by real structural signal -- a record already
    touching a relationship edge (reviewing it directly firms up a number
    already shown in reports/pages) ranks above one merely appearing in a
    relationship candidate pair, which ranks above everything else. Never
    a judgment about a record's own content or accuracy; that is exactly
    what the review itself is for. Reads `--evidence` and the already-built
    graph; writes nothing.
    """

    if output is not None:
        _validate_output(output, force=force)

    evidence_records = _read_jsonl_records(evidence)

    database = _local_database()
    database.initialize()

    with database.session() as session:
        graph_repository = GraphRepository(session)
        queue = _build_evidence_review_queue(graph_repository, evidence_records, limit=limit)

    if output is not None:
        _write_output(output, queue)
        console.print(f"[green]Wrote evidence review queue:[/green] {output}")
        return

    console.print(queue, markup=False)


def _is_already_reviewed(record: dict[str, Any]) -> bool:
    """True when a record needs no further automated-review pass.

    Mirrors `automate_review_for_record`'s own skip rule (manual
    `extraction_method`, or `review_checklist.human_reviewed=True` even
    when `extraction_method` is still an older automated value -- the
    convention `_build_evidence_review_queue` documents: a manually
    reviewed record keeps its prior `extraction_method` as provenance) and
    `compute_evidence_quality`'s `llm_grounded`-tier rule: an
    `extraction_method` in `LLM_GROUNDED_PICO_RULES_VERSIONS` only counts as
    already reviewed when `review_checklist` is actually populated --
    otherwise it is the same as any other automated record and stays
    eligible for reprocessing.
    """

    if record.get("extraction_method") in _MANUAL_EXTRACTION_METHODS:
        return True
    review_checklist = record.get("review_checklist")
    if isinstance(review_checklist, dict) and review_checklist.get("human_reviewed") is True:
        return True
    return (
        record.get("extraction_method") in LLM_GROUNDED_PICO_RULES_VERSIONS
        and isinstance(review_checklist, dict)
        and bool(review_checklist)
    )


@app.command("evidence-record-review-promote")
def evidence_record_review_promote(
    evidence: EvidenceRecordReviewPromoteEvidenceOption,
    dry_run: DryRunOption = False,
) -> None:
    """M72: promote review_status to "reviewed" without requiring a human to set it.

    Several validators (`evidence_map.py`, `binary_statistical_verification.py`,
    `statistical_verification.py`, `statistical_readiness.py`) require
    `review_status == "reviewed"` before a record can be used -- but
    nothing in this project has ever set that field automatically. M52
    only ever writes `"draft"`; the only way a record has ever reached
    `"reviewed"` was hand-editing the JSONL directly. This command closes
    that gap using this project's own existing definition of "already
    trustworthy without a human reading it" -- `_is_already_reviewed`,
    the same eligibility check `ke evidence-review-automate` already uses
    to decide a record needs no further automated-review pass (manual
    provenance, or an LLM-grounded `extraction_method` whose fields
    already passed `verify_grounding` during extraction). A record still
    at raw `m52-evidence-classification-v1` -- never grounding-verified --
    is left untouched; run `ke evidence-review-automate` on it first.
    """

    raw_lines = evidence.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any] | None] = []
    for line_number, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            records.append(None)
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Line {line_number}: invalid JSON.[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(record, dict):
            console.print(f"[red]Line {line_number}: record must be a JSON object.[/red]")
            raise typer.Exit(1)
        records.append(record)

    eligible_indices = [
        index
        for index, record in enumerate(records)
        if record is not None
        and record.get("review_status") != "reviewed"
        and _is_already_reviewed(record)
    ]

    console.print(f"Records eligible for promotion: {len(eligible_indices)}.")

    if dry_run:
        console.print(
            f"[yellow]Dry run:[/yellow] {len(eligible_indices)} record(s) would be promoted; "
            "nothing written."
        )
        return

    promoted_ids: list[str] = []
    for index in eligible_indices:
        record = records[index]
        assert record is not None
        record["review_status"] = "reviewed"
        existing_notes = record.get("review_notes")
        promotion_note = (
            "M72 promotion: review_status set to 'reviewed' without human review, "
            "based on this record's own already-grounding-verified extraction "
            "(see review_checklist) or manual provenance. No human read this record."
        )
        record["review_notes"] = (
            f"{existing_notes} {promotion_note}" if existing_notes else promotion_note
        )
        promoted_ids.append(str(record.get("evidence_record_id", f"line {index + 1}")))

    if eligible_indices:
        with evidence.open("w", encoding="utf-8") as handle:
            for index, raw_line in enumerate(raw_lines):
                if index in eligible_indices:
                    record = records[index]
                    assert record is not None
                    handle.write(json.dumps(record, separators=(",", ":")) + "\n")
                else:
                    handle.write(raw_line + "\n")

    console.print(f"[green]Promoted {len(promoted_ids)} record(s) to 'reviewed'.[/green]")
    if promoted_ids:
        console.print(", ".join(promoted_ids))


@app.command("evidence-review-automate")
def evidence_review_automate(
    evidence: EvidenceReviewQueueEvidenceOption,
    limit: EvidenceReviewAutomateLimitOption = 5,
    model: EvidenceReviewAutomateModelOption = None,
    evidence_record_id: EvidenceReviewAutomateRecordIdOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """M69: run the LLM-grounded PICO pipeline over still-automated records.

    Replaces the human-reading review gate with a grounding-verified LLM
    extraction path, per `docs/roadmap/long_term_vision.md`'s "Decision:
    automated evidence review at scale" -- manual review does not scale
    to this project's real corpus-growth plans. For each still-automated
    (`m52-evidence-classification-v1`) record, re-derives
    `population`/`intervention`/`comparator`/`outcome` from that record's
    own source page plus page 1 when they differ. This fixes both the
    PICO-broadcast bug M68 found by hand (where a paper-level extraction
    got glued onto every claim) and the terse-result context gap found
    after the first full M69 backlog run. The command uses the
    local model at `--model`/`KE_LLM_MODEL`. Every LLM-proposed field is
    checked against that bounded source context before being accepted; a field
    that fails grounding is left unchanged, never blanked or guessed.
    `claim_text`, `research_question`, and `evidence_direction` are never
    touched -- they stay on their existing deterministic path.

    A record is relabeled with its own honest `extraction_method`
    (never `manual_human_review`) only when at least one field is
    accepted. Requires a running `ollama serve` with the model already
    pulled. Writes `--evidence` in place, rewriting only the lines for
    records this run actually changed. Does **not** rebuild the graph --
    print a reminder listing which `evidence_record_id`s changed, since
    `ke graph-build`'s M54 incremental design skips any
    `evidence_record_id` that already has a `graph_claims` row; clear
    those rows before the next `ke graph-build` run to pick up the
    correction.
    """

    llm_model = model or build_settings(Path.cwd()).llm_model
    if not llm_model:
        console.print("[red]No model given.[/red] Pass --model or set KE_LLM_MODEL.")
        raise typer.Exit(1)

    settings = build_settings(Path.cwd())
    llm = OllamaLLM(model=llm_model, host=settings.ollama_host)

    raw_lines = evidence.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any] | None] = []
    for line_number, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            records.append(None)
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Line {line_number}: invalid JSON.[/red]")
            raise typer.Exit(1) from exc
        if not isinstance(record, dict):
            console.print(f"[red]Line {line_number}: record must be a JSON object.[/red]")
            raise typer.Exit(1)
        records.append(record)

    eligible_indices = [
        index
        for index, record in enumerate(records)
        if record is not None
        and not _is_already_reviewed(record)
        and (evidence_record_id is None or record.get("evidence_record_id") == evidence_record_id)
    ]

    if evidence_record_id is not None and not eligible_indices:
        console.print(
            f"[red]No eligible record found for evidence_record_id "
            f"{evidence_record_id!r}[/red] (missing, already manually reviewed, or "
            "already llm-grounded)."
        )
        raise typer.Exit(1)

    batch_indices = eligible_indices[:limit]
    total_eligible = len(eligible_indices)

    console.print(
        f"Automated records still eligible: {total_eligible}. "
        f"Processing {len(batch_indices)} this run."
    )

    updated_ids: list[str] = []
    updated_indices: set[int] = set()
    skipped: list[tuple[str, str]] = []
    page_text_cache: dict[tuple[int, int], str | None] = {}

    for index in batch_indices:
        record = records[index]
        assert record is not None
        record_evidence_id = str(record.get("evidence_record_id", f"line {index + 1}"))
        source_span = record.get("source_span") or {}
        paper_id = source_span.get("paper_id")
        page_number = source_span.get("page_number")

        page_text: str | None = None
        paper_first_page_text: str | None = None
        if isinstance(paper_id, int) and isinstance(page_number, int):
            cache_key = (paper_id, page_number)
            if cache_key not in page_text_cache:
                loaded = _load_paper_pages(paper_id)
                page_by_number = (
                    {page.page_number: page.text for page in loaded[1]}
                    if loaded is not None
                    else {}
                )
                for candidate_page_number, candidate_text in page_by_number.items():
                    page_text_cache[(paper_id, candidate_page_number)] = candidate_text
            page_text = page_text_cache.get(cache_key)
            if page_number != 1:
                paper_first_page_text = page_text_cache.get((paper_id, 1))

        try:
            result = automate_review_for_record(
                llm,
                record,
                page_text,
                paper_first_page_text=paper_first_page_text,
            )
        except LocalLLMError as exc:
            console.print(f"[red]{record_evidence_id}: {exc}[/red]")
            raise typer.Exit(1) from exc

        if result.updated:
            updated_ids.append(record_evidence_id)
            updated_indices.add(index)
            console.print(
                f"[green]{record_evidence_id}:[/green] grounded {', '.join(result.fields_grounded)}"
            )
        else:
            skipped.append((record_evidence_id, result.skipped_reason or "unknown"))
            console.print(
                f"[yellow]{record_evidence_id}:[/yellow] skipped ({result.skipped_reason})"
            )

    if dry_run:
        console.print(
            f"[yellow]Dry run:[/yellow] {len(updated_ids)} record(s) would be updated; "
            "nothing written."
        )
        return

    if updated_indices:
        with evidence.open("w", encoding="utf-8") as handle:
            for index, raw_line in enumerate(raw_lines):
                if index in updated_indices:
                    record = records[index]
                    assert record is not None
                    handle.write(json.dumps(record, separators=(",", ":")) + "\n")
                else:
                    handle.write(raw_line + "\n")

    console.print(f"[green]Updated {len(updated_ids)} record(s), skipped {len(skipped)}.[/green]")
    if updated_ids:
        console.print(
            "[yellow]Graph not rebuilt.[/yellow] Clear stale graph_claims/"
            "graph_claim_concepts rows for the updated evidence_record_id(s) "
            f"before the next `ke graph-build` run: {', '.join(updated_ids)}"
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
                        PaperPage(
                            page_number=page.page_number,
                            text=page.text,
                            table_text=page.table_text,
                        )
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


@app.command("paper-pages-table-text-backfill")
def paper_pages_table_text_backfill(dry_run: DryRunOption = False) -> None:
    """Backfill `paper_pages.table_text` for papers imported before this field existed.

    Unlike `paper-pages-backfill` (which only targets papers with zero
    `paper_pages` rows at all), this targets every paper that already has
    pages, since `table_text` cannot be recovered from already-persisted
    page text alone -- it depends on PDF layout geometry only a fresh parse
    of the original file can recompute. Reuses the exact same safety gate:
    only papers whose original local PDF is still present, and whose
    freshly re-parsed content hash matches the persisted one, are
    backfilled. A missing or changed source file is reported, never
    silently skipped. Already-idempotent: a paper whose pages already carry
    `table_text` is re-parsed and rewritten with the same values (parsing is
    deterministic), so running this command twice is safe.
    """

    database = _local_database()
    database.initialize()
    parser = PyMuPDFParser()

    counts: dict[str, int] = {}
    with database.session() as session:
        repository = PaperRepository(session)
        papers = [paper for paper in repository.list_papers() if paper.pages]

        if not papers:
            console.print("[green]No papers with existing pages need backfilling.[/green]")
            return

        for paper in papers:
            outcome, parsed = backfill_paper(paper, parser)
            counts[outcome.status] = counts.get(outcome.status, 0) + 1

            if outcome.status == "backfilled" and parsed is not None:
                if not dry_run:
                    paper.pages = [
                        PaperPage(
                            page_number=page.page_number,
                            text=page.text,
                            table_text=page.table_text,
                        )
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
    except OperationalError as exc:
        if "no such column" in str(exc):
            console.print(
                "[red]This snapshot predates the current database schema[/red] "
                f"(schema version {CURRENT_SCHEMA_VERSION}) -- {escape(str(exc.orig))}. "
                "Regenerate it from a fully-migrated local database with "
                "`ke corpus-library-export --output <path>` and re-commit the result; "
                "there is no automatic schema upgrade for a corpus-library snapshot file "
                "itself, only for the local database `ke init` builds."
            )
            raise typer.Exit(1) from None
        raise
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


def _federated_discovery_registry(
    *, openalex_api_key: str | None, semantic_scholar_api_key: str | None = None
) -> DiscoveryProviderRegistry:
    """Compose the production federated-discovery providers (FRD-1 through FRD-4/FRD-6).

    Reuses this project's existing, already-battle-tested PubMed and Crossref
    services (`_pubmed_discovery_service`/`_crossref_provider`) behind their
    FRD adapters rather than building new transports for hosts this project
    already talks to. OpenAlex, Semantic Scholar, and arXiv are the three
    genuinely new providers wired here. OpenAlex is optional and reports
    itself `disabled` (not an error) when no API key is configured, matching
    `OpenAlexProvider`'s own graceful-degradation contract. Semantic Scholar's
    public Academic Graph access works without any key by design
    (`SemanticScholarProvider`'s own contract) -- an optional key only raises
    its rate limit, sent as an `x-api-key` header, never a hard requirement
    to search. arXiv (FRD-4) is fully public and keyless -- no credential
    parameter exists for it, matching `ArxivProvider`'s own contract.
    """

    providers: list[DiscoveryProvider] = [
        PubmedFederatedAdapter(_pubmed_discovery_service()),
        CrossrefFederatedAdapter(_crossref_provider()),
        OpenAlexProvider(transport=UrllibOpenAlexTransport(), api_key=openalex_api_key),
        SemanticScholarProvider(
            transport=UrllibSemanticScholarTransport(), api_key=semantic_scholar_api_key
        ),
        ArxivProvider(transport=UrllibArxivTransport()),
    ]
    return DiscoveryProviderRegistry(providers)


def _parse_federated_providers(providers: str | None) -> tuple[str, ...] | None:
    if providers is None:
        return None
    names = tuple(name.strip() for name in providers.split(",") if name.strip())
    if not names:
        raise typer.BadParameter("--providers must name at least one provider when given.")
    return names


@app.command("federated-discover")
def federated_discover(
    query: FederatedQueryOption,
    ledger_root: FederatedLedgerRootOption,
    limit: FederatedLimitOption = 20,
    year_from: FederatedYearFromOption = None,
    year_to: FederatedYearToOption = None,
    providers: FederatedProvidersOption = None,
    openalex_api_key: FederatedOpenAlexApiKeyOption = None,
    semantic_scholar_api_key: FederatedSemanticScholarApiKeyOption = None,
    initiated_by: FederatedInitiatedByOption = None,
    project_id: FederatedProjectIdOption = None,
    research_question_id: FederatedResearchQuestionIdOption = None,
    output: FederatedDiscoverOutputOption = None,
) -> None:
    """Run one federated discovery search and durably persist its coverage (FRD-6).

    Fans one query out across every configured provider (PubMed, Crossref,
    OpenAlex, Semantic Scholar, and arXiv today -- see
    `_federated_discovery_registry`), deduplicates candidates by exact DOI,
    and -- critically -- persists the run to `--ledger-root` *before*
    returning it, so coverage can always be re-fetched later via
    `federated-coverage-report` rather than trusted from memory. This is the
    first CLI surface for the FRD-1 through FRD-4/FRD-6 federated-discovery
    modules (`discovery_broker.py`, `federated_discovery_service.py`,
    `federated_search_ledger.py`, the provider adapters); until this command
    existed, that code was built and unit-tested but unreachable from outside
    a test file. See `docs/roadmap/federated_research_discovery_adoption.md`.

    A provider that cannot answer a given query (rate-limited, unavailable,
    or -- as with Crossref's DOI-only lookup today -- structurally
    unsupported for a free-text query) is reported as an explicit, labeled
    provider status, never silently dropped from the result. Coverage must
    never be inferred from the presence of results.

    `--output <path.json>` additionally saves the full result for a
    programmatic caller: the same facts as the console table
    (`FederatedSearchResult.to_json()`'s candidate/provider shape) plus the
    persisted `search_run_id`, the deterministic public `coverage` record
    (search timestamp, normalized query, year bounds, per-provider limit --
    see `SearchCoverageReport.to_dict()`), and `provider_disagreements`
    (conflicting provider-observed metadata for the same candidate, with no
    provider treated as authoritative -- see `build_provider_disagreement_report`).
    The ledger under `--ledger-root` is the durable, replayable record
    either way; `--output` is a convenience snapshot of one run's own
    result, not a second source of truth.

    `--project-id` and `--research-question-id` are optional internal run
    context, threaded straight through to `FederatedDiscoveryService.search`
    and persisted on the ledger record -- they were already accepted by
    every layer beneath this command, only unreachable from the CLI until
    now. `--research-question-id` is what later lets `ke
    federated-discover-history <id>` list every run for the same tracked
    question together; neither value enters the public coverage payload
    (`SearchCoverageReport`) `--output`/`federated-coverage-report` expose.
    """

    try:
        broker_query = DiscoveryQuery(
            text=query,
            year_from=year_from,
            year_to=year_to,
            limit_per_provider=limit,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    registry = _federated_discovery_registry(
        openalex_api_key=openalex_api_key,
        semantic_scholar_api_key=semantic_scholar_api_key,
    )
    try:
        provider_names = _parse_federated_providers(providers)
        recorder = FederatedSearchLedger(ledger_root)
        service = registry.build_recorded_service(recorder, provider_names)
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(
        "[yellow]Network access:[/yellow] querying configured federated discovery "
        "providers over HTTPS."
    )
    execution = service.search(
        broker_query,
        initiated_by=initiated_by,
        project_id=project_id,
        research_question_id=research_question_id,
    )

    if output is not None:
        payload = build_public_federated_result_payload(execution.result, execution.coverage)
        _write_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    _print_federated_coverage(execution.coverage, search_run_id=execution.record.search_run_id)

    if execution.result.candidates:
        table = Table(title="Deduplicated candidates (exact DOI)")
        table.add_column("Title")
        table.add_column("Year")
        table.add_column("DOI")
        table.add_column("Providers")
        for candidate in execution.result.candidates:
            providers_seen = ", ".join(
                sorted({observation.provider for observation in candidate.observations})
            )
            table.add_row(
                escape(candidate.title),
                str(candidate.publication_year) if candidate.publication_year else "",
                escape(candidate.doi or ""),
                providers_seen,
            )
        console.print(table)

    console.print(
        "[bold]Discovery only -- these are not Evidence Records and were not acquired. "
        "Run the same PMC-scoped candidate/acquisition commands for anything meant to "
        "enter the corpus.[/bold]"
    )


@app.command("federated-coverage-report")
def federated_coverage_report(
    search_run_id: FederatedSearchRunIdArgument,
    ledger_root: FederatedLedgerRootOption,
    output: FederatedCoverageReportOutputOption = None,
) -> None:
    """Print the persisted coverage facts for one federated search run (FRD-6).

    Lets a caller (a person, or `knowledge-engine-web`/`knowledge-engine-ai`
    once they read this ledger) re-fetch a run's coverage deterministically
    after the fact, rather than trusting whatever `federated-discover`
    printed at search time -- the reproducibility guarantee
    `FederatedDiscoveryService`'s own docstring names explicitly.

    `--output <path.json>` additionally saves this run's own deduplicated
    candidate list (title, DOI, year, and every provider's full observation
    -- the same shape `federated-discover --output` already serializes at
    request time) alongside its coverage record, so a caller can look up a
    *specific past run's* candidates without re-running the search --
    closing the point-lookup gap `knowledge-engine-web`'s WEB-FRD-5
    freshness-history design identified (see
    `docs/roadmap/federated_research_discovery_adoption.md`'s FRD-6
    section). Runs persisted before this capability existed carry no
    candidate snapshot in the ledger; `candidates` is an honest empty list
    for those, never reconstructed or approximated.
    """

    recorder = FederatedSearchLedger(ledger_root)
    try:
        record = recorder.load(search_run_id)
    except FileNotFoundError:
        console.print(f"[red]No federated search run found:[/red] {escape(search_run_id)}")
        raise typer.Exit(1) from None
    except ValueError as exc:
        console.print(f"[red]Malformed federated search-run record:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    coverage = build_search_coverage_report(record)

    if output is not None:
        payload = {
            "search_run_id": coverage.search_run_id,
            "coverage": coverage.to_dict(),
            "candidates": [candidate.to_dict() for candidate in record.candidates],
        }
        _write_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    _print_federated_coverage(coverage, search_run_id=coverage.search_run_id)


@app.command("general-question-acquisition-plan")
def general_question_acquisition_plan(
    request_path: GeneralQuestionAcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    output: GeneralQuestionAcquisitionOutputOption = None,
    no_database: GeneralQuestionAcquisitionNoDatabaseOption = False,
) -> None:
    """Resolve a bounded General Question Research Loop v1 acquisition request (CORE-GQR-1/GQR-2).

    Reads a JSON `GeneralQuestionAcquisitionRequest` from `REQUEST_PATH`,
    resolves its `candidate_ids` strictly against the persisted
    `federated-discover` snapshot named by `search_run_id` under
    `--ledger-root`, and reconciles explicit acquisition/full-text budgets
    into a stable, auditable `GeneralQuestionAcquisitionPlan`
    (`knowledge_engine/general_question_acquisition.py`). This is the first
    CLI surface for that module -- until now it was built and unit-tested
    but reachable only from a test file, the same gap `federated-discover`
    closed for the FRD-1 through FRD-4/FRD-6 modules. See
    `docs/general_question_research_loop_v1.md`.

    Every returned item's disposition (`already_indexed`,
    `eligible_full_text`, `metadata_only`, `skipped_budget`, or
    `not_found_in_run`) describes acquisition eligibility, never scientific
    support -- this command plans and reuses; it does not download full
    text, ingest anything, or produce an Evidence Record (CORE-GQR-3/4/5
    remain future work, tracked on `docs/general_question_research_loop_v1.md`).

    By default the local database is opened read-only-in-effect (nothing is
    added, so its commit is a no-op) to detect candidates that already
    match an existing `Paper` by DOI, then PMID, then arXiv ID, reporting
    them `already_indexed` instead of re-queuing them for acquisition --
    reuse never competes with genuinely new candidates for the full-text
    budget. `--no-database` skips that lookup entirely, matching
    `build_acquisition_plan`'s own `session=None` snapshot-only contract,
    for a caller that only wants the search-run resolution and budget
    reconciliation without touching local state.

    `--output <path.json>` additionally saves the full plan
    (`GeneralQuestionAcquisitionPlan.to_dict()`) for a programmatic caller
    -- e.g. `knowledge-engine-ai`, which consumes Core only through this
    CLI JSON boundary -- rather than parsing the console table.
    """

    try:
        request = GeneralQuestionAcquisitionRequest.from_json(
            request_path.read_text(encoding="utf-8")
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    try:
        if no_database:
            plan = build_acquisition_plan(request, ledger_root=ledger_root)
        else:
            database = _local_database()
            database.initialize()
            with database.session() as session:
                plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
    except FileNotFoundError:
        console.print(f"[red]No federated search run found:[/red] {escape(request.search_run_id)}")
        raise typer.Exit(1) from None
    except ValueError as exc:
        console.print(f"[red]Acquisition request could not be resolved:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if output is not None:
        _write_output(output, plan.to_json())

    _print_acquisition_plan(plan)


@app.command("general-question-acquire-pmc")
def general_question_acquire_pmc(
    request_path: GeneralQuestionAcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible PMC routes from one bounded acquisition request (CORE-GQR-4)."""

    _validate_output(receipt, force=force)
    try:
        request = GeneralQuestionAcquisitionRequest.from_json(
            request_path.read_text(encoding="utf-8")
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    try:
        database = _local_database()
        database.initialize()
        with database.session() as session:
            plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
        console.print(
            "[yellow]Network access:[/yellow] resolving planned PMIDs and acquiring "
            "license-verified PDFs from official PMC OA resources."
        )
        execution = execute_pmc_acquisition_plan(
            plan,
            resolver=_pubmed_discovery_service(),
            acquisition_service=_pmc_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        console.print(f"[red]No federated search run found:[/red] {escape(request.search_run_id)}")
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionPmcAcquisitionError) as exc:
        console.print(f"[red]General-question PMC acquisition failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    try:
        with database.session() as session:
            persistence_receipt = persist_pmc_acquisition_execution(
                session,
                plan,
                execution,
                output_directory=papers_dir,
            )
            _write_output(receipt, persistence_receipt.to_json())
    except typer.BadParameter:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes "
            "were rolled back."
        ) from None
    except GeneralQuestionPmcAcquisitionError as exc:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        console.print(
            f"[red]General-question PMC persistence failed:[/red] {escape(str(exc))}"
        )
        raise typer.Exit(1) from exc
    except Exception:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise

    console.print(
        f"[green]Acquired and parsed {persistence_receipt.parsed_count} planned PMC OA "
        f"PDFs.[/green] Receipt: {receipt}"
    )
    console.print(
        f"[bold]Persisted {persistence_receipt.persisted_count} new Papers and reused "
        f"{persistence_receipt.reused_count} existing Papers with search-run and "
        "candidate provenance preserved in the receipt.[/bold]"
    )


def _print_acquisition_plan(plan: GeneralQuestionAcquisitionPlan) -> None:
    console.print(f"[bold]Search run:[/bold] {plan.search_run_id}")
    console.print(f"[bold]Research question:[/bold] {escape(plan.research_question_id)}")
    console.print(
        f"[bold]Requested:[/bold] {plan.requested_candidate_count}  "
        f"[bold]Resolved:[/bold] {plan.resolved_candidate_count}  "
        f"[green]Already indexed:[/green] {plan.already_indexed_count}  "
        f"[cyan]Full text eligible:[/cyan] {plan.full_text_selected_count}  "
        f"[blue]Metadata only:[/blue] {plan.metadata_only_count}  "
        f"[yellow]Skipped (budget):[/yellow] {plan.skipped_budget_count}  "
        f"[red]Not in run:[/red] {plan.missing_candidate_count}"
    )
    if plan.provider_failures:
        console.print(
            "[red]Provider failures on the underlying search run:[/red] "
            f"{', '.join(plan.provider_failures)}"
        )

    disposition_color = {
        AcquisitionDisposition.ALREADY_INDEXED.value: "green",
        AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value: "cyan",
        AcquisitionDisposition.METADATA_ONLY.value: "blue",
        AcquisitionDisposition.SKIPPED_BUDGET.value: "yellow",
        AcquisitionDisposition.NOT_FOUND_IN_RUN.value: "red",
    }
    table = Table(title="Acquisition plan")
    table.add_column("Candidate")
    table.add_column("Title")
    table.add_column("Disposition")
    table.add_column("Reason")
    for item in plan.items:
        color = disposition_color.get(item.disposition, "white")
        table.add_row(
            escape(item.candidate_id),
            escape(item.title or ""),
            f"[{color}]{item.disposition}[/{color}]",
            escape(item.reason or ""),
        )
    console.print(table)

    console.print(
        "[bold]Plan only -- no full text was downloaded and nothing was ingested. "
        "Dispositions describe acquisition eligibility, not scientific support.[/bold]"
    )


@app.command("federated-discover-history")
def federated_discover_history(
    research_question_id: FederatedHistoryResearchQuestionIdArgument,
    ledger_root: FederatedLedgerRootOption,
    output: FederatedHistoryOutputOption = None,
) -> None:
    """List every persisted `federated-discover` run for one tracked question (FRD-6).

    `federated-coverage-report` above is a point lookup: it requires the
    caller to already know one run's exact `search_run_id`. This command is
    the first ledger read that discovers which runs exist at all for a
    tracked question -- `FederatedSearchLedger.list_by_research_question_id`
    -- letting a caller (e.g. `knowledge-engine-web`'s planned freshness-
    history view) fetch every past run for the same
    `research_question_id` a caller previously passed to `ke
    federated-discover --research-question-id`, newest first, and diff them.

    Each listed run is rendered through the same public,
    provenance-safe `SearchCoverageReport` shape `federated-coverage-report`
    and `federated-discover --output`'s `coverage` field already expose --
    `initiated_by`/`project_id` never enter this payload either. No matching
    runs is reported plainly, never as an error: a tracked question with no
    prior recorded search is an expected, honest state, not a failure.
    """

    recorder = FederatedSearchLedger(ledger_root)
    try:
        records = recorder.list_by_research_question_id(research_question_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    coverage_reports = [recorder.coverage_report(record.search_run_id) for record in records]

    if output is not None:
        payload = {
            "research_question_id": research_question_id.strip(),
            "run_count": len(coverage_reports),
            "runs": [report.to_dict() for report in coverage_reports],
        }
        _write_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    if not coverage_reports:
        console.print(
            "[yellow]No federated-discover runs found for research_question_id:[/yellow] "
            f"{escape(research_question_id)}"
        )
        return

    console.print(
        f"[bold]Federated-discover history:[/bold] {escape(research_question_id)} "
        f"({len(coverage_reports)} run(s), newest first)"
    )
    table = Table(title="Search runs")
    table.add_column("search_run_id")
    table.add_column("created_at")
    table.add_column("completeness")
    table.add_column("candidates")
    for report in coverage_reports:
        table.add_row(
            report.search_run_id,
            report.created_at,
            report.completeness,
            str(report.candidate_count),
        )
    console.print(table)


def _print_federated_coverage(coverage: SearchCoverageReport, *, search_run_id: str) -> None:
    providers_completed = set(coverage.providers_completed)
    providers_failed = set(coverage.providers_failed)

    completeness_color = {
        "complete": "green",
        "partial": "yellow",
        "failed": "red",
    }.get(coverage.completeness, "white")

    console.print(f"[bold]Search run:[/bold] {search_run_id}")
    console.print(
        f"[bold]Coverage:[/bold] "
        f"[{completeness_color}]{coverage.completeness}[/{completeness_color}] "
        f"({coverage.candidate_count} deduplicated candidate(s))"
    )
    table = Table(title="Provider coverage")
    table.add_column("Provider")
    table.add_column("Status")
    for provider in coverage.providers_requested:
        if provider in providers_completed:
            status = "[green]completed[/green]"
        elif provider in providers_failed:
            status = "[red]failed/unavailable[/red]"
        else:
            status = "[yellow]not attempted[/yellow]"
        table.add_row(provider, status)
    console.print(table)


_DIRECTION_BY_NAME = {direction.value: direction for direction in CitationDirection}
_SNOWBALL_PROVIDERS = ("semantic_scholar", "openalex")


def _parse_snowball_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("-", "_")
    if normalized not in _SNOWBALL_PROVIDERS:
        allowed = ", ".join(_SNOWBALL_PROVIDERS)
        raise typer.BadParameter(f"Unknown provider '{provider}'. Choose from: {allowed}.")
    return normalized


def _build_snowball_provider(
    provider: str,
    *,
    semantic_scholar_api_key: str | None,
    openalex_api_key: str | None,
) -> CitationTraversalProvider:
    if provider == "semantic_scholar":
        return SemanticScholarProvider(
            transport=UrllibSemanticScholarTransport(), api_key=semantic_scholar_api_key
        )
    return OpenAlexCitationAdapter(
        citation_source=OpenAlexCitationProvider(
            transport=UrllibOpenAlexTransport(), api_key=openalex_api_key
        ),
        work_lookup=OpenAlexProvider(transport=UrllibOpenAlexTransport(), api_key=openalex_api_key),
    )


def _parse_snowball_seeds(seeds: str) -> tuple[str, ...]:
    parsed = tuple(seed.strip() for seed in seeds.split(",") if seed.strip())
    if not parsed:
        raise typer.BadParameter("--seeds must name at least one seed identifier.")
    return parsed


def _parse_snowball_directions(directions: str) -> tuple[CitationDirection, ...]:
    names = tuple(name.strip() for name in directions.split(",") if name.strip())
    if not names:
        raise typer.BadParameter("--directions must name at least one direction.")
    parsed: list[CitationDirection] = []
    for name in names:
        direction = _DIRECTION_BY_NAME.get(name)
        if direction is None:
            allowed = ", ".join(sorted(_DIRECTION_BY_NAME))
            raise typer.BadParameter(f"Unknown direction '{name}'. Choose from: {allowed}.")
        parsed.append(direction)
    return tuple(parsed)


@app.command("citation-snowball")
def citation_snowball(
    seeds: SnowballSeedsOption,
    ledger_root: SnowballLedgerRootOption,
    provider: SnowballProviderOption = "semantic_scholar",
    directions: SnowballDirectionsOption = "references,citations",
    max_depth: SnowballMaxDepthOption = 1,
    limit_per_traversal: SnowballLimitPerTraversalOption = 25,
    max_candidates: SnowballMaxCandidatesOption = 100,
    semantic_scholar_api_key: FederatedSemanticScholarApiKeyOption = None,
    openalex_api_key: FederatedOpenAlexApiKeyOption = None,
    output: SnowballOutputOption = None,
) -> None:
    """Run one bounded citation-snowball expansion and durably persist it (FRD-7).

    Breadth-first expands `--seeds` through `--provider`'s public
    references/citations graph, up to `--max-depth` hops, and persists a
    deterministic, replayable record of the plan, every traversal's provider
    outcome, discovered candidate IDs, and citation-edge provenance to
    `--ledger-root` *before* returning, matching `federated-discover`'s
    persist-before-return discipline. This is the first CLI surface for
    `citation_snowball.py`/`citation_snowball_ledger.py` (FRD-7); until this
    command existed that code was built and unit-tested but unreachable
    outside a test file -- the same "built but unreachable" gap this project
    has repeatedly found and fixed for other providers. See
    `docs/roadmap/federated_research_discovery_adoption.md`'s FRD-7 section.

    `--provider semantic_scholar` (the default) uses
    `SemanticScholarProvider.traverse`, already used for federated search --
    see `_federated_discovery_registry`. `--provider openalex` uses
    `OpenAlexCitationAdapter`, which wraps the same `OpenAlexCitationProvider`
    and `OpenAlexProvider` (work-hydration lookup) instances
    `federated-discover` already constructs, and requires
    `--openalex-api-key`/`KE_OPENALEX_API_KEY` -- without one it reports
    itself `disabled`, matching `OpenAlexProvider`'s existing federated-search
    behavior, never a silent empty result. A run traverses exactly one
    provider -- `CitationSnowballDiscovery` validates every traversal's
    reported provider identity stays constant for the run, the same
    discipline `federated-discover` fans out across providers instead of
    relying on.

    A seed or an intermediate discovered work that the provider cannot
    resolve is reported as an explicit, labeled traversal outcome, never
    silently dropped -- completeness must never be inferred from candidate
    count alone. `--output <path.json>` additionally saves the full result
    (plan, every traversal's outcome, discovered candidates with their
    provider observations, and edge provenance) for a programmatic caller;
    the ledger under `--ledger-root` is the durable, replayable record
    either way, re-fetchable later via `citation-snowball-report`.
    """

    try:
        parsed_seeds = _parse_snowball_seeds(seeds)
        parsed_directions = _parse_snowball_directions(directions)
        plan = CitationSnowballPlan(
            seed_identifiers=parsed_seeds,
            directions=parsed_directions,
            max_depth=max_depth,
            limit_per_traversal=limit_per_traversal,
            max_candidates=max_candidates,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    parsed_provider = _parse_snowball_provider(provider)
    traversal_provider = _build_snowball_provider(
        parsed_provider,
        semantic_scholar_api_key=semantic_scholar_api_key,
        openalex_api_key=openalex_api_key,
    )
    discovery = CitationSnowballDiscovery(traversal_provider)

    provider_label = "Semantic Scholar" if parsed_provider == "semantic_scholar" else "OpenAlex"
    console.print(
        f"[yellow]Network access:[/yellow] querying {provider_label}'s public citation "
        "graph over HTTPS."
    )
    result = discovery.run(plan)

    ledger = CitationSnowballLedger(ledger_root)
    record = ledger.record(result)

    if output is not None:
        payload: dict[str, Any] = {
            "snowball_run_id": record.snowball_run_id,
            "provider": result.provider,
            "plan": {
                "seed_identifiers": list(plan.normalized_seed_identifiers),
                "directions": [direction.value for direction in plan.directions],
                "max_depth": plan.max_depth,
                "limit_per_traversal": plan.limit_per_traversal,
                "max_candidates": plan.max_candidates,
            },
            "completeness": result.completeness.value,
            "truncated": result.truncated,
            "candidates": [asdict(candidate) for candidate in result.candidates],
            "edges": [{**asdict(edge), "direction": edge.direction.value} for edge in result.edges],
        }
        _write_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    _print_snowball_result(record.snowball_run_id, result=result)


@app.command("citation-snowball-report")
def citation_snowball_report(
    snowball_run_id: SnowballRunIdArgument,
    ledger_root: SnowballLedgerRootOption,
) -> None:
    """Print the persisted plan and outcome for one citation-snowball run (FRD-7).

    Lets a caller re-fetch a snowball run's deterministic replay record after
    the fact, the "expansion can be replayed and compared later" exit
    criterion `docs/roadmap/federated_research_discovery_adoption.md`'s FRD-7
    section names -- mirroring `federated-coverage-report`'s role for
    `federated-discover`.
    """

    ledger = CitationSnowballLedger(ledger_root)
    try:
        record = ledger.load(snowball_run_id)
    except FileNotFoundError:
        console.print(f"[red]No citation-snowball run found:[/red] {escape(snowball_run_id)}")
        raise typer.Exit(1) from None
    except ValueError as exc:
        console.print(f"[red]Malformed citation-snowball run record:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    completeness_color = {
        "complete": "green",
        "partial": "yellow",
        "failed": "red",
    }.get(record.completeness, "white")

    console.print(f"[bold]Snowball run:[/bold] {record.snowball_run_id}")
    console.print(f"[bold]Provider:[/bold] {escape(record.provider)}")
    console.print(
        f"[bold]Seeds:[/bold] {', '.join(escape(seed) for seed in record.seed_identifiers)}"
    )
    console.print(
        f"[bold]Completeness:[/bold] "
        f"[{completeness_color}]{record.completeness}[/{completeness_color}] "
        f"({len(record.candidate_ids)} candidate(s), truncated={record.truncated})"
    )

    table = Table(title="Traversals")
    table.add_column("Seed")
    table.add_column("Direction")
    table.add_column("Outcome")
    table.add_column("Results")
    for traversal in record.traversals:
        outcome_color = "green" if traversal.outcome in {"success", "empty"} else "red"
        table.add_row(
            escape(traversal.seed_identifier),
            traversal.direction,
            f"[{outcome_color}]{traversal.outcome}[/{outcome_color}]",
            str(traversal.result_count),
        )
    console.print(table)


def _print_snowball_result(snowball_run_id: str, *, result: CitationSnowballResult) -> None:
    completeness_color = {
        "complete": "green",
        "partial": "yellow",
        "failed": "red",
    }.get(result.completeness.value, "white")

    console.print(f"[bold]Snowball run:[/bold] {snowball_run_id}")
    console.print(
        f"[bold]Completeness:[/bold] "
        f"[{completeness_color}]{result.completeness.value}[/{completeness_color}] "
        f"({len(result.candidates)} candidate(s), truncated={result.truncated})"
    )

    if result.candidates:
        table = Table(title="Discovered candidates")
        table.add_column("Title")
        table.add_column("Year")
        table.add_column("DOI")
        for candidate in result.candidates:
            table.add_row(
                escape(candidate.title),
                str(candidate.publication_year) if candidate.publication_year else "",
                escape(candidate.doi or ""),
            )
        console.print(table)

    console.print(
        "[bold]Discovery only -- these are not Evidence Records and were not acquired. "
        "Run the same PMC-scoped candidate/acquisition commands for anything meant to "
        "enter the corpus.[/bold]"
    )
