# Phase 0: Local Source Vault

Phase 0 establishes the repository foundation and a fully offline local
application.

## Completed Scope

- Import scientific PDFs.
- Extract raw text and best-effort metadata.
- Store papers, authors, journals, keywords, and extracted text.
- Search with SQLite FTS5.
- Provide a Typer CLI.
- Add tests and quality tooling.
- Add repository governance, issue templates, CI, ADRs, and project docs.

## Exit Criteria

- Local quality checks pass.
- Initial public commit is created.
- GitHub remote is configured.
- CI passes on `main`.
- `v0.1.0` tag is created after the public bootstrap is verified.
