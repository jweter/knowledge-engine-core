# Core Interface Contract

## Purpose

`docs/roadmap.md`'s Release Milestones name `v0.6.0` as the point where
`core`'s output becomes "a consumable interface (not new reasoning logic
in `core` itself) so the separately versioned `knowledge-engine-ai`
package can begin its own reasoning experiments on top of it." This
document is that contract, written early rather than after the fact: what
a future layer (`knowledge-engine-ai`, `knowledge-engine-graph`,
`knowledge-engine-web`, or anything else) needs to know to configure
itself against `core` and consume what `core` produces, without reading
`core`'s own source to reverse-engineer it.

It is a description of what already exists, not a new design. Every
schema, command, and config value below is implemented and tested today.
Where something is explicitly unstable or likely to change before v1.0,
that is called out rather than hidden.

## The seam: what `core` decides, what it deliberately does not

`core` locates, validates, and persists evidence. It never decides what
that evidence means for a person's actual question. Concretely, `core`
never sets or infers:

- `research_question` (Evidence Record field) -- inherently supplied by
  whoever is asking a question, not derivable from a paper's own text.
- `evidence_direction` (Evidence Record field) -- defined *relative to* a
  `research_question`, so it cannot be honestly populated without one.
- Any confidence *rating* beyond the existing free-text `confidence_note`
  field -- see `docs/roadmap/long_term_vision.md`'s Confidence Rating
  Design Guidance. `core`'s job is to make the per-record quality signals
  (study design, sample size, recency, limitations) available; computing
  and compounding a rating from them is explicitly the future
  `knowledge-engine-ai` layer's job.

Any consumer of `core` must supply these itself (today: a human reviewer,
via `ke extraction-review-promote`; in the future: the AI Interface
Layer). This is the one boundary every milestone in this repository has
held to without exception -- see `docs/reference_knowledge_layer_design.md`'s
Addendum for the same boundary redrawn for reference-layer content
specifically.

## Configuration

`core` reads settings via `knowledge_engine.config.Settings`
(`pydantic-settings`, prefix `KE_`, also reads a `.env` file in the
working directory). All fields are optional with sane defaults:

