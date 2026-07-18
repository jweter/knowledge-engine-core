# Knowledge Engine Core

Knowledge Engine Core is the offline-first scientific source-vault foundation for
the wider Knowledge Engine project. It imports local scientific PDFs, extracts text
and best-effort metadata, stores traceable corpus/import state, and provides local
lexical retrieval.

The long-term mission is to help humanity preserve, connect, evaluate, and apply
scientific knowledge with traceable evidence and visible uncertainty. This
repository does not yet implement AI reasoning, a knowledge graph, vector search,
a public API, or a web application. It builds the reliable core those later systems
must be able to trust.

## Status

Current version: `0.2.0a1`

Current phase: **Phase 1 — Focused Scientific Corpus**

Completed capabilities include:

- PDF ingestion with PyMuPDF
- SQLite persistence with SQLAlchemy
- papers, authors, journals, keywords, extracted text, and FTS5 search
- versioned corpus-manifest validation and local path-safety checks
- persisted manifest snapshots, import runs, items, and issues
- local-only corpus import with no URL following or document downloads
- atomic per-item paper and FTS persistence with rollback on item failure
- pre-persistence duplicate evidence decisions
- exact-duplicate skipping and probable-match review outcomes
- linked resume and retry behavior
- separate execution and review status semantics
- provenance-preserving metadata preview and Crossref enrichment boundaries
- controlled 100-paper rehearsal reporting
- deterministic M13 scale-readiness assessment
- strict mypy, Ruff formatting/linting, and pytest coverage

### Milestone history

- **M9:** connected validated local PDFs to persisted import runs and paper/FTS
  persistence.
- **M10:** added duplicate handling, linked resume/retry, and explicit status
  contracts.
- **M11:** added metadata preview/enrichment with provenance-preserving boundaries.
- **M12:** completed the controlled 100-paper rehearsal.
- **M13:** conditionally authorized one controlled 500-paper rehearsal with explicit
  measurement and stop conditions.

The next bounded milestone is the controlled 500-paper rehearsal. It must follow the
M13 entry, measurement, stop, reconciliation, resume, and artifact-hygiene contract.
The rehearsal has not begun.

## Requirements

- Python 3.12 or newer
- Poetry
- Git

Current local validation was performed with Python 3.14.6. Poetry is the intended
dependency manager. A machine-specific Poetry certificate issue remains documented
in [docs/pain_points.txt](docs/pain_points.txt); the pip fallback below exists so
contributors are not blocked by that local environment problem.

## Installation

Clone the repository:

```bash
git clone https://github.com/<owner>/knowledge-engine-core.git
cd knowledge-engine-core
```

Install with Poetry:

```bash
poetry install
poetry run ke init
```

Fallback installation with `venv` and `pip`:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e . pytest ruff mypy
.venv\Scripts\ke init
```

On macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python` and
`.venv\Scripts\ke` with `.venv/bin/ke`.

## Quick Start

Initialize the local database:

```bash
poetry run ke init
```

Import one paper:

```bash
poetry run ke import papers/example.pdf
```

Attach keywords during import:

```bash
poetry run ke import papers/example.pdf --keyword alzheimer --keyword metabolism
```

Search by keyword or phrase:

```bash
poetry run ke search alzheimer
poetry run ke search "\"metabolic signaling\""
```

List imported papers and collection statistics:

```bash
poetry run ke list
poetry run ke stats
```

Validate a corpus manifest without importing papers:

