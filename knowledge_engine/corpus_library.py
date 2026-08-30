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

CORE-GQR-6 added one more optional, explicitly-opt-in piece: a corpus's
promoted `EvidenceRecord`s (`evidence_records.jsonl`, e.g. as populated by
`ke general-question-extract-and-promote`) live outside the SQLite database
entirely, so they were previously left behind by an export/import cycle.
Passing `evidence_path`/`evidence_output_path` to the functions below carries
them along inside the same snapshot file, deduplicated by
`evidence_record_id` on import -- see `_EVIDENCE_SNAPSHOT_TABLE`.
"""

from __future__ import annotations

import gzip
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import (
    Column,
    ColumnElement,
    Engine,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
)
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

# CORE-GQR-6: a snapshot-only transport table for promoted GeneralQuestion
# `EvidenceRecord`s, deliberately declared on its own `MetaData` rather than
# added to `models.Base`. `GraphClaim`'s docstring is still accurate about the
# *working* database: an `EvidenceRecord` is a JSONL object appended to a
# corpus's `evidence_records.jsonl` file, never a row in any table the live
# application queries. This table exists solely so a portable corpus-library
# snapshot file -- already the mechanism for carrying a corpus's papers
# between environments -- can carry that corpus's promoted evidence records
# alongside them, so `ke corpus-library-import` doesn't silently leave a
# freshly hydrated database's evidence behind. `record_json` stores the
# original JSONL line verbatim; only `evidence_record_id` is unpacked, for
# dedup on import.
_EVIDENCE_SNAPSHOT_METADATA = MetaData()
_EVIDENCE_SNAPSHOT_TABLE = Table(
    "evidence_records_snapshot",
    _EVIDENCE_SNAPSHOT_METADATA,
    Column("evidence_record_id", String, primary_key=True),
    Column("record_json", Text, nullable=False),
)


@dataclass(frozen=True)
class ExportSummary:
    """Counts of rows written to a new corpus-library snapshot."""

    paper_count: int
    journal_count: int
    author_count: int
    keyword_count: int
    evidence_record_count: int = 0


@dataclass(frozen=True)
class ImportSummary:
    """Counts of rows hydrated from a corpus-library snapshot."""

    imported_paper_count: int
    skipped_existing_paper_count: int
    imported_evidence_record_count: int = 0
    skipped_existing_evidence_record_count: int = 0


def export_corpus_library(
    source_engine: Engine, output_path: Path, evidence_path: Path | None = None
) -> ExportSummary:
    """Copy corpus-content tables into a fresh, standalone snapshot file.

    `output_path` must not already exist -- callers needing to overwrite an
    existing snapshot delete it first, mirroring the `--force` pattern used
    for other `ke` output files rather than silently clobbering one here.

    `evidence_path`, when given and it exists, is a corpus's
    `evidence_records.jsonl` file (e.g. one populated by
    `ke general-question-extract-and-promote`): every well-formed record in
    it is copied into the snapshot's `evidence_records_snapshot` table so
    `ke corpus-library-import` can carry it into another environment
    alongside the papers it describes. A missing or omitted `evidence_path`
    exports zero evidence records -- not an error, since not every corpus has
    promoted evidence yet.
    """

    if output_path.exists():
        msg = f"Corpus library output already exists: {output_path}"
        raise FileExistsError(msg)

    evidence_rows = _read_evidence_jsonl(evidence_path) if evidence_path else []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_engine = create_engine(f"sqlite:///{output_path}", future=True)
    try:
        tables = [Base.metadata.tables[name] for name in CORPUS_LIBRARY_TABLES]
        Base.metadata.create_all(target_engine, tables=tables)

        if evidence_rows:
            _EVIDENCE_SNAPSHOT_METADATA.create_all(target_engine)
            with target_engine.begin() as connection:
                connection.execute(
                    _EVIDENCE_SNAPSHOT_TABLE.insert(),
                    [
                        {"evidence_record_id": record_id, "record_json": raw_line}
                        for record_id, raw_line in evidence_rows
                    ],
                )

        source_session_factory = sessionmaker(source_engine, future=True)
        target_session_factory = sessionmaker(target_engine, future=True)

        journal_cache: dict[int, Journal] = {}
        author_cache: dict[int, Author] = {}
        keyword_cache: dict[int, Keyword] = {}

        with (
            source_session_factory() as source_session,
            target_session_factory() as target_session,
        ):
            papers = source_session.scalars(
                select(Paper).options(*_PAPER_LOAD_OPTIONS).order_by(Paper.id)
            ).all()

            for paper in papers:
                new_journal = None
                if paper.journal is not None:
                    new_journal = journal_cache.get(paper.journal.id)
                    if new_journal is None:
                        new_journal = Journal(
                            name=paper.journal.name,
                            issn=paper.journal.issn,
                            created_at=paper.journal.created_at,
                        )
                        journal_cache[paper.journal.id] = new_journal

                new_paper = _copy_paper_fields(paper, journal=new_journal)

                for author_link in paper.author_links:
                    new_author = author_cache.get(author_link.author.id)
                    if new_author is None:
                        new_author = Author(
                            name=author_link.author.name,
                            orcid=author_link.author.orcid,
                            created_at=author_link.author.created_at,
                        )
                        author_cache[author_link.author.id] = new_author
                    new_paper.author_links.append(
                        PaperAuthor(author=new_author, position=author_link.position)
                    )
                for keyword_link in paper.keyword_links:
                    new_keyword = keyword_cache.get(keyword_link.keyword.id)
                    if new_keyword is None:
                        new_keyword = Keyword(
                            value=keyword_link.keyword.value,
                            created_at=keyword_link.keyword.created_at,
                        )
                        keyword_cache[keyword_link.keyword.id] = new_keyword
                    new_paper.keyword_links.append(PaperKeyword(keyword=new_keyword))

                target_session.add(new_paper)

            target_session.commit()

            return ExportSummary(
                paper_count=len(papers),
                journal_count=len(journal_cache),
                author_count=len(author_cache),
                keyword_count=len(keyword_cache),
                evidence_record_count=len(evidence_rows),
            )
    finally:
        # On Windows, a SQLAlchemy engine's connection pool keeps the underlying
        # SQLite file handle open until disposed -- garbage collection alone
        # doesn't release it deterministically. Left open, it blocks a caller's
        # temp-directory cleanup (export_corpus_library_compressed) from
        # deleting this file immediately afterward. Harmless on POSIX, fatal
        # on Windows: PermissionError: [WinError 32].
        target_engine.dispose()


def import_corpus_library(
    target_session: Session, input_path: Path, evidence_output_path: Path | None = None
) -> ImportSummary:
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

    `evidence_output_path`, when given, is the corpus's own
    `evidence_records.jsonl` file: any evidence record carried in this
    snapshot (see `export_corpus_library`) whose `evidence_record_id` is not
    already present there is appended, exactly matching
    `_promote_evidence_records`'s own append-only, ID-deduplicated contract.
    An older snapshot with no `evidence_records_snapshot` table (predating
    CORE-GQR-6) is simply treated as carrying zero evidence records, not an
    error.
    """

    if not input_path.exists():
        msg = f"Corpus library input does not exist: {input_path}"
        raise FileNotFoundError(msg)

    source_engine = create_engine(f"sqlite:///{input_path}", future=True)
    try:
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

            imported_evidence, skipped_evidence = _merge_evidence_snapshot(
                source_engine, evidence_output_path
            )

        return ImportSummary(
            imported_paper_count=imported,
            skipped_existing_paper_count=skipped,
            imported_evidence_record_count=imported_evidence,
            skipped_existing_evidence_record_count=skipped_evidence,
        )
    finally:
        # Same leaked-handle hazard as export_corpus_library's target_engine:
        # import_corpus_library_compressed deletes this file's temp directory
        # immediately after this function returns, which Windows refuses while
        # an undisposed engine still holds it open.
        source_engine.dispose()


