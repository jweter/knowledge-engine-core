# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 0 local PDF ingestion, SQLite persistence, and FTS5 search.
- Typer CLI commands: `init`, `import`, `search`, `list`, and `stats`.
- SQLAlchemy models for papers, authors, journals, keywords, and extracted text.
- PyMuPDF parser with best-effort metadata extraction.
- pytest, ruff, black, and mypy configuration.
- Repository governance files, issue templates, PR template, and CI workflow.
- Pain-point tracking for known developer and product issues.
- GLP-1 vertical slice demo for retrieval, corpus metadata overlays, manual
  evidence display, evidence validation, and local Markdown evidence reports.

## [0.1.0] - 2026-07-06

Initial public Phase 0 release.
