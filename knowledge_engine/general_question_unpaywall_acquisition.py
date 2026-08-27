"""Execute and persist validation-gated Unpaywall routes from a General Question plan."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
    AcquisitionPlanItem,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.import_runs._helpers import new_uuid, utc_now
from knowledge_engine.import_runs.repository import ImportRunRepository
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.models import ImportItem, ImportRun, ManifestSnapshot
from knowledge_engine.paper_persistence import ClassifiedPaperRepository
from knowledge_engine.parser import DocumentParseError, DocumentParser, PyMuPDFParser
from knowledge_engine.persistence_errors import PaperPersistenceError
from knowledge_engine.unpaywall_acquisition import (
    UnpaywallAcquisitionApproval,
    UnpaywallAcquisitionReceipt,
    UnpaywallResolvedPdf,
    deterministic_pdf_filename,
)
from knowledge_engine.utils import file_sha256, normalize_arxiv_id, normalize_doi, normalize_pmid


class GeneralQuestionUnpaywallAcquisitionError(RuntimeError):
    """Sanitized failure while resolving, acquiring, or persisting Unpaywall routes."""


class UnpaywallCandidateResolver(Protocol):
    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[UnpaywallResolvedPdf, ...]: ...


class UnpaywallAcquisitionExecutor(Protocol):
    def acquire(
        self,
        *,
        resolved: tuple[UnpaywallResolvedPdf, ...],
        approvals: tuple[UnpaywallAcquisitionApproval, ...],
        output_directory: Path,
    ) -> UnpaywallAcquisitionReceipt: ...


@dataclass(frozen=True)
class GeneralQuestionUnpaywallReceiptItem:
    candidate_id: str
    doi: str
    pdf_url: str
    source_host: str
    plan_license: str
    resolved_license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class GeneralQuestionUnpaywallReceipt:
    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    acquired_count: int
    items: tuple[GeneralQuestionUnpaywallReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GeneralQuestionUnpaywallExecution:
    receipt: GeneralQuestionUnpaywallReceipt
    acquisition_receipt: UnpaywallAcquisitionReceipt


@dataclass(frozen=True)
class GeneralQuestionUnpaywallPersistenceReceiptItem:
    candidate_id: str
    doi: str
    pdf_url: str
    source_host: str
    filename: str
    sha256: str
    paper_id: int
    persistence_status: str
    import_item_id: str | None = None


@dataclass(frozen=True)
class GeneralQuestionUnpaywallPersistenceReceipt:
    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    import_run_id: str
    parsed_count: int
    persisted_count: int
    reused_count: int
    items: tuple[GeneralQuestionUnpaywallPersistenceReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def execute_unpaywall_acquisition_plan(
    plan: GeneralQuestionAcquisitionPlan,
    *,
    resolver: UnpaywallCandidateResolver,
    acquisition_service: UnpaywallAcquisitionExecutor,
    output_directory: Path,
) -> GeneralQuestionUnpaywallExecution:
    """Refresh exact DOI/OA evidence and atomically acquire Unpaywall-routed items."""

    selected = tuple(
        plan_item
        for plan_item in plan.items
        if plan_item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and plan_item.acquisition_route == AcquisitionRoute.UNPAYWALL.value
    )
    if not selected:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Acquisition plan contains no eligible Unpaywall routes."
        )

    candidate_ids_by_doi: dict[str, str] = {}
    planned_by_doi: dict[str, AcquisitionPlanItem] = {}
    dois: list[str] = []
    for plan_item in selected:
        identity = plan_item.identity
        doi = normalize_doi(identity.doi) if identity is not None and identity.doi else ""
        if not doi:
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Every planned Unpaywall route must carry a valid DOI."
            )
        if doi in candidate_ids_by_doi:
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Planned Unpaywall routes contain a duplicate DOI."
            )
        if plan_item.selected_observation_provider != "unpaywall":
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Planned Unpaywall route lacks Unpaywall source provenance."
            )
        if not plan_item.full_text_url:
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Planned Unpaywall route lacks a direct full-text URL."
            )
        if plan_item.license is None or evaluate_license(plan_item.license) != "passed":
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Planned Unpaywall route lacks explicit reusable license evidence."
            )
        candidate_ids_by_doi[doi] = plan_item.candidate_id
        planned_by_doi[doi] = plan_item
        dois.append(doi)

    try:
        resolved = resolver.resolve_dois(tuple(dois))
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Planned Unpaywall identifiers could not be resolved."
        ) from exc

    resolved_by_doi = {normalize_doi(item.doi): item for item in resolved}
    if len(resolved_by_doi) != len(resolved) or set(resolved_by_doi) != set(dois):
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Resolved Unpaywall PDFs did not reconcile with the acquisition plan."
        )

    approvals: list[UnpaywallAcquisitionApproval] = []
    for doi in dois:
        current = resolved_by_doi[doi]
        plan_item = planned_by_doi[doi]
        if current.pdf_url != plan_item.full_text_url:
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Refreshed Unpaywall direct-PDF evidence did not reconcile with the plan."
            )
        if evaluate_license(current.license) != "passed":
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Refreshed Unpaywall license evidence is not reusable."
            )
        approvals.append(
            UnpaywallAcquisitionApproval(
                doi=doi,
                pdf_url=current.pdf_url,
                license=current.license,
                filename=deterministic_pdf_filename(doi),
            )
        )

    try:
        acquired = acquisition_service.acquire(
            resolved=tuple(resolved_by_doi[doi] for doi in dois),
            approvals=tuple(approvals),
            output_directory=output_directory,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Planned Unpaywall acquisition failed."
        ) from exc

    if acquired.acquired_count != len(dois) or acquired.acquired_count != len(acquired.items):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall acquisition receipt count did not reconcile with the plan."
        )
    acquired_by_doi = {
        normalize_doi(receipt_item.doi): receipt_item for receipt_item in acquired.items
    }
    if len(acquired_by_doi) != len(acquired.items) or set(acquired_by_doi) != set(dois):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall acquisition receipt identities did not reconcile with the plan."
        )

    receipt_items: list[GeneralQuestionUnpaywallReceiptItem] = []
    for doi in dois:
        acquired_item = acquired_by_doi[doi]
        current = resolved_by_doi[doi]
        plan_item = planned_by_doi[doi]
        if (
            acquired_item.pdf_url != current.pdf_url
            or acquired_item.source_host != current.source_host
            or acquired_item.license != current.license
        ):
            _rollback_acquired_files(output_directory, acquired)
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Unpaywall acquisition receipt evidence did not reconcile with resolution."
            )
        receipt_items.append(
            GeneralQuestionUnpaywallReceiptItem(
                candidate_id=candidate_ids_by_doi[doi],
                doi=doi,
                pdf_url=acquired_item.pdf_url,
                source_host=acquired_item.source_host,
                plan_license=str(plan_item.license),
                resolved_license=acquired_item.license,
                filename=acquired_item.filename,
                byte_count=acquired_item.byte_count,
                sha256=acquired_item.sha256,
            )
        )

    return GeneralQuestionUnpaywallExecution(
        receipt=GeneralQuestionUnpaywallReceipt(
            schema_version=1,
            search_run_id=plan.search_run_id,
            research_question_id=plan.research_question_id,
            acquisition_route=AcquisitionRoute.UNPAYWALL.value,
            acquired_count=len(receipt_items),
            items=tuple(receipt_items),
        ),
        acquisition_receipt=acquired,
    )


def persist_unpaywall_acquisition_execution(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    execution: GeneralQuestionUnpaywallExecution,
    *,
    output_directory: Path,
    parser: DocumentParser | None = None,
) -> GeneralQuestionUnpaywallPersistenceReceipt:
    """Verify bytes, parse, persist/reuse Papers, and record immutable import lineage."""

    receipt = execution.receipt
    if (
        receipt.search_run_id != plan.search_run_id
        or receipt.research_question_id != plan.research_question_id
        or receipt.acquisition_route != AcquisitionRoute.UNPAYWALL.value
    ):
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall acquisition receipt provenance did not reconcile with the plan."
        )

    planned = {
        plan_item.candidate_id: plan_item
        for plan_item in plan.items
        if plan_item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and plan_item.acquisition_route == AcquisitionRoute.UNPAYWALL.value
    }
    received_ids = [receipt_item.candidate_id for receipt_item in receipt.items]
    if (
        receipt.acquired_count != len(receipt.items)
        or len(set(received_ids)) != len(received_ids)
        or set(planned) != set(received_ids)
    ):
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Unpaywall acquisition receipt identities did not reconcile with the plan."
        )

    document_parser = parser or PyMuPDFParser()
    repository = DuplicateQueryRepository(session)
    persistence_items: list[GeneralQuestionUnpaywallPersistenceReceiptItem] = []
    persisted_count = 0
    reused_count = 0
    try:
        output_root = output_directory.resolve(strict=True)
        for receipt_item in receipt.items:
            plan_item = planned[receipt_item.candidate_id]
            identity = plan_item.identity
            if (
                identity is None
                or identity.doi is None
                or normalize_doi(identity.doi) != normalize_doi(receipt_item.doi)
            ):
                raise GeneralQuestionUnpaywallAcquisitionError(
                    "Unpaywall acquisition receipt identity did not reconcile with the plan."
                )
            if (
                Path(receipt_item.filename).name != receipt_item.filename
                or Path(receipt_item.filename).suffix.lower() != ".pdf"
            ):
                raise GeneralQuestionUnpaywallAcquisitionError(
                    "Unpaywall acquisition receipt contains an unsafe filename."
                )
            paper_path = (output_root / receipt_item.filename).resolve(strict=True)
            if paper_path.parent != output_root:
                raise GeneralQuestionUnpaywallAcquisitionError(
                    "Unpaywall acquisition receipt contains an unsafe file path."
                )
            if paper_path.stat().st_size != receipt_item.byte_count:
                raise GeneralQuestionUnpaywallAcquisitionError(
                    "Acquired Unpaywall file size did not match its receipt."
                )
            digest = file_sha256(paper_path)
            if digest != receipt_item.sha256:
                raise GeneralQuestionUnpaywallAcquisitionError(
                    "Acquired Unpaywall file digest did not match its receipt."
                )

            parsed = document_parser.parse(paper_path)
            existing = (
                repository.paper_by_content_hash(parsed.content_hash)
                or repository.paper_by_normalized_doi(identity.doi)
                or repository.paper_by_pmid(identity.pmid)
                or repository.paper_by_arxiv_id(identity.arxiv_id)
            )
            if existing is not None:
                paper = existing
                persistence_status = "reused"
                reused_count += 1
            else:
                paper = ClassifiedPaperRepository(session).add_parsed_paper(
                    parsed,
                    manifest_title=plan_item.title,
                    manifest_doi=identity.doi,
                    manifest_pmid=identity.pmid,
                    manifest_arxiv_id=identity.arxiv_id,
                )
                persistence_status = "persisted"
                persisted_count += 1
            persistence_items.append(
                GeneralQuestionUnpaywallPersistenceReceiptItem(
                    candidate_id=receipt_item.candidate_id,
                    doi=normalize_doi(receipt_item.doi),
                    pdf_url=receipt_item.pdf_url,
                    source_host=receipt_item.source_host,
                    filename=receipt_item.filename,
                    sha256=receipt_item.sha256,
                    paper_id=paper.id,
                    persistence_status=persistence_status,
                )
            )
    except GeneralQuestionUnpaywallAcquisitionError:
        raise
    except (DocumentParseError, FileNotFoundError, OSError, PaperPersistenceError) as exc:
        raise GeneralQuestionUnpaywallAcquisitionError(
            "Acquired Unpaywall files could not be parsed and persisted safely."
        ) from exc

    import_run_id, item_ids = _record_unpaywall_import_run(
        session, plan, receipt, tuple(persistence_items)
    )
    linked_items = tuple(
        GeneralQuestionUnpaywallPersistenceReceiptItem(
            candidate_id=item.candidate_id,
            doi=item.doi,
            pdf_url=item.pdf_url,
            source_host=item.source_host,
            filename=item.filename,
            sha256=item.sha256,
            paper_id=item.paper_id,
            persistence_status=item.persistence_status,
            import_item_id=item_id,
        )
        for item, item_id in zip(persistence_items, item_ids, strict=True)
    )
    return GeneralQuestionUnpaywallPersistenceReceipt(
        schema_version=1,
        search_run_id=receipt.search_run_id,
        research_question_id=receipt.research_question_id,
        acquisition_route=receipt.acquisition_route,
        import_run_id=import_run_id,
        parsed_count=len(linked_items),
        persisted_count=persisted_count,
        reused_count=reused_count,
        items=linked_items,
    )


def _record_unpaywall_import_run(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    receipt: GeneralQuestionUnpaywallReceipt,
    persistence_items: tuple[GeneralQuestionUnpaywallPersistenceReceiptItem, ...],
) -> tuple[str, tuple[str, ...]]:
    now = utc_now()
    import_run_id = new_uuid()
    snapshot_id = new_uuid()
    item_ids = tuple(new_uuid() for _ in persistence_items)
    corpus_path = f"gqr://search-runs/{plan.search_run_id}"
    snapshot_payload = {
        "schema_version": 1,
        "kind": "general_question_unpaywall_import",
        "plan": plan.to_dict(),
        "acquisition_receipt": asdict(receipt),
        "persistence_items": [
            {**asdict(item), "import_item_id": item_id}
            for item, item_id in zip(persistence_items, item_ids, strict=True)
        ],
    }
    snapshot_text = json.dumps(snapshot_payload, indent=2, sort_keys=True) + "\n"
    snapshot_bytes = snapshot_text.encode("utf-8")
    snapshot_digest = sha256(snapshot_bytes).hexdigest()
    combined_digest = sha256(b"general_question_unpaywall_import_v1\0" + snapshot_bytes).hexdigest()

    repository = ImportRunRepository(session)
    repository.add_snapshot(
        ManifestSnapshot(
            snapshot_id=snapshot_id,
            corpus_path=corpus_path,
            source_manifest_path=None,
            corpus_json_bytes=snapshot_bytes,
            source_csv_bytes=None,
            corpus_json_text=snapshot_text,
            source_csv_text=None,
            corpus_json_sha256=snapshot_digest,
            source_csv_sha256=None,
            combined_sha256=combined_digest,
            captured_at=now,
        )
    )
    repository.add_run(
        ImportRun(
            import_run_id=import_run_id,
            corpus_id=f"gqr-search-{plan.search_run_id}"[:256],
            corpus_name=f"General question: {plan.query_text}"[:512],
            manifest_version=1,
            validation_mode="gqr_unpaywall_acquisition",
            run_mode="fresh",
            run_status="succeeded",
            review_status="clear",
            manifest_validity="valid",
            import_readiness="ready",
            total_source_rows=len(persistence_items),
            valid_source_rows=len(persistence_items),
            warning_count=0,
            structural_error_count=0,
            import_blocker_count=0,
            created_at=now,
            completed_at=now,
            source_manifest_path=None,
            license_policy_path=None,
            corpus_path=corpus_path,
            parent_import_run_id=None,
            manifest_snapshot_id=snapshot_id,
        )
    )

    import_items: list[ImportItem] = []
    for ordinal, (persisted, item_id) in enumerate(
        zip(persistence_items, item_ids, strict=True), start=1
    ):
        plan_item = next(item for item in plan.items if item.candidate_id == persisted.candidate_id)
        identity = plan_item.identity
        if identity is None:
            raise GeneralQuestionUnpaywallAcquisitionError(
                "Unpaywall import lineage lost the planned identity."
            )
        duplicate_evidence = {
            "acquisition_route": receipt.acquisition_route,
            "pdf_url": persisted.pdf_url,
            "source_host": persisted.source_host,
            "persistence_status": persisted.persistence_status,
            "matched_paper_id": persisted.paper_id,
        }
        import_items.append(
            ImportItem(
                import_item_id=item_id,
                import_run_id=import_run_id,
                source_id=persisted.candidate_id,
                csv_line_number=ordinal,
                title=plan_item.title,
                normalized_doi=normalize_doi(identity.doi) if identity.doi else None,
                normalized_pmid=normalize_pmid(identity.pmid) if identity.pmid else None,
                normalized_arxiv_id=(
                    normalize_arxiv_id(identity.arxiv_id) if identity.arxiv_id else None
                ),
                inclusion_status="included",
                usage_status="approved_open_access",
                local_path=persisted.filename,
                item_status=(
                    "imported" if persisted.persistence_status == "persisted" else "skipped"
                ),
                duplicate_outcome=(
                    "new_paper"
                    if persisted.persistence_status == "persisted"
                    else "reused_existing_paper"
                ),
                matched_paper_id=persisted.paper_id,
                matched_import_item_id=None,
                computed_content_hash=persisted.sha256,
                duplicate_evidence_json=json.dumps(
                    duplicate_evidence, sort_keys=True, separators=(",", ":")
                ),
                retry_of_import_item_id=None,
                blocks_manifest=False,
                blocks_import=False,
                warning_count=0,
                structural_error_count=0,
                import_blocker_count=0,
                created_at=now,
                completed_at=now,
            )
        )
    repository.add_items(import_items)
    return import_run_id, item_ids


def _rollback_acquired_files(output_directory: Path, receipt: UnpaywallAcquisitionReceipt) -> None:
    rollback_failed = False
    for item in receipt.items:
        try:
            (output_directory / item.filename).unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise GeneralQuestionUnpaywallAcquisitionError("Unpaywall acquisition rollback failed.")
