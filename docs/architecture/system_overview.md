# System Overview

Knowledge Engine Core Phase 0 is a local offline application for importing,
storing, and searching scientific PDFs.

## Flow

```text
PDF file
  -> PyMuPDF parser
  -> ParsedPaper
  -> SQLAlchemy repository
  -> SQLite relational tables
  -> SQLite FTS5 index
  -> Typer CLI search/list/stats commands
```

## Components

- CLI: command-line interface in `knowledge_engine/cli.py`.
- Parser: PDF extraction in `knowledge_engine/parser.py`.
- Repository: persistence operations in `knowledge_engine/database.py`.
- Models: relational schema in `knowledge_engine/models.py`.
- Search: FTS query behavior in `knowledge_engine/search.py`.
- Config: environment-aware settings in `knowledge_engine/config.py`.

## Non-Goals for Phase 0

- AI reasoning
- Embeddings
- OCR
- Web UI
- Public API
- Distributed workers
- Knowledge graph

These are expected future capabilities, but Phase 0 stays focused on a reliable
local source vault.
