"""Production ``ke`` command surface with additive GQR provider executors.

The historical command registry remains in :mod:`knowledge_engine.entrypoint`.
This module imports that same Typer application and registers provider commands
that are implemented in independently testable modules. The console-script
entrypoint points here so existing commands remain unchanged while new commands
can be added without rewriting the monolithic registry.
"""

from __future__ import annotations

import typer
from rich.markup import escape

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.cli import console
from knowledge_engine.core_acquisition import (
    CoreDoiResolver,
    CoreOaAcquisitionService,
    UrllibCorePdfTransport,
)
from knowledge_engine.entrypoint import (
    FederatedLedgerRootOption,
    ForceOutputOption,
    GeneralQuestionAcquisitionRequestArgument,
    PapersDirectoryOption,
    ReceiptOutputOption,
    _core_discovery_service,
    _local_database,
    _unpaywall_lookup_service,
    _validate_output,
    _write_output,
)
from knowledge_engine.general_question_acquisition import (
    AcquisitionRoute,
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.general_question_acquisition_failures import (
    clear_acquisition_failure_record,
    write_acquisition_failure_record,
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

app = entrypoint.app


def _core_doi_resolver() -> CoreDoiResolver:
    """Build the exact-DOI CORE resolver for an explicit acquisition command."""

    return CoreDoiResolver(_core_discovery_service())


def _core_acquisition_service() -> CoreOaAcquisitionService:
    """Build the strict CORE-hosted PDF acquisition service."""

    return CoreOaAcquisitionService(UrllibCorePdfTransport())


def _unpaywall_doi_resolver() -> UnpaywallDoiResolver:
    """Build the exact-DOI Unpaywall resolver for an explicit acquisition command."""

    return UnpaywallDoiResolver(_unpaywall_lookup_service())


def _unpaywall_acquisition_service() -> UnpaywallOaAcquisitionService:
    """Build the strict Unpaywall-resolved PDF acquisition service."""

    return UnpaywallOaAcquisitionService(UrllibUnpaywallPdfTransport())


def _receipt_collides_with_acquired_pdf(
    receipt: ReceiptOutputOption,
    papers_dir: PapersDirectoryOption,
    execution: GeneralQuestionCoreExecution,
) -> bool:
    """Return whether the requested CORE receipt path names an acquired PDF."""

    receipt_path = receipt.resolve(strict=False)
    return any(
        receipt_path == (papers_dir / item.filename).resolve(strict=False)
        for item in execution.acquisition_receipt.items
    )


def _unpaywall_receipt_collides_with_acquired_pdf(
    receipt: ReceiptOutputOption,
    papers_dir: PapersDirectoryOption,
    execution: GeneralQuestionUnpaywallExecution,
) -> bool:
    """Return whether the requested Unpaywall receipt path names an acquired PDF."""

    receipt_path = receipt.resolve(strict=False)
    return any(
        receipt_path == (papers_dir / item.filename).resolve(strict=False)
        for item in execution.acquisition_receipt.items
    )


def _restore_receipt_after_failure(receipt: ReceiptOutputOption, previous: bytes | None) -> None:
    """Remove a new CORE receipt or restore the file that ``--force`` replaced."""

    try:
        if previous is None:
            receipt.unlink(missing_ok=True)
        else:
            receipt.write_bytes(previous)
    except OSError as exc:
        raise GeneralQuestionCoreAcquisitionError(
            "CORE receipt rollback failed after persistence did not commit."
        ) from exc


def _restore_unpaywall_receipt_after_failure(
    receipt: ReceiptOutputOption, previous: bytes | None
) -> None:
    """Remove a new Unpaywall receipt or restore the forced previous file."""

    try:
        if previous is None:
            receipt.unlink(missing_ok=True)
        else:
            receipt.write_bytes(previous)
    except OSError as exc:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall receipt rollback failed after persistence did not commit."
        ) from exc


def _cleanup_failed_persistence(
    *,
    receipt: ReceiptOutputOption,
    previous_receipt: bytes | None,
    receipt_write_attempted: bool,
    papers_dir: PapersDirectoryOption,
    execution: GeneralQuestionCoreExecution,
) -> None:
    """Best-effort cleanup for the filesystem sides of a failed CORE transaction."""

    receipt_error: GeneralQuestionCoreAcquisitionError | None = None
    if receipt_write_attempted:
        try:
            _restore_receipt_after_failure(receipt, previous_receipt)
        except GeneralQuestionCoreAcquisitionError as exc:
            receipt_error = exc

    rollback_error: GeneralQuestionCoreAcquisitionError | None = None
    try:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
    except GeneralQuestionCoreAcquisitionError as exc:
        rollback_error = exc

    if receipt_error is not None:
        raise receipt_error
    if rollback_error is not None:
        raise rollback_error


def _cleanup_failed_unpaywall_persistence(
    *,
    receipt: ReceiptOutputOption,
    previous_receipt: bytes | None,
    receipt_write_attempted: bool,
    papers_dir: PapersDirectoryOption,
    execution: GeneralQuestionUnpaywallExecution,
) -> None:
    """Best-effort filesystem cleanup for a failed Unpaywall DB transaction."""

    receipt_error: GeneralQuestionUnpaywallAcquisitionError | None = None
    if receipt_write_attempted:
        try:
            _restore_unpaywall_receipt_after_failure(receipt, previous_receipt)
        except GeneralQuestionUnpaywallAcquisitionError as exc:
            receipt_error = exc

    rollback_error: GeneralQuestionUnpaywallAcquisitionError | None = None
    try:
        _rollback_unpaywall_files(papers_dir, execution.acquisition_receipt)
    except GeneralQuestionUnpaywallAcquisitionError as exc:
        rollback_error = exc

    if receipt_error is not None:
        raise receipt_error
    if rollback_error is not None:
        raise rollback_error


@app.command("general-question-acquire-core")
def general_question_acquire_core(
    request_path: GeneralQuestionAcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible CORE routes from one acquisition request (CORE-GQR-4)."""

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
            "[yellow]Network access:[/yellow] resolving planned DOIs and acquiring "
            "explicitly licensed PDFs from official CORE resources."
        )
        execution = execute_core_acquisition_plan(
            plan,
            resolver=_core_doi_resolver(),
            acquisition_service=_core_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            stage="build_plan",
            reason="No federated search run found.",
            candidate_ids=request.candidate_ids,
        )
        console.print(f"[red]No federated search run found:[/red] {escape(request.search_run_id)}")
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionCoreAcquisitionError) as exc:
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            stage="build_plan" if isinstance(exc, ValueError) else "acquire",
            reason=str(exc),
            candidate_ids=request.candidate_ids,
        )
        console.print(f"[red]General-question CORE acquisition failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    if _receipt_collides_with_acquired_pdf(receipt, papers_dir, execution):
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter("Receipt output path must not overwrite an acquired CORE PDF.")

    try:
        previous_receipt = receipt.read_bytes() if receipt.exists() else None
    except OSError as exc:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Existing receipt could not be preserved before CORE persistence."
        ) from exc

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
        _cleanup_failed_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            stage="persist",
            reason="Receipt output could not be written.",
            candidate_ids=request.candidate_ids,
        )
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionCoreAcquisitionError as exc:
        _cleanup_failed_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            stage="persist",
            reason=str(exc),
            candidate_ids=request.candidate_ids,
        )
        console.print(f"[red]General-question CORE persistence failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _cleanup_failed_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            stage="persist",
            reason=f"Unexpected error: {type(exc).__name__}.",
            candidate_ids=request.candidate_ids,
        )
        raise

    clear_acquisition_failure_record(receipt)
    console.print(
        f"[green]Acquired and parsed {persistence_receipt.parsed_count} planned CORE "
        f"PDFs.[/green] Receipt: {receipt}"
    )
    console.print(
        f"[bold]Persisted {persistence_receipt.persisted_count} new Papers and reused "
        f"{persistence_receipt.reused_count} existing Papers with search-run and "
        "candidate provenance preserved in the receipt.[/bold]"
    )


@app.command("general-question-acquire-unpaywall")
def general_question_acquire_unpaywall(
    request_path: GeneralQuestionAcquisitionRequestArgument,
    ledger_root: FederatedLedgerRootOption,
    papers_dir: PapersDirectoryOption,
    receipt: ReceiptOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Execute eligible Unpaywall routes from one acquisition request (CORE-GQR-4)."""

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
            "[yellow]Network access:[/yellow] re-resolving planned DOIs through "
            "Unpaywall and acquiring only reusable-license direct PDFs on reviewed hosts."
        )
        execution = execute_unpaywall_acquisition_plan(
            plan,
            resolver=_unpaywall_doi_resolver(),
            acquisition_service=_unpaywall_acquisition_service(),
            output_directory=papers_dir,
        )
    except FileNotFoundError:
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            stage="build_plan",
            reason="No federated search run found.",
            candidate_ids=request.candidate_ids,
        )
        console.print(f"[red]No federated search run found:[/red] {escape(request.search_run_id)}")
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionUnpaywallAcquisitionError) as exc:
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            stage="build_plan" if isinstance(exc, ValueError) else "acquire",
            reason=str(exc),
            candidate_ids=request.candidate_ids,
        )
        console.print(
            f"[red]General-question Unpaywall acquisition failed:[/red] {escape(str(exc))}"
        )
        raise typer.Exit(1) from exc

    if _unpaywall_receipt_collides_with_acquired_pdf(receipt, papers_dir, execution):
        _rollback_unpaywall_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output path must not overwrite an acquired Unpaywall PDF."
        )

    try:
        previous_receipt = receipt.read_bytes() if receipt.exists() else None
    except OSError as exc:
        _rollback_unpaywall_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Existing receipt could not be preserved before Unpaywall persistence."
        ) from exc

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
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            stage="persist",
            reason="Receipt output could not be written.",
            candidate_ids=request.candidate_ids,
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
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            stage="persist",
            reason=str(exc),
            candidate_ids=request.candidate_ids,
        )
        console.print(
            f"[red]General-question Unpaywall persistence failed:[/red] {escape(str(exc))}"
        )
        raise typer.Exit(1) from exc
    except Exception as exc:
        _cleanup_failed_unpaywall_persistence(
            receipt=receipt,
            previous_receipt=previous_receipt,
            receipt_write_attempted=receipt_write_attempted,
            papers_dir=papers_dir,
            execution=execution,
        )
        write_acquisition_failure_record(
            receipt,
            search_run_id=request.search_run_id,
            research_question_id=request.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            stage="persist",
            reason=f"Unexpected error: {type(exc).__name__}.",
            candidate_ids=request.candidate_ids,
        )
        raise

    clear_acquisition_failure_record(receipt)
    console.print(
        f"[green]Acquired and parsed {persistence_receipt.parsed_count} planned Unpaywall "
        f"PDFs.[/green] Receipt: {receipt}"
    )
    console.print(
        f"[bold]Persisted {persistence_receipt.persisted_count} new Papers and reused "
        f"{persistence_receipt.reused_count} existing Papers with search-run and "
        "candidate provenance preserved in the receipt.[/bold]"
    )
