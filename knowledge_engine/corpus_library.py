"""Portable corpus-library snapshot export/import.

The working SQLite database (`data/*.sqlite3`) is deliberately gitignored --
it is large, environment-specific, and regenerable from `corpus-import`. But
the *content* it holds once a corpus has been imported and parsed --
`papers`, their extracted `paper_pages`/`paper_texts`, and the
`journals`/`authors`/`keywords` they reference -- is exactly what Phase 2
extraction tuning needs, and re-deriving it means re-running discovery,
adjudication, and acquisition from scratch every session. This module copies
only that paper-intrinsic content into a single, standalone, git-committable
snapshot file, and hydrates a fresh local database from one.

Deliberately excluded: `import_runs`/`import_items`/`import_issues`,
`extraction_runs`, and `manifest_snapshots` describe *this* database's own
operational history (when a command ran, against which ruleset), not the
corpus itself -- re-running the relevant `ke` command regenerates them
locally, and a snapshot from one machine's history has no meaning on
another's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import ColumnElement, Engine, create_engine, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from knowledge_engine.database import PaperRepository
from knowledge_engine.models import (
    Author,
    Base,
    Journal,
    Keyword,
    Paper,
    PaperAuthor,
    PaperKeyword,
    PaperPage,
    PaperText,
)

CORPUS_LIBRARY_TABLES = (
    "journals",
    "authors",
    "keywords",
    "papers",
    "paper_authors",
    "paper_keywords",
    "paper_texts",
    "paper_pages",
)

_PAPER_LOAD_OPTIONS = (
    selectinload(Paper.journal),
    selectinload(Paper.text),
    selectinload(Paper.pages),
    selectinload(Paper.author_links).selectinload(PaperAuthor.author),
    selectinload(Paper.keyword_links).selectinload(PaperKeyword.keyword),
)


@dataclass(frozen=True)
class ExportSummary:
    """Counts of rows written to a new corpus-library snapshot."""

    paper_count: int
    journal_count: int
    author_count: int
    keyword_count: int


@dataclass(frozen=True)
class ImportSummary:
    """Counts of rows hydrated from a corpus-library snapshot."""

    imported_paper_count: int
    skipped_existing_paper_count: int


def export_corpus_library(source_engine: Engine, output_path: Path) -> ExportSummary:
    """Copy corpus-content tables into a fresh, standalone snapshot file.

    `output_path` must not already exist -- callers needing to overwrite an
    existing snapshot delete it first, mirroring the `--force` pattern used
    for other `ke` output files rather than silently clobbering one here.
    """

    if output_path.exists():
        msg = f"Corpus library output already exists: {output_path}"
        raise FileExistsError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_engine = create_engine(f"sqlite:///{output_path}", future=True)
    tables = [Base.metadata.tables[name] for name in CORPUS_LIBRARY_TABLES]
    Base.metadata.create_all(target_engine, tables=tables)

    source_session_factory = sessionmaker(source_engine, future=True)
    target_session_factory = sessionmaker(target_engine, future=True)

    journal_cache: dict[int, Journal] = {}
    author_cache: dict[int, Author] = {}
    keyword_cache: dict[int, Keyword] = {}

    with source_session_factory() as source_session, target_session_factory() as target_session:
        papers = source_session.scalars(
            select(Paper).options(*_PAPER_LOAD_OPTIONS).order_by(Paper.id)
        ).all()

        for paper in papers:
            new_journal = None
            if paper.journal is not None:
                new_journal = journal_cache.get(paper.journal.id)
                if new_journal is None:
                    new_journal = Journal(name=paper.journal.name, issn=paper.journal.issn)
                    journal_cache[paper.journal.id] = new_journal

            new_paper = _copy_paper_fields(paper, journal=new_journal)

            for author_link in paper.author_links:
                new_author = author_cache.get(author_link.author.id)
                if new_author is None:
                    new_author = Author(
                        name=author_link.author.name, orcid=author_link.author.orcid
                    )
                    author_cache[author_link.author.id] = new_author
                new_paper.author_links.append(
                    PaperAuthor(author=new_author, position=author_link.position)
                )
            for keyword_link in paper.keyword_links:
                new_keyword = keyword_cache.get(keyword_link.keyword.id)
                if new_keyword is None:
                    new_keyword = Keyword(value=keyword_link.keyword.value)
                    keyword_cache[keyword_link.keyword.id] = new_keyword
                new_paper.keyword_links.append(PaperKeyword(keyword=new_keyword))

            target_session.add(new_paper)

        target_session.commit()

        return ExportSummary(
            paper_count=len(papers),
            journal_count=len(journal_cache),
            author_count=len(author_cache),
            keyword_count=len(keyword_cache),
        )


def import_corpus_library(target_session: Session, input_path: Path) -> ImportSummary:
    """Hydrate a local working database from a corpus-library snapshot.

    A paper whose `content_hash` already exists locally is skipped entirely,
    so importing the same or an overlapping snapshot twice is idempotent --
    mirroring `PaperRepository.add_parsed_paper`'s own content-hash identity.
    Journals/authors/keywords are matched by their existing natural unique
    key (name/value) or inserted; a snapshot's own primary keys are never
    reused, since they are not portable across databases. Each newly
    imported paper is also indexed into `paper_search`
    (`PaperRepository.upsert_search_index`), so `ke search`/`ke answer`
    can find it immediately -- without this, an imported paper would sit in
    the relational tables but never surface through either command.
    """

    if not input_path.exists():
        msg = f"Corpus library input does not exist: {input_path}"
        raise FileNotFoundError(msg)

    source_engine = create_engine(f"sqlite:///{input_path}", future=True)
    source_session_factory = sessionmaker(source_engine, future=True)

    imported = 0
    skipped = 0

    with source_session_factory() as source_session:
        papers = source_session.scalars(
            select(Paper).options(*_PAPER_LOAD_OPTIONS).order_by(Paper.id)
        ).all()

        for paper in papers:
            existing = target_session.scalar(
                select(Paper).where(Paper.content_hash == paper.content_hash)
            )
            if existing is not None:
                skipped += 1
                continue

            new_journal = None
            if paper.journal is not None:
                source_journal = paper.journal
                new_journal = _get_or_create(
                    target_session,
                    Journal,
                    Journal.name == source_journal.name,
                    Journal(name=source_journal.name, issn=source_journal.issn),
                )

            new_paper = _copy_paper_fields(paper, journal=new_journal)
            target_session.add(new_paper)

            for author_link in paper.author_links:
                source_author = author_link.author
                new_author = _get_or_create(
                    target_session,
                    Author,
                    Author.name == source_author.name,
                    Author(name=source_author.name, orcid=source_author.orcid),
                )
                new_paper.author_links.append(
                    PaperAuthor(author=new_author, position=author_link.position)
                )
            for keyword_link in paper.keyword_links:
                source_keyword = keyword_link.keyword
                new_keyword = _get_or_create(
                    target_session,
                    Keyword,
                    Keyword.value == source_keyword.value,
                    Keyword(value=source_keyword.value),
                )
                new_paper.keyword_links.append(PaperKeyword(keyword=new_keyword))

            target_session.flush()
            PaperRepository(target_session).upsert_search_index(new_paper)
            imported += 1

    return ImportSummary(imported_paper_count=imported, skipped_existing_paper_count=skipped)


def _copy_paper_fields(paper: Paper, *, journal: Journal | None) -> Paper:
    """Build a detached `Paper` copy, ready to `add()` into a new session.

    Deliberately excludes `embedding_model`/`embedding_id`: M30's mechanism
    sets `embedding_id` to the source database's own `Paper.id`, which the
    target database's fresh auto-incremented primary key will not match
    once this row is inserted -- copying it verbatim would let an imported
    paper silently claim another (unrelated) paper's embedding identity in
    the target database, or a stale one nothing indexes. Neither the FAISS
    index file nor any embedding-generation state is part of this
    snapshot's paper-intrinsic content (see the module docstring); an
    operator must re-run `ke embedding-index-build` for imported papers.
    """

    new_paper = Paper(
        title=paper.title,
        doi=paper.doi,
        abstract=paper.abstract,
        source_path=paper.source_path,
        content_hash=paper.content_hash,
        publication_year=paper.publication_year,
        journal=journal,
        page_count=paper.page_count,
        word_count=paper.word_count,
    )
    if paper.text is not None:
        new_paper.text = PaperText(
            raw_text=paper.text.raw_text,
            body_text=paper.text.body_text,
            extraction_method=paper.text.extraction_method,
            extraction_version=paper.text.extraction_version,
            language=paper.text.language,
        )
    new_paper.pages = [
        PaperPage(page_number=page.page_number, text=page.text) for page in paper.pages
    ]
    return new_paper


def _get_or_create[ModelT](
    session: Session,
    model: type[ModelT],
    clause: ColumnElement[bool],
    candidate: ModelT,
) -> ModelT:
    existing = session.scalar(select(model).where(clause))
    if existing is not None:
        return existing
    session.add(candidate)
    session.flush()
    return candidate
