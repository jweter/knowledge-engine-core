"""Execute validation-gated PMC routes from a General Question acquisition plan."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository
from knowledge_engine.general_question_acquisition import (
    AcquisitionDisposition,
    AcquisitionRoute,
    GeneralQuestionAcquisitionPlan,
)
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.paper_persistence import ClassifiedPaperRepository
from knowledge_engine.parser import DocumentParseError, DocumentParser, PyMuPDFParser
from knowledge_engine.persistence_errors import PaperPersistenceError
from knowledge_engine.pmc_acquisition import AcquisitionReceipt
from knowledge_engine.pubmed_discovery import PubmedCandidate
from knowledge_engine.utils import file_sha256


class GeneralQuestionPmcAcquisitionError(RuntimeError):
    """A sanitized failure while compiling or executing planned PMC routes."""


class PmcCandidateResolver(Protocol):
    """Resolve exact PMIDs to current, independently verified PMC OA evidence."""

    def resolve_pmids(self, pmids: tuple[str, ...]) -> tuple[PubmedCandidate, ...]:
        """Resolve the supplied identifiers without running a new search."""


class PmcAcquisitionExecutor(Protocol):
    """Approval-gated subset of the existing PMC acquisition service."""

    def acquire(
        self,
        *,
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
        expected_count: int | None = None,
    ) -> AcquisitionReceipt:
        """Acquire one exact, reconciled batch."""


@dataclass(frozen=True)
class GeneralQuestionPmcReceiptItem:
    """One acquired file tied back to its provider-neutral plan identity."""

    candidate_id: str
    pmid: str
    pmcid: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class GeneralQuestionPmcReceipt:
    """Durable, sanitized receipt for one planned PMC acquisition batch."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    acquired_count: int
    items: tuple[GeneralQuestionPmcReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class GeneralQuestionPmcExecution:
    """Public receipt plus the underlying receipt used for rollback."""

    receipt: GeneralQuestionPmcReceipt
    acquisition_receipt: AcquisitionReceipt


@dataclass(frozen=True)
class GeneralQuestionPmcPersistenceReceiptItem:
    """One verified acquisition reconciled to its durable Paper record."""

    candidate_id: str
    pmid: str
    pmcid: str
    filename: str
    sha256: str
    paper_id: int
    persistence_status: str


@dataclass(frozen=True)
class GeneralQuestionPmcPersistenceReceipt:
    """Durable result of parsing and persisting one acquired PMC batch."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    parsed_count: int
    persisted_count: int
    reused_count: int
    items: tuple[GeneralQuestionPmcPersistenceReceiptItem, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def execute_pmc_acquisition_plan(
    plan: GeneralQuestionAcquisitionPlan,
    *,
    resolver: PmcCandidateResolver,
    acquisition_service: PmcAcquisitionExecutor,
    output_directory: Path,
) -> GeneralQuestionPmcExecution:
    """Resolve and acquire every PMC-routed eligible item in one atomic batch."""

    selected = tuple(
        item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.PMC_OA.value
    )
    if not selected:
        raise GeneralQuestionPmcAcquisitionError(
            "Acquisition plan contains no eligible PMC OA routes."
        )

    candidate_ids_by_pmid: dict[str, str] = {}
    pmids: list[str] = []
    for item in selected:
        pmid = item.identity.pmid if item.identity is not None else None
        if pmid is None or not pmid.isdigit():
            raise GeneralQuestionPmcAcquisitionError(
                "Every planned PMC route must carry a valid PMID."
            )
        if pmid in candidate_ids_by_pmid:
            raise GeneralQuestionPmcAcquisitionError("Planned PMC routes contain a duplicate PMID.")
        candidate_ids_by_pmid[pmid] = item.candidate_id
        pmids.append(pmid)

    try:
        resolved = resolver.resolve_pmids(tuple(pmids))
    except (OSError, RuntimeError, ValueError) as exc:
        raise GeneralQuestionPmcAcquisitionError(
            "Planned PMC identifiers could not be resolved."
        ) from exc

    resolved_by_pmid = {candidate.pmid: candidate for candidate in resolved}
    if len(resolved_by_pmid) != len(resolved) or set(resolved_by_pmid) != set(pmids):
        raise GeneralQuestionPmcAcquisitionError(
            "Resolved PMC candidates did not reconcile with the acquisition plan."
        )

    approvals: list[dict[str, str]] = []
    for pmid in pmids:
        candidate = resolved_by_pmid[pmid]
        if (
            candidate.status != "oa_verified"
            or candidate.open_access is not True
            or candidate.pmcid is None
            or candidate.pdf_url is None
            or candidate.license is None
            or evaluate_license(candidate.license) != "passed"
        ):
            raise GeneralQuestionPmcAcquisitionError(
                "A planned PMC candidate lacks verified reusable full-text evidence."
            )
        approvals.append(
            {
                "pmid": candidate.pmid,
                "pmcid": candidate.pmcid,
                "license": candidate.license,
                "pdf_url": candidate.pdf_url,
                "filename": f"{candidate.pmcid}.pdf",
            }
        )

    with tempfile.TemporaryDirectory(prefix="ke-gqr-pmc-") as temporary:
        temporary_root = Path(temporary)
        candidates_path = temporary_root / "candidates.json"
        approvals_path = temporary_root / "approvals.json"
        candidates_path.write_text(
            json.dumps(
                {"candidates": [asdict(resolved_by_pmid[pmid]) for pmid in pmids]},
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
            raise GeneralQuestionPmcAcquisitionError("Planned PMC acquisition failed.") from exc

    if acquired.acquired_count != len(pmids):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionPmcAcquisitionError(
            "PMC acquisition receipt count did not reconcile with the plan."
        )
    acquired_by_pmid = {item.pmid: item for item in acquired.items}
    if len(acquired_by_pmid) != len(acquired.items) or set(acquired_by_pmid) != set(pmids):
        _rollback_acquired_files(output_directory, acquired)
        raise GeneralQuestionPmcAcquisitionError(
            "PMC acquisition receipt identities did not reconcile with the plan."
        )

    receipt_items = tuple(
        GeneralQuestionPmcReceiptItem(
            candidate_id=candidate_ids_by_pmid[pmid],
            pmid=item.pmid,
            pmcid=item.pmcid,
            license=item.license,
            filename=item.filename,
            byte_count=item.byte_count,
            sha256=item.sha256,
        )
        for pmid in pmids
        for item in (acquired_by_pmid[pmid],)
    )
    return GeneralQuestionPmcExecution(
        receipt=GeneralQuestionPmcReceipt(
            schema_version=1,
            search_run_id=plan.search_run_id,
            research_question_id=plan.research_question_id,
            acquisition_route=AcquisitionRoute.PMC_OA.value,
            acquired_count=len(receipt_items),
            items=receipt_items,
        ),
        acquisition_receipt=acquired,
    )


def persist_pmc_acquisition_execution(
    session: Session,
    plan: GeneralQuestionAcquisitionPlan,
    execution: GeneralQuestionPmcExecution,
    *,
    output_directory: Path,
    parser: DocumentParser | None = None,
) -> GeneralQuestionPmcPersistenceReceipt:
    """Verify, parse, and persist an acquired PMC batch atomically with the caller.

    The public acquisition receipt is an integrity boundary: every filename must
    remain directly under the output directory and every byte count and SHA-256
    digest must match before parsing starts. The caller owns the outer transaction,
    so any raised error rolls back the complete batch.
    """

    receipt = execution.receipt
    if (
        receipt.search_run_id != plan.search_run_id
        or receipt.research_question_id != plan.research_question_id
        or receipt.acquisition_route != AcquisitionRoute.PMC_OA.value
    ):
        raise GeneralQuestionPmcAcquisitionError(
            "PMC acquisition receipt provenance did not reconcile with the plan."
        )

    planned = {
        item.candidate_id: item
        for item in plan.items
        if item.disposition == AcquisitionDisposition.ELIGIBLE_FULL_TEXT.value
        and item.acquisition_route == AcquisitionRoute.PMC_OA.value
    }
    if receipt.acquired_count != len(receipt.items) or set(planned) != {
        item.candidate_id for item in receipt.items
    }:
        raise GeneralQuestionPmcAcquisitionError(
            "PMC acquisition receipt identities did not reconcile with the plan."
        )

    document_parser = parser or PyMuPDFParser()
    repository = DuplicateQueryRepository(session)
    persistence_items: list[GeneralQuestionPmcPersistenceReceiptItem] = []
    persisted_count = 0
    reused_count = 0
    try:
        output_root = output_directory.resolve(strict=True)
        for receipt_item in receipt.items:
            plan_item = planned[receipt_item.candidate_id]
            identity = plan_item.identity
            if identity is None or identity.pmid != receipt_item.pmid:
                raise GeneralQuestionPmcAcquisitionError(
                    "PMC acquisition receipt identity did not reconcile with the plan."
                )
            if (
                Path(receipt_item.filename).name != receipt_item.filename
                or Path(receipt_item.filename).suffix.lower() != ".pdf"
            ):
                raise GeneralQuestionPmcAcquisitionError(
                    "PMC acquisition receipt contains an unsafe filename."
                )

            paper_path = (output_root / receipt_item.filename).resolve(strict=True)
            if paper_path.parent != output_root:
                raise GeneralQuestionPmcAcquisitionError(
                    "PMC acquisition receipt contains an unsafe file path."
                )
            if paper_path.stat().st_size != receipt_item.byte_count:
                raise GeneralQuestionPmcAcquisitionError(
                    "Acquired PMC file size did not match its receipt."
                )
            digest = file_sha256(paper_path)
            if digest != receipt_item.sha256:
                raise GeneralQuestionPmcAcquisitionError(
                    "Acquired PMC file digest did not match its receipt."
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
                GeneralQuestionPmcPersistenceReceiptItem(
                    candidate_id=receipt_item.candidate_id,
                    pmid=receipt_item.pmid,
                    pmcid=receipt_item.pmcid,
                    filename=receipt_item.filename,
                    sha256=receipt_item.sha256,
                    paper_id=paper.id,
                    persistence_status=status,
                )
            )
    except GeneralQuestionPmcAcquisitionError:
        raise
    except (DocumentParseError, FileNotFoundError, OSError, PaperPersistenceError) as exc:
        raise GeneralQuestionPmcAcquisitionError(
            "Acquired PMC files could not be parsed and persisted safely."
        ) from exc

    return GeneralQuestionPmcPersistenceReceipt(
        schema_version=1,
        search_run_id=receipt.search_run_id,
        research_question_id=receipt.research_question_id,
        acquisition_route=receipt.acquisition_route,
        parsed_count=len(persistence_items),
        persisted_count=persisted_count,
        reused_count=reused_count,
        items=tuple(persistence_items),
    )


def _rollback_acquired_files(output_directory: Path, receipt: AcquisitionReceipt) -> None:
    try:
        for item in receipt.items:
            (output_directory / item.filename).unlink(missing_ok=True)
    except OSError as exc:
        raise GeneralQuestionPmcAcquisitionError(
            "PMC acquisition receipt reconciliation failed and rollback was incomplete."
        ) from exc


__all__ = [
    "GeneralQuestionPmcAcquisitionError",
    "GeneralQuestionPmcExecution",
    "GeneralQuestionPmcPersistenceReceipt",
    "GeneralQuestionPmcPersistenceReceiptItem",
    "GeneralQuestionPmcReceipt",
    "GeneralQuestionPmcReceiptItem",
    "PmcCandidateResolver",
    "execute_pmc_acquisition_plan",
    "persist_pmc_acquisition_execution",
]
