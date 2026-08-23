"""Database access and repository operations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from itertools import combinations
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, create_engine, event, func, select, text, update
from sqlalchemy.engine import Connection, CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from knowledge_engine.config import Settings
from knowledge_engine.models import (
    Author,
    Base,
    ExtractionRun,
    GraphCitation,
    GraphClaim,
    GraphClaimConcept,
    GraphClaimRelationship,
    GraphConcept,
    Keyword,
    Paper,
    PaperAuthor,
    PaperKeyword,
    PaperPage,
    PaperText,
)
from knowledge_engine.parser import ParsedPaper

CURRENT_SCHEMA_VERSION = 13

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

_SCHEMA_V7_COLUMNS: dict[str, dict[str, str]] = {
    "extraction_runs": {
        "pico_extraction_rules_version": "VARCHAR(64) NOT NULL DEFAULT 'pre-m28'",
    },
}

_SCHEMA_V11_COLUMNS: dict[str, dict[str, str]] = {
    "paper_pages": {
        "table_text": "TEXT",
    },
}

_SCHEMA_V12_COLUMNS: dict[str, dict[str, str]] = {
    "graph_claims": {
        "corpus_id": "VARCHAR(128)",
    },
}

_SCHEMA_V13_COLUMNS: dict[str, dict[str, str]] = {
    "papers": {
        "pmid": "VARCHAR(32)",
        "arxiv_id": "VARCHAR(64)",
    },
}

_SCHEMA_V13_INDEXES: dict[str, tuple[str, str]] = {
    "ix_papers_pmid": ("papers", "pmid"),
    "ix_papers_arxiv_id": ("papers", "arxiv_id"),
}

_TABLES_INTRODUCED_AT_VERSION: dict[int, frozenset[str]] = {
    4: frozenset({"paper_pages"}),
    5: frozenset({"extraction_runs"}),
    8: frozenset(
        {
            "graph_concepts",
            "graph_claims",
            "graph_claim_concepts",
            "graph_claim_relationships",
        }
    ),
    9: frozenset({"graph_citations"}),
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
        event.listen(self.engine, "connect", _disable_pysqlite_transaction_management)
        event.listen(self.engine, "begin", _begin_sqlite_transaction)
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


def _disable_pysqlite_transaction_management(
    dbapi_connection: Any, connection_record: object
) -> None:
    """Hand transaction control to SQLAlchemy instead of pysqlite's own heuristics.

    pysqlite (the stdlib `sqlite3` driver) implicitly commits before certain
    statements and tracks its own notion of "in a transaction" separately
    from SQLAlchemy's. Left in that default mode, a `Session.begin_nested()`
    SAVEPOINT that completes normally can end up not actually undone by a
    later, unrelated `Session.rollback()` on the same session -- found via
    M40's `ke extraction-review-batch-generate` (a per-paper SAVEPOINT
    released successfully, followed by an unrelated write failure, left the
    released SAVEPOINT's row committed instead of rolled back). This is
    SQLAlchemy's own documented workaround for pysqlite's SAVEPOINT support:
    disable pysqlite's isolation-level heuristics entirely and let
    `_begin_sqlite_transaction` below issue explicit `BEGIN` statements.
    """

    del connection_record
    dbapi_connection.isolation_level = None


def _begin_sqlite_transaction(conn: Connection) -> None:
    """Issue an explicit `BEGIN`, replacing pysqlite's own (now-disabled) heuristics."""

    conn.exec_driver_sql("BEGIN")


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
        if existing_version < 7:
            _migrate_schema_v7(connection)
        if existing_version < 10:
            _migrate_schema_v10(connection)
        if existing_version < 11:
            _migrate_schema_v11(connection)
        if existing_version < 12:
            _migrate_schema_v12(connection)
        if existing_version < 13:
            _migrate_schema_v13(connection)

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
    """Separate operational execution status from review disposition (AI/automated, not human)."""

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


def _migrate_schema_v7(connection: Connection) -> None:
    """Add M28 PICO extraction rules version to extraction run history."""

    for table_name, columns in _SCHEMA_V7_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )


