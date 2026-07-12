"""Database access and repository operations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from knowledge_engine.config import Settings
from knowledge_engine.models import (
    Author,
    Base,
    Keyword,
    Paper,
    PaperAuthor,
    PaperKeyword,
    PaperText,
)
from knowledge_engine.parser import ParsedPaper

CURRENT_SCHEMA_VERSION = 1


class Database:
    """Owns the SQLAlchemy engine and schema lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = create_engine(settings.resolved_database_url, future=True)
        event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transactional session."""

        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def initialize(self) -> None:
        """Create application directories, relational tables, and FTS indexes."""

        self.settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        migrate_schema(self.engine)
        create_fts_tables(self.engine)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: object) -> None:
    """Enable SQLite foreign-key enforcement for every connection."""

    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def migrate_schema(engine: Engine) -> None:
    """Apply additive local SQLite schema migrations."""

    with engine.begin() as connection:
        existing_version = _current_schema_version(connection)
        if existing_version > CURRENT_SCHEMA_VERSION:
            msg = (
                f"Database schema version {existing_version} is newer than this application "
                f"supports ({CURRENT_SCHEMA_VERSION})."
            )
            raise RuntimeError(msg)
        if existing_version == CURRENT_SCHEMA_VERSION:
            _verify_schema_complete(connection)
            return

        Base.metadata.create_all(connection)
        _verify_schema_complete(connection)
        connection.execute(
            text("INSERT INTO schema_versions(version, applied_at) VALUES (:version, :applied_at)"),
            {"version": CURRENT_SCHEMA_VERSION, "applied_at": _utc_now_iso()},
        )


def _current_schema_version(connection: Connection) -> int:
    table_exists = connection.execute(
        text(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'schema_versions' LIMIT 1"
        )
    ).scalar()
    if not table_exists:
        return 0
    duplicate_versions = connection.execute(
        text("SELECT version FROM schema_versions " "GROUP BY version HAVING count(*) > 1 LIMIT 1")
    ).scalar()
    if duplicate_versions is not None:
        msg = f"Database schema version {duplicate_versions} is recorded more than once."
        raise RuntimeError(msg)
    version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar()
    return int(version or 0)


def _verify_schema_complete(connection: Connection) -> None:
    expected_tables = set(Base.metadata.tables)
    existing_tables = set(
        connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars()
    )
    missing_tables = sorted(expected_tables - existing_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        msg = f"Database schema version {CURRENT_SCHEMA_VERSION} is incomplete; missing: {missing}."
        raise RuntimeError(msg)


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def create_fts_tables(engine: Engine) -> None:
    """Create SQLite FTS5 tables used for local search."""

    with engine.begin() as connection:
        connection.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS paper_search
                USING fts5(
                    title,
                    abstract,
                    body_text,
                    raw_text,
                    tokenize='porter unicode61'
                )
                """))


class PaperRepository:
    """Persistence operations for papers and related metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_parsed_paper(self, parsed: ParsedPaper, keywords: list[str] | None = None) -> Paper:
        """Store a parsed paper and update the full-text index."""

        paper = Paper(
            title=parsed.title,
            doi=parsed.doi,
            abstract=parsed.abstract,
            source_path=str(parsed.source_path),
            content_hash=parsed.content_hash,
            page_count=parsed.page_count,
            word_count=parsed.word_count,
        )
        paper.text = PaperText(raw_text=parsed.raw_text, body_text=parsed.body_text)
        self.session.add(paper)

        with self.session.no_autoflush:
            for position, author_name in enumerate(parsed.authors):
                author = self._get_or_create_author(author_name)
                author_link = PaperAuthor(author=author, position=position)
                paper.author_links.append(author_link)
                self.session.add(author_link)

            for keyword_value in keywords or []:
                keyword = self._get_or_create_keyword(keyword_value)
                keyword_link = PaperKeyword(keyword=keyword)
                paper.keyword_links.append(keyword_link)
                self.session.add(keyword_link)

        try:
            self.session.flush()
        except IntegrityError as exc:
            msg = "Paper already exists in the database by path, DOI, or content hash."
            raise ValueError(msg) from exc

        self.upsert_search_index(paper)
        return paper

    def upsert_search_index(self, paper: Paper) -> None:
        """Insert paper text into the FTS index."""

        self.session.execute(
            text("""
                INSERT INTO paper_search(rowid, title, abstract, body_text, raw_text)
                VALUES (:rowid, :title, :abstract, :body_text, :raw_text)
                """),
            {
                "rowid": paper.id,
                "title": paper.title,
                "abstract": paper.abstract or "",
                "body_text": paper.text.body_text if paper.text else "",
                "raw_text": paper.text.raw_text if paper.text else "",
            },
        )

    def list_papers(self) -> list[Paper]:
        """Return all papers ordered by insertion."""

        statement = (
            select(Paper)
            .options(selectinload(Paper.author_links).selectinload(PaperAuthor.author))
            .order_by(Paper.id)
        )
        return list(self.session.scalars(statement))

    def get(self, paper_id: int) -> Paper | None:
        """Return one paper by primary key."""

        return self.session.get(Paper, paper_id)

    def stats(self) -> dict[str, int]:
        """Return simple collection statistics."""

        counts = {}
        for name, model in {
            "papers": Paper,
            "authors": Author,
            "keywords": Keyword,
        }.items():
            counts[name] = self.session.scalar(select(text("count(*)")).select_from(model)) or 0
        total_words = self.session.scalar(
            select(text("coalesce(sum(word_count), 0)")).select_from(Paper)
        )
        counts["words"] = int(total_words or 0)
        return counts

    def _get_or_create_author(self, name: str) -> Author:
        author = self.session.scalar(select(Author).where(Author.name == name))
        if author:
            return author
        author = Author(name=name)
        self.session.add(author)
        self.session.flush()
        return author

    def _get_or_create_keyword(self, value: str) -> Keyword:
        normalized = value.strip().lower()
        keyword = self.session.scalar(select(Keyword).where(Keyword.value == normalized))
        if keyword:
            return keyword
        keyword = Keyword(value=normalized)
        self.session.add(keyword)
        self.session.flush()
        return keyword


def database_exists(settings: Settings) -> bool:
    """Return whether the default SQLite database file exists."""

    prefix = "sqlite:///"
    if not settings.resolved_database_url.startswith(prefix):
        return True
    return Path(settings.resolved_database_url.removeprefix(prefix)).exists()
