"""Database access and repository operations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from knowledge_engine.config import Settings
from knowledge_engine.models import (
    Author,
    Base,
    ExtractionRun,
    Keyword,
    Paper,
    PaperAuthor,
    PaperKeyword,
    PaperPage,
    PaperText,
)
from knowledge_engine.parser import ParsedPaper

CURRENT_SCHEMA_VERSION = 6

_SCHEMA_V2_COLUMNS: dict[str, dict[str, str]] = {
    "import_runs": {
        "run_mode": "VARCHAR(32) NOT NULL DEFAULT 'fresh'",
    },
    "import_items": {
        "duplicate_outcome": "VARCHAR(64)",
        "matched_paper_id": "INTEGER REFERENCES papers(id)",
        "matched_import_item_id": "VARCHAR(36) REFERENCES import_items(import_item_id)",
        "computed_content_hash": "VARCHAR(64)",
        "duplicate_evidence_json": "TEXT",
        "retry_of_import_item_id": "VARCHAR(36) REFERENCES import_items(import_item_id)",
    },
}

_SCHEMA_V3_COLUMNS: dict[str, dict[str, str]] = {
    "import_runs": {
        "review_status": "VARCHAR(32) NOT NULL DEFAULT 'clear'",
    },
}

_SCHEMA_V6_COLUMNS: dict[str, dict[str, str]] = {
    "extraction_runs": {
        "study_design_rules_version": "VARCHAR(64) NOT NULL DEFAULT 'pre-m26'",
    },
}

_TABLES_INTRODUCED_AT_VERSION: dict[int, frozenset[str]] = {
    4: frozenset({"paper_pages"}),
    5: frozenset({"extraction_runs"}),
}

_SCHEMA_V2_INDEXES: dict[str, tuple[str, str]] = {
    "ix_import_runs_parent_import_run_id": ("import_runs", "parent_import_run_id"),
    "ix_import_items_duplicate_outcome": ("import_items", "duplicate_outcome"),
    "ix_import_items_matched_paper_id": ("import_items", "matched_paper_id"),
    "ix_import_items_matched_import_item_id": ("import_items", "matched_import_item_id"),
    "ix_import_items_computed_content_hash": ("import_items", "computed_content_hash"),
    "ix_import_items_retry_of_import_item_id": ("import_items", "retry_of_import_item_id"),
}


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

        # A table introduced at a version strictly newer than existing_version cannot
        # exist yet on an upgrading database; that is expected, not corruption, so it
        # is exempted from this pre-creation check. Every other expected table must
        # already be present, or create_all below would silently recreate a table an
        # operator or bug had actually dropped, masking data loss instead of failing.
        not_yet_introduced: frozenset[str] = frozenset().union(
            *(
                tables
                for version, tables in _TABLES_INTRODUCED_AT_VERSION.items()
                if existing_version < version
            )
        )
        if existing_version > 0:
            _verify_expected_tables(connection, ignore_missing=not_yet_introduced)

        Base.metadata.create_all(connection)

        if existing_version < 2:
            _migrate_schema_v2(connection)
        if existing_version < 3:
            _migrate_schema_v3(connection)
        if existing_version < 6:
            _migrate_schema_v6(connection)

        _verify_schema_complete(connection)

        if existing_version < CURRENT_SCHEMA_VERSION:
            connection.execute(
                text(
                    "INSERT INTO schema_versions(version, applied_at) "
                    "VALUES (:version, :applied_at)"
                ),
                {"version": CURRENT_SCHEMA_VERSION, "applied_at": _utc_now_iso()},
            )


def _migrate_schema_v2(connection: Connection) -> None:
    """Add M10 duplicate evidence and run-lineage schema fields."""

    for table_name, columns in _SCHEMA_V2_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )

    for index_name, (table_name, column_name) in _SCHEMA_V2_INDEXES.items():
        connection.execute(
            text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{column_name}")')
        )


def _migrate_schema_v3(connection: Connection) -> None:
    """Separate operational execution status from human-review disposition."""

    existing_columns = _table_columns(connection, "import_runs")
    for column_name, definition in _SCHEMA_V3_COLUMNS["import_runs"].items():
        if column_name not in existing_columns:
            connection.execute(
                text(f'ALTER TABLE "import_runs" ADD COLUMN "{column_name}" {definition}')
            )
    connection.execute(
        text(
            "UPDATE import_runs SET review_status = 'needs_review', "
            "run_status = 'succeeded' WHERE run_status = 'needs_review'"
        )
    )


def _migrate_schema_v6(connection: Connection) -> None:
    """Add M26 study-design rules version to extraction run history."""

    for table_name, columns in _SCHEMA_V6_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )


def _current_schema_version(connection: Connection) -> int:
    table_exists = connection.execute(
        text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_versions' LIMIT 1"
        )
    ).scalar()
    if not table_exists:
        return 0
    duplicate_versions = connection.execute(
        text("SELECT version FROM schema_versions GROUP BY version HAVING count(*) > 1 LIMIT 1")
    ).scalar()
    if duplicate_versions is not None:
        msg = f"Database schema version {duplicate_versions} is recorded more than once."
        raise RuntimeError(msg)
    version = connection.execute(text("SELECT max(version) FROM schema_versions")).scalar()
    return int(version or 0)


def _verify_expected_tables(
    connection: Connection, *, ignore_missing: frozenset[str] = frozenset()
) -> None:
    expected_tables = set(Base.metadata.tables) - ignore_missing
    existing_tables = set(
        connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars()
    )
    missing_tables = sorted(expected_tables - existing_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        msg = f"Database schema version {CURRENT_SCHEMA_VERSION} is incomplete; missing: {missing}."
        raise RuntimeError(msg)


def _verify_schema_complete(connection: Connection) -> None:
    _verify_expected_tables(connection)

    missing_columns: list[str] = []
    for table_name, columns in _SCHEMA_V2_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                missing_columns.append(f"{table_name}.{column_name}")
    for table_name, columns in _SCHEMA_V3_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                missing_columns.append(f"{table_name}.{column_name}")
    for table_name, columns in _SCHEMA_V6_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name in columns:
            if column_name not in existing_columns:
                missing_columns.append(f"{table_name}.{column_name}")
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        msg = (
            f"Database schema version {CURRENT_SCHEMA_VERSION} is incomplete; "
            f"missing columns: {missing}."
        )
        raise RuntimeError(msg)

    existing_indexes = set(
        connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL")
        ).scalars()
    )
    missing_indexes = sorted(set(_SCHEMA_V2_INDEXES) - existing_indexes)
    if missing_indexes:
        missing = ", ".join(missing_indexes)
        msg = (
            f"Database schema version {CURRENT_SCHEMA_VERSION} is incomplete; "
            f"missing indexes: {missing}."
        )
        raise RuntimeError(msg)


def _table_columns(connection: Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
    }


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


def create_fts_tables(engine: Engine) -> None:
    """Create SQLite FTS5 tables used for local search."""

    with engine.begin() as connection:
        connection.execute(
            text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS paper_search
                USING fts5(
                    title,
                    abstract,
                    body_text,
                    raw_text,
                    tokenize='porter unicode61'
                )
                """)
        )


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
        paper.pages = [
            PaperPage(page_number=page.page_number, text=page.text) for page in parsed.pages
        ]
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

    def list_papers_without_pages(self) -> list[Paper]:
        """Return papers with zero persisted `PaperPage` rows.

        A paper that already has any page rows -- from `add_parsed_paper`
        or a prior backfill run -- is never returned, so repeated backfill
        runs are idempotent.
        """

        statement = (
            select(Paper)
            .outerjoin(PaperPage, PaperPage.paper_id == Paper.id)
            .where(PaperPage.paper_id.is_(None))
            .order_by(Paper.id)
        )
        return list(self.session.scalars(statement))

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


