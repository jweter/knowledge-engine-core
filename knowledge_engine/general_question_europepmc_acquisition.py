"""Execute validation-gated Europe PMC routes from a General Question plan."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository
from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionReceipt,
)
from knowledge_engine.europepmc_discovery import EuropePmcCandidate
from knowledge_engine.europepmc_http import EUROPEPMC_PLUS_HOST
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
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
from knowledge_engine.utils import (
    file_sha256,
    normalize_arxiv_id,
    normalize_doi,
    normalize_pmid,
)


class GeneralQuestionEuropePmcAcquisitionError(RuntimeError):
    """A sanitized failure while compiling or executing Europe PMC routes."""


class EuropePmcCandidateResolver(Protocol):
    """Resolve exact DOIs to current, independently verified Europe PMC evidence."""

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[EuropePmcCandidate, ...]:
        """Resolve the supplied identifiers without running a topical search."""


class EuropePmcAcquisitionExecutor(Protocol):
    """Approval-gated subset of the existing Europe PMC acquisition service."""

    def acquire(
        self,
        *,
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
        expected_count: int | None = None,
    ) -> EuropePmcAcquisitionReceipt:
        """Acquire one exact, reconciled batch."""


@dataclass(frozen=True)
class GeneralQuestionEuropePmcReceiptItem:
    """One acquired file tied back to its provider-neutral plan identity."""

    candidate_id: str
    europepmc_id: str
    doi: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class GeneralQuestionEuropePmcReceipt:
    """Durable, sanitized receipt for one planned Europe PMC batch."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    acquired_count: int
    items: tuple[GeneralQuestionEuropePmcReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GeneralQuestionEuropePmcExecution:
    """Public receipt plus the underlying receipt used for rollback."""

    receipt: GeneralQuestionEuropePmcReceipt
    acquisition_receipt: EuropePmcAcquisitionReceipt


@dataclass(frozen=True)
class GeneralQuestionEuropePmcPersistenceReceiptItem:
    """One verified acquisition reconciled to its durable Paper record."""

    candidate_id: str
    europepmc_id: str
    doi: str
    filename: str
    sha256: str
    paper_id: int
    persistence_status: str
    import_item_id: str | None = None


@dataclass(frozen=True)
class GeneralQuestionEuropePmcPersistenceReceipt:
    """Durable result of parsing and persisting one acquired Europe PMC batch."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    import_run_id: str
    parsed_count: int
    persisted_count: int
    reused_count: int
    items: tuple[GeneralQuestionEuropePmcPersistenceReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def execute_europepmc_acquisition_plan(
    plan: GeneralQuestionAcquisitionPlan,
    *,
    resolver: EuropePmcCandidateResolver,
    acquisition_service: EuropePmcAcquisitionExecutor,
    output_directory: Path,
) -> GeneralQuestionEuropePmcExecution:
    """Resolve and acquire every Europe-PMC-routed eligible item atomically."""

    selected = tuple(
        item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.EUROPE_PMC_OA.value
    )
    if not selected:
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Acquisition plan contains no eligible Europe PMC OA routes."
        )

    candidate_ids_by_doi: dict[str, str] = {}
    dois: list[str] = []
    for item in selected:
        raw_doi = item.identity.doi if item.identity is not None else None
        doi = normalize_doi(raw_doi) if raw_doi is not None else ""
        if not doi:
            raise GeneralQuestionEuropePmcAcquisitionError(
                "Every planned Europe PMC route must carry a valid DOI."
            )
        if doi in candidate_ids_by_doi:
            raise GeneralQuestionEuropePmcAcquisitionError(
                "Planned Europe PMC routes contain a duplicate DOI."
            )
        candidate_ids_by_doi[doi] = item.candidate_id
        dois.append(doi)

    try:
        resolved = resolver.resolve_dois(tuple(dois))
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Planned Europe PMC identifiers could not be resolved."
        ) from exc

    resolved_by_doi = {
        normalize_doi(candidate.doi): candidate
        for candidate in resolved
        if candidate.doi is not None
    }
    if len(resolved_by_doi) != len(resolved) or set(resolved_by_doi) != set(dois):
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Resolved Europe PMC candidates did not reconcile with the acquisition plan."
        )

    approvals: list[dict[str, str]] = []
    for doi in dois:
        candidate = resolved_by_doi[doi]
        if (
            candidate.in_pmc
            or candidate.open_access is not True
            or candidate.pdf_host != EUROPEPMC_PLUS_HOST
            or candidate.pdf_url is None
            or candidate.license is None
            or evaluate_license(candidate.license) != "passed"
        ):
            raise GeneralQuestionEuropePmcAcquisitionError(
                "A planned Europe PMC candidate lacks verified reusable full-text evidence."
            )
        approvals.append(
            {
                "europepmc_id": candidate.europepmc_id,
                "doi": doi,
                "license": candidate.license,
                "pdf_url": candidate.pdf_url,
                "filename": f"europepmc-{candidate.europepmc_id}.pdf",
            }
        )

    with tempfile.TemporaryDirectory(prefix="ke-gqr-europepmc-") as temporary:
        temporary_root = Path(temporary)
        candidates_path = temporary_root / "candidates.json"
        approvals_path = temporary_root / "approvals.json"
        candidates_path.write_text(
            json.dumps(
                {"candidates": [asdict(resolved_by_doi[doi]) for doi in dois]},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        approvals_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "selected_count": len(approvals),
                    "approvals": approvals,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            acquired = acquisition_service.acquire(
                candidates_path=candidates_path,
                approvals_path=approvals_path,
                output_directory=output_directory,
                expected_count=len(approvals),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise GeneralQuestionEuropePmcAcquisitionError(
                "Planned Europe PMC acquisition failed."
            ) from exc

    if acquired.acquired_count != len(dois):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC acquisition receipt count did not reconcile with the plan."
        )
    acquired_by_doi = {normalize_doi(item.doi): item for item in acquired.items}
    if len(acquired_by_doi) != len(acquired.items) or set(acquired_by_doi) != set(dois):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC acquisition receipt identities did not reconcile with the plan."
        )
    if any(
        acquired_by_doi[doi].europepmc_id != resolved_by_doi[doi].europepmc_id
        or acquired_by_doi[doi].license != resolved_by_doi[doi].license
        for doi in dois
    ):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC acquisition receipt evidence did not reconcile with resolution."
        )

    receipt_items = tuple(
        GeneralQuestionEuropePmcReceiptItem(
            candidate_id=candidate_ids_by_doi[doi],
            europepmc_id=item.europepmc_id,
            doi=normalize_doi(item.doi),
            license=item.license,
            filename=item.filename,
            byte_count=item.byte_count,
            sha256=item.sha256,
        )
        for doi in dois
        for item in (acquired_by_doi[doi],)
    )
    return GeneralQuestionEuropePmcExecution(
        receipt=GeneralQuestionEuropePmcReceipt(
            schema_version=1,
            search_run_id=plan.search_run_id,
            research_question_id=plan.research_question_id,
            acquisition_route=AcquisitionRoute.EUROPE_PMC_OA.value,
            acquired_count=len(receipt_items),
            items=receipt_items,
        ),
        acquisition_receipt=acquired,
    )


def persist_europepmc_acquisition_execution(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    execution: GeneralQuestionEuropePmcExecution,
    *,
    output_directory: Path,
    parser: DocumentParser | None = None,
) -> GeneralQuestionEuropePmcPersistenceReceipt:
    """Verify, parse, and persist one acquired Europe PMC batch atomically."""

    receipt = execution.receipt
    if (
        receipt.search_run_id != plan.search_run_id
        or receipt.research_question_id != plan.research_question_id
        or receipt.acquisition_route != AcquisitionRoute.EUROPE_PMC_OA.value
    ):
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC acquisition receipt provenance did not reconcile with the plan."
        )

    planned = {
        item.candidate_id: item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.EUROPE_PMC_OA.value
    }
    received_ids = [item.candidate_id for item in receipt.items]
    if (
        receipt.acquired_count != len(receipt.items)
        or len(set(received_ids)) != len(received_ids)
        or set(planned) != set(received_ids)
    ):
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC acquisition receipt identities did not reconcile with the plan."
        )

    document_parser = parser or PyMuPDFParser()
    repository = DuplicateQueryRepository(session)
    persistence_items: list[GeneralQuestionEuropePmcPersistenceReceiptItem] = []
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
                raise GeneralQuestionEuropePmcAcquisitionError(
                    "Europe PMC acquisition receipt identity did not reconcile with the plan."
                )
            if (
                Path(receipt_item.filename).name != receipt_item.filename
                or Path(receipt_item.filename).suffix.lower() != ".pdf"
            ):
                raise GeneralQuestionEuropePmcAcquisitionError(
                    "Europe PMC acquisition receipt contains an unsafe filename."
                )

            paper_path = (output_root / receipt_item.filename).resolve(strict=True)
            if paper_path.parent != output_root:
                raise GeneralQuestionEuropePmcAcquisitionError(
                    "Europe PMC acquisition receipt contains an unsafe file path."
                )
            if paper_path.stat().st_size != receipt_item.byte_count:
                raise GeneralQuestionEuropePmcAcquisitionError(
                    "Acquired Europe PMC file size did not match its receipt."
                )
            digest = file_sha256(paper_path)
            if digest != receipt_item.sha256:
                raise GeneralQuestionEuropePmcAcquisitionError(
                    "Acquired Europe PMC file digest did not match its receipt."
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
                status = "reused"
                reused_count += 1
            else:
                paper = ClassifiedPaperRepository(session).add_parsed_paper(
                    parsed,
                    manifest_title=plan_item.title,
                    manifest_doi=identity.doi,
                    manifest_pmid=identity.pmid,
                    manifest_arxiv_id=identity.arxiv_id,
                )
                status = "persisted"
                persisted_count += 1

            persistence_items.append(
                GeneralQuestionEuropePmcPersistenceReceiptItem(
                    candidate_id=receipt_item.candidate_id,
                    europepmc_id=receipt_item.europepmc_id,
                    doi=normalize_doi(receipt_item.doi),
                    filename=receipt_item.filename,
                    sha256=receipt_item.sha256,
                    paper_id=paper.id,
                    persistence_status=status,
                )
            )
    except GeneralQuestionEuropePmcAcquisitionError:
        raise
    except (DocumentParseError, FileNotFoundError, OSError, PaperPersistenceError) as exc:
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Acquired Europe PMC files could not be parsed and persisted safely."
        ) from exc

    import_run_id, import_item_ids = _record_europepmc_import_run(
        session,
        plan,
        receipt,
        tuple(persistence_items),
    )
    linked_items = tuple(
        GeneralQuestionEuropePmcPersistenceReceiptItem(
            candidate_id=item.candidate_id,
            europepmc_id=item.europepmc_id,
            doi=item.doi,
            filename=item.filename,
            sha256=item.sha256,
            paper_id=item.paper_id,
            import_item_id=import_item_id,
            persistence_status=item.persistence_status,
        )
        for item, import_item_id in zip(persistence_items, import_item_ids, strict=True)
    )
    return GeneralQuestionEuropePmcPersistenceReceipt(
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


def _record_europepmc_import_run(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    receipt: GeneralQuestionEuropePmcReceipt,
    persistence_items: tuple[GeneralQuestionEuropePmcPersistenceReceiptItem, ...],
) -> tuple[str, tuple[str, ...]]:
    """Persist immutable ImportRun/ImportItem provenance for the completed batch."""

    now = utc_now()
    import_run_id = new_uuid()
    snapshot_id = new_uuid()
    item_ids = tuple(new_uuid() for _ in persistence_items)
    corpus_path = f"gqr://search-runs/{plan.search_run_id}"
    snapshot_payload = {
        "schema_version": 1,
        "kind": "general_question_europepmc_import",
        "plan": plan.to_dict(),
        "acquisition_receipt": asdict(receipt),
        "persistence_items": [
            {**asdict(item), "import_item_id": import_item_id}
            for item, import_item_id in zip(persistence_items, item_ids, strict=True)
        ],
    }
    snapshot_text = json.dumps(snapshot_payload, indent=2, sort_keys=True) + "\n"
    snapshot_bytes = snapshot_text.encode("utf-8")
    snapshot_digest = sha256(snapshot_bytes).hexdigest()
    combined_digest = sha256(b"general_question_europepmc_import_v1\0" + snapshot_bytes).hexdigest()

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
            validation_mode="gqr_europepmc_acquisition",
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

    plan_by_candidate = {item.candidate_id: item for item in plan.items}
    import_items: list[ImportItem] = []
    linked_items = zip(persistence_items, item_ids, strict=True)
    for ordinal, (persisted, import_item_id) in enumerate(linked_items, start=2):
        plan_item = plan_by_candidate[persisted.candidate_id]
        identity = plan_item.identity
        if identity is None:
            raise GeneralQuestionEuropePmcAcquisitionError(
                "Persisted Europe PMC item lost its acquisition-plan identity."
            )
        duplicate_evidence = {
            "schema_version": 1,
            "search_run_id": plan.search_run_id,
            "research_question_id": plan.research_question_id,
            "candidate_id": persisted.candidate_id,
            "europepmc_id": persisted.europepmc_id,
            "acquisition_route": receipt.acquisition_route,
            "persistence_status": persisted.persistence_status,
            "matched_paper_id": persisted.paper_id,
        }
        import_items.append(
            ImportItem(
                import_item_id=import_item_id,
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
                    duplicate_evidence,
                    sort_keys=True,
                    separators=(",", ":"),
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
    session.flush()

    persisted_run = repository.get_run(import_run_id)
    if persisted_run is None or len(persisted_run.items) != len(import_items):
        raise RuntimeError("Europe PMC import-run provenance was not readable after persistence.")
    return import_run_id, item_ids


def _rollback_acquired_files(
    output_directory: Path,
    receipt: EuropePmcAcquisitionReceipt,
) -> None:
    try:
        for item in receipt.items:
            (output_directory / item.filename).unlink(missing_ok=True)
    except OSError as exc:
        raise GeneralQuestionEuropePmcAcquisitionError(
            "Europe PMC receipt reconciliation failed and rollback was incomplete."
        ) from exc


__all__ = [
    "EuropePmcCandidateResolver",
    "GeneralQuestionEuropePmcAcquisitionError",
    "GeneralQuestionEuropePmcExecution",
    "GeneralQuestionEuropePmcPersistenceReceipt",
    "GeneralQuestionEuropePmcPersistenceReceiptItem",
    "GeneralQuestionEuropePmcReceipt",
    "GeneralQuestionEuropePmcReceiptItem",
    "execute_europepmc_acquisition_plan",
    "persist_europepmc_acquisition_execution",
]