def export_corpus_library_compressed(
    source_engine: Engine, output_path: Path, evidence_path: Path | None = None
) -> ExportSummary:
    """Like `export_corpus_library`, but writes a gzip-compressed snapshot.

    GitHub hard-caps individual pushed files at 100MB. This corpus's
    paper-intrinsic text (mostly `paper_pages`) compresses well -- gzip
    keeps a committed snapshot under that cap for much longer as the
    corpus grows than committing the raw SQLite file would. `output_path`
    is conventionally named `*.sqlite3.gz`, though this function does not
    enforce it. `output_path` must not already exist, matching
    `export_corpus_library`'s own no-clobber contract.

    Written with a fixed `mtime=0` gzip header: `gzip.open`'s default embeds
    the current wall-clock time, so two exports of byte-for-byte identical
    content would otherwise still produce different compressed bytes --
    and therefore different SHA-256 hashes -- whenever they happen more
    than about a second apart. `ke-corpus-library-drive-backup`'s entire
    skip-if-unchanged behavior depends on identical content hashing
    identically regardless of when it was exported.
    """

    if output_path.exists():
        msg = f"Corpus library output already exists: {output_path}"
        raise FileExistsError(msg)

    with tempfile.TemporaryDirectory() as raw_dir:
        raw_path = Path(raw_dir) / "snapshot.sqlite3"
        summary = export_corpus_library(source_engine, raw_path, evidence_path)
        with (
            raw_path.open("rb") as raw_file,
            gzip.GzipFile(output_path, "wb", mtime=0) as compressed_file,
        ):
            shutil.copyfileobj(raw_file, compressed_file)
    return summary