def _migrate_schema_v10(connection: Connection) -> None:
    """Widen `graph_claim_relationships.relationship_type` to add M50's `supersedes` type.

    SQLite `CHECK` constraints cannot be altered in place, unlike the
    additive `ALTER TABLE ... ADD COLUMN` migrations above. This rebuilds
    the table instead: rename the existing table aside, drop the indexes
    still attached to it (SQLite does not rename or drop a table's
    indexes when the table itself is renamed, so they would otherwise
    collide with the freshly created table's identically-named indexes),
    create a fresh table from the current model (already carrying the
    widened constraint), copy every row across unchanged, then drop the
    old table. A no-op both on a fresh database (where
    `Base.metadata.create_all` above already created the table with the
    widened constraint from the start) and on a database already rebuilt
    by an earlier run of this migration -- checked by inspecting the
    table's own stored `CREATE TABLE` text for `'supersedes'`, since this
    migration runs on every `initialize()` call while `existing_version <
    10` (matching every additive migration above), not just once.
    """

    existing_sql = connection.execute(
        text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='graph_claim_relationships'"
        )
    ).scalar()
    if existing_sql is None or "supersedes" in existing_sql:
        return

    old_table_name = "graph_claim_relationships_pre_v10"
    connection.execute(
        text(f'ALTER TABLE "graph_claim_relationships" RENAME TO "{old_table_name}"')
    )

    old_indexes = list(
        connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=:table_name "
                "AND name NOT LIKE 'sqlite_autoindex_%'"
            ),
            {"table_name": old_table_name},
        ).scalars()
    )
    for index_name in old_indexes:
        connection.execute(text(f'DROP INDEX "{index_name}"'))

    Base.metadata.tables["graph_claim_relationships"].create(connection)

    connection.execute(
        text(
            "INSERT INTO graph_claim_relationships "
            "(id, relationship_id, source_claim_id, target_claim_id, relationship_type, "
            "rationale, created_at) "
            "SELECT id, relationship_id, source_claim_id, target_claim_id, relationship_type, "
            f'rationale, created_at FROM "{old_table_name}"'
        )
    )
    connection.execute(text(f'DROP TABLE "{old_table_name}"'))


def _migrate_schema_v11(connection: Connection) -> None:
    """Add `paper_pages.table_text` for table-derived-sentence filtering.

    Additive and nullable, same shape as the v6/v7 migrations above -- a
    paper's existing pages simply have `table_text = NULL` until a separate
    backfill re-parses their original local PDF (mirroring the M22
    `paper_pages` backfill's own "re-parse, verify content hash, then
    persist" pattern), which is the only way to compute this signal for
    already-persisted pages since it depends on layout geometry `text`
    alone does not retain.
    """

    for table_name, columns in _SCHEMA_V11_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )


def _migrate_schema_v12(connection: Connection) -> None:
    """Add `graph_claims.corpus_id` so relationship candidates can be scoped to one corpus.

    Additive and nullable, same shape as the v6/v7/v11 migrations above.
    An existing claim's `corpus_id` stays `NULL` until a caller re-runs
    `ke graph-build --corpus <id> --evidence <that corpus's file>`, which
    backfills it via `GraphRepository.backfill_claim_corpus_id` -- there
    is no way to derive a claim's corpus purely from its
    `evidence_record_id` (many are `auto-<hash>` automated-extraction IDs
    with no corpus hint in the string itself), so this migration does not
    attempt to guess one.
    """

    for table_name, columns in _SCHEMA_V12_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )


