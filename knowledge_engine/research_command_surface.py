"""Slim Core command surface for the hosted Research Copilot path.

This is deliberately built on :mod:`knowledge_engine.cli`, not the production
``knowledge_engine.command_surface`` / ``knowledge_engine.entrypoint`` registry.
The latter imports Phase 3 vector backends at module import time and therefore
pulls FAISS, sentence-transformers, PyTorch, and Qdrant into any process that
only wants the deterministic research commands.

The slim surface grows in bounded groups and never claims completeness early.
``research-runtime-capabilities`` compares the commands registered here against
the exact command manifest the current AI orchestration can invoke. Until that
payload reports ``complete: true``, a hosted Web deployment must continue to
fail closed.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, cast

import typer

import knowledge_engine.cli as cli
from knowledge_engine.acquisition_plan_ledger import AcquisitionPlanLedger
from knowledge_engine.arxiv_http import UrllibArxivTransport
from knowledge_engine.arxiv_provider import ArxivProvider
from knowledge_engine.citation_snowball import (
    CitationSnowballDiscovery,
    CitationSnowballPlan,
    CitationTraversalProvider,
)
from knowledge_engine.citation_snowball_ledger import CitationSnowballLedger
from knowledge_engine.citation_traversal import CitationDirection
from knowledge_engine.config import build_settings
from knowledge_engine.crossref_federated_adapter import CrossrefFederatedAdapter
from knowledge_engine.crossref_http import UrllibCrossrefTransport
from knowledge_engine.crossref_provider import CrossrefProvider
from knowledge_engine.database import Database
from knowledge_engine.discovery_broker import DiscoveryProvider
from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry
from knowledge_engine.federated_discovery import DiscoveryQuery
from knowledge_engine.federated_result_snapshot import build_public_federated_result_payload
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.general_question_acquisition import (
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.ncbi_http import UrllibNcbiTransport
from knowledge_engine.openalex_citation_adapter import OpenAlexCitationAdapter
from knowledge_engine.openalex_citations import OpenAlexCitationProvider
from knowledge_engine.openalex_http import UrllibOpenAlexTransport
from knowledge_engine.openalex_provider import OpenAlexProvider
from knowledge_engine.pubmed_discovery import GetTransport, PubmedPmcDiscoveryService
from knowledge_engine.pubmed_federated_adapter import PubmedFederatedAdapter
from knowledge_engine.semantic_scholar_http import UrllibSemanticScholarTransport
from knowledge_engine.semantic_scholar_provider import SemanticScholarProvider

RESEARCH_RUNTIME_CONTRACT_VERSION = 1
RESEARCH_RUNTIME_REQUIRED_COMMANDS: tuple[str, ...] = (
    "evidence-report",
    "evidence-intelligence",
    "federated-discover",
    "citation-snowball",
    "general-question-acquisition-plan",
    "general-question-acquire-pmc",
    "general-question-acquire-europe-pmc",
    "general-question-acquire-core",
    "general-question-acquire-unpaywall",
    "extraction-review-batch-generate",
    "extraction-review-autoclassify",
    "extraction-review-promote",
    "evidence-review-automate",
    "evidence-record-review-promote",
)

FederatedQueryOption = Annotated[str, typer.Option("--query", help="Free-text discovery query.")]
FederatedLedgerRootOption = Annotated[
    Path,
    typer.Option("--ledger-root", help="Directory for persisted federated search-run records."),
]
FederatedLimitOption = Annotated[
    int,
    typer.Option("--limit", min=1, max=100, help="Maximum candidates per provider."),
]
FederatedYearFromOption = Annotated[int | None, typer.Option("--year-from")]
FederatedYearToOption = Annotated[int | None, typer.Option("--year-to")]
FederatedProvidersOption = Annotated[
    str | None,
    typer.Option("--providers", help="Optional comma-separated provider subset."),
]
FederatedOpenAlexApiKeyOption = Annotated[
    str | None,
    typer.Option("--openalex-api-key", envvar="KE_OPENALEX_API_KEY"),
]
FederatedSemanticScholarApiKeyOption = Annotated[
    str | None,
    typer.Option("--semantic-scholar-api-key", envvar="KE_SEMANTIC_SCHOLAR_API_KEY"),
]
FederatedProjectIdOption = Annotated[str | None, typer.Option("--project-id")]
FederatedResearchQuestionIdOption = Annotated[
    str | None,
    typer.Option("--research-question-id"),
]
FederatedOutputOption = Annotated[Path | None, typer.Option("--output")]
AcquisitionRequestArgument = Annotated[
    Path,
    typer.Argument(exists=True, dir_okay=False, readable=True),
]
AcquisitionOutputOption = Annotated[Path | None, typer.Option("--output")]
AcquisitionNoDatabaseOption = Annotated[
    bool,
    typer.Option("--no-database", help="Skip already-indexed lookup against the local database."),
]
SnowballSeedsOption = Annotated[
    str,
    typer.Option("--seeds", help="Comma-separated seed identifiers."),
]
SnowballLedgerRootOption = Annotated[
    Path,
    typer.Option("--ledger-root", help="Directory for persisted citation-snowball runs."),
]
SnowballProviderOption = Annotated[
    str,
    typer.Option("--provider", help="Citation provider: semantic_scholar or openalex."),
]
SnowballDirectionsOption = Annotated[
    str,
    typer.Option("--directions", help="Comma-separated references,citations directions."),
]
SnowballMaxDepthOption = Annotated[
    int,
    typer.Option("--max-depth", min=1, max=3),
]
SnowballLimitPerTraversalOption = Annotated[
    int,
    typer.Option("--limit-per-traversal", min=1, max=100),
]
SnowballMaxCandidatesOption = Annotated[
    int,
    typer.Option("--max-candidates", min=1, max=1000),
]
SnowballOutputOption = Annotated[Path | None, typer.Option("--output")]

app = typer.Typer()

# These two commands are genuinely inherited unmodified from the production
# `ke` CLI (see PR description). Every other command below is a slim
# reimplementation and must NOT be registered onto `cli.app`: several of
# these command names (federated-discover, citation-snowball,
# general-question-acquisition-plan, evidence-intelligence, ...) already
# exist there, and sharing the Typer instance would silently overwrite the
# production implementations the moment this module is imported.
app.command("evidence-report")(cli.evidence_report)
app.command("extraction-review-promote")(cli.extraction_review_promote)

_DIRECTION_BY_NAME = {direction.value: direction for direction in CitationDirection}
_SNOWBALL_PROVIDERS = ("semantic_scholar", "openalex")


def research_runtime_capability_payload() -> dict[str, object]:
    """Return the exact Research Copilot command coverage of this slim surface."""

    registered = _registered_command_names()
    available = tuple(
        command for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS if command in registered
    )
    missing = tuple(
        command for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS if command not in registered
    )
    return {
        "schema_version": RESEARCH_RUNTIME_CONTRACT_VERSION,
        "surface": "ke-research",
        "complete": not missing,
        "required_commands": list(RESEARCH_RUNTIME_REQUIRED_COMMANDS),
        "available_commands": list(available),
        "missing_commands": list(missing),
    }


def _registered_command_names() -> frozenset[str]:
    command = typer.main.get_command(app)
    commands = getattr(command, "commands", None)
    if not isinstance(commands, dict):
        return frozenset()
    return frozenset(commands)


def _crossref_provider() -> CrossrefProvider:
    return CrossrefProvider(transport=UrllibCrossrefTransport())


def _pubmed_discovery_service() -> PubmedPmcDiscoveryService:
    transport = cast(GetTransport, UrllibNcbiTransport())
    return PubmedPmcDiscoveryService(transport)


def _federated_discovery_registry(
    *, openalex_api_key: str | None, semantic_scholar_api_key: str | None
) -> DiscoveryProviderRegistry:
    """Compose the production provider set without importing the heavyweight entrypoint."""

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


def _parse_provider_subset(providers: str | None) -> tuple[str, ...] | None:
    if providers is None:
        return None
    names = tuple(name.strip() for name in providers.split(",") if name.strip())
    if not names:
        raise typer.BadParameter("--providers must name at least one provider when given.")
    return names


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


def _local_database() -> Database:
    return Database(build_settings(Path.cwd()))


def _write_text_output(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError:
        raise typer.BadParameter("Output file could not be written.") from None


@app.command("research-runtime-capabilities")
def research_runtime_capabilities() -> None:
    """Print machine-readable hosted Research Copilot command coverage."""

    typer.echo(json.dumps(research_runtime_capability_payload(), sort_keys=True))


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
    project_id: FederatedProjectIdOption = None,
    research_question_id: FederatedResearchQuestionIdOption = None,
    output: FederatedOutputOption = None,
) -> None:
    """Run recorded federated discovery without importing the heavyweight entrypoint."""

    try:
        discovery_query = DiscoveryQuery(
            text=query,
            year_from=year_from,
            year_to=year_to,
            limit_per_provider=limit,
        )
        registry = _federated_discovery_registry(
            openalex_api_key=openalex_api_key,
            semantic_scholar_api_key=semantic_scholar_api_key,
        )
        recorder = FederatedSearchLedger(ledger_root)
        service = registry.build_recorded_service(recorder, _parse_provider_subset(providers))
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    execution = service.search(
        discovery_query,
        project_id=project_id,
        research_question_id=research_question_id,
    )
    if output is not None:
        payload = build_public_federated_result_payload(execution.result, execution.coverage)
        _write_text_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    typer.echo(
        f"search_run_id={execution.record.search_run_id} "
        f"completeness={execution.coverage.completeness} "
        f"candidates={len(execution.result.candidates)}"
    )


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
    """Run one bounded citation expansion and persist its replay record."""

    try:
        plan = CitationSnowballPlan(
            seed_identifiers=_parse_snowball_seeds(seeds),
            directions=_parse_snowball_directions(directions),
            max_depth=max_depth,
            limit_per_traversal=limit_per_traversal,
            max_candidates=max_candidates,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    parsed_provider = _parse_snowball_provider(provider)
    discovery = CitationSnowballDiscovery(
        _build_snowball_provider(
            parsed_provider,
            semantic_scholar_api_key=semantic_scholar_api_key,
            openalex_api_key=openalex_api_key,
        )
    )
    result = discovery.run(plan)
    record = CitationSnowballLedger(ledger_root).record(result)

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
        _write_text_output(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    typer.echo(
        f"snowball_run_id={record.snowball_run_id} provider={result.provider} "
        f"completeness={result.completeness.value} candidates={len(result.candidates)}"
    )


@app.command("general-question-acquisition-plan")
def general_question_acquisition_plan(
    request_path: AcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    output: AcquisitionOutputOption = None,
    no_database: AcquisitionNoDatabaseOption = False,
) -> None:
    """Resolve one bounded GQR acquisition request without downloading full text."""

    try:
        request = GeneralQuestionAcquisitionRequest.from_json(
            request_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
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
        typer.echo("No federated search run found.", err=True)
        raise typer.Exit(1) from None
    except ValueError as exc:
        typer.echo(f"Acquisition request could not be resolved: {exc}", err=True)
        raise typer.Exit(1) from exc

    AcquisitionPlanLedger(ledger_root / "acquisition_plans").record(plan)

    if output is not None:
        _write_text_output(output, plan.to_json())

    typer.echo(
        f"search_run_id={plan.search_run_id} requested={plan.requested_candidate_count} "
        f"resolved={plan.resolved_candidate_count} full_text={plan.full_text_selected_count}"
    )
