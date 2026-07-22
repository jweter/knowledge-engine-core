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

Current phase: **Phase 2 — Evidence Records** (Phase 1 ingestion complete through M14)

Phase 1 completed capabilities include:

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

Phase 2 completed capabilities include:

- page/span-level extraction provenance (`ParsedPaper.pages`, the `paper_pages`
  table), so an extracted claim can cite an exact page and character offset
- evidence-record validation of `source_span` shape and required
  `extraction_status`, and evidence renderers that display each record's real
  `extraction_method` instead of a hardcoded manual label
- deterministic structured-section detection
  (`knowledge_engine.extraction.detect_sections`)
- deterministic claim-candidate sentence detection
  (`knowledge_engine.extraction.detect_claim_candidates`) within results/
  conclusion sections
- deterministic claim framing-cue classification
  (`knowledge_engine.extraction.classify_claim_framing`), distinct from the
  evidence-record schema's research-question-relative `evidence_direction`
  field
- draft extraction review-item generation
  (`knowledge_engine.extraction.build_draft_evidence_items`); an intentionally
  incomplete draft that fails the existing evidence validator until a
  reviewer supplies `research_question` and `evidence_direction`

See [docs/phase2_design.md](docs/phase2_design.md) for the Phase 2 architecture
and milestone-by-milestone status.

### Milestone history

- **M9:** connected validated local PDFs to persisted import runs and paper/FTS
  persistence.
- **M10:** added duplicate handling, linked resume/retry, and explicit status
  contracts.
- **M11:** added metadata preview/enrichment with provenance-preserving boundaries.
- **M12:** completed the controlled 100-paper rehearsal.
- **M13:** conditionally authorized one controlled 500-paper rehearsal with explicit
  measurement and stop conditions.
- **M14:** completed the controlled 500-paper rehearsal with a `PROCEED` decision. A
  fresh import and a linked resume against the same manifest snapshot both
  reconciled exactly, with zero failures, zero issues, and a fully idempotent
  resume. See [docs/m14_500_paper_rehearsal_report.md](docs/m14_500_paper_rehearsal_report.md).
- **M15:** implemented Phase 2's foundation prerequisite, page/span-level
  extraction provenance, plus evidence-record validator and renderer fixes.
- **M16:** implemented deterministic structured-section detection, the first
  piece of the Phase 2 Extraction Layer.
- **M17:** implemented deterministic claim-candidate sentence detection within
  results/conclusion sections, the second piece of the Extraction Layer.
- **M18:** implemented deterministic claim framing-cue classification, the
  third piece of the Extraction Layer. Deliberately not the schema's
  research-question-relative `evidence_direction` field.
- **M19:** implemented draft extraction review-item generation, the first
  piece of the Evidence Layer. Deliberately incomplete: fields without an
  honest deterministic source (`research_question`, `evidence_direction`,
  PICO) are left `None`, not guessed.

Phase 1 ingestion is complete through M14. Phase 2 evidence extraction is in
progress through M19. See [docs/roadmap.md](docs/roadmap.md) and
[docs/phase2_design.md](docs/phase2_design.md) for the next milestone.

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
completed M9–M14 ingestion, duplicate/resume, metadata, 100-paper rehearsal,
scale-readiness, and the controlled 500-paper rehearsal
([`PROCEED`](docs/m14_500_paper_rehearsal_report.md)) work. Phase 2 (see
[docs/phase2_design.md](docs/phase2_design.md)) is in progress through M19:
deterministic, rule-based structured-section detection, claim-candidate
detection, claim framing-cue classification, and draft extraction
review-item generation. A valid `EvidenceRecord`, and the schema's
research-question-relative `evidence_direction` field, are not yet
implemented -- `research_question` acquisition has no source anywhere in
this pipeline yet. All Phase 2 extraction is rule-based, with no LLM-based
extraction, synthesis, or reasoning of any kind.

Neither phase should be expanded into Alembic adoption, a new package manager,
persistent telemetry, vector search, a graph, AI reasoning, an API, web
functionality, or unrelated refactoring without separate evidence and
authorization.

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
- `paper_pages` provenance is only populated for papers imported after M15; a
  backfill utility for pre-M15 papers is tracked as a follow-up (see
  [docs/phase2_design.md](docs/phase2_design.md))

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
