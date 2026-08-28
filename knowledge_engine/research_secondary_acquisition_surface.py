"""CORE and Unpaywall GQR executors for the slim ``ke-research`` runtime.

Kept separate from the PMC/Europe PMC surface because these routes have their
own receipt rollback and resolver contracts. Like the other slim command
modules, this file composes focused Core modules directly and never imports the
heavyweight production command registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from knowledge_engine.config import build_settings
from knowledge_engine.core_acquisition import (
    CoreDoiResolver,
    CoreOaAcquisitionService,
    UrllibCorePdfTransport,
)
from knowledge_engine.core_discovery import CoreDiscoveryService
from knowledge_engine.core_discovery import GetTransport as CoreGetTransport
from knowledge_engine.core_http import UrllibCoreTransport
from knowledge_engine.database import Database
from knowledge_engine.general_question_acquisition import (
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.general_question_core_acquisition import (
    GeneralQuestionCoreAcquisitionError,
    GeneralQuestionCoreExecution,
    _rollback_acquired_files,
    execute_core_acquisition_plan,
    persist_core_acquisition_execution,
)
from knowledge_engine.general_question_unpaywall_acquisition import (
    GeneralQuestionUnpaywallAcquisitionError,
    GeneralQuestionUnpaywallExecution,
    execute_unpaywall_acquisition_plan,
    persist_unpaywall_acquisition_execution,
)
from knowledge_engine.general_question_unpaywall_acquisition import (
    _rollback_acquired_files as _rollback_unpaywall_files,
)
from knowledge_engine.unpaywall_acquisition import (
    UnpaywallDoiResolver,
    UnpaywallOaAcquisitionService,
    UrllibUnpaywallPdfTransport,
)
from knowledge_engine.unpaywall_http import UrllibUnpaywallTransport
from knowledge_engine.unpaywall_lookup import GetTransport as UnpaywallGetTransport
from knowledge_engine.unpaywall_lookup import UnpaywallLookupService

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


def register_research_secondary_acquisition_commands(app: typer.Typer) -> None:
    """Register CORE and Unpaywall GQR acquisition routes on ``app``."""

    app.command("general-question-acquire-core")(general_question_acquire_core)
    app.command("general-question-acquire-unpaywall")(general_question_acquire_unpaywall)


def general_question_acquire_core(
    request_path: AcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible CORE routes from one bounded acquisition request."""

    _validate_output(receipt, force=force)
    request = _read_request(request_path)
    try:
        database = _local_database()
        database.initialize()
        with database.session() as session:
            plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
        execution = execute_core_acquisition_plan(
            plan,
            resolver=_core_doi_resolver(),
            acquisition_service=_core_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        typer.echo("No federated search run found.", err=True)
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionCoreAcquisitionError) as exc:
        typer.echo(f"General-question CORE acquisition failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    if _core_receipt_collides_with_pdf(receipt, papers_dir, execution):
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter("Receipt output path must not overwrite an acquired CORE PDF.")

    previous_receipt = _preserve_existing_receipt(
        receipt,
        papers_dir=papers_dir,
        core_execution=execution,
    )
    receipt_write_attempted = False
    try:
        with database.session() as session:
            persistence_receipt = persist_core_acquisition_execution(
                session,
                plan,
                execution,
                output_directory=papers_dir,
            )
            receipt_write_attempted = True
            _write_output(receipt, persistence_receipt.to_json())
    except typer.BadParameter:
        _cleanup_failed_core_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionCoreAcquisitionError as exc:
        _cleanup_failed_core_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        typer.echo(f"General-question CORE persistence failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception:
        _cleanup_failed_core_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        raise

    typer.echo(
        f"parsed={persistence_receipt.parsed_count} "
        f"persisted={persistence_receipt.persisted_count} "
        f"reused={persistence_receipt.reused_count} receipt={receipt}"
    )


def general_question_acquire_unpaywall(
    request_path: AcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible Unpaywall routes from one bounded acquisition request."""

    _validate_output(receipt, force=force)
    request = _read_request(request_path)
    try:
        database = _local_database()
        database.initialize()
        with database.session() as session:
            plan = build_acquisition_plan(request, ledger_root=ledger_root, session=session)
        execution = execute_unpaywall_acquisition_plan(
            plan,
            resolver=_unpaywall_doi_resolver(),
            acquisition_service=_unpaywall_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        typer.echo("No federated search run found.", err=True)
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionUnpaywallAcquisitionError) as exc:
        typer.echo(f"General-question Unpaywall acquisition failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    if _unpaywall_receipt_collides_with_pdf(receipt, papers_dir, execution):
        _rollback_unpaywall_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output path must not overwrite an acquired Unpaywall PDF."
        )

    previous_receipt = _preserve_existing_receipt(
        receipt,
        papers_dir=papers_dir,
        unpaywall_execution=execution,
    )
    receipt_write_attempted = False
    try:
        with database.session() as session:
            persistence_receipt = persist_unpaywall_acquisition_execution(
                session,
                plan,
                execution,
                output_directory=papers_dir,
            )
            receipt_write_attempted = True
            _write_output(receipt, persistence_receipt.to_json())
    except typer.BadParameter:
        _cleanup_failed_unpaywall_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionUnpaywallAcquisitionError as exc:
        _cleanup_failed_unpaywall_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        typer.echo(f"General-question Unpaywall persistence failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception:
        _cleanup_failed_unpaywall_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
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


def _core_discovery_service() -> CoreDiscoveryService:
    transport = cast(CoreGetTransport, UrllibCoreTransport())
    api_key = build_settings(Path.cwd()).core_api_key
    return CoreDiscoveryService(transport, api_key=api_key)


def _core_doi_resolver() -> CoreDoiResolver:
    return CoreDoiResolver(_core_discovery_service())


def _core_acquisition_service() -> CoreOaAcquisitionService:
    return CoreOaAcquisitionService(UrllibCorePdfTransport())


def _unpaywall_lookup_service() -> UnpaywallLookupService:
    email = build_settings(Path.cwd()).unpaywall_email
    if not email:
        raise ValueError("KE_UNPAYWALL_EMAIL is required for Unpaywall acquisition.")
    transport = cast(UnpaywallGetTransport, UrllibUnpaywallTransport())
    return UnpaywallLookupService(transport, email=email)


def _unpaywall_doi_resolver() -> UnpaywallDoiResolver:
    return UnpaywallDoiResolver(_unpaywall_lookup_service())


def _unpaywall_acquisition_service() -> UnpaywallOaAcquisitionService:
    return UnpaywallOaAcquisitionService(UrllibUnpaywallPdfTransport())


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


def _core_receipt_collides_with_pdf(
    receipt: Path, papers_dir: Path, execution: GeneralQuestionCoreExecution
) -> bool:
    receipt_path = receipt.resolve(strict=False)
    return any(
        receipt_path == (papers_dir / item.filename).resolve(strict=False)
        for item in execution.acquisition_receipt.items
    )


def _unpaywall_receipt_collides_with_pdf(
    receipt: Path, papers_dir: Path, execution: GeneralQuestionUnpaywallExecution
) -> bool:
    receipt_path = receipt.resolve(strict=False)
    return any(
        receipt_path == (papers_dir / item.filename).resolve(strict=False)
        for item in execution.acquisition_receipt.items
    )


def _preserve_existing_receipt(
    receipt: Path,
    *,
    papers_dir: Path,
    core_execution: GeneralQuestionCoreExecution | None = None,
    unpaywall_execution: GeneralQuestionUnpaywallExecution | None = None,
) -> bytes | None:
    try:
        return receipt.read_bytes() if receipt.exists() else None
    except OSError as exc:
        if core_execution is not None:
            _rollback_acquired_files(papers_dir, core_execution.acquisition_receipt)
        if unpaywall_execution is not None:
            _rollback_unpaywall_files(papers_dir, unpaywall_execution.acquisition_receipt)
        raise typer.BadParameter("Existing receipt could not be preserved.") from exc


def _restore_receipt(receipt: Path, previous: bytes | None) -> None:
    if previous is None:
        receipt.unlink(missing_ok=True)
    else:
        receipt.write_bytes(previous)


def _cleanup_failed_core_persistence(
    *,
    receipt: Path,
    previous_receipt: bytes | None,
    receipt_write_attempted: bool,
    papers_dir: Path,
    execution: GeneralQuestionCoreExecution,
) -> None:
    receipt_error: OSError | None = None
    if receipt_write_attempted:
        try:
            _restore_receipt(receipt, previous_receipt)
        except OSError as exc:
            receipt_error = exc

    rollback_error: GeneralQuestionCoreAcquisitionError | None = None
    try:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
    except GeneralQuestionCoreAcquisitionError as exc:
        rollback_error = exc

    if receipt_error is not None:
        raise GeneralQuestionCoreAcquisitionError(
            "CORE receipt rollback failed after persistence did not commit."
        ) from receipt_error
    if rollback_error is not None:
        raise rollback_error


def _cleanup_failed_unpaywall_persistence(
    *,
    receipt: Path,
    previous_receipt: bytes | None,
    receipt_write_attempted: bool,
    papers_dir: Path,
    execution: GeneralQuestionUnpaywallExecution,
) -> None:
    receipt_error: OSError | None = None
    if receipt_write_attempted:
        try:
            _restore_receipt(receipt, previous_receipt)
        except OSError as exc:
            receipt_error = exc

    rollback_error: GeneralQuestionUnpaywallAcquisitionError | None = None
    try:
        _rollback_unpaywall_files(papers_dir, execution.acquisition_receipt)
    except GeneralQuestionUnpaywallAcquisitionError as exc:
        rollback_error = exc

    if receipt_error is not None:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall receipt rollback failed after persistence did not commit."
        ) from receipt_error
    if rollback_error is not None:
        raise rollback_error
