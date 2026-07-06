# Architecture

Knowledge Engine Core Phase 0 is intentionally small: it ingests PDFs, extracts
text, stores metadata, and provides local full-text search.

Phase 0 is a local source vault. It is not an AI system, not a web application,
and not a distributed ingestion platform yet.

## Boundaries

- `parser.py` owns file parsing and returns a typed `ParsedPaper`.
- `database.py` owns SQLAlchemy sessions, schema creation, and repository writes.
- `models.py` defines durable relational data structures.
- `search.py` owns search behavior behind a service class.
- `cli.py` adapts command line input to application services.

This keeps infrastructure decisions from leaking into the command interface.
Later, PostgreSQL, vector databases, graph databases, OCR, distributed workers,
and AI services can be added behind new implementations without rewriting the
CLI or parser contracts.

## Phase 0 Storage

SQLite stores canonical metadata and extracted text. SQLite FTS5 stores a
search-optimized copy of title, abstract, body text, and raw text. The FTS table
uses paper IDs as row IDs so results can join back to relational metadata.

## Future Extension Points

- Replace `Database` with PostgreSQL-backed session construction.
- Add parser implementations for OCR, HTML, EPUB, XML, patents, and datasets.
- Add embedding fields in a separate table or external vector store.
- Add citation, claim, evidence, contradiction, and concept graph models.
- Add worker queues for large-scale ingestion.

## Architecture Decision Records

Durable design decisions are recorded in `docs/architecture/adr/`.

- `0001-use-python-poetry-and-typed-service-boundaries.md`
- `0002-use-sqlite-and-fts5-for-phase-0.md`