| Env var | Default | Purpose |
|---|---|---|
| `KE_PROJECT_ROOT` | current working directory | Base path other defaults resolve under. |
| `KE_DATA_DIR` | `{project_root}/data` | Where the SQLite database and corpus artifacts live. |
| `KE_DATABASE_URL` | `sqlite:///{data_dir}/knowledge_engine.sqlite3` | Full SQLAlchemy URL; set this to point `core` at a specific database file without touching the default one (e.g. a scratch DB for verification, matching this project's own established pattern for getting a clean database without deleting the default file). |
| `KE_OPENAI_API_KEY` | none | Only read by `ke embedding-generate --generator openai`. |
| `KE_CORE_API_KEY` | none | Only read by the CORE discovery source (`ke core-candidate-discover`), a third-party literature API, not related to this project's own "core" package. |
| `KE_UNPAYWALL_EMAIL` | none | Required by Unpaywall's terms of service for `ke unpaywall-doi-lookup`/`ke unpaywall-batch-lookup`. |

No other configuration surface exists. There is no config *file* format
of `core`'s own (beyond `.env`) -- the CLI and the SQLite database are the
entire interface.

## Data access: two supported paths

**1. The SQLite database directly**, at `resolved_database_url` above.
Read access via SQLAlchemy or any SQLite client is safe for read-only
consumption. `core` uses a lightweight, additive migration model (a
`schema_versions` table; see `docs/technical_debt.md`'s "Lightweight
migrations only" entry) -- schema changes are additive pre-1.0, but the
table layout itself is not yet a versioned, published contract. A
consumer reading the database directly should expect to track `core`
schema changes by watching `CHANGELOG.md`, not assume long-term column
stability before v1.0.

**2. The portable corpus-library snapshot** (`ke corpus-library-export`/
`ke corpus-library-import`, M27) -- a single `.sqlite3` (or `.gz`-
compressed) file containing paper-intrinsic content (title, authors,
abstract, full text, pages, keywords) but deliberately *not* raw PDFs
(archived separately) or embedding vectors (cleared on import, since
`Paper.id` is only unique within one database -- see `docs/phase3_design.md`'s
Open Questions). This is the actual portable artifact: import it into a
fresh database with `ke corpus-library-import --input <file>` rather than
copying the live working database.

## The CLI is the primary API

There is no HTTP API, no RPC layer, no Python package published for
import today -- `ke <command>` is the interface. Full command list is in
`pyproject.toml`'s `[tool.poetry.scripts]` entry point
(`knowledge_engine.entrypoint:app`); the commands a consuming layer is
most likely to actually call:

**Reading what `core` has already validated:**
- `ke search <query>` / `ke answer <question>` -- lexical (FTS5) retrieval.
- `ke vector-search --query-text <text>` -- semantic retrieval (FAISS/Qdrant).
- `ke fused-search <query-text>` -- Reciprocal Rank Fusion of both.
- `ke evidence <records.jsonl>` / `ke evidence-report` -- read/report on
  persisted manual Evidence Records.
- `ke relationship-report` -- read Relationship Records.

**Corpus-building (the pipeline a consumer generally does not re-run
itself, but may need to trigger for a specific paper):**
- `ke corpus-import`, `ke extraction-review-generate`/`-batch-generate`,
  `ke extraction-review-annotate` (M45), `ke extraction-review-promote`.

**Reference-layer live lookups (M41-M45, always background context, see
"the seam" above):**
- `ke reference-lookup` (Wikipedia), `ke rxnorm-lookup`, `ke mesh-lookup`,
  `ke pubchem-lookup`, `ke extraction-review-annotate`.

Every command supports `--output <path>` (JSON/JSONL) where scripting
against it matters, rather than requiring stdout scraping -- prefer that
over parsing Rich-formatted console output, which is for humans and may
reflow.

## Data schemas

### Evidence Record

The unit of validated evidence. Schema version `"0.1"`
(`EVIDENCE_SCHEMA_VERSION` in `knowledge_engine/cli.py`). Required fields
(`REQUIRED_EVIDENCE_FIELDS`):

```
schema_version, evidence_record_id, extraction_method, extraction_status,
source_doi, source_title, source_type, study_type, research_question,
claim_text, evidence_direction, population, intervention, comparator,
outcome, result_summary, source_span, limitations, uncertainty_notes,
confidence_note, provenance, created_for_milestone
```

Optional review fields (`REVIEW_EVIDENCE_FIELDS`): `review_status`
(`draft`/`reviewed`/`needs_revision`/`rejected`), `review_checklist`,
`review_notes`.

`extraction_status` is constrained to exactly two values
(`ALLOWED_EXTRACTION_STATUSES`): `draft_review_required` (every
M19-generated draft, including after promotion -- promotion never
overwrites this) or `draft_manual_prototype` (pre-M19 hand-authored
records). `source_span` validates `paper_id` always, and
`start_offset`/`end_offset` together as non-negative integers with
`start_offset < end_offset` when present.

A record only becomes real evidence via `ke extraction-review-promote`,
which validates with `_validate_evidence_record` (the same validator `ke
evidence-validate` runs) and refuses any record missing
`research_question`/`evidence_direction` -- see "the seam" above. There
is no way to bypass this validation from the CLI.

### Relationship Record

Typed links between two Evidence Records. Required fields
(`REQUIRED_RELATIONSHIP_FIELDS`):

```
schema_version, relationship_id, source_evidence_record_id,
target_evidence_record_id, relationship_type, rationale, provenance,
created_for_milestone
```

`relationship_type` is constrained to exactly four values
(`ALLOWED_RELATIONSHIP_TYPES`): `supports`, `contradicts`, `qualifies`,
`contextualizes` -- reusing `evidence_direction`'s own vocabulary rather
than a separate one (M24). Validated with `ke relationship-validate`,
which also checks referenced `evidence_record_id`s exist when an
`--evidence` file is supplied.

### Draft evidence item (pre-validation)

`ke extraction-review-generate`/`-batch-generate`'s output --
*intentionally incomplete*, never itself a valid Evidence Record. Same
field set as an Evidence Record's `to_dict()` output
(`knowledge_engine/extraction/evidence_items.py`), plus an
`extraction_context` object carrying the M17/M18 audit trail (matched
signal, framing, matched cue, rules versions) a reviewer needs to judge
the extraction without re-deriving it. `research_question`/
`evidence_direction`/`uncertainty_notes`/`confidence_note`/`provenance`
are always `null`; `study_type`/`limitations`/PICO fields are populated
when M26/M28's deterministic extraction detects them, `null` otherwise --
never guessed.

If M45's `ke extraction-review-annotate` has run, each item additionally
carries `reference_context` -- see below.

### Reference-layer lookup results (M41-M44)

Every lookup source returns a JSON object with the same shape family:
`term`, `found` (bool), source-specific identity/definition fields (all
`null` when `found: false`), `source_url`, `license`, `retrieved_at`.
Source-specific fields:

- **Wikipedia** (`ReferenceLookupResult`, M41): `title`, `summary`,
  `page_type` (including `"disambiguation"`), `revision`,
  `permanent_url`.
- **RxNorm** (`RxNormLookupResult`, M42): `rxcui`, `name`, `term_type`,
  `synonym`, `ingredients` (list of `{rxcui, name}` -- compare this, not
  `rxcui`, to recognize a brand name and its generic as the same drug).
- **MeSH** (`MeshLookupResult`, M43): `mesh_id`, `heading`, `scope_note`,
  `synonyms` (list).
- **PubChem** (`PubchemLookupResult`, M44): `cid`, `title`, `iupac_name`,
  `molecular_formula`, `molecular_weight`, `smiles`.

All four: never evidence, never routed through Evidence Record promotion,
never merged into `core`'s own search commands. `license` is a
human-readable string describing real, verified provenance (see each
milestone's own doc for the exact basis) -- not machine-parseable, and
deliberately not run through `license_rules.py`'s CC-family pattern
(which governs the separate paper corpus only).

### `reference_context` (M45)

Added to a draft evidence item by `ke extraction-review-annotate`. An
object with keys `intervention`/`comparator`/`population`/`outcome`,
each either `null` (nothing to look up) or one of the RxNorm/MeSH shapes
above plus a `source` key (`"rxnorm"` or `"mesh"`). See
`docs/m45_extraction_review_annotate.md` for what "found" actually means
here (a single matched candidate word, not the whole raw field) and its
real cost profile (roughly a minute or more of network calls per real
paper).

### Corpus source metadata (`sources.csv`)

The curated overlay a corpus directory (e.g.
`data/corpora/glp1_weight_loss/`) carries alongside the database, one row
per included/excluded paper:

```
source_id, title, authors, publication_year, venue, doi, pmid, arxiv_id,
other_identifier, source_url, pdf_url, local_path, access_date,
license_type, license_url, usage_status, inclusion_status,
inclusion_reason, exclusion_reason, expected_content_hash, source_type,
study_type, population, intervention, comparator, outcome_notes, notes
```

`inclusion_status`/`inclusion_reason`/`exclusion_reason` are the human
audit trail for why a paper is or is not in the corpus.
`license_type`/`license_url` record the CC BY/CC0 basis
`license_rules.py`'s `ALLOWED_LICENSE_PATTERN` requires for inclusion.
**Known gap, not yet built** (see `docs/roadmap.md`'s M14 corpus-growth
section): this file records only current inclusions, not a durable
ledger of previously-rejected records, so a consumer building its own
duplicate/exclusion tracking should not assume absence from this file
means "never considered."

## Versioning and stability

Nothing here is published under semantic versioning yet (`core` is
`0.2.0a1`). Treat as stable now: the Evidence/Relationship Record field
sets and their `ALLOWED_*` enums (changing these is a breaking schema
change and would be called out loudly in `CHANGELOG.md`); the CLI command
names and their `--output` JSON shapes for the commands listed above.
Treat as likely to evolve before v1.0: the raw SQLite table layout (no
long-term column-stability guarantee pre-1.0, per
`docs/technical_debt.md`); exact wording of `license`/error-message
strings (never parse these; use the structured fields).

Each extraction stage's own rules version is stamped into its output for
traceability, not for consumers to branch on:
`SECTION_DETECTION_RULES_VERSION` (`m16-section-detection-v2`),
`CLAIM_CANDIDATE_RULES_VERSION` (`m17-claim-candidate-v1`),
`CLAIM_FRAMING_RULES_VERSION` (`m18-claim-framing-v1`),
`DRAFT_EVIDENCE_ITEM_RULES_VERSION` (`m19-draft-evidence-item-v1`),
`STUDY_DESIGN_RULES_VERSION` (`m26-study-design-v2`),
`PICO_EXTRACTION_RULES_VERSION` (`m28-pico-v2`),
`EXTRACTION_REVIEW_ANNOTATE_RULES_VERSION` (`m45-extraction-review-annotate-v2`).
A future re-run with a bumped ruleset is never automatic (M25) -- a human
decides when to re-invoke extraction for a given paper.

## What does not exist yet

- No Knowledge Graph (Phase 4, unstarted) -- there is no `concept`,
  `claim`-as-graph-node, or typed contradiction/support edge beyond the
  Relationship Record's flat four-type vocabulary above. This document
  will need a Graph section once Phase 4 exists.
- No HTTP/RPC API -- the CLI and direct SQLite/corpus-library access are
  the only interfaces.
- No published Python package -- importing `knowledge_engine` modules
  directly from another repository is possible today (it is plain
  Python) but not a supported, versioned interface; go through the CLI.
- No formal confidence rating of any kind -- see "the seam" above.