def import_corpus_library_compressed(
    target_session: Session, input_path: Path, evidence_output_path: Path | None = None
) -> ImportSummary:
    """Like `import_corpus_library`, but reads a gzip-compressed snapshot."""

    if not input_path.exists():
        msg = f"Corpus library input does not exist: {input_path}"
        raise FileNotFoundError(msg)

    with tempfile.TemporaryDirectory() as raw_dir:
        raw_path = Path(raw_dir) / "snapshot.sqlite3"
        with gzip.open(input_path, "rb") as compressed_file, raw_path.open("wb") as raw_file:
            shutil.copyfileobj(compressed_file, raw_file)
        return import_corpus_library(target_session, raw_path, evidence_output_path)


def _read_evidence_jsonl(path: Path) -> list[tuple[str, str]]:
    """Parse a JSONL evidence file into `(evidence_record_id, raw_line)` pairs.

    Skips a missing file, a blank line, invalid JSON, a non-object record, or
    a record with no non-empty string `evidence_record_id` -- a
    corpus-library snapshot is a transport format, not a second validator, so
    this mirrors `_promote_evidence_records`'s own defensive (not rejecting)
    parsing rather than raising on a malformed line.
    """

    if not path.exists():
        return []

    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        record_id = record.get("evidence_record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            continue
        pairs.append((record_id, stripped))
    return pairs


def _merge_evidence_snapshot(
    source_engine: Engine, evidence_output_path: Path | None
) -> tuple[int, int]:
    """Append a snapshot's evidence records into `evidence_output_path`.

    Returns `(imported_count, skipped_existing_count)`. A `None`
    `evidence_output_path`, or a snapshot with no `evidence_records_snapshot`
    table (predating CORE-GQR-6, or exported with no `evidence_path`), is
    zero records on both counts rather than an error.
    """

    if evidence_output_path is None:
        return 0, 0
    if not inspect(source_engine).has_table(_EVIDENCE_SNAPSHOT_TABLE.name):
        return 0, 0

    existing_ids = {record_id for record_id, _ in _read_evidence_jsonl(evidence_output_path)}
    with source_engine.connect() as connection:
        rows = connection.execute(
            select(_EVIDENCE_SNAPSHOT_TABLE).order_by(_EVIDENCE_SNAPSHOT_TABLE.c.evidence_record_id)
        ).all()

    new_lines = [row.record_json for row in rows if row.evidence_record_id not in existing_ids]
    skipped = len(rows) - len(new_lines)

    if new_lines:
        evidence_output_path.parent.mkdir(parents=True, exist_ok=True)
        with evidence_output_path.open("a", encoding="utf-8") as handle:
            for line in new_lines:
                handle.write(line + "\n")

    return len(new_lines), skipped


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
        created_at=paper.created_at,
        updated_at=paper.updated_at,
    )
    if paper.text is not None:
        new_paper.text = PaperText(
            raw_text=paper.text.raw_text,
            body_text=paper.text.body_text,
            extraction_method=paper.text.extraction_method,
            extraction_version=paper.text.extraction_version,
            language=paper.text.language,
            created_at=paper.text.created_at,
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
