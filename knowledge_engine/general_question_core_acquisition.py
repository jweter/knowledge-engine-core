"""Execute and persist validation-gated CORE routes from a General Question plan."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from knowledge_engine.core_acquisition import (
    CoreAcquisitionApproval,
    CoreAcquisitionReceipt,
)
from knowledge_engine.core_discovery import CORE_PDF_HOST, CoreCandidate
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
from knowledge_engine.utils import file_sha256, normalize_arxiv_id, normalize_doi, normalize_pmid


class GeneralQuestionCoreAcquisitionError(RuntimeError):
    """Sanitized failure while resolving, acquiring, or persisting CORE routes."""


class CoreCandidateResolver(Protocol):
    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[CoreCandidate, ...]: ...


class CoreAcquisitionExecutor(Protocol):
    def acquire(
        self,
        *,
        candidates: tuple[CoreCandidate, ...],
        approvals: tuple[CoreAcquisitionApproval, ...],
        output_directory: Path,
    ) -> CoreAcquisitionReceipt: ...


@dataclass(frozen=True)
class GeneralQuestionCoreReceiptItem:
    candidate_id: str
    core_id: str
    doi: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class GeneralQuestionCoreReceipt:
    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    acquired_count: int
    items: tuple[GeneralQuestionCoreReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GeneralQuestionCoreExecution:
    receipt: GeneralQuestionCoreReceipt
    acquisition_receipt: CoreAcquisitionReceipt


@dataclass(frozen=True)
class GeneralQuestionCorePersistenceReceiptItem:
    candidate_id: str
    core_id: str
    doi: str
    filename: str
    sha256: str
    paper_id: int
    persistence_status: str
    import_item_id: str | None = None


@dataclass(frozen=True)
class GeneralQuestionCorePersistenceReceipt:
    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    import_run_id: str
    parsed_count: int
    persisted_count: int
    reused_count: int
    items: tuple[GeneralQuestionCorePersistenceReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def execute_core_acquisition_plan(
    plan: GeneralQuestionAcquisitionPlan,
    *,
    resolver: CoreCandidateResolver,
    acquisition_service: CoreAcquisitionExecutor,
    output_directory: Path,
) -> GeneralQuestionCoreExecution:
    """Refresh exact DOI identity and atomically acquire every CORE-routed item.

    CORE does not expose per-work license metadata.  The route therefore fails
    closed unless the persisted plan itself carries a reusable license, even if
    the planning stage considered provider OA evidence sufficient.  Current CORE
    identity/full-text location is independently refreshed before acquisition.
    """

    selected = tuple(
        item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.CORE.value
    )
    if not selected:
        raise GeneralQuestionCoreAcquisitionError(
            "Acquisition plan contains no eligible CORE routes."
        )

    candidate_ids_by_doi: dict[str, str] = {}
    planned_by_doi: dict[str, AcquisitionPlanItem] = {}
    dois: list[str] = []
    for item in selected:
        raw_doi = item.identity.doi if item.identity is not None else None
        doi = normalize_doi(raw_doi) if raw_doi is not None else ""
        if not doi:
            raise GeneralQuestionCoreAcquisitionError(
                "Every planned CORE route must carry a valid DOI."
            )
        if doi in candidate_ids_by_doi:
            raise GeneralQuestionCoreAcquisitionError(
                "Planned CORE routes contain a duplicate DOI."
            )
        if item.license is None or evaluate_license(item.license) != "passed":
            raise GeneralQuestionCoreAcquisitionError(
                "Planned CORE route lacks explicit reusable license evidence."
            )
        if not item.full_text_url:
            raise GeneralQuestionCoreAcquisitionError("Planned CORE route lacks a full-text URL.")
        candidate_ids_by_doi[doi] = item.candidate_id
        planned_by_doi[doi] = item
        dois.append(doi)

    try:
        resolved = resolver.resolve_dois(tuple(dois))
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionCoreAcquisitionError(
            "Planned CORE identifiers could not be resolved."
        ) from exc

    resolved_by_doi = {
        normalize_doi(candidate.doi): candidate
        for candidate in resolved
        if candidate.doi is not None
    }
    if len(resolved_by_doi) != len(resolved) or set(resolved_by_doi) != set(dois):
        raise GeneralQuestionCoreAcquisitionError(
            "Resolved CORE candidates did not reconcile with the acquisition plan."
        )

    approvals: list[CoreAcquisitionApproval] = []
    for doi in dois:
        candidate = resolved_by_doi[doi]
        plan_item = planned_by_doi[doi]
        planned_url = plan_item.full_text_url
        planned_license = plan_item.license
        if (
            candidate.pdf_url is None
            or candidate.pdf_host != CORE_PDF_HOST
            or candidate.pdf_url != planned_url
        ):
            raise GeneralQuestionCoreAcquisitionError(
                "Refreshed CORE full-text evidence did not reconcile with the plan."
            )
        safe_core_id = "".join(character for character in candidate.core_id if character.isalnum())
        if not safe_core_id:
            raise GeneralQuestionCoreAcquisitionError("CORE work identifier is unsafe.")
        approvals.append(
            CoreAcquisitionApproval(
                core_id=candidate.core_id,
                doi=doi,
                license=str(planned_license),
                pdf_url=candidate.pdf_url,
                filename=f"core-{safe_core_id}.pdf",
            )
        )

    try:
        acquired = acquisition_service.acquire(
            candidates=tuple(resolved_by_doi[doi] for doi in dois),
            approvals=tuple(approvals),
            output_directory=output_directory,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionCoreAcquisitionError("Planned CORE acquisition failed.") from exc

    if acquired.acquired_count != len(dois) or acquired.acquired_count != len(acquired.items):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionCoreAcquisitionError(
            "CORE acquisition receipt count did not reconcile with the plan."
        )
    acquired_by_doi = {normalize_doi(item.doi): item for item in acquired.items}
    if len(acquired_by_doi) != len(acquired.items) or set(acquired_by_doi) != set(dois):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionCoreAcquisitionError(
            "CORE acquisition receipt identities did not reconcile with the plan."
        )
    for doi in dois:
        item = acquired_by_doi[doi]
        candidate = resolved_by_doi[doi]
        plan_item = planned_by_doi[doi]
        if item.core_id != candidate.core_id or item.license != plan_item.license:
            _rollback_acquired_files(output_directory, acquired)
            raise GeneralQuestionCoreAcquisitionError(
                "CORE acquisition receipt evidence did not reconcile with resolution."
            )

    receipt_items = tuple(
        GeneralQuestionCoreReceiptItem(
            candidate_id=candidate_ids_by_doi[doi],
            core_id=item.core_id,
            doi=doi,
            license=item.license,
            filename=item.filename,
            byte_count=item.byte_count,
            sha256=item.sha256,
        )
        for doi in dois
        for item in (acquired_by_doi[doi],)
    )
    return GeneralQuestionCoreExecution(
        receipt=GeneralQuestionCoreReceipt(
            schema_version=1,
            search_run_id=plan.search_run_id,
            research_question_id=plan.research_question_id,
            acquisition_route=AcquisitionRoute.CORE.value,
            acquired_count=len(receipt_items),
            items=receipt_items,
        ),
        acquisition_receipt=acquired,
    )


def persist_core_acquisition_execution(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    execution: GeneralQuestionCoreExecution,
    *,
    output_directory: Path,
    parser: DocumentParser | None = None,
) -> GeneralQuestionCorePersistenceReceipt:
    """Verify acquired bytes, parse them, persist/reuse Papers, and record import lineage."""

    receipt = execution.receipt
    if (
        receipt.search_run_id != plan.search_run_id
        or receipt.research_question_id != plan.research_question_id
        or receipt.acquisition_route != AcquisitionRoute.CORE.value
    ):
        raise GeneralQuestionCoreAcquisitionError(
            "CORE acquisition receipt provenance did not reconcile with the plan."
        )

    planned = {
        item.candidate_id: item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.CORE.value
    }
    received_ids = [item.candidate_id for item in receipt.items]
    if (
        receipt.acquired_count != len(receipt.items)
        or len(set(received_ids)) != len(received_ids)
        or set(planned) != set(received_ids)
    ):
        raise GeneralQuestionCoreAcquisitionError(
            "CORE acquisition receipt identities did not reconcile with the plan."
        )

    document_parser = parser or PyMuPDFParser()
    repository = DuplicateQueryRepository(session)
    persistence_items: list[GeneralQuestionCorePersistenceReceiptItem] = []
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
                raise GeneralQuestionCoreAcquisitionError(
                    "CORE acquisition receipt identity did not reconcile with the plan."
                )
            if (
                Path(receipt_item.filename).name != receipt_item.filename
                or Path(receipt_item.filename).suffix.lower() != ".pdf"
            ):
                raise GeneralQuestionCoreAcquisitionError(
                    "CORE acquisition receipt contains an unsafe filename."
                )
            paper_path = (output_root / receipt_item.filename).resolve(strict=True)
            if paper_path.parent != output_root:
                raise GeneralQuestionCoreAcquisitionError(
                    "CORE acquisition receipt contains an unsafe file path."
                )
            if paper_path.stat().st_size != receipt_item.byte_count:
                raise GeneralQuestionCoreAcquisitionError(
                    "Acquired CORE file size did not match its receipt."
                )
            digest = file_sha256(paper_path)
            if digest != receipt_item.sha256:
                raise GeneralQuestionCoreAcquisitionError(
                    "Acquired CORE file digest did not match its receipt."
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
                GeneralQuestionCorePersistenceReceiptItem(
                    candidate_id=receipt_item.candidate_id,
                    core_id=receipt_item.core_id,
                    doi=normalize_doi(receipt_item.doi),
                    filename=receipt_item.filename,
                    sha256=receipt_item.sha256,
                    paper_id=paper.id,
                    persistence_status=persistence_status,
                )
            )
    except GeneralQuestionCoreAcquisitionError:
        raise
    except (DocumentParseError, FileNotFoundError, OSError, PaperPersistenceError) as exc:
        raise GeneralQuestionCoreAcquisitionError(
            "Acquired CORE files could not be parsed and persisted safely."
        ) from exc

    import_run_id, item_ids = _record_core_import_run(
        session, plan, receipt, tuple(persistence_items)
    )
    linked_items = tuple(
        GeneralQuestionCorePersistenceReceiptItem(
            candidate_id=item.candidate_id,
            core_id=item.core_id,
            doi=item.doi,
            filename=item.filename,
            sha256=item.sha256,
            paper_id=item.paper_id,
            persistence_status=item.persistence_status,
            import_item_id=item_id,
        )
        for item, item_id in zip(persistence_items, item_ids, strict=True)
    )
    return GeneralQuestionCorePersistenceReceipt(
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


def _record_core_import_run(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    receipt: GeneralQuestionCoreReceipt,
    persistence_items: tuple[GeneralQuestionCorePersistenceReceiptItem, ...],
) -> tuple[str, tuple[str, ...]]:
    now = utc_now()
    import_run_id = new_uuid()
    snapshot_id = new_uuid()
    item_ids = tuple(new_uuid() for _ in persistence_items)
    corpus_path = f"gqr://search-runs/{plan.search_run_id}"
    snapshot_payload = {
        "schema_version": 1,
        "kind": "general_question_core_import",
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
    combined_digest = sha256(b"general_question_core_import_v1\0" + snapshot_bytes).hexdigest()

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
            validation_mode="gqr_core_acquisition",
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
        plan_item = planned_item = next(
            item for item in plan.items if item.candidate_id == persisted.candidate_id
        )
        identity = plan_item.identity
        if identity is None:
            raise GeneralQuestionCoreAcquisitionError(
                "CORE import lineage lost the planned identity."
            )
        duplicate_evidence = {
            "acquisition_route": receipt.acquisition_route,
            "core_id": persisted.core_id,
            "persistence_status": persisted.persistence_status,
            "matched_paper_id": persisted.paper_id,
        }
        import_items.append(
            ImportItem(
                import_item_id=item_id,
                import_run_id=import_run_id,
                source_id=persisted.candidate_id,
                csv_line_number=ordinal,
                title=planned_item.title,
                normalized_doi=normalize_doi(identity.doi) if identity.doi else None,
                normalized_pmid=normalize_pmid(identity.pmid) if identity.pmid else None,
                normalized_arxiv_id=(
                    normalize_arxiv_id(identity.arxiv_id) if identity.arxiv_id else None
                ),
                inclusion_status="included",
                usage_status="approved_open_access",
                local_path=persisted.filename,
                item_status="imported"
                if persisted.persistence_status == "persisted"
                else "skipped",
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


def _rollback_acquired_files(output_directory: Path, receipt: CoreAcquisitionReceipt) -> None:
    rollback_failed = False
    for item in receipt.items:
        try:
            (output_directory / item.filename).unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise GeneralQuestionCoreAcquisitionError("CORE acquisition rollback failed.")
