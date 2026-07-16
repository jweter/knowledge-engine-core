"""Deterministic database lookups for M10 duplicate and lineage evidence."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from knowledge_engine.models import ImportItem, Paper
from knowledge_engine.utils import normalize_doi


class DuplicateQueryRepository:
    """Read duplicate candidates without using integrity errors as control flow."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def paper_by_content_hash(self, content_hash: str) -> Paper | None:
        """Return the exact persisted paper for one SHA-256 digest."""

        statement = select(Paper).where(Paper.content_hash == content_hash).order_by(Paper.id)
        return self.session.scalar(statement)

    def paper_by_normalized_doi(self, doi: str | None) -> Paper | None:
        """Return the first paper whose DOI normalizes to the requested value."""

        if not doi:
            return None
        target = normalize_doi(doi)
        statement = select(Paper).where(Paper.doi.is_not(None)).order_by(Paper.id)
        return next(
            (paper for paper in self.session.scalars(statement) if normalize_doi(paper.doi or "") == target),
            None,
        )

    def papers_by_normalized_title_year(self, title: str, publication_year: int) -> list[Paper]:
        """Return deterministic advisory title/year candidates."""

        target = normalize_title(title)
        statement = (
            select(Paper)
            .where(Paper.publication_year == publication_year)
            .order_by(Paper.id)
        )
        return [paper for paper in self.session.scalars(statement) if normalize_title(paper.title) == target]

    def same_run_item_by_content_hash(
        self,
        import_run_id: str,
        content_hash: str,
        *,
        exclude_import_item_id: str | None = None,
    ) -> ImportItem | None:
        """Return the earliest same-run item already associated with a hash."""

        statement = select(ImportItem).where(
            ImportItem.import_run_id == import_run_id,
            ImportItem.computed_content_hash == content_hash,
        )
        if exclude_import_item_id is not None:
            statement = statement.where(ImportItem.import_item_id != exclude_import_item_id)
        statement = statement.order_by(ImportItem.csv_line_number, ImportItem.import_item_id)
        return self.session.scalar(statement)

    def same_run_item_by_normalized_doi(
        self,
        import_run_id: str,
        normalized_doi: str,
        *,
        exclude_import_item_id: str | None = None,
    ) -> ImportItem | None:
        """Return the earliest same-run item with a normalized DOI."""

        statement = select(ImportItem).where(
            ImportItem.import_run_id == import_run_id,
            ImportItem.normalized_doi == normalized_doi,
        )
        if exclude_import_item_id is not None:
            statement = statement.where(ImportItem.import_item_id != exclude_import_item_id)
        statement = statement.order_by(ImportItem.csv_line_number, ImportItem.import_item_id)
        return self.session.scalar(statement)

    def prior_item_by_source_id(self, import_run_id: str, source_id: str) -> ImportItem | None:
        """Return one prior-run item by stable source identity."""

        statement = (
            select(ImportItem)
            .where(
                ImportItem.import_run_id == import_run_id,
                ImportItem.source_id == source_id,
            )
            .order_by(ImportItem.csv_line_number, ImportItem.import_item_id)
        )
        return self.session.scalar(statement)


def normalize_title(title: str) -> str:
    """Normalize Unicode, case, and whitespace for conservative title comparison."""

    normalized = unicodedata.normalize("NFKC", title).casefold().strip()
    return re.sub(r"\s+", " ", normalized)