class ExtractionRunRepository:
    """Persistence operations for `ke extraction-review-generate` run history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        paper_id: int,
        output_path: str,
        page_count: int,
        section_count: int,
        candidate_count: int,
        draft_item_count: int,
        section_detection_rules_version: str,
        claim_candidate_rules_version: str,
        claim_framing_rules_version: str,
        draft_evidence_item_rules_version: str,
        study_design_rules_version: str,
    ) -> ExtractionRun:
        """Persist a durable record of one extraction-review-generate invocation."""

        run = ExtractionRun(
            extraction_run_id=str(uuid4()),
            paper_id=paper_id,
            output_path=output_path,
            page_count=page_count,
            section_count=section_count,
            candidate_count=candidate_count,
            draft_item_count=draft_item_count,
            section_detection_rules_version=section_detection_rules_version,
            claim_candidate_rules_version=claim_candidate_rules_version,
            claim_framing_rules_version=claim_framing_rules_version,
            draft_evidence_item_rules_version=draft_evidence_item_rules_version,
            study_design_rules_version=study_design_rules_version,
            created_at=_utc_now_iso(),
        )
        self.session.add(run)
        self.session.flush()
        return run

    def list_for_paper(self, paper_id: int) -> list[ExtractionRun]:
        """Return every extraction run recorded for one paper, oldest first."""

        statement = (
            select(ExtractionRun)
            .where(ExtractionRun.paper_id == paper_id)
            .order_by(ExtractionRun.id)
        )
        return list(self.session.scalars(statement))


def database_exists(settings: Settings) -> bool:
    """Return whether the default SQLite database file exists."""

    prefix = "sqlite:///"
    if not settings.resolved_database_url.startswith(prefix):
        return True
    return Path(settings.resolved_database_url.removeprefix(prefix)).exists()
