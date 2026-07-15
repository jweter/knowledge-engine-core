# Knowledge Engine Core

Knowledge Engine Core is the Phase 0 foundation for an open scientific
knowledge platform. It runs offline and provides the first durable source vault:
import scientific PDFs, extract text, store metadata, and search a local
collection.

The long-term Knowledge Engine mission is to help humanity preserve, connect,
evaluate, and apply scientific knowledge with traceable evidence and visible
uncertainty. This repository does not build the AI layer yet. It builds the
reliable core that future AI, graph, API, and web systems can trust.

## Project Vision

Knowledge Engine is an open-source effort to organize, connect, and accelerate
scientific knowledge.

The long-term objective is to build a transparent, reproducible, AI-assisted
platform that helps researchers discover connections across disciplines while
preserving evidence, citations, and scientific rigor.

The project begins with reliable document ingestion and search, then gradually
expands toward metadata enrichment, knowledge graphs, semantic search, and
AI-assisted reasoning. Every stage is designed to remain open, modular, and
community-driven.

## Status

Phase 0 is implemented:

- PDF ingestion with PyMuPDF
- SQLite persistence with SQLAlchemy
- Tables for papers, authors, journals, keywords, and extracted text
- SQLite FTS5 keyword and phrase search
- Version 1 corpus manifest validation with no import side effects
- Durable import-run records for persisted corpus validation attempts
- Typer CLI with Rich terminal output
- pytest coverage for parser, persistence/search, and CLI behavior
- ruff, black, and mypy configuration
- Project governance files and GitHub templates

## Requirements

- Python 3.12 or newer
- Poetry
- Git

Current local validation was performed with Python 3.14.6. Poetry is the
intended dependency manager, but this machine currently has a Poetry certificate
issue documented in [docs/pain_points.txt](docs/pain_points.txt). The pip-based
fallback below is provided so contributors are not blocked while that environment
issue is fixed.

## Installation

Clone the repository:

```bash
git clone https://github.com/<owner>/knowledge-engine-core.git
cd knowledge-engine-core
```

Replace `<owner>` with the GitHub account or organization that publishes the
repository.

Install with Poetry:

```bash
poetry install
poetry run ke init
```

Fallback installation with `venv` and `pip`:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e . pytest black ruff mypy
.venv\Scripts\ke init
```

On macOS or Linux, replace `.venv\Scripts\python` with
`.venv/bin/python` and `.venv\Scripts\ke` with `.venv/bin/ke`.

## Quick Start

Initialize the local database:

```bash
poetry run ke init
```

Import a paper:

```bash
poetry run ke import papers/example.pdf
```

Attach keywords during import:

```bash
poetry run ke import papers/example.pdf --keyword alzheimer --keyword metabolism
```

Search by keyword:

```bash
poetry run ke search alzheimer
```

Search by phrase:

```bash
poetry run ke search "\"metabolic signaling\""
```

List imported papers:

```bash
poetry run ke list
```

Show collection statistics:

```bash
poetry run ke stats
```

Validate a corpus manifest without importing papers:

```bash
poetry run ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
```

Check local PDF readiness for included full-text rows:

```bash
poetry run ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Record a corpus validation attempt as an import run:

```bash
poetry run ke corpus-run-create data/corpora/glp1_weight_loss/corpus.json
```

Inspect a persisted import run:

```bash
poetry run ke corpus-run-show <import-run-id>
```

Persist and import a local corpus:

```bash
poetry run ke corpus-import data/corpora/glp1_weight_loss/corpus.json
```

Run the GLP-1 vertical slice demo checklist:

```text
docs/glp1_vertical_slice_demo_checklist.md
```

The demo is retrieval and manual evidence display only. It does not perform
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

Run the complete local quality suite:

```bash
poetry run black --check .
poetry run ruff check .
poetry run mypy knowledge_engine tests
poetry run pytest
```

Format code:

```bash
poetry run black .
poetry run ruff check . --fix
```

Development conventions:

- Work on feature branches, not directly on `main`, after the initial bootstrap.
- Keep commits focused and use Conventional Commits.
- Update `CHANGELOG.md` for user-visible changes.
- Add or update tests for behavior changes.
- Record important design decisions as ADRs under `docs/architecture/adr/`.

## Project Structure

