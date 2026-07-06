# Contributing

Thank you for helping build Knowledge Engine Core. The project is intentionally
beginner friendly, but it is also meant to become durable infrastructure. Please
favor clear, tested, well-documented changes over clever shortcuts.

## Development Workflow

1. Open or choose an issue before starting non-trivial work.
2. Create a branch from `main`.
3. Make a focused change.
4. Add or update tests.
5. Run the quality checks.
6. Open a pull request.

After the initial bootstrap, avoid committing directly to `main`. Use feature
branches and pull requests even for small changes.

## Branch Names

Use short, descriptive branch names:

- `feature/phase-1-corpus-ingestion`
- `fix/fts-snippet-ranking`
- `docs/windows-setup`
- `chore/github-templates`

## Commit Messages

Use Conventional Commits:

- `feat: add import manifest model`
- `fix: handle empty PDF text extraction`
- `docs: document Windows setup`
- `test: cover duplicate paper imports`
- `chore: update issue templates`

## Quality Checks

Run these before opening a pull request:

```bash
poetry run black --check .
poetry run ruff check .
poetry run mypy knowledge_engine tests
poetry run pytest
```

If Poetry is blocked by the known local certificate issue, use the pip fallback
from `README.md` and run the same tools through `.venv`.

## Code Style

- Prefer readable, typed Python.
- Keep modules focused and small where practical.
- Avoid global mutable state.
- Use repository/service boundaries for persistence and search behavior.
- Add docstrings for public classes and functions.
- Do not add AI, embeddings, OCR, or external services to Phase 0 without an
  accepted issue and design discussion.

## Tests

Tests should be small, deterministic, and offline. Use generated fixtures when
possible. Do not commit copyrighted papers or private datasets.

## Scientific Data

Only commit data that is legally redistributable. When in doubt, add a script or
instructions for generating/fetching the data instead of committing the data.

## Architecture Decisions

Record significant decisions in `docs/architecture/adr/`. An ADR should explain
the context, decision, consequences, and alternatives considered.
