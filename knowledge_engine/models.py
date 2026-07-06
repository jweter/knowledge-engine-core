"""Database models for scientific source documents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


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
