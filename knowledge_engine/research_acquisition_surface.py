"""Import-safe GQR acquisition commands for the slim ``ke-research`` surface.

These functions reproduce the production command behavior by composing the
focused acquisition modules directly. They intentionally do not import
``knowledge_engine.entrypoint`` or ``knowledge_engine.command_surface`` so the
hosted research CLI can grow without inheriting the Phase 3 vector stack merely
from command registration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database
from knowledge_engine.europepmc_acquisition import (
    AcquisitionTransport as EuropePmcAcquisitionTransport,
)
from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionReceipt,
    EuropePmcOaAcquisitionService,
)
from knowledge_engine.europepmc_discovery import (
    EuropePmcDiscoveryService,
    GetTransport as EuropePmcGetTransport,
)
from knowledge_engine.europepmc_http import UrllibEuropePmcTransport
from knowledge_engine.general_question_acquisition import (
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.general_question_europepmc_acquisition import (
    GeneralQuestionEuropePmcAcquisitionError,
    execute_europepmc_acquisition_plan,
    persist_europepmc_acquisition_execution,
)
from knowledge_engine.general_question_pmc_acquisition import (
    GeneralQuestionPmcAcquisitionError,
    execute_pmc_acquisition_plan,
    persist_pmc_acquisition_execution,
)
from knowledge_engine.ncbi_http import UrllibNcbiTransport
from knowledge_engine.pmc_acquisition import (
    AcquisitionReceipt,
    AcquisitionTransport,
    PmcOaAcquisitionService,
)
from knowledge_engine.pubmed_discovery import GetTransport, PubmedPmcDiscoveryService

AcquisitionRequestArgument = Annotated[
    Path,
    typer.Argument(exists=True, dir_okay=False, readable=True),
]
FederatedLedgerRootOption = Annotated[
    Path,
    typer.Option("--ledger-root", help="Directory containing the persisted search run."),
]
PapersDirectoryOption = Annotated[
    Path,
    typer.Option("--papers-dir", help="Directory for acquired reusable full text."),
]
ReceiptOutputOption = Annotated[
    Path,
    typer.Option("--receipt", help="Path for the machine-readable persistence receipt."),
]
ForceOutputOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite an existing receipt."),
]


def register_research_oa_acquisition_commands(app: typer.Typer) -> None:
    """Register the PMC and Europe PMC GQR executors on ``app`` exactly once."""

    app.command("general-question-acquire-pmc")(general_question_acquire_pmc)
    app.command("general-question-acquire-europe-pmc")(general_question_acquire_europe_pmc)


def general_question_acquire_pmc(
    request_path: AcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible PMC routes from one bounded acquisition request."""

    _validate_output(receipt, force=force)
    request = _read_request(request_path)
    try:
        database = _local_database()
        database.initialize()
        with database.session() as session:
            plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
        execution = execute_pmc_acquisition_plan(
            plan,
            resolver=_pubmed_discovery_service(),
            acquisition_service=_pmc_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        typer.echo("No federated search run found.", err=True)
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionPmcAcquisitionError) as exc:
        typer.echo(f"General-question PMC acquisition failed: {exc}", err=True)
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
        _rollback_pmc_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionPmcAcquisitionError as exc:
        _rollback_pmc_files(papers_dir, execution.acquisition_receipt)
        typer.echo(f"General-question PMC persistence failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception:
        _rollback_pmc_files(papers_dir, execution.acquisition_receipt)
        raise

    typer.echo(
        f"parsed={persistence_receipt.parsed_count} "
        f"persisted={persistence_receipt.persisted_count} "
        f"reused={persistence_receipt.reused_count} receipt={receipt}"
    )


def general_question_acquire_europe_pmc(
    request_path: AcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible Europe PMC routes from one bounded acquisition request."""

    _validate_output(receipt, force=force)
    request = _read_request(request_path)
    try:
        database = _local_database()
        database.initialize()
        with database.session() as session:
            plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
        execution = execute_europepmc_acquisition_plan(
            plan,
            resolver=_europepmc_discovery_service(),
            acquisition_service=_europepmc_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        typer.echo("No federated search run found.", err=True)
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionEuropePmcAcquisitionError) as exc:
        typer.echo(f"General-question Europe PMC acquisition failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        with database.session() as session:
            persistence_receipt = persist_europepmc_acquisition_execution(
                session,
                plan,
                execution,
                output_directory=papers_dir,
            )
            _write_output(receipt, persistence_receipt.to_json())
    except typer.BadParameter:
        _rollback_europepmc_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionEuropePmcAcquisitionError as exc:
        _rollback_europepmc_files(papers_dir, execution.acquisition_receipt)
        typer.echo(f"General-question Europe PMC persistence failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception:
        _rollback_europepmc_files(papers_dir, execution.acquisition_receipt)
        raise

    typer.echo(
        f"parsed={persistence_receipt.parsed_count} "
        f"persisted={persistence_receipt.persisted_count} "
        f"reused={persistence_receipt.reused_count} receipt={receipt}"
    )


def _read_request(path: Path) -> GeneralQuestionAcquisitionRequest:
    try:
        return GeneralQuestionAcquisitionRequest.from_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _local_database() -> Database:
    return Database(build_settings(Path.cwd()))


def _pubmed_discovery_service() -> PubmedPmcDiscoveryService:
    transport = cast(GetTransport, UrllibNcbiTransport())
    return PubmedPmcDiscoveryService(transport)


def _pmc_acquisition_service() -> PmcOaAcquisitionService:
    transport = cast(AcquisitionTransport, UrllibNcbiTransport())
    return PmcOaAcquisitionService(transport)


def _europepmc_discovery_service() -> EuropePmcDiscoveryService:
    transport = cast(EuropePmcGetTransport, UrllibEuropePmcTransport())
    return EuropePmcDiscoveryService(transport)


def _europepmc_acquisition_service() -> EuropePmcOaAcquisitionService:
    transport = cast(EuropePmcAcquisitionTransport, UrllibEuropePmcTransport())
    return EuropePmcOaAcquisitionService(transport)


def _validate_output(output: Path, *, force: bool) -> None:
    if output.is_symlink():
        raise typer.BadParameter("Receipt output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Receipt output already exists. Use --force to overwrite.")


def _write_output(output: Path, content: str) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    except OSError:
        raise typer.BadParameter("Receipt output could not be written.") from None


def _rollback_pmc_files(output_directory: Path, receipt: AcquisitionReceipt) -> None:
    rollback_failed = False
    for item in receipt.items:
        try:
            (output_directory / item.filename).unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise typer.BadParameter("Acquired PMC files could not be fully rolled back.")


def _rollback_europepmc_files(output_directory: Path, receipt: EuropePmcAcquisitionReceipt) -> None:
    rollback_failed = False
    for item in receipt.items:
        try:
            (output_directory / item.filename).unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise typer.BadParameter("Acquired Europe PMC files could not be fully rolled back.")
