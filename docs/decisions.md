# Decisions

This file is a lightweight index of significant project decisions. Larger
decisions should also receive an Architecture Decision Record under
`docs/architecture/adr/`.

## Decision Log

### Use Python for Phase 0

Python is familiar to scientific computing contributors and has strong libraries
for PDFs, databases, CLIs, testing, and future data workflows.

See: `docs/architecture/adr/0001-use-python-poetry-and-typed-service-boundaries.md`

### Use Poetry as the intended dependency manager

Poetry provides project metadata, dependency groups, virtual environment
management, and package scripts. A pip/venv fallback is documented while local
Windows certificate behavior is investigated.

See: `docs/architecture/adr/0001-use-python-poetry-and-typed-service-boundaries.md`

### Use SQLite before PostgreSQL

SQLite keeps Phase 0 offline and beginner friendly. PostgreSQL remains a likely
future backend once corpus scale and concurrent workflows require it.

See: `docs/architecture/adr/0002-use-sqlite-and-fts5-for-phase-0.md`

### Use FTS5 before vector search

Lexical search is transparent, offline, and easy to verify. Embeddings can be
added later after the source vault and metadata model are reliable.

See: `docs/architecture/adr/0002-use-sqlite-and-fts5-for-phase-0.md`

### Keep AI out of Phase 0

The project must first preserve and search source documents. AI layers should
build on traceable source data rather than becoming the foundation.

### Use ADRs for durable architecture choices

The project is intended to last. Future contributors need to know why decisions
were made, not only what the current code does.
