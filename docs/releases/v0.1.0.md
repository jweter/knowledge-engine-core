# Release Notes: v0.1.0

Release date: 2026-07-06

## Summary

`v0.1.0` is the initial public release of Knowledge Engine Core. It establishes
the Phase 0 local source vault: an offline Python application for importing
scientific PDFs, extracting text, storing metadata, and searching a local SQLite
database.

## Major Features

- Typer CLI with `init`, `import`, `search`, `list`, and `stats` commands.
- PDF text extraction with PyMuPDF.
- SQLite persistence with SQLAlchemy ORM models.
- Tables for papers, authors, journals, keywords, and extracted paper text.
- SQLite FTS5 keyword and phrase search.
- Pydantic settings for environment-aware configuration.
- Rich terminal output.
- pytest test suite.
- ruff, black, and mypy quality gates.
- GitHub Actions workflow for quality checks.
- Governance docs, issue templates, pull request template, ADRs, roadmap,
  project principles, technical debt tracking, and pain-point tracking.

## Known Limitations

- PDF metadata extraction is best-effort.
- Bulk corpus ingestion is not implemented yet.
- Import manifests, duplicate reports, and recovery workflows are not
  implemented yet.
- Database migrations are not implemented yet.
- Search is lexical only; embeddings are intentionally out of scope for Phase 0.
- Poetry dependency resolution has a local Windows certificate issue documented
  in `docs/pain_points.txt`; CI verified Poetry successfully on GitHub Actions.

## Pain Points

See `docs/pain_points.txt` for the prioritized maintenance backlog. Current
high-priority items are:

- Harden Poetry setup on Windows.
- Diagnose local Poetry certificate behavior.
- Add import manifests for Phase 1 corpus ingestion.

## Future Work

- Phase 1 focused corpus ingestion.
- Import manifests and duplicate detection.
- PubMed and Crossref metadata enrichment.
- Parser failure tracking and realistic legal fixtures.
- Database migration strategy.
- Future vector search, knowledge graph, and AI-assisted reasoning layers after
  the source vault is reliable.

## Repository Statistics

- Tracked files: 47
- Python files: 11
- Python lines of code: 636
- Documentation files: 29
- Documentation lines: 972
- Tests: 4

## Python Version

- Supported: Python 3.12 or newer
- Locally verified: Python 3.14.6
- CI verified: Python 3.12

## Supported Platforms

Phase 0 is intended to support:

- Windows
- macOS
- Linux

Current direct local validation was performed on Windows. CI validation was
performed on Ubuntu through GitHub Actions.

## Dependencies

Runtime dependencies:

- Pydantic
- pydantic-settings
- PyMuPDF
- Rich
- SQLAlchemy
- Typer
- Click

Development dependencies:

- black
- mypy
- pytest
- ruff

## Architecture Summary

Knowledge Engine Core uses a small layered architecture:

- `cli.py` adapts command-line input to application services.
- `parser.py` extracts PDF text and best-effort metadata.
- `models.py` defines relational data structures.
- `database.py` owns schema initialization and repository operations.
- `search.py` provides SQLite FTS5 search.
- `config.py` centralizes runtime settings.

This keeps Phase 0 simple while preserving extension points for future
PostgreSQL, vector search, OCR, knowledge graph, and AI integrations.
