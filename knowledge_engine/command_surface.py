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
    _validate_output,
    _write_output,
    app,
    console,
)
from knowledge_engine.general_question_acquisition import (
    GeneralQuestionAcquisitionRequest,
    build_acquisition_plan,
)
from knowledge_engine.general_question_core_acquisition import (
    GeneralQuestionCoreAcquisitionError,
    _rollback_acquired_files,
    execute_core_acquisition_plan,
    persist_core_acquisition_execution,
)


def _core_doi_resolver() -> CoreDoiResolver:
    """Build the exact-DOI CORE resolver for an explicit acquisition command."""

    return CoreDoiResolver(_core_discovery_service())


def _core_acquisition_service() -> CoreOaAcquisitionService:
    """Build the strict CORE-hosted PDF acquisition service."""

    return CoreOaAcquisitionService(UrllibCorePdfTransport())


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
        console.print(f"[red]No federated search run found:[/red] {escape(request.search_run_id)}")
        raise typer.Exit(1) from None
    except (ValueError, GeneralQuestionCoreAcquisitionError) as exc:
        console.print(f"[red]General-question CORE acquisition failed:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc

    try:
        with database.session() as session:
            persistence_receipt = persist_core_acquisition_execution(
                session,
                plan,
                execution,
                output_directory=papers_dir,
            )
            _write_output(receipt, persistence_receipt.to_json())
    except typer.BadParameter:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise typer.BadParameter(
            "Receipt output could not be written; acquired PDFs and Paper writes were rolled back."
        ) from None
    except GeneralQuestionCoreAcquisitionError as exc:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        console.print(
            f"[red]General-question CORE persistence failed:[/red] {escape(str(exc))}"
        )
        raise typer.Exit(1) from exc
    except Exception:
        _rollback_acquired_files(papers_dir, execution.acquisition_receipt)
        raise

    console.print(
        f"[green]Acquired and parsed {persistence_receipt.parsed_count} planned CORE "
        f"PDFs.[/green] Receipt: {receipt}"
    )
    console.print(
        f"[bold]Persisted {persistence_receipt.persisted_count} new Papers and reused "
        f"{persistence_receipt.reused_count} existing Papers with search-run and "
        "candidate provenance preserved in the receipt.[/bold]"
    )
