"""Repository operations for persisted import runs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from knowledge_engine.models import ImportIssue, ImportItem, ImportRun, ManifestSnapshot


class ImportRunRepository:
    """Persist and read import-run records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_snapshot(self, snapshot: ManifestSnapshot) -> None:
        """Add a manifest snapshot."""

        self.session.add(snapshot)

    def add_run(self, run: ImportRun) -> None:
        """Add an import run."""

        self.session.add(run)

    def add_items(self, items: list[ImportItem]) -> None:
        """Add import items."""

        self.session.add_all(items)

    def add_issues(self, issues: list[ImportIssue]) -> None:
        """Add validation issues."""

        self.session.add_all(issues)

    def get_run(self, import_run_id: str) -> ImportRun | None:
        """Return one import run with snapshot, items, and issues."""

        statement = (
            select(ImportRun)
            .where(ImportRun.import_run_id == import_run_id)
            .options(
                selectinload(ImportRun.manifest_snapshot),
                selectinload(ImportRun.items).selectinload(ImportItem.issues),
                selectinload(ImportRun.issues),
            )
        )
        return self.session.scalar(statement)

    def list_runs(self) -> list[ImportRun]:
        """Return import runs in creation order."""

        statement = select(ImportRun).order_by(ImportRun.created_at, ImportRun.import_run_id)
        return list(self.session.scalars(statement))