def _migrate_schema_v13(connection: Connection) -> None:
    """Add `papers.pmid`/`papers.arxiv_id` so reuse detection can key on them.

    Additive and nullable, same shape as the v6/v7/v11/v12 migrations above.
    Until a caller backfills these for already-persisted papers, existing
    rows simply have `pmid`/`arxiv_id = NULL` -- exactly like `paper_pages
    .table_text` after v11, this does not attempt to derive a value that
    was never captured at import time. Populating these for newly imported
    papers, and backfilling existing ones, is separate follow-up work (see
    CORE-GQR-2 in docs/general_question_research_loop_v1.md); this
    migration only adds the queryable columns and their unique indexes so
    `DuplicateQueryRepository.paper_by_pmid`/`paper_by_arxiv_id` and
    `general_question_acquisition._find_existing_paper` have something to
    query against once that data exists. The unique indexes are created
    with `IF NOT EXISTS` because a fresh database's `Base.metadata
    .create_all` call earlier in `migrate_schema` already created them from
    the current model -- this is a no-op there, and only does real work
    when upgrading a database that predates this migration.
    """

    for table_name, columns in _SCHEMA_V13_COLUMNS.items():
        existing_columns = _table_columns(connection, table_name)
        for column_name, definition in columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
            )

    for index_name, (table_name, column_name) in _SCHEMA_V13_INDEXES.items():
        connection.execute(
            text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{table_name}" ("{column_name}")'
            )
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
    for table_name, columns in _SCHEMA_V7_COLUMNS.items():
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

    def _build_paper(
        self,
        parsed: ParsedPaper,
        keywords: list[str] | None = None,
        *,
        manifest_title: str | None = None,
        manifest_doi: str | None = None,
    ) -> Paper:
        """Construct and stage an unflushed `Paper` with text, pages, authors, and keywords.

        Shared by every `add_parsed_paper` override so a field added here (for
        example `PaperPage` persistence, added in M15) cannot silently apply
        to only one persistence path.

        `manifest_title`/`manifest_doi`, when supplied, win over `parsed.title`/
        `parsed.doi`: PDF-layout extraction is a heuristic (`PyMuPDFParser` picks
        the largest text on the first page for title; DOI extraction can grab a
        truncated in-text citation instead of the paper's own DOI) that some
        publisher layouts defeat -- Cureus's "Review began MM/DD/YYYY" peer-review
        banner, Frontiers' "TYPE Review" article-type header, a DOI cut short at
        "10.1172/jci" instead of the full "10.1172/jci.insight.198707" -- while a
        manifest row's title/DOI come from PubMed/PMC bibliographic metadata and
        are authoritative when present. A wrong parsed DOI is not just a display
        bug: `resolve_duplicate_before_persistence` also prefers `parsed.doi`,
        so a truncated one can falsely collide with an unrelated paper and send a
        genuinely new paper to `needs_review` instead of importing it -- found
        via a live Codex review flagging exactly this on three records.
        """

        paper = Paper(
            title=manifest_title or parsed.title,
            doi=manifest_doi or parsed.doi,
            abstract=parsed.abstract,
            source_path=str(parsed.source_path),
            content_hash=parsed.content_hash,
            page_count=parsed.page_count,
            word_count=parsed.word_count,
        )
        paper.text = PaperText(raw_text=parsed.raw_text, body_text=parsed.body_text)
        paper.pages = [
            PaperPage(page_number=page.page_number, text=page.text, table_text=page.table_text)
            for page in parsed.pages
        ]
        self.session.add(paper)

        with self.session.no_autoflush:
            linked_author_ids: set[int] = set()
            for position, author_name in enumerate(parsed.authors):
                author = self._get_or_create_author(author_name)
                if author.id in linked_author_ids:
                    # Two distinct entries in the parsed author list resolved to
                    # the same Author row (e.g. a byline artifact the parser's
                    # own name-splitting heuristic didn't fully filter). Linking
                    # it twice would violate paper_authors' (paper_id, author_id)
                    # uniqueness and abort the whole import; keep the first
                    # (earliest-listed) position rather than guess which is real.
                    continue
                linked_author_ids.add(author.id)
                author_link = PaperAuthor(author=author, position=position)
                paper.author_links.append(author_link)
                self.session.add(author_link)

            for keyword_value in keywords or []:
                keyword = self._get_or_create_keyword(keyword_value)
                keyword_link = PaperKeyword(keyword=keyword)
                paper.keyword_links.append(keyword_link)
                self.session.add(keyword_link)

        return paper

    def add_parsed_paper(
        self,
        parsed: ParsedPaper,
        keywords: list[str] | None = None,
        *,
        manifest_title: str | None = None,
        manifest_doi: str | None = None,
    ) -> Paper:
        """Store a parsed paper and update the full-text index."""

        paper = self._build_paper(
            parsed, keywords, manifest_title=manifest_title, manifest_doi=manifest_doi
        )

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

    def set_embedding(self, paper_id: int, *, embedding_model: str, embedding_id: str) -> None:
        """Record a paper's embedding identity.

        `embedding_model` and `embedding_id` are supplied by the caller
        (M30's `embedding-index-build` command) rather than invented here --
        this method only persists what it is given, mirroring how every
        other `*_RULES_VERSION`-style provenance field in this project is
        recorded, never guessed.
        """

        paper = self.session.get(Paper, paper_id)
        if paper is None:
            raise ValueError(f"Unknown paper ID: {paper_id}")
        paper.embedding_model = embedding_model
        paper.embedding_id = embedding_id

    def get_many(self, paper_ids: Sequence[int]) -> list[Paper]:
        """Return the papers matching `paper_ids`, in database order.

        A missing ID is simply absent from the result -- the caller is
        responsible for checking which requested IDs were not found.
        """

        if not paper_ids:
            return []
        statement = select(Paper).where(Paper.id.in_(paper_ids)).order_by(Paper.id)
        return list(self.session.scalars(statement))

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
        pico_extraction_rules_version: str,
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
            pico_extraction_rules_version=pico_extraction_rules_version,
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


