"""Database models for scientific source documents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class SchemaVersion(Base):
    """Applied local database schema version."""

    __tablename__ = "schema_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    applied_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ManifestSnapshot(Base):
    """Exact corpus manifest inputs captured for an import run."""

    __tablename__ = "manifest_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    corpus_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_json_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_csv_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    corpus_json_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_csv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_csv_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    combined_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[str] = mapped_column(String(32), nullable=False)

    import_runs: Mapped[list[ImportRun]] = relationship(back_populates="manifest_snapshot")


class ImportRun(Base):
    """Durable record of one corpus validation/import-run attempt."""

    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    corpus_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    corpus_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    manifest_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="fresh")
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    manifest_validity: Mapped[str] = mapped_column(String(32), nullable=False)
    import_readiness: Mapped[str] = mapped_column(String(32), nullable=False)
    total_source_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_source_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structural_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(32), nullable=False)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_policy_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_path: Mapped[str] = mapped_column(Text, nullable=False)
    parent_import_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    manifest_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("manifest_snapshots.snapshot_id"), nullable=False, index=True
    )

    manifest_snapshot: Mapped[ManifestSnapshot] = relationship(back_populates="import_runs")
    items: Mapped[list[ImportItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ImportItem.csv_line_number"
    )
    issues: Mapped[list[ImportIssue]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ImportIssue.sequence"
    )

    __table_args__ = (
        CheckConstraint("total_source_rows >= 0", name="ck_import_runs_total_source_rows"),
        CheckConstraint("valid_source_rows >= 0", name="ck_import_runs_valid_source_rows"),
        CheckConstraint("warning_count >= 0", name="ck_import_runs_warning_count"),
        CheckConstraint(
            "structural_error_count >= 0", name="ck_import_runs_structural_error_count"
        ),
        CheckConstraint("import_blocker_count >= 0", name="ck_import_runs_import_blocker_count"),
    )


class ImportItem(Base):
    """Run-specific validation state for one source-manifest row."""

    __tablename__ = "import_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_item_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    import_run_id: Mapped[str] = mapped_column(
        ForeignKey("import_runs.import_run_id"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    csv_line_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_doi: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    inclusion_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    duplicate_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    matched_paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id"), nullable=True, index=True
    )
    matched_import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    computed_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    blocks_manifest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocks_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structural_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(32), nullable=False)

    run: Mapped[ImportRun] = relationship(back_populates="items")
    issues: Mapped[list[ImportIssue]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ImportIssue.sequence"
    )

    __table_args__ = (
        CheckConstraint("warning_count >= 0", name="ck_import_items_warning_count"),
        CheckConstraint(
            "structural_error_count >= 0", name="ck_import_items_structural_error_count"
        ),
        CheckConstraint("import_blocker_count >= 0", name="ck_import_items_import_blocker_count"),
        UniqueConstraint("import_run_id", "csv_line_number", name="uq_item_run_line"),
    )


class ImportIssue(Base):
    """Persisted validation issue for an import run or item."""

    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    import_run_id: Mapped[str] = mapped_column(
        ForeignKey("import_runs.import_run_id"), nullable=False, index=True
    )
    import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    csv_line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blocks_manifest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocks_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    run: Mapped[ImportRun] = relationship(back_populates="issues")
    item: Mapped[ImportItem | None] = relationship(back_populates="issues")

    __table_args__ = (UniqueConstraint("import_run_id", "sequence", name="uq_issue_run_sequence"),)


class PaperAuthor(Base):
    """Join table preserving author order for a paper."""

    __tablename__ = "paper_authors"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    paper: Mapped[Paper] = relationship(back_populates="author_links")
    author: Mapped[Author] = relationship(back_populates="paper_links")


class PaperKeyword(Base):
    """Join table for paper keywords."""

    __tablename__ = "paper_keywords"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), primary_key=True)

    paper: Mapped[Paper] = relationship(back_populates="keyword_links")
    keyword: Mapped[Keyword] = relationship(back_populates="paper_links")


class Journal(Base):
    """A publication venue."""

    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    issn: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    papers: Mapped[list[Paper]] = relationship(back_populates="journal")


class Author(Base):
    """A paper author."""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper_links: Mapped[list[PaperAuthor]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class Keyword(Base):
    """A normalized keyword or topic label."""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper_links: Mapped[list[PaperKeyword]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )


class Paper(Base):
    """Metadata for a scientific paper or source document."""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True, index=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    journal_id: Mapped[int | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    journal: Mapped[Journal | None] = relationship(back_populates="papers")
    text: Mapped[PaperText | None] = relationship(
        back_populates="paper", cascade="all, delete-orphan", uselist=False
    )
    author_links: Mapped[list[PaperAuthor]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperAuthor.position"
    )
    keyword_links: Mapped[list[PaperKeyword]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_papers_embedding", "embedding_model", "embedding_id"),
        UniqueConstraint("content_hash", name="uq_papers_content_hash"),
    )


class PaperText(Base):
    """Extracted text for a paper."""

    __tablename__ = "paper_texts"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(128), nullable=False, default="pymupdf")
    extraction_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[Paper] = relationship(back_populates="text")
