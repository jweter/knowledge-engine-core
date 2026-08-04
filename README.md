# Knowledge Engine Core

Knowledge Engine Core is the offline-first scientific source, evidence, and graph
foundation for the wider Knowledge Engine project. It imports local scientific
PDFs, preserves provenance, extracts traceable evidence, supports lexical and
semantic retrieval, and builds a reviewable scientific relationship graph.

The long-term mission is to help humanity preserve, connect, evaluate, and apply
scientific knowledge with traceable evidence and visible uncertainty. This
Core does not decide scientific truth or hide reasoning inside an AI model. The
separate web and AI repositories consume its evidence and graph outputs; the
read-only persistent-host boundary remains designed but deliberately unbuilt.

Public entry points:

- [Project showcase](https://knowledge-engine.steelzombie9999.chatgpt.site/)
  -- the mission and public introduction.
- [Working web alpha](https://knowledge-engine-web-alpha.onrender.com/)
  -- the current read-only laboratory over a published point-in-time snapshot.

The showcase is the front door; the alpha is the inspectable demonstration.
Neither should imply that the system has reached scientific synthesis or open
public-service maturity.

## Status

Current version: `0.2.0a1`

Current strategic cycle: **measured retrieval and one complete GLP-1 evidence
map**. The ingestion, Evidence Record, semantic retrieval, relationship-graph,
web-alpha, and first AI retrieval/synthesis foundations already exist. See
[Current Project Path](docs/roadmap.md#current-project-path).

The first bounded GLP-1/body-weight map is now available as a
[reviewed golden evidence map](docs/glp1_body_weight_golden_evidence_map.md).
It links twelve cited Evidence Records through seventeen reviewer-authored
relationships while keeping population, comparator, endpoint, and review
boundaries explicit. An AI-assisted independent source audit verified
record-to-source fidelity, including bounded withdrawal, safety, and
agent/population qualifiers. A reproducible same-PICO search found no aligned
direction-reversing semaglutide result and preserved that as a bounded negative
finding rather than manufacturing a contradiction;
it is not human domain-expert approval, a benefit-harm assessment, or a
scientific conclusion.

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
- a second automated discovery source, Europe PMC (M34), alongside PubMed/PMC
  (`ke europepmc-candidate-discover`, `ke europepmc-candidate-review-prepare`)
  -- discovery and adjudication only, not yet wired into acquisition
- a third automated discovery source, CORE (M35)
  (`ke core-candidate-discover`, `ke core-candidate-review-prepare`) --
  discovery and adjudication only, not yet wired into acquisition; CORE
  never reports a license field, so every CORE candidate is held pending
  human license verification
- an Unpaywall per-DOI OA-location/license evidence lookup (M36)
  (`ke unpaywall-doi-lookup`, `ke unpaywall-batch-lookup`) -- a lookup
  tool, not a fifth discovery pipeline, since Unpaywall's topic-search API
  was confirmed broken at build time; makes no accept/reject/hold decision
- a manual-PDF preview and manifest-draft tool (M37)
  (`ke manual-pdf-preview`, `ke manual-pdf-manifest-draft`) -- local
  parsing plus an optional Unpaywall DOI lookup instead of hand-typing a
  manifest row for a manually-supplied PDF; refuses to draft a row
  without a passed license
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
- the `ke extraction-review-generate` CLI command, which runs the full
  deterministic pipeline against one persisted paper (`--paper-id`) and
  writes a JSONL draft review queue (`--output`); a separate, opt-in command
  that never runs as part of `corpus-import`
- the `ke extraction-review-promote` CLI command, which promotes
  reviewer-completed draft items into real `EvidenceRecord` rows, reusing
  the existing evidence validator unchanged; idempotent, append-only, and
  adds zero new judgment logic
- the `ke paper-pages-backfill` CLI command, which backfills `paper_pages`
  rows for papers imported before M15 by re-parsing a still-present local
  PDF, only trusting the result once its content hash matches what was
  originally persisted
- a closed `extraction_status` vocabulary and `source_span` offset-range
  validation in `ke evidence-validate`, replacing the earlier
  any-non-empty-string check now that real extraction logic defines real
  values
- the Relationship Layer's first slice: a human-authored evidence-relationship
  schema (reusing `evidence_direction`'s vocabulary), the `ke
  relationship-validate` CLI command (validates that a reviewer-supplied
  relationship is well-formed, never detects or suggests one automatically),
  and the `ke relationship-report` CLI command (renders each relationship
  next to the claim text of the two evidence records it links)
- `extraction_runs` persistence: `ke extraction-review-generate` now records
  a durable row per invocation (paper, output path, item counts, ruleset
  versions), so a paper's extraction history is findable without re-reading
  every JSONL file; extraction is never automatically re-run on a ruleset
  change
- deterministic `study_type` classification and `limitations` extraction
  (`knowledge_engine.extraction.classify_study_type`/`extract_limitations`)
  from an explicit cue in Abstract/Methods or a "Limitations" heading
- deterministic PICO extraction
  (`knowledge_engine.extraction.extract_pico`): `population`, `intervention`,
  `comparator`, `outcome`, each the first sentence matching an explicit cue
  within Abstract/Methods (and also Results for comparator/outcome)

See [docs/phase2_design.md](docs/phase2_design.md) for the Phase 2 architecture
and milestone-by-milestone status.

Phase 3 completed capabilities include:

- a pluggable `VectorIndex` interface
  (`knowledge_engine.vector_search.index`) with two implementations: a
  local `FaissVectorIndex` (flat, exact L2 index; no server) and a
  `QdrantVectorIndex` (`knowledge_engine.vector_search.qdrant_index`)
  targeting an operator-run Qdrant server -- usable via direct Python
  import; not yet wired into the CLI commands below (those remain FAISS
  only)
- two `EmbeddingGenerator` implementations
  (`knowledge_engine.vector_search.generator`): a local
  `SentenceTransformerEmbeddingGenerator` (default `all-MiniLM-L6-v2`,
  fully offline once weights are cached) and an `OpenAiEmbeddingGenerator`
  (OpenAI's `/v1/embeddings` endpoint over stdlib `urllib`, requires
  `KE_OPENAI_API_KEY`)
- the `ke embedding-generate` CLI command, which embeds every paper's
  title/abstract with either generator and writes a vectors JSONL file
- the `ke embedding-index-build` CLI command, which parses and validates
  a JSONL file of paper embeddings (from `ke embedding-generate` or any
  external tool), referentially checks every `paper_id` against the local
  database, and builds/updates the FAISS index
- the `ke vector-search` CLI command, which searches that index by either
  a free-text query (`--query-text`, embedded live with `--generator
  local|openai`) or an already-embedded query vector (`--query-vector`),
  and returns ranked papers with their real title/DOI metadata

See [docs/phase3_design.md](docs/phase3_design.md) for the Phase 3
architecture and milestone-by-milestone status.

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
  resume. See [docs/history/milestones/m14_500_paper_rehearsal_report.md](docs/history/milestones/m14_500_paper_rehearsal_report.md).
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
- **M20:** added the `ke extraction-review-generate` CLI command, wiring
  M16-M19 into an actually runnable pipeline for the first time. Opt-in,
  separate from `corpus-import`.
- **M21:** added the `ke extraction-review-promote` CLI command, closing the
  extraction-to-evidence loop: promotes reviewer-completed draft items into
  real `EvidenceRecord` rows using the existing validator unchanged.
- **M22:** added the `ke paper-pages-backfill` CLI command, closing the M15
  "Known gap" tracked since issue #89: pre-M15 papers can now become
  extractable again, but only when a re-parse's content hash matches what
  was originally persisted.
- **M23:** constrained `extraction_status` to a closed vocabulary and added
  `source_span` character-offset-range validation, resolving two questions
  left open since M15 pending real extraction logic to define real values.
- **M24:** implemented the Relationship Layer's first slice: a
  human-authored relationship schema (reusing `evidence_direction`'s
  vocabulary) and `ke relationship-validate`. Automated relationship
  detection remains a human judgment call, not yet built.
- **M25:** added `extraction_runs` persistence -- `ke
  extraction-review-generate` now records a durable row per invocation
  (paper, output path, item counts, ruleset versions). `core` never
  automatically re-runs extraction on a ruleset change; a human decides.
- **M26:** implemented deterministic `study_type` classification and
  `limitations` extraction, the first slice of non-human-typed
  PICO-adjacent extraction. Both are paper-intrinsic facts (an explicit
  study-design phrase, an explicit "Limitations" heading), extracted the
  same conservative way as claims: a missing signal produces `None`.
- **M27:** added `ke corpus-library-export`/`ke corpus-library-import`, a
  portable snapshot of a local database's paper-intrinsic content (papers,
  extracted pages/text, journals, authors, keywords) that can be committed
  and shared, since the working database itself is gitignored and does not
  survive a fresh clone. Idempotent, content-hash-keyed import. A `.gz`
  output/input path compresses/decompresses the snapshot -- past ~605
  papers it exceeds GitHub's 100MB file limit uncompressed, and this
  corpus's page-level text compresses roughly 3x, restoring real headroom.
  See [docs/history/milestones/m27_corpus_library.md](docs/history/milestones/m27_corpus_library.md).
- **M28:** implemented deterministic PICO extraction (population,
  intervention, comparator, outcome), the second and final slice of
  non-human-typed PICO-adjacent extraction after M26. Each field is the
  first sentence matching an explicit cue within Abstract/Methods (and
  also Results for comparator/outcome); patterns were tuned by reading a
  real sample of the corpus's own abstracts rather than guessed
  speculatively. No new dependency, no LLM.
- **M29:** added the `ke relationship-report` CLI command, expanding the
  Relationship Layer past M24's validate-only first slice with a pure
  Markdown display layer -- not automated detection, which remains a
  human judgment call. Renders each relationship's type and rationale
  next to the claim text of the two evidence records it links, reusing
  `relationship-validate`'s and `evidence-validate`'s checks unchanged.
- **M30 (Phase 3's first milestone):** added a pluggable
  `knowledge_engine.vector_search` package -- a `VectorIndex` interface,
  a local `FaissVectorIndex` implementation, and an `EmbeddingGenerator`
  interface with no implementation yet -- and two CLI commands,
  `ke embedding-index-build` and `ke vector-search`. No embedding-
  generation code existed yet at this point (see `docs/phase3_design.md`'s
  Open Questions), so both commands operated on externally-supplied
  vectors only, proving the retrieval architecture without committing to
  a new-dependency embedding-generation decision.
- **M31:** resolved the embedding-generation decision as "both": added
  `SentenceTransformerEmbeddingGenerator` (local, `sentence-transformers`
  pinned to a CPU-only PyTorch build) and `OpenAiEmbeddingGenerator`
  (OpenAI's `/v1/embeddings` endpoint over stdlib `urllib`, no SDK), both
  implementing `EmbeddingGenerator`, plus the `ke embedding-generate`
  CLI command that writes the same vectors-file format M30's commands
  already consume.
- **M32:** `ke vector-search` now accepts `--query-text --generator
  local|openai`, embedding a free-text query live before searching, as
  an alternative to `--query-vector`'s pre-embedded JSON file. Combining
  this with lexical `ke search`/`ke answer` results into one ranked list
  is still a separate, undesigned question.
- **M33:** added `QdrantVectorIndex`, the second `VectorIndex`
  implementation the roadmap named from the start, targeting a collection
  on an operator-run Qdrant server. Its score is squared Euclidean
  distance, matching `FaissVectorIndex`'s convention exactly (Qdrant's own
  score is not squared -- verified empirically, since Qdrant's docs do not
  state this precisely). Scoped to the class and its test suite; CLI
  wiring (`ke embedding-index-build`/`ke vector-search` targeting a
  collection instead of a local file) is deliberately deferred until a
  real operator need for it appears.
- **M34 (Phase 1):** added Europe PMC as a second automated discovery
  source alongside M14's PubMed/PMC pipeline (`ke europepmc-candidate-discover`,
  `ke europepmc-candidate-review-prepare`), with its own adjudication
  engine since identity and full-text evidence work differently for
  Europe PMC than for PMC. Scientific-scope and license rules are shared
  with M14's engine (`scientific_scope.py`, `license_rules.py`, extracted
  with zero behavior change). Scoped to discovery and adjudication only --
  not wired into acquisition, and does not resume corpus growth (frozen at
  605 papers). See [docs/history/milestones/m34_europepmc_discovery.md](docs/history/milestones/m34_europepmc_discovery.md).
- **M35 (Phase 1):** added CORE as a third automated discovery source
  (`ke core-candidate-discover`, `ke core-candidate-review-prepare`), with
  its own adjudication engine. CORE's API never returns a license field
  (verified empirically), so every CORE candidate's license rule is
  `incomplete_missing_license` and no CORE candidate can ever auto-accept.
  PMC/Europe PMC overlap detection is a known, deliberate limitation (CORE
  never reports a PMCID). Scoped to discovery and adjudication only -- not
  wired into acquisition, and does not resume corpus growth (frozen at 605
  papers). See [docs/history/milestones/m35_core_discovery.md](docs/history/milestones/m35_core_discovery.md).
- **M36 (Phase 1):** added Unpaywall as a fourth evidence source, but as a
  per-DOI OA-location/license *lookup tool* (`ke unpaywall-doi-lookup`,
  `ke unpaywall-batch-lookup`) rather than a fifth discovery pipeline --
  Unpaywall's topic-search API returned a consistent `HTTP 500` on every
  query tried at build time. Makes no accept/reject/hold decision; intended
  to enrich a DOI already surfaced (and possibly `held`) by another
  pipeline. Requires `KE_UNPAYWALL_EMAIL`. See
  [docs/history/milestones/m36_unpaywall_lookup.md](docs/history/milestones/m36_unpaywall_lookup.md).
- **M37 (Phase 1):** added `ke manual-pdf-preview`/`ke
  manual-pdf-manifest-draft`, so adding a manually-supplied PDF no longer
  means hand-typing a `sources.csv` row -- `PyMuPDFParser` (the same
  parser `ke import` already uses) extracts title/authors/DOI/page-count
  locally, and an optional `--doi-lookup` checks Unpaywall (M36) for
  OA/license evidence. Refuses to draft a manifest row unless license
  evidence already passed. See
  [docs/history/milestones/m37_manual_pdf_preview.md](docs/history/milestones/m37_manual_pdf_preview.md).

These milestone notes preserve the sequence that built the present system.
Later work added corpus-scale evidence extraction, the relationship graph,
Evidence Intelligence, web and AI consumers, and grounding-verified local-LLM
PICO extraction. See [docs/roadmap.md](docs/roadmap.md) for current status and
the next ordered goals.

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
[docs/history/vertical_slice/glp1_vertical_slice_demo_checklist.md](docs/history/vertical_slice/glp1_vertical_slice_demo_checklist.md).
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

The authoritative roadmap is [docs/roadmap.md](docs/roadmap.md). Its current
five-goal sequence is: unify the public showcase and live alpha; benchmark and
improve Ask retrieval; complete one defensible GLP-1/body-weight evidence map;
advance Evidence and Analytical Intelligence over that evaluated foundation;
then migrate web and AI to a parity-tested read-only persistent host when its
operator and security trigger is met.

Historical phase and milestone details remain in the roadmap and
`docs/history/`. They are implementation records, not competing current plans.
The project now prefers retrieval quality and one coherent scientific evidence
map over further corpus growth, cosmetic polish in isolation, or more
autonomous AI.

The first three tasks are therefore:

1. Align the showcase, live alpha, and repository READMEs into one truthful
   guided public journey, with visible snapshot freshness and trust boundaries.
2. Establish a golden-question retrieval benchmark and fix measured ranking
   failures before adding more narration.
3. Complete the GLP-1/body-weight evidence map across key sources,
   populations, limitations, citations, and conservatively reviewed
   relationships. The version 1 map, source-fidelity review, and first bounded
   durability/safety qualifiers are implemented; identified coverage gaps
   remain.

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