class GraphRepository:
    """Persistence operations for the Phase 4 knowledge graph.

    See `docs/phase4_design.md`. `graph_citations` is deliberately absent --
    citation-list extraction is unscoped and deferred, so no methods for it
    exist here yet.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_concept(
        self,
        *,
        label: str,
        source: str,
        source_reference_id: str | None,
        definition: str | None,
        source_url: str | None,
        license: str | None,
        retrieved_at: str,
    ) -> GraphConcept:
        """Return an existing concept by identity, or create one.

        Only concepts with a real `source_reference_id` (a resolved
        reference-layer lookup) are deduplicated. Bare `source='pico'`
        concepts have no lookup identity and are always inserted fresh --
        see the design doc's "Concept-node duplication across sources" risk.
        """

        if source_reference_id is not None:
            existing = self.session.scalar(
                select(GraphConcept).where(
                    GraphConcept.source == source,
                    GraphConcept.source_reference_id == source_reference_id,
                )
            )
            if existing:
                return existing

        concept = GraphConcept(
            label=label,
            source=source,
            source_reference_id=source_reference_id,
            definition=definition,
            source_url=source_url,
            license=license,
            retrieved_at=retrieved_at,
        )
        self.session.add(concept)
        self.session.flush()
        return concept

    def get_concept(self, concept_id: int) -> GraphConcept | None:
        """Return one concept by primary key."""

        return self.session.get(GraphConcept, concept_id)

    def get_or_create_claim(
        self, evidence_record_id: str, *, corpus_id: str | None = None
    ) -> GraphClaim:
        """Return an existing claim node by `EvidenceRecord` ID, or create one.

        `corpus_id` is only applied on creation -- an already-existing
        claim's `corpus_id` is never overwritten here (use
        `backfill_claim_corpus_id` to fill in a `NULL` value on an
        already-existing claim, which never overwrites a real value
        either).
        """

        existing = self.session.scalar(
            select(GraphClaim).where(GraphClaim.evidence_record_id == evidence_record_id)
        )
        if existing:
            return existing

        claim = GraphClaim(
            evidence_record_id=evidence_record_id,
            created_at=_utc_now_iso(),
            corpus_id=corpus_id,
        )
        self.session.add(claim)
        self.session.flush()
        return claim

    def backfill_claim_corpus_id(self, evidence_record_ids: Sequence[str], corpus_id: str) -> int:
        """Set `corpus_id` on already-existing claims that don't have one yet.

        Only touches rows where `corpus_id IS NULL` -- never overwrites a
        value a prior call (possibly for a different corpus) already set,
        since that would silently relabel a claim without a human
        deciding to. Returns the number of rows actually updated. This is
        the only way an already-existing claim (created before `--corpus`
        existed, or by a `ke graph-build` run that omitted it) gets a
        `corpus_id` -- M54's incremental skip-logic means
        `get_or_create_claim` is never called again for a claim that
        already exists, so its `corpus_id` cannot be set there.
        """

        if not evidence_record_ids:
            return 0

        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(GraphClaim)
                .where(
                    GraphClaim.evidence_record_id.in_(evidence_record_ids),
                    GraphClaim.corpus_id.is_(None),
                )
                .values(corpus_id=corpus_id)
            ),
        )
        return int(result.rowcount or 0)

    def get_claim(self, claim_id: int) -> GraphClaim | None:
        """Return one claim by primary key."""

        return self.session.get(GraphClaim, claim_id)

    def find_claim_by_evidence_id(self, evidence_record_id: str) -> GraphClaim | None:
        """Return one claim by its `EvidenceRecord` ID, read-only.

        Unlike `get_or_create_claim`, never creates a row -- for read-facing
        callers like `ke graph-report`, where an unrecognized ID must be
        reported as "not found," not silently promoted into a new claim.
        """

        return self.session.scalar(
            select(GraphClaim).where(GraphClaim.evidence_record_id == evidence_record_id)
        )

    def find_claim_ids_by_evidence_ids(self, evidence_record_ids: Sequence[str]) -> dict[str, int]:
        """Return `{evidence_record_id: claim_id}` for every ID that already has a claim.

        Read-only bulk variant of `find_claim_by_evidence_id` -- one query
        instead of N, for a caller deciding what work to skip for
        already-persisted claims *before* doing anything expensive (e.g.
        `ke graph-build`'s per-record RxNorm/MeSH network lookups). A claim
        row is only ever created inside a fully-committed `graph-build`
        transaction, so its existence here is a reliable signal that its
        concept links were already resolved too -- see M54's design note
        in `ke graph-build`'s own docstring.
        """

        ids = [
            evidence_record_id for evidence_record_id in evidence_record_ids if evidence_record_id
        ]
        if not ids:
            return {}
        rows = self.session.execute(
            select(GraphClaim.evidence_record_id, GraphClaim.id).where(
                GraphClaim.evidence_record_id.in_(ids)
            )
        ).all()
        return {evidence_record_id: claim_id for evidence_record_id, claim_id in rows}

    def link_claim_concept(
        self, claim_id: int, concept_id: int, edge_role: str
    ) -> GraphClaimConcept:
        """Return an existing claim-concept edge, or create one.

        Idempotent on `(claim_id, concept_id, edge_role)`.
        """

        existing = self.session.scalar(
            select(GraphClaimConcept).where(
                GraphClaimConcept.claim_id == claim_id,
                GraphClaimConcept.concept_id == concept_id,
                GraphClaimConcept.edge_role == edge_role,
            )
        )
        if existing:
            return existing

        edge = GraphClaimConcept(
            claim_id=claim_id,
            concept_id=concept_id,
            edge_role=edge_role,
            created_at=_utc_now_iso(),
        )
        self.session.add(edge)
        self.session.flush()
        return edge

    def get_or_create_relationship_edge(
        self,
        relationship_id: str,
        *,
        source_claim_id: int,
        target_claim_id: int,
        relationship_type: str,
        rationale: str,
    ) -> GraphClaimRelationship:
        """Return an existing relationship edge by `RelationshipRecord` ID, or create one."""

        existing = self.session.scalar(
            select(GraphClaimRelationship).where(
                GraphClaimRelationship.relationship_id == relationship_id
            )
        )
        if existing:
            return existing

        edge = GraphClaimRelationship(
            relationship_id=relationship_id,
            source_claim_id=source_claim_id,
            target_claim_id=target_claim_id,
            relationship_type=relationship_type,
            rationale=rationale,
            created_at=_utc_now_iso(),
        )
        self.session.add(edge)
        self.session.flush()
        return edge

    def concept_edges_for_claim(self, claim_id: int) -> list[tuple[str, GraphConcept]]:
        """Return every (edge_role, concept) pair linked to one claim.

        Unlike `concepts_for_claim`, preserves which PICO role produced each
        edge -- e.g. for `ke graph-report`, which groups a claim's concepts
        by role rather than listing them as one undifferentiated set.
        """

        statement = (
            select(GraphClaimConcept.edge_role, GraphConcept)
            .join(GraphConcept, GraphClaimConcept.concept_id == GraphConcept.id)
            .where(GraphClaimConcept.claim_id == claim_id)
            .order_by(GraphClaimConcept.edge_role, GraphConcept.id)
        )
        return [(edge_role, concept) for edge_role, concept in self.session.execute(statement)]

    def concepts_for_claim(self, claim_id: int) -> list[GraphConcept]:
        """Return every concept linked to one claim, via any edge role.

        A claim may link to the same concept under more than one edge role
        (the `graph_claim_concepts` unique constraint is per
        `(claim_id, concept_id, edge_role)`, not per `(claim_id,
        concept_id)`) -- `distinct()` collapses that to one node per claim,
        matching the traversal's own "every concept" contract rather than
        "every edge."
        """

        statement = (
            select(GraphConcept)
            .join(GraphClaimConcept, GraphClaimConcept.concept_id == GraphConcept.id)
            .where(GraphClaimConcept.claim_id == claim_id)
            .order_by(GraphConcept.id)
            .distinct()
        )
        return list(self.session.scalars(statement))

    def claims_for_concept(self, concept_id: int) -> list[GraphClaim]:
        """Return every claim linked to one concept, via any edge role.

        See `concepts_for_claim` -- the same multi-role duplication is
        possible in this direction too.
        """

        statement = (
            select(GraphClaim)
            .join(GraphClaimConcept, GraphClaimConcept.claim_id == GraphClaim.id)
            .where(GraphClaimConcept.concept_id == concept_id)
            .order_by(GraphClaim.id)
            .distinct()
        )
        return list(self.session.scalars(statement))

    def relationships_for_claim(self, claim_id: int) -> list[GraphClaimRelationship]:
        """Return every relationship edge touching one claim, as source or target."""

        statement = (
            select(GraphClaimRelationship)
            .where(
                (GraphClaimRelationship.source_claim_id == claim_id)
                | (GraphClaimRelationship.target_claim_id == claim_id)
            )
            .order_by(GraphClaimRelationship.id)
        )
        return list(self.session.scalars(statement))

    def unconfirmed_claims(self) -> list[GraphClaim]:
        """Return every claim with zero relationship edges, as source or target.

        M50's Tracking the Unknown decision (`docs/stability_and_tracking_design.md`):
        the only "gap" `core` can honestly report without guessing is a real,
        structural fact the graph already stores -- no `supports`/
        `contradicts`/`qualifies`/`contextualizes`/`supersedes` edge touches
        this claim yet, meaning no second claim has been reviewed and
        explicitly related to it. Says nothing about the science itself, only
        about `core`'s own review coverage so far.
        """

        statement = (
            select(GraphClaim)
            .outerjoin(
                GraphClaimRelationship,
                (GraphClaimRelationship.source_claim_id == GraphClaim.id)
                | (GraphClaimRelationship.target_claim_id == GraphClaim.id),
            )
            .where(GraphClaimRelationship.id.is_(None))
            .order_by(GraphClaim.id)
        )
        return list(self.session.scalars(statement))

    def add_citation_edge(
        self, *, citing_paper_id: int, cited_paper_id: int, raw_citation_text: str
    ) -> GraphCitation:
        """Return an existing citation edge, or create one.

        Idempotent on `(citing_paper_id, cited_paper_id)`. Callers must
        only invoke this once a reference-list DOI has actually been
        matched to another *corpus* paper -- see
        `knowledge_engine/citation_extraction.py`.
        """

        existing = self.session.scalar(
            select(GraphCitation).where(
                GraphCitation.citing_paper_id == citing_paper_id,
                GraphCitation.cited_paper_id == cited_paper_id,
            )
        )
        if existing:
            return existing

        edge = GraphCitation(
            citing_paper_id=citing_paper_id,
            cited_paper_id=cited_paper_id,
            raw_citation_text=raw_citation_text,
            created_at=_utc_now_iso(),
        )
        self.session.add(edge)
        self.session.flush()
        return edge

    def citations_for_paper(self, paper_id: int) -> list[GraphCitation]:
        """Return every citation edge touching one paper, as citer or cited."""

        statement = (
            select(GraphCitation)
            .where(
                (GraphCitation.citing_paper_id == paper_id)
                | (GraphCitation.cited_paper_id == paper_id)
            )
            .order_by(GraphCitation.id)
        )
        return list(self.session.scalars(statement))

    def relationship_candidates(
        self, *, minimum_shared_concepts: int = 1, corpus_id: str | None = None
    ) -> list[tuple[GraphClaim, GraphClaim, list[GraphConcept]]]:
        """Return claim pairs sharing at least `minimum_shared_concepts` concepts.

        Structural overlap only -- shared concepts, never a relationship type
        or rationale. Matches `relationship-validate`'s "never infers,
        detects, or suggests a relationship" posture (see
        `docs/phase4_design.md`'s Open Questions on automated
        candidate-surfacing): this method only surfaces which claim pairs
        share PICO-resolved concepts, leaving whether and how they relate
        entirely to whoever authors a `RelationshipRecord` (an AI agent or a
        human -- this project's actual RelationshipRecords have mostly been
        AI-authored, not a human-only step). A pair already linked by a
        `graph_claim_relationships` edge, in either direction, is excluded
        -- that call has already been made for it.

        `corpus_id`, when given, restricts candidates to pairs where *both*
        claims carry that `corpus_id` -- the graph is otherwise
        corpus-agnostic by design (see `GraphClaim.corpus_id`'s docstring),
        so omitting this preserves today's cross-corpus behavior exactly.
        A claim with `corpus_id IS NULL` (never backfilled) never matches a
        `corpus_id`-scoped call, even if it happens to belong to that
        corpus in practice -- this method only trusts what was explicitly
        recorded, never guesses from `evidence_record_id`.
        """

        concept_claim_pairs = self.session.execute(
            select(GraphClaimConcept.concept_id, GraphClaimConcept.claim_id).distinct()
        ).all()

        claims_by_concept: dict[int, set[int]] = defaultdict(set)
        for concept_id, claim_id in concept_claim_pairs:
            claims_by_concept[concept_id].add(claim_id)

        if corpus_id is not None:
            scoped_claim_ids = set(
                self.session.scalars(select(GraphClaim.id).where(GraphClaim.corpus_id == corpus_id))
            )
            claims_by_concept = {
                concept_id: claim_ids & scoped_claim_ids
                for concept_id, claim_ids in claims_by_concept.items()
            }

        shared_concepts_by_pair: dict[tuple[int, int], set[int]] = defaultdict(set)
        for concept_id, claim_ids in claims_by_concept.items():
            for claim_a_id, claim_b_id in combinations(sorted(claim_ids), 2):
                shared_concepts_by_pair[(claim_a_id, claim_b_id)].add(concept_id)

        existing_edges = {
            frozenset((source_claim_id, target_claim_id))
            for source_claim_id, target_claim_id in self.session.execute(
                select(
                    GraphClaimRelationship.source_claim_id,
                    GraphClaimRelationship.target_claim_id,
                )
            )
        }

        candidates: list[tuple[GraphClaim, GraphClaim, list[GraphConcept]]] = []
        for (claim_a_id, claim_b_id), concept_ids in shared_concepts_by_pair.items():
            if len(concept_ids) < minimum_shared_concepts:
                continue
            if frozenset((claim_a_id, claim_b_id)) in existing_edges:
                continue
            claim_a = self.session.get(GraphClaim, claim_a_id)
            claim_b = self.session.get(GraphClaim, claim_b_id)
            assert claim_a is not None and claim_b is not None
            concepts = [
                concept
                for concept_id in sorted(concept_ids)
                if (concept := self.session.get(GraphConcept, concept_id)) is not None
            ]
            candidates.append((claim_a, claim_b, concepts))

        candidates.sort(key=lambda item: (-len(item[2]), item[0].id, item[1].id))
        return candidates

    def population_counts(self) -> dict[str, Any]:
        """Return the graph's total current row counts, e.g. for `ke graph-build`'s summary.

        Reports the database's actual current state, not a per-run delta --
        matching `docs/phase4_design.md`'s Testing Strategy promise to
        report real graph population counts, mirroring
        `scripts/m38_extraction_corpus_report.py`'s own corpus-state
        reporting.
        """

        concepts_by_source: dict[str, int] = {
            source: count
            for source, count in self.session.execute(
                select(GraphConcept.source, func.count()).group_by(GraphConcept.source)
            )
        }
        return {
            "concepts": sum(concepts_by_source.values()),
            "concepts_by_source": concepts_by_source,
            "claims": self.session.scalar(select(func.count()).select_from(GraphClaim)) or 0,
            "claim_concept_edges": self.session.scalar(
                select(func.count()).select_from(GraphClaimConcept)
            )
            or 0,
            "relationship_edges": self.session.scalar(
                select(func.count()).select_from(GraphClaimRelationship)
            )
            or 0,
            "citation_edges": self.session.scalar(select(func.count()).select_from(GraphCitation))
            or 0,
        }


def database_exists(settings: Settings) -> bool:
    """Return whether the default SQLite database file exists."""

    prefix = "sqlite:///"
    if not settings.resolved_database_url.startswith(prefix):
        return True
    return Path(settings.resolved_database_url.removeprefix(prefix)).exists()