```bash
poetry run ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
poetry run ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Create and inspect a persisted validation run:

```bash
poetry run ke corpus-run-create data/corpora/glp1_weight_loss/corpus.json
poetry run ke corpus-run-show <import-run-id>
```

Persist and import a declared local corpus:

```bash
poetry run ke corpus-import data/corpora/glp1_weight_loss/corpus.json
```

`ke corpus-import` reads only manifest-declared local files. It follows no URLs and
downloads no documents.

The GLP-1 vertical-slice demo checklist is in
[docs/glp1_vertical_slice_demo_checklist.md](docs/glp1_vertical_slice_demo_checklist.md).
The demo performs retrieval and manual evidence display only; it does not perform
scientific synthesis.

By default, the SQLite database is created at:

```text
data/knowledge_engine.sqlite3
```

Override it with environment variables:

```bash
KE_DATA_DIR=/path/to/data poetry run ke init
KE_DATABASE_URL=sqlite:////absolute/path/ke.sqlite3 poetry run ke stats
```

## Developer Setup

Ruff is the single authoritative formatter and linter. The complete local quality
suite matches `.github/workflows/quality.yml`:

```bash
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy knowledge_engine tests
poetry run pytest
```

Format and apply safe lint fixes:

```bash
poetry run ruff format .
poetry run ruff check . --fix
```

Development conventions:

- Work on feature branches rather than directly on `main`.
- Keep commits focused and use Conventional Commits.
- Update `CHANGELOG.md` for user-visible changes.
- Add or update tests for behavioral changes.
- Record important design decisions under `docs/architecture/adr/`.

## Architecture

Knowledge Engine Core uses a small layered architecture:

- `knowledge_engine.parser` extracts text and best-effort metadata from PDFs and
  exposes typed expected document failures.
- `knowledge_engine.models` defines durable relational state.
- `knowledge_engine.database` owns initialization and repository writes.
- `knowledge_engine.corpus` validates versioned corpus manifests and path safety.
- `knowledge_engine.import_runs` persists validation/import state and orchestrates
  local corpus ingestion.
- `knowledge_engine.duplicate_resolution` evaluates duplicate evidence before any
  paper persistence.
- `knowledge_engine.search` provides SQLite FTS5 keyword and phrase search.
- `knowledge_engine.cli` adapts user commands to application services.

Expected document-level parser failures and explicitly expected duplicate-resolution
failures remain recoverable per item. Unexpected programming, type, assertion, ORM,
or dependency defects propagate as systemic failures rather than being persisted as
ordinary `paper_parse_failed` or `duplicate_resolution_failed` issues. Persisted
messages for expected failures remain stable and sanitized.

The CLI does not contain parsing, persistence, or ranking logic. Later interfaces
can reuse the same services without moving those responsibilities into command
handlers.

See [docs/architecture.md](docs/architecture.md),
[docs/architecture/system_overview.md](docs/architecture/system_overview.md),
[docs/architecture/adr/](docs/architecture/adr/), and
[docs/decisions.md](docs/decisions.md).

## Data Model

Core relational state includes:

- `papers`: canonical document metadata, source path, content hash, DOI, page count,
  and word count
- `authors`, `journals`, and `keywords`
- `paper_texts`, `paper_authors`, and `paper_keywords`
- `manifest_snapshots`, `import_runs`, `import_items`, and `import_issues`
- SQLite FTS5 `paper_search` rows for local lexical retrieval

Probable scholarly matches remain review outcomes rather than silent merges. Exact
or high-confidence duplicate evidence is evaluated before paper persistence.

## Roadmap

The authoritative roadmap is [docs/roadmap.md](docs/roadmap.md). Phase 1 now includes
completed M9–M13 ingestion, duplicate/resume, metadata, 100-paper rehearsal, and
scale-readiness work.

The immediate continuation is one controlled 500-paper rehearsal. It must not be
expanded into Alembic adoption, a new package manager, persistent telemetry, vector
search, a graph, AI reasoning, an API, web functionality, or unrelated refactoring
without separate evidence and authorization.

## Known Issues

Known issues and future fixes are tracked in
[docs/pain_points.txt](docs/pain_points.txt) and
[docs/technical_debt.md](docs/technical_debt.md). Current highlights:

- a machine-specific Poetry/PyPI certificate problem remains unresolved
- PDF text and metadata extraction remain best-effort and need real-corpus evidence
- persistence failures still use a broad sanitized category pending observed failure
  semantics
- FTS update/delete synchronization is not implemented
- scholarly work/version/file/assertion identity is not yet separated
- page-level extraction provenance is deferred until before Phase 2 evidence work

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), follow the
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and report vulnerabilities through
[SECURITY.md](SECURITY.md).

## Repository Family

This repository is intentionally limited to the scientific source-vault core. Future
separate repositories may host AI reasoning, web, API, agent, graph, and model
systems after their prerequisites are justified.

## License

MIT License. See [LICENSE](LICENSE).
