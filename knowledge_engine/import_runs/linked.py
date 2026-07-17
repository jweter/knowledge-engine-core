"""Creation of immutable import runs linked to a prior attempt."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from knowledge_engine.corpus.validation import discover_project_root
from knowledge_engine.import_runs._helpers import utc_now
from knowledge_engine.import_runs.repository import ImportRunRepository
from knowledge_engine.import_runs.resume import ImportRunPlan, RunMode, plan_linked_run
from knowledge_engine.import_runs.service import ImportRunService
from knowledge_engine.models import ImportItem


@dataclass(frozen=True)
class PersistedLinkedRun:
    """Result of creating one immutable resume or retry run."""

    import_run_id: str
    run_status: str
    plan: ImportRunPlan


class LinkedImportRunService:
    """Create a new linked run while preserving the parent attempt unchanged."""

    def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
        self.session = session
        self.project_root = (project_root or discover_project_root()).resolve()
        self.repository = ImportRunRepository(session)
        self.run_service = ImportRunService(session, project_root=self.project_root)

    def create_linked_run(
        self,
        corpus_path: Path,
        *,
        parent_import_run_id: str,
        mode: RunMode,
        check_files: bool = False,
    ) -> PersistedLinkedRun:
        """Create and plan a new run linked to one immutable parent run."""

        parent = self.repository.get_run(parent_import_run_id)
        if parent is None:
            raise ValueError("Parent import run does not exist.")

        with self.session.begin_nested():
            persisted = self.run_service.create_run(corpus_path, check_files=check_files)
            current = self.repository.get_run(persisted.import_run_id)
            if current is None:
                raise RuntimeError("Linked import run was not readable after persistence.")
            if current.corpus_id != parent.corpus_id:
                raise ValueError("Linked run corpus_id does not match the parent run.")

            plan = plan_linked_run(
                mode=mode,
                parent_import_run_id=parent_import_run_id,
                current_items=current.items,
                prior_items=parent.items,
            )
            prior_by_id = {item.import_item_id: item for item in parent.items}
            decisions = {item.source_id: item for item in plan.items}

            current.run_mode = mode
            current.parent_import_run_id = parent_import_run_id
            for item in current.items:
                source_id = (item.source_id or "").strip()
                decision = decisions[source_id]
                prior = (
                    prior_by_id.get(decision.prior_import_item_id)
                    if decision.prior_import_item_id is not None
                    else None
                )
                _apply_planned_item(item, decision.action, decision.reason_code, prior)

            current.completed_at = utc_now()
            self.session.flush()

        return PersistedLinkedRun(
            import_run_id=current.import_run_id,
            run_status=current.run_status,
            plan=plan,
        )


def _apply_planned_item(
    item: ImportItem,
    action: str,
    reason_code: str,
    prior: ImportItem | None,
) -> None:
    if action == "process":
        if reason_code == "retry_prior_failure" and prior is not None:
            item.retry_of_import_item_id = prior.import_item_id
        return

    item.item_status = "skipped"
    if prior is None:
        return
    item.matched_import_item_id = prior.import_item_id
    item.matched_paper_id = prior.matched_paper_id
    if reason_code == "prior_safe_duplicate":
        item.duplicate_outcome = prior.duplicate_outcome
        item.computed_content_hash = prior.computed_content_hash
        item.duplicate_evidence_json = prior.duplicate_evidence_json