```text
knowledge-engine-core/
  knowledge_engine/
    cli.py          # Typer command line interface
    config.py       # Pydantic settings
    corpus/         # Corpus manifest validation models and service
    database.py     # SQLAlchemy engine/session/repository logic
    import_runs/    # Import-run persistence service and repository
    models.py       # SQLAlchemy ORM models
    parser.py       # PDF parsing interface and PyMuPDF implementation
    search.py       # SQLite FTS5 search service
    utils.py        # Small shared helpers
  tests/            # Unit tests and integration-style service tests
  data/             # Local SQLite database location, ignored except .gitkeep
  papers/           # Local PDF import staging, ignored except .gitkeep
  database/         # Reserved for future migrations or database assets
  docs/             # Architecture, roadmap, ADRs, and pain-point tracking
    architecture/
      adr/          # Architecture Decision Records
      diagrams/     # Future system diagrams
    roadmap/        # Phase-specific roadmap notes
    research/       # Future corpus and scientific research notes
  .github/          # Issue templates, PR template, and CI workflow
```

## Architecture

Knowledge Engine Core uses a small layered architecture:

- `knowledge_engine.parser` extracts text and best-effort metadata from PDFs.
- `knowledge_engine.models` defines durable relational tables.
- `knowledge_engine.database` owns initialization and repository writes.
- `knowledge_engine.import_runs` persists corpus validation attempts.
- `knowledge_engine.search` provides FTS5-backed keyword and phrase search.
- `knowledge_engine.corpus` validates versioned corpus manifests before import.
- `knowledge_engine.cli` adapts user commands to application services.

The CLI does not contain parsing, storage, or ranking logic. That keeps the
project easy to test and makes later interfaces possible: an API server, web
application, worker process, or notebook integration can reuse the same services.

See [docs/architecture.md](docs/architecture.md),
[docs/architecture/system_overview.md](docs/architecture/system_overview.md),
[docs/architecture/adr/](docs/architecture/adr/), and
[docs/decisions.md](docs/decisions.md) for design rationale.

## Data Model

Phase 0 creates these core tables:

- `papers`: canonical document metadata, source path, content hash, DOI, page
  count, word count, and future embedding references.
- `authors`: normalized author records.
- `journals`: publication venues.
- `keywords`: normalized topic labels.
- `paper_texts`: raw and body text extracted from each paper.
- `paper_authors` and `paper_keywords`: relationship tables.
- `manifest_snapshots`, `import_runs`, `import_items`, and `import_issues`:
  durable validation-attempt state for Phase 1 corpus ingestion.

SQLite FTS5 powers local search through a separate `paper_search` virtual table.
This keeps lexical search fast without coupling canonical data to a single
search implementation.

## Roadmap

The recommended next milestone is Phase 1: build a focused scientific corpus.
Start with one domain, such as obesity and metabolic disease, import 500 to
1,000 legally available papers, then improve metadata extraction with PubMed and
Crossref adapters.

See [docs/roadmap.md](docs/roadmap.md) and `docs/roadmap/` for the longer
roadmap.

The current vertical slice demo is documented in
[docs/vertical_slice.md](docs/vertical_slice.md) and
[docs/glp1_vertical_slice_demo_checklist.md](docs/glp1_vertical_slice_demo_checklist.md).

## Known Issues

Known issues and future fixes are tracked in
[docs/pain_points.txt](docs/pain_points.txt) and
[docs/technical_debt.md](docs/technical_debt.md). Current highlights:

- Poetry dependency resolution fails on this machine due to PyPI certificate
  verification, while pip-based installation works.
- Metadata extraction is best-effort and needs real-corpus hardening.
- Bulk PDF ingestion and duplicate reports are not implemented yet.

## Contributing

Contributions are welcome once the repository is published. Please read
[CONTRIBUTING.md](CONTRIBUTING.md), follow the
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and report vulnerabilities through
[SECURITY.md](SECURITY.md).

## Repository Family

This repository is named `knowledge-engine-core` so the ecosystem can grow
without becoming a monolith:

- `knowledge-engine-core`: document ingestion and local search
- `knowledge-engine-ai`: reasoning and synthesis
- `knowledge-engine-web`: web interface
- `knowledge-engine-api`: public API
- `knowledge-engine-agents`: research agents
- `knowledge-engine-graph`: citation and knowledge graph
- `knowledge-engine-models`: trained and evaluated models

## License

MIT License. See [LICENSE](LICENSE).
