# M6 Phase 1 Corpus Ingestion Plan

## Executive Summary

M6 defines the implementation-ready architecture for Phase 1 corpus ingestion.
It is a design milestone, not an implementation milestone.

The next major capability for Knowledge Engine Core is reproducible ingestion of
focused scientific corpora. Phase 0 proved that individual PDFs can be parsed,
stored in SQLite, indexed with FTS5, and retrieved. The GLP-1 vertical slice
proved that curated corpus metadata, legal source provenance, manual evidence
records, validation, and no-synthesis boundaries can be made visible to users.

Phase 1 should now turn those lessons into a durable ingestion workflow:

```text
corpus definition
  -> source manifest
  -> manifest validation
  -> import run
  -> import items
  -> legal/provenance checks
  -> local file discovery
  -> file hashing
  -> duplicate evaluation
  -> parsing
  -> metadata capture
  -> persistence
  -> warnings/errors
  -> run summary
  -> resumable rerun
  -> human review
```

The first implementation step should be deliberately small. M7 should implement
manifest validation and dry-run reporting only. It should not parse PDFs, write
papers to the database, create import-run tables, download files, enrich
metadata, or perform scientific synthesis.

## Current State

### What Already Exists

- A Python 3.12+ package managed with Poetry.
- A Typer CLI with Rich output.
- A `ke import` command for one local PDF at a time.
- A PyMuPDF parser returning `ParsedPaper`.
- SHA-256 content hashing through `knowledge_engine.utils.file_sha256`.
- SQLite persistence through SQLAlchemy models.
- A `papers` table with unique `source_path`, unique `content_hash`, and unique
  DOI when present.
- A `paper_texts` table for extracted raw and body text.
- Author, journal, keyword, and relationship tables for Phase 0 metadata.
- SQLite FTS5 search through `paper_search`.
- Retrieval-oriented commands such as `ke answer`.
- Display-time corpus metadata overlay from `sources.csv`.
- Manual evidence JSONL records, validation, display, and local report
  generation for the GLP-1 demo.
- A small GLP-1 corpus directory with a corpus JSON file, `sources.csv`,
  inclusion/exclusion criteria, license policy, and a demo checklist.
- Tests for parser behavior, repository writes, search, retrieval, metadata
  overlay, evidence validation, and evidence reports.

### Reusable Pieces

- `DocumentParser` and `PyMuPDFParser` can remain the parser boundary.
- `ParsedPaper` can remain the parser output for PDF papers until a more general
  parsed document type is needed.
- `file_sha256` should be reused for exact file identity.
- `PaperRepository.add_parsed_paper` can remain the final storage operation for
  single-paper persistence during early Phase 1.
- SQLite FTS5 remains the search baseline.
- The GLP-1 `corpus.json` and `sources.csv` provide a useful seed shape for a
  real manifest, but their fields need versioning, validation rules, legal-use
  gating, and stricter identity semantics.
- Evidence JSONL validation shows that small, explicit validation helpers are
  effective before heavier persistence is introduced.

### What Is Missing

- A versioned manifest contract.
- A manifest validation command.
- Structured legal-use status and blocking behavior.
- Relative-path security checks for local source documents.
- Import run identity.
- Import item identity.
- Import status lifecycle.
- Manifest snapshots.
- Run summaries.
- Structured warnings and errors.
- Field-level metadata provenance.
- Duplicate candidate records beyond current database uniqueness errors.
- Resumable import semantics.
- Retry semantics.
- A migration strategy for new ingestion tables.
- Tests for manifest parsing, validation, dry-run behavior, legal gating, path
  safety, duplicate source IDs, and hash formats.

### What the Vertical Slice Taught Us

- Curated metadata is essential. Parser-derived metadata is useful but too weak
  to be trusted as the primary display source for real scientific work.
- DOI normalization is necessary for matching across sources, database records,
  and manual evidence files.
- Legal provenance must be visible before import, not reconstructed afterward.
- Local PDFs should remain ignored artifacts; committed metadata must be enough
  to reproduce source selection without committing full text or copyrighted
  documents.
- Manual records can be safer than premature automation if review status and
  provenance are explicit.
- Users need repeated reminders when a workflow is retrieval-only or
  review-only.
- Generated reports are useful local artifacts but should remain ignored until
  a future milestone creates sanitized committed examples.
- CLI helper functions can grow quickly; Phase 1 should introduce focused
  service modules rather than continuing to expand `cli.py`.

### Outdated Assumptions in the Original Phase 1 Design

- The original target of 500 to 1,000 papers is still a long-term Phase 1 goal,
  but it is too large for the first implementation milestone.
- The first manifest should not be a single CSV or JSONL file. A small JSON file
  for corpus-level metadata plus a CSV file for source rows is clearer and
  matches the existing GLP-1 corpus structure.
- Metadata enrichment should not be part of the first ingestion implementation.
  Manifest validation and legal gating should come first.
- Import-run tables should not be the first step. They need a migration
  decision and table design. M7 can produce dry-run summaries without schema
  changes.
- Exact hash and DOI duplicates should not always be automatic skips without
  preserving duplicate evidence. The system needs an explicit duplicate outcome
  model.
- "Paper" should not be treated as the whole knowledge model. Phase 1 should
  preserve source identity, document identity, local file identity, canonical
  paper identity, and import attempt identity separately.

## Goals

- Define a durable Phase 1 ingestion workflow.
- Start with a small, inspectable pilot before scaling.
- Preserve legal provenance and source identity.
- Make manifest validation deterministic and reviewable.
- Keep local file paths safe and relative.
- Detect exact and likely duplicates conservatively.
- Preserve conflicting metadata values instead of silently overwriting them.
- Allow partial success and safe reruns.
- Record warnings, errors, and run summaries in a machine-readable way.
- Remain compatible with the existing Phase 0 source vault where practical.
- Keep the system offline-capable by default.
- Keep future adapters for PubMed, Crossref, OCR, PostgreSQL, and distributed
  workers possible without designing them prematurely.

## Non-Goals

- Bulk ingestion implementation in M6.
- Importing hundreds of papers in the next milestone.
- Downloading PDFs automatically.
- AI, embeddings, automated evidence extraction, scientific synthesis,
  consensus, confidence scoring, graph databases, APIs, or web interfaces.
- Metadata enrichment adapters in M7.
- Database schema changes in M7.
- Parser redesign in M7.
- Fuzzy duplicate merging in M7.
- Automatic correction of curated metadata.
- Committing local PDFs, SQLite databases, generated reports, or cache files.

## Proposed Ingestion Workflow

### Stage 1: Corpus Definition

Input:
- A versioned corpus JSON file.

Output:
- Parsed corpus-level configuration.

Responsibility:
- Define corpus identity, purpose, research question, legal policy, source CSV
  path, local paper directory, and human notes.

Failure modes:
- Missing file.
- Malformed JSON.
- Unsupported `manifest_version`.
- Missing required fields.
- Source CSV path missing.

Persisted state:
- In M7, none. Later, a manifest snapshot should be recorded with an import run.

Automatic or manual:
- Manual authoring, automatic validation.

### Stage 2: Source Manifest

Input:
- The CSV referenced by the corpus JSON.

Output:
- Parsed manifest rows with line numbers and normalized identifiers.

Responsibility:
- List candidate sources, local paths, legal status, identifiers, expected
  hashes, inclusion decisions, and provenance.

Failure modes:
- Missing CSV.
- Missing required columns.
- Duplicate `source_id`.
- Malformed row.
- Unsupported usage status.
- Absolute or escaping local path.

Persisted state:
- In M7, dry-run summary only. Later, manifest rows should become import items.

Automatic or manual:
- Manual curation, automatic validation.

### Stage 3: Manifest Validation

Input:
- Parsed corpus JSON and source CSV rows.

Output:
- Validation result containing blocking errors, warnings, counts, and normalized
  values.

Responsibility:
- Confirm the manifest is safe and coherent before any import work occurs.

Failure modes:
- Blocking validation errors prevent import.
- Non-blocking warnings allow dry-run success with review notes.

Persisted state:
- In M7, none by default. Optional JSON dry-run report may be added later.

Automatic or manual:
- Automatic validation with human review of output.

### Stage 4: Import Run

Input:
- Validated corpus definition.
- User command and options.
- Current code version.

Output:
- Import run identity and run status.

Responsibility:
- Represent one execution of the ingestion workflow.

Failure modes:
- Cannot create run state.
- Manifest snapshot cannot be recorded.
- Database unavailable.

Persisted state:
- Recommended from M8 onward: SQLite `import_runs` row plus manifest snapshot.

Automatic or manual:
- Automatic once real import begins.

### Stage 5: Import Items

Input:
- Validated manifest rows.
- Import run identity.

Output:
- One import item per source row.

Responsibility:
- Track per-source status, warnings, errors, duplicate outcomes, parser output,
  and persistence result.

Failure modes:
- Item cannot be initialized.
- Item has blocking legal/path/hash/duplicate/parser errors.

Persisted state:
- Recommended from M8 onward: SQLite `import_items` rows.

Automatic or manual:
- Automatic with human review of failed or `needs_review` items.

### Stage 6: Legal and Provenance Checks

Input:
- Manifest row legal fields.

Output:
- Legal-use decision for the item.

Responsibility:
- Gate imports so unclear or disallowed full-text use does not enter the local
  source vault by accident.

Failure modes:
- Missing usage status.
- Usage status not approved for local full-text import.
- Missing source URL or access date for included source.
- Missing license evidence where required.

Persisted state:
- Legal status, source URL, access date, license type, license URL, and decision
  rationale should be stored with import item and source provenance.

Automatic or manual:
- Manual curation of legal fields, automatic enforcement.

### Stage 7: Local File Discovery

Input:
- Manifest row `local_path`.
- Corpus default local papers directory.

Output:
- Resolved local file candidate under the project or allowed corpus directory.

Responsibility:
- Find local files without allowing path escapes or absolute private paths.

Failure modes:
- Missing local path.
- File not found.
- Absolute path.
- Path escapes the configured local papers directory.
- Directory path supplied instead of file.
- Unsupported file extension.

Persisted state:
- Local relative path and file existence result. Avoid storing private absolute
  paths.

Automatic or manual:
- Automatic validation of manually provided paths.

### Stage 8: File Hashing

Input:
- Valid local file.

Output:
- Content hash such as `sha256:<hex>`.

Responsibility:
- Establish exact local file identity.

Failure modes:
- File unreadable.
- Hash mismatch against expected hash.
- Unsupported expected hash algorithm.

Persisted state:
- Computed hash, expected hash, algorithm, and mismatch warning/error.

Automatic or manual:
- Automatic.

### Stage 9: Duplicate Evaluation

Input:
- Computed content hash.
- Normalized DOI and other identifiers.
- Source ID.
- Normalized title/year.
- Existing database records.
- Previous import items.

Output:
- Duplicate outcome and candidate list.

Responsibility:
- Avoid corrupting the database or losing provenance when a source has already
  been imported or may represent the same paper.

Failure modes:
- Conflicting identifiers.
- Exact hash already exists.
- DOI already exists with different file hash.
- Possible title/year duplicate.

Persisted state:
- Duplicate candidates, matching method, severity, action taken, and reviewer
  requirement.

Automatic or manual:
- Automatic detection, conservative human review for uncertain cases.

### Stage 10: Parsing

Input:
- Local PDF file selected for import.

Output:
- `ParsedPaper` or parser failure.

Responsibility:
- Extract text, parser-derived metadata, content hash, page count, and word
  count.

Failure modes:
- Unsupported file type.
- Encrypted PDF.
- Unreadable PDF.
- Parser exception.
- Empty extracted text.
- Missing DOI.
- Poor metadata extraction.

Persisted state:
- Parser status, parser name/version, diagnostics, page count, word count,
  metadata candidates, and failure details.

Automatic or manual:
- Automatic, with human review of warnings/failures.

### Stage 11: Metadata Capture

Input:
- Curated manifest metadata.
- Parser-derived metadata.
- Future external metadata candidates.

Output:
- Preferred metadata values plus preserved candidates and provenance.

Responsibility:
- Keep curated metadata separate from parser output and preserve conflicts.

Failure modes:
- Missing title.
- Conflicting DOI.
- Conflicting year.
- Parser title is garbage.
- License metadata incomplete.

Persisted state:
- In early import, preferred values may still land in existing `papers` fields.
  From M8 or M11 onward, metadata candidates and provenance should be stored
  separately.

Automatic or manual:
- Automatic application of precedence rules, manual review for conflicts.

### Stage 12: Persistence

Input:
- Parsed paper.
- Preferred metadata.
- Import item context.

Output:
- Stored paper, extracted text, authors, keywords, FTS row, and import item
  result.

Responsibility:
- Reuse Phase 0 source vault while preserving import-run context.

Failure modes:
- Unique constraint violation.
- Database write failure.
- FTS write failure.
- Transaction rollback.

Persisted state:
- Paper and text records; import item status and result from M8 onward.

Automatic or manual:
- Automatic.

### Stage 13: Warnings and Errors

Input:
- Validation, duplicate, parser, metadata, and persistence events.

Output:
- Structured warnings/errors with user-facing messages.

Responsibility:
- Make partial success and failures explainable and reproducible.

Failure modes:
- Unclassified exception.
- Message lacks enough context for retry.

Persisted state:
- M8 should persist warnings and errors with run/item scope.

Automatic or manual:
- Automatic.

### Stage 14: Run Summary

Input:
- Import run and item outcomes.

Output:
- Human-readable and machine-readable summary.

Responsibility:
- Show what happened, what changed, what failed, what was skipped, and what
  needs review.

Failure modes:
- Summary generation fails.
- Summary omits blocking warnings or duplicate decisions.

Persisted state:
- JSON summary can be stored locally; import-run tables should preserve core
  counts.

Automatic or manual:
- Automatic output, human review.

### Stage 15: Resumable Rerun

Input:
- Prior import run.
- Same manifest or new manifest snapshot.
- User retry options.

Output:
- New run or resumed run that skips already-successful items and retries
  eligible failures.

Responsibility:
- Make interrupted imports safe and deterministic.

Failure modes:
- Manifest changed without snapshot comparison.
- Successful item imported again.
- Failed item retried without user intent.
- Hash changed for same local path.

Persisted state:
- Prior run linkage, item attempt history, content hashes, statuses, and retry
  policy.

Automatic or manual:
- Automatic idempotency, manual retry decisions.

### Stage 16: Human Review

Input:
- Run summary.
- Warnings.
- Errors.
- Duplicate candidates.
- Metadata conflicts.

Output:
- Review decisions for uncertain items.

Responsibility:
- Keep legal, duplicate, and metadata uncertainty visible rather than hidden.

Failure modes:
- Reviewer decisions are not recorded.
- Review status is confused with scientific review.

Persisted state:
- Later milestones should store reviewer decisions and timestamps.

Automatic or manual:
- Manual.

## Conceptual Entities

### Corpus

Responsibility:
A reproducible, scoped collection of source documents assembled for a domain,
question, release, or benchmark.

Boundary:
A corpus is not the same as a database table or local folder. It is the
documented scope and inclusion policy for a collection.

### Corpus Definition

Responsibility:
The corpus-level JSON file describing corpus identity, research question,
manifest version, source CSV path, local papers directory, legal policy, and
notes.

Boundary:
It defines the corpus; it does not list every source row directly.

### Source Manifest

Responsibility:
The versioned source-row file referenced by the corpus definition.

Boundary:
It declares intended inputs. It is not proof that import succeeded.

### Manifest Row

Responsibility:
One curated source entry in the source manifest.

Boundary:
A manifest row is not a paper record, not an import item, and not a local file.
It is a planned source entry.

### Import Run

Responsibility:
One execution of an ingestion workflow against a corpus definition.

Boundary:
An import run records an attempt. It is not the corpus itself.

### Import Item

Responsibility:
The run-specific processing state for one manifest row.

Boundary:
An import item is not the source and not the canonical paper. It is an attempt
to validate, parse, and possibly persist one source document during one run.

### Source

Responsibility:
The intellectual or scientific source being represented, such as a journal
article, preprint, patent, dataset, or clinical trial record.

Boundary:
A source may have multiple documents, local files, identifiers, and import
attempts.

### Source Document

Responsibility:
A concrete representation of a source that can be parsed or cited, usually a
PDF in Phase 1.

Boundary:
A source document is not identical to a local file. The same document content
may exist at multiple paths or URLs.

### Local File

Responsibility:
A file on the user's machine used as an input to parsing.

Boundary:
Local file identity is path plus observed file content. It should not become the
canonical scientific identity.

### Canonical Paper

Responsibility:
The Phase 0 database representation of a scientific paper after import.

Boundary:
It is the current storage model for papers, not the whole scientific knowledge
model and not necessarily the same as source identity.

### Content Hash

Responsibility:
An exact fingerprint of a local file or source document content.

Boundary:
It detects identical bytes. It does not prove that two different files are
different papers.

### Source Identifier

Responsibility:
A stable identifier for source identity, such as DOI, PMID, arXiv ID, trial ID,
patent number, or corpus-local `source_id`.

Boundary:
Identifiers can conflict or be missing. They should be normalized and preserved
with provenance.

### Duplicate Candidate

Responsibility:
A detected possible overlap between a manifest row, local file, source
document, canonical paper, or previous import item.

Boundary:
A candidate is not an automatic merge decision unless the match type is exact
and policy says it is safe.

### Import Warning

Responsibility:
A non-blocking issue that should be visible to users and reviewers.

Boundary:
Warnings do not prevent dry-run success or import unless policy escalates them.

### Import Error

Responsibility:
A blocking issue for a row, item, or run.

Boundary:
Errors should be structured, retry-aware, and scoped to run or item.

### Import Result

Responsibility:
The final outcome for one import item, including status, stored paper ID when
available, warnings, errors, and duplicate outcome.

Boundary:
It summarizes an attempt; it is not the source itself.

### Import Summary

Responsibility:
Run-level counts, outcomes, warnings, errors, duplicate decisions, and review
needs.

Boundary:
It is a report over a run, not the durable source vault.

### Metadata Candidate

Responsibility:
A proposed metadata value from a manifest, parser, or future external adapter.

Boundary:
Candidates are not automatically preferred values.

### Curated Metadata

Responsibility:
Metadata intentionally supplied or reviewed by a human curator.

Boundary:
Curated metadata can be wrong, but it should not be silently overwritten by
parser output.

### Parser-Derived Metadata

Responsibility:
Metadata extracted from the source document by the parser.

Boundary:
Parser-derived values are candidates with parser provenance, not authoritative
truth.

## Identity Boundaries

The ingestion architecture must clearly distinguish:

- Source identity: the intellectual source, usually anchored by DOI, PMID, arXiv
  ID, or another stable source identifier.
- Document identity: the representation of the source, such as publisher PDF,
  author manuscript PDF, JATS XML, or HTML.
- Canonical paper identity: the stored `papers.id` row in the current SQLite
  source vault.
- Local file identity: a local path plus observed content hash.
- Import attempt identity: one import item inside one import run.

Conflating these identities is the fastest way to make resumability and
duplicate handling fragile.

## Manifest Design

Phase 1 should use:

- One small JSON file for corpus-level metadata.
- One CSV file for source rows.

This is more maintainable than a single large JSON file because corpus-level
metadata changes less often than source rows, and source rows are easier for
contributors to inspect and edit in CSV form.

Corpus metadata files and local source documents intentionally use different
base directories:

- Corpus metadata paths are resolved relative to the directory containing
  `corpus.json`.
- Local document paths are resolved relative to the repository/project root and
  the configured local papers directory.

This keeps committed corpus metadata portable while keeping local PDFs outside
version control.

### Corpus JSON Fields

Recommended file name:

```text
corpus.json
```

Fields:

| Field | Required | Source | Notes |
| --- | --- | --- | --- |
| `manifest_version` | yes | manual | Integer manifest contract version. Initial supported value is `1`. |
| `corpus_id` | yes | manual | Stable lowercase identifier, unique in the repository. |
| `name` | yes | manual | Human-readable corpus name. |
| `description` | yes | manual | Short purpose statement. |
| `scientific_domain` | yes | manual | Broad domain such as metabolic disease. |
| `research_question` | yes | manual | Main research question or object with `question_id` and `text`. |
| `created_at` | yes | manual | ISO 8601 date or datetime. |
| `updated_at` | yes | manual | ISO 8601 date or datetime. |
| `license_policy` | yes | manual | Path relative to the directory containing `corpus.json`; example: `license_policy.md`. |
| `source_manifest` | yes | manual | Path relative to the directory containing `corpus.json`; example: `sources.csv`. |
| `default_local_papers_directory` | yes | local-only/manual | Path relative to the repository/project root; example: `papers/corpora/glp1_weight_loss`. |
| `notes` | no | manual | Human-readable curation notes. |

`manifest_version` must be a JSON integer, not a semantic-version string. Future
breaking manifest contracts increment the integer. Unsupported values are
blocking validation errors.

### Source CSV Fields

Recommended file name:

```text
sources.csv
```

Fields:

| Field | Required | Source | Notes |
| --- | --- | --- | --- |
| `source_id` | yes | manual | Stable corpus-local identifier. |
| `title` | yes | curated metadata | Preferred curated title or best available title. |
| `authors` | no | curated metadata | Semicolon-delimited author names initially. |
| `publication_year` | no | curated metadata | Four-digit year when known. |
| `venue` | no | curated metadata | Journal, conference, repository, or venue. |
| `doi` | no | curated/external | DOI, normalized for comparison. |
| `pmid` | no | curated/external | PubMed ID. |
| `arxiv_id` | no | curated/external | arXiv identifier. |
| `other_identifier` | no | curated/external | Stable identifier not covered above. |
| `source_url` | yes for included rows | manual provenance | Landing page or stable source page. |
| `pdf_url` | no | manual provenance | Direct PDF URL when legally available. |
| `local_path` | no until import | local-only | Path relative to `default_local_papers_directory`; example: `fphar-2022-935823.pdf`. |
| `access_date` | yes for included rows | manual provenance | Date source was accessed. |
| `license_type` | yes for approved full text | manual provenance | Example: `CC-BY`, `CC-BY-NC`, `public_domain`, `local_use_only`. |
| `license_url` | yes for open licenses | manual provenance | URL proving license status. |
| `usage_status` | yes | manual legal status | Controlled vocabulary. |
| `inclusion_status` | yes | manual curation | Controlled vocabulary. |
| `inclusion_reason` | yes for included rows | manual curation | Why it belongs. |
| `exclusion_reason` | no | manual curation | Required when excluded. |
| `expected_content_hash` | no | machine/manual | Format: `sha256:<64 lowercase hex>`. |
| `notes` | no | manual | Curation notes. |

`publication_year` is the canonical Phase 1 source CSV field. For M7 only, the
existing legacy `year` column may be accepted as a compatibility alias. M7 must
not rewrite the CSV.

`local_path` must name a file relative to `default_local_papers_directory`. It
must not repeat the configured papers directory. For example, if
`default_local_papers_directory` is `papers/corpora/glp1_weight_loss`, the source
row should use `fphar-2022-935823.pdf`, not
`papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf`.

### Field Classifications

Required:
- `source_id`
- `title`
- `source_url` for included rows
- `access_date` for included rows
- `usage_status`
- `inclusion_status`
- `inclusion_reason` for included rows

Optional:
- `authors`
- `publication_year`
- `venue`
- `doi`
- `pmid`
- `arxiv_id`
- `other_identifier`
- `pdf_url`
- `local_path`
- `license_url`
- `exclusion_reason`
- `expected_content_hash`
- `notes`

Manually curated:
- `source_id`
- `title`
- `authors`
- `publication_year`
- `venue`
- `source_url`
- `pdf_url`
- `access_date`
- `license_type`
- `license_url`
- `usage_status`
- `inclusion_status`
- `inclusion_reason`
- `exclusion_reason`
- `notes`

Parser-derived:
- None in the manifest. Parser-derived metadata should be captured during import
  as metadata candidates, not written back into curated manifest fields.

Externally enriched:
- `doi`
- `pmid`
- `arxiv_id`
- `other_identifier`
- Future enriched title/authors/venue/year candidates.

Local-only:
- `local_path`
- `expected_content_hash`

Machine-generated:
- `expected_content_hash` when produced by an import or hash command.
- Future import item IDs and run summaries.

### Controlled Vocabularies

`usage_status`:
- `approved_open_access`
- `approved_public_domain`
- `approved_author_manuscript`
- `approved_local_only`
- `metadata_only`
- `needs_legal_review`
- `excluded_legal`

`inclusion_status`:
- `included`
- `candidate`
- `excluded`
- `deferred`

M7 should validate the vocabularies but not implement legal analysis. Humans
curate the fields; the system enforces the declared policy.

## Manifest Validation Rules

Corpus JSON:
- Must be valid JSON.
- Must have integer `manifest_version`.
- Must have supported `manifest_version`; M7 supports only `1`.
- `corpus_id` must match `^[a-z0-9][a-z0-9_\\-]*$`.
- `source_manifest` must be relative to the directory containing `corpus.json`.
- `license_policy` must be relative to the directory containing `corpus.json`.
- `default_local_papers_directory` must be relative to the repository/project
  root.
- Paths must not be absolute.
- Metadata paths must not escape the directory containing `corpus.json`.
- `default_local_papers_directory` must not escape the repository/project root.
- Referenced files must exist for validation.
- Paths must be resolved canonically before containment checks.

Source CSV:
- Must be valid CSV with headers.
- Required columns must be present.
- `source_id` must be unique within the corpus.
- `source_id` must match `^[a-z0-9][a-z0-9_\\-]*$`.
- DOI should be normalized before comparison.
- `publication_year`, when present, must be four digits.
- M7 may accept legacy `year` as a compatibility alias only:
  - if `publication_year` exists, use it;
  - if only `year` exists, accept it and emit a deterministic warning that
    `year` is deprecated and should be renamed to `publication_year`;
  - if both fields exist with the same value, accept them and warn that `year`
    is redundant;
  - if both fields exist with conflicting non-empty values, produce a blocking
    error;
  - remove this alias only in a later manifest-version change.
- `local_path`, when present, must be relative to
  `default_local_papers_directory`.
- `local_path` must not repeat the configured papers directory.
- `local_path` must not be absolute.
- `local_path` must not contain path traversal.
- `local_path` must not escape the configured local papers directory after
  canonical resolution.
- Symlink or canonical-resolution escape from the allowed local papers directory
  must be rejected.
- When `--check-files` is used, included rows with importable usage status must
  have `local_path`; missing paths block import readiness but do not make an
  otherwise valid manifest structurally invalid.
- User-facing output should use committed relative paths rather than private
  absolute paths.
- `usage_status` must use the controlled vocabulary.
- `inclusion_status` must use the controlled vocabulary.
- Included rows must have source provenance: `source_url`, `access_date`, and
  `inclusion_reason`.
- Rows approved for full-text import must have a legal basis:
  `license_type` or a clear `usage_status`.
- Missing optional metadata should not block dry-run validation.
- Missing legal approval should block real import.
- Missing local files should be a warning for validation-only mode and a
  blocking error for import mode.
- `expected_content_hash`, when present, must include an algorithm prefix such
  as `sha256:`.
- Hash algorithms outside an allowlist should be blocking errors.
- Duplicate DOI values should be warnings or errors depending on whether the
  rows intentionally represent different document versions.

## Metadata Precedence

Metadata precedence should be field-specific, but the default order should be:

1. Manually reviewed curated metadata.
2. Trusted external metadata adapter.
3. Manifest metadata.
4. Parser-derived metadata.
5. Unknown.

In M7, there are no external adapters and no parser step. The first
implementation should still define the future precedence model so manifest
validation and import reports can preserve the right provenance.

### Title

Source of truth:
- Reviewed curated metadata.

Fallback order:
1. Reviewed curated title.
2. External provider title.
3. Manifest title.
4. Parser-derived title.
5. File stem as last resort.

Conflicts:
- Preserve parser and provider title candidates if they differ materially.

Overwrite:
- Parser output must not overwrite curated title.

Provenance:
- Record provider, manifest row, parser name/version, and review status.

### Authors

Source of truth:
- Reviewed curated or trusted external author list.

Fallback order:
1. Reviewed curated authors.
2. PubMed/Crossref authors.
3. Manifest authors.
4. Parser-derived authors.
5. Unknown.

Conflicts:
- Preserve ordering and source. Parser author extraction is often weak.

Overwrite:
- Only human review should replace preferred authors.

Provenance:
- Record source, timestamp, and whether ordering was preserved.

### Year

Source of truth:
- Trusted bibliographic metadata or reviewed curated value.

Fallback order:
1. Reviewed curated year.
2. External provider year.
3. Manifest year.
4. Parser-derived year.
5. Unknown.

Conflicts:
- Preserve all candidate years; flag conflicts.

Overwrite:
- No silent overwrite.

Provenance:
- Record field source and original value.

### Journal or Venue

Source of truth:
- Reviewed curated venue or trusted external metadata.

Fallback order:
1. Reviewed curated venue.
2. External provider venue.
3. Manifest venue.
4. Parser-derived venue.
5. Unknown.

Conflicts:
- Preserve abbreviations and full names as candidates where possible.

Overwrite:
- No parser overwrite.

Provenance:
- Record provider and normalized display value.

### DOI

Source of truth:
- Normalized DOI with strongest provenance from publisher, Crossref, PubMed, or
  reviewed manifest.

Fallback order:
1. Reviewed curated DOI.
2. External provider DOI.
3. Manifest DOI.
4. Parser-derived DOI.
5. Unknown.

Conflicts:
- Conflicting DOI values are blocking for automatic import unless human review
  marks the conflict as understood.

Overwrite:
- Never silently overwrite DOI.

Provenance:
- Preserve original DOI string and normalized DOI for each candidate.

### Abstract

Source of truth:
- External provider abstract or reviewed source text, depending on license and
  provenance.

Fallback order:
1. Reviewed curated abstract if explicitly allowed.
2. External provider abstract.
3. Parser-derived abstract.
4. Unknown.

Conflicts:
- Preserve source. Abstracts can differ between publisher, PubMed, and PDF.

Overwrite:
- No silent overwrite.

Provenance:
- Record provider or parser source and extraction method.

### License

Source of truth:
- Curated legal/provenance fields.

Fallback order:
1. Reviewed curated license type and URL.
2. Publisher license page.
3. Repository license metadata.
4. Unknown.

Conflicts:
- License conflicts block import until reviewed.

Overwrite:
- Parser output should not affect license.

Provenance:
- Record license URL, access date, source URL, and curator notes.

### Source URL

Source of truth:
- Curated manifest URL.

Fallback order:
1. Reviewed source URL.
2. Manifest source URL.
3. External provider URL.
4. PDF URL.
5. Unknown.

Conflicts:
- Multiple URLs may be valid. Preserve landing page and PDF URL separately.

Overwrite:
- No silent overwrite.

Provenance:
- Record access date and URL role.

## Identity and Duplicate Detection

Duplicate detection should be conservative and layered:

1. Exact content hash.
2. Normalized DOI.
3. PMID or stable external identifier.
4. Source ID.
5. Normalized title plus publication year.
6. Filename or local path.
7. Possible duplicate requiring human review.

### Duplicate Outcomes

`new_source`:
- No meaningful duplicate candidate found.

`exact_file_duplicate`:
- Same content hash already exists.

`same_paper_same_file`:
- Same DOI or identifier and same content hash.

`same_paper_different_file`:
- Same DOI or stable identifier but different content hash. May represent
  publisher PDF versus author manuscript, updated PDF, or corrupted file.

`metadata_duplicate`:
- Same title/year or other metadata suggests same paper, but identifiers are
  missing or inconclusive.

`possible_duplicate`:
- Similar enough to require human review.

`conflicting_identifiers`:
- Strong identifiers disagree, such as same DOI with different PMID or same
  source row pointing to two unrelated titles.

`replacement_document`:
- A reviewed decision says a new document should replace an older local file.

`superseded_document`:
- A reviewed decision says an older document remains traceable but should not be
  preferred.

`skipped`:
- Item was intentionally not imported.

`failed`:
- Duplicate evaluation or import failed.

`requires_human_review`:
- Automatic policy cannot decide safely.

### Duplicate Evidence to Preserve

When duplicate candidates are found, preserve:

- Matching strategy.
- Candidate source IDs.
- Existing paper IDs.
- Existing content hashes.
- New content hash.
- DOI/PMID/arXiv/other identifiers.
- Normalized title/year comparison.
- Local paths.
- Source URLs and PDF URLs.
- Import run and item IDs.
- Decision taken.
- Whether human review is required.

Do not automatically merge uncertain records.

## Import Run Lifecycle

Statuses:

- `created`: run object exists but validation has not started.
- `validating`: manifest and source rows are being checked.
- `ready`: validation passed and import can begin.
- `running`: import items are being processed.
- `partially_succeeded`: at least one item succeeded and at least one item
  failed, was skipped, or needs review.
- `succeeded`: all importable items succeeded or were intentionally skipped by
  policy.
- `failed`: run-level failure prevented meaningful completion.
- `cancelled`: user stopped the run.

Legal state transitions:
- A run cannot move to `ready` for real import if any included source lacks
  approved legal status.
- A run may move to `ready` for dry-run validation with legal warnings, but the
  dry-run result must clearly say real import would be blocked.

Successful run:
- A run is successful when every eligible item has a terminal non-error outcome:
  `succeeded`, `skipped`, or confirmed duplicate skip.

Partial success:
- Represented by `partially_succeeded` with item-level detail.

Retry:
- Failed items can be retried when their error category is retryable.
- Successful items are skipped on rerun unless the user requests reprocess and
  the policy allows it.

Idempotency:
- Use manifest snapshot identity, source ID, content hash, normalized DOI, and
  prior item status to avoid duplicate imports.

Resume:
- Resume should compare the current manifest to the saved snapshot. If the
  manifest changed, create a new run or require explicit user confirmation.

New run relation:
- A new run may reference an earlier run as `rerun_of` or `supersedes` once run
  persistence exists.

## Import Item Lifecycle

Statuses:

- `pending`: item exists but no validation has run.
- `validated`: row passed validation for the selected mode.
- `skipped`: policy or user skipped the item.
- `importing`: item is actively being processed.
- `succeeded`: item produced or matched a stored paper as intended.
- `warning`: item succeeded but has warnings needing review.
- `failed`: item failed with blocking error.
- `duplicate`: item matched an existing source/document according to policy.
- `needs_review`: item cannot be safely resolved automatically.

Legal transitions:
- `pending` -> `validated` only if row-level legal/provenance fields are valid
  for the selected mode.
- `validated` -> `skipped` if usage status is `metadata_only`, `candidate`, or
  another non-importable state.
- `validated` -> `needs_review` if legal fields conflict.
- `validated` -> `importing` only when legal status permits local full-text
  import.

## Error and Warning Model

Structured errors and warnings should contain:

- `code`
- `severity`
- `scope` (`run`, `item`, `manifest`, `field`)
- `source_id` when applicable
- `field` when applicable
- `message`
- `details`
- `retryable`
- `blocking`

| Category | Severity | Continue? | Item fails? | Run fails? | Retry? | User-facing message |
| --- | --- | --- | --- | --- | --- | --- |
| `manifest_missing` | error | no | n/a | yes | yes | Corpus manifest not found. |
| `malformed_manifest` | error | no | n/a | yes | yes | Corpus manifest is not valid JSON. |
| `unsupported_manifest_version` | error | no | n/a | yes | no | Manifest version is not supported. |
| `duplicate_source_id` | error | no import | affected rows | validation fails | yes | Source IDs must be unique. |
| `missing_local_file` | warning in validation, error in import | yes in dry run | yes in import | no unless all fail | yes | Local file is missing. |
| `unsupported_file_type` | error | yes | yes | no | no | Only supported file types can be imported. |
| `unreadable_pdf` | error | yes | yes | no | yes | PDF could not be read. |
| `encrypted_pdf` | error | yes | yes | no | maybe | PDF appears encrypted. |
| `parser_exception` | error | yes | yes | no | yes | Parser failed with exception class. |
| `empty_extracted_text` | error | yes | yes | no | maybe | Parser extracted no text. |
| `content_hash_mismatch` | error | yes | yes | no | yes | File hash does not match manifest. |
| `missing_doi` | warning | yes | no | no | n/a | DOI is missing; duplicate detection is weaker. |
| `conflicting_doi` | error | yes | yes | no | no | DOI candidates conflict. |
| `duplicate_candidate` | warning or error | yes | maybe | no | n/a | Possible duplicate requires review. |
| `legal_status_not_approved` | error for import | yes | yes | no | after review | Legal status does not permit import. |
| `database_write_failure` | error | yes | yes | maybe | yes | Database write failed. |
| `metadata_conflict` | warning or error | yes | maybe | no | after review | Metadata candidates conflict. |
| `source_path_escape_attempt` | error | no import | yes | validation fails | no | Path escapes allowed directory. |
| `invalid_absolute_path` | error | no import | yes | validation fails | yes | Local path must be relative. |

## Resumability and Idempotency

Phase 1 resumability should be based on stable inputs:

- Corpus ID.
- Manifest version.
- Manifest snapshot hash.
- Source ID.
- Normalized DOI or stable external identifier.
- Local relative path.
- Content hash.
- Prior import item status.

Rules:

- Successful items should be skipped on rerun when source ID and content hash
  match a previous successful item.
- Failed items should be retryable when the error is retryable.
- Items with changed content hash should be treated as changed input, not the
  same item.
- Items with changed metadata but same content hash should produce a metadata
  review warning.
- A changed manifest should create a new run or require explicit resume
  confirmation.
- Idempotency must be tested before scaling beyond pilot size.

## Persistence Recommendation

### Option 1: SQLite Tables

Pros:
- Queryable.
- Supports resumability.
- Supports future API use.
- Keeps import history near stored papers.
- Easier to test with SQLAlchemy.

Cons:
- Requires schema migration strategy.
- Adds table design burden.
- Harder to change casually once users have databases.

### Option 2: JSON Run Reports Only

Pros:
- Simple.
- Portable.
- No schema migration.
- Easy to inspect.

Cons:
- Weak resumability.
- Harder to query.
- Easy to lose or edit accidentally.
- Awkward for future APIs and duplicate tracking.

### Option 3: Hybrid Approach

Pros:
- SQLite stores durable run/item state needed for resumability.
- JSON reports provide human-readable and portable artifacts.
- Manifest snapshots can be recorded without bloating core paper tables.
- Supports future API use while preserving easy local review.

Cons:
- Requires both table design and report generation.
- Needs clear rules about which representation is authoritative.

Recommendation:
- Use the hybrid approach, but phase it in.
- M7: validation-only, no persistence and no schema changes.
- M8: introduce minimal SQLite tables for import runs, import items, warnings,
  errors, duplicate candidates, and manifest snapshots.
- M9 and later: generate JSON or Markdown run reports from persisted state.

Smallest durable M8 tables should likely be:

- `import_runs`
- `import_items`
- `import_events` or separate `import_warnings` and `import_errors`
- `duplicate_candidates`
- `manifest_snapshots`

Metadata provenance may be a separate M11 concern unless needed earlier for
conflict visibility.

## CLI Recommendation

M7 should introduce the smallest validation-focused CLI:

```text
ke corpus-validate <corpus.json> [--check-files]
```

Example:

```text
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Do not implement nested Typer command groups yet unless the CLI becomes
unmanageable. A flat command keeps M7 small and consistent with current command
style.

M7 should not implement `ke corpus-import` yet. A dry-run import command can
come later if validation-only output proves insufficient.

M7 should implement deterministic human-readable terminal output only.
Machine-readable JSON validation output should be deferred until import-run
reporting or persistence begins.

M7 output must separate two concepts:

- Manifest validity: whether the corpus JSON and source CSV conform
  structurally to manifest version 1.
- Import readiness: whether included rows currently have approved
  legal/provenance status and, when `--check-files` is used, usable local files.

Required result fields:

- Manifest validity: `valid` or `invalid`.
- Import readiness: `ready`, `blocked`, or `not evaluated`.
- Blocking structural errors.
- Import-blocking policy/legal issues.
- Non-blocking warnings.

Required behavior:

- Structural errors cause a nonzero exit.
- A structurally valid manifest with unresolved legal status is reported as
  valid but import-blocked.
- Without `--check-files`, local-file readiness is `not evaluated`.
- With `--check-files`, missing files block import readiness but do not make a
  structurally valid manifest structurally invalid.
- The command must state that no papers were imported, no database writes were
  performed, and validation does not constitute legal approval or scientific
  review.

### Example Human Output

```text
Corpus validation

Corpus: GLP-1 Weight Loss Prototype Corpus
Corpus ID: glp1_weight_loss
Manifest version: 1
Source manifest: data/corpora/glp1_weight_loss/sources.csv

Sources: 3
Manifest validity: valid
Import readiness: ready

Blocking structural errors: 0
Import-blocking policy/legal issues: 0
Non-blocking warnings: 0

Legal-use status:
  approved_open_access: 3

Local files:
  present: 3
  missing: 0
  readiness: ready

No papers were imported.
No database writes were performed.
Validation does not constitute legal approval or scientific review.
```

### Example Error Output

```text
Corpus validation failed

Manifest validity: invalid
Import readiness: blocked

Blocking structural errors:
  row 4 source_id=glp1-example:
    local_path must be relative to default_local_papers_directory and must not
    escape that directory after canonical resolution.

Import-blocking policy/legal issues:
  row 5 source_id=glp1-unclear-license:
    usage_status is needs_legal_review; real import is blocked.

Non-blocking warnings:
  row 2 source_id=glp1-gao-2022:
    DOI missing; duplicate detection will be weaker.

No papers were imported.
No database writes were performed.
Validation does not constitute legal approval or scientific review.
```

### Example Valid But Import-Blocked Output

```text
Corpus validation

Corpus: GLP-1 Weight Loss Prototype Corpus
Corpus ID: glp1_weight_loss
Manifest version: 1

Manifest validity: valid
Import readiness: blocked

Blocking structural errors: 0
Import-blocking policy/legal issues:
  row 3 source_id=glp1-candidate:
    usage_status is needs_legal_review; real import is blocked.

Local files:
  readiness: not evaluated

No papers were imported.
No database writes were performed.
Validation does not constitute legal approval or scientific review.
```

## Legal and Provenance Requirements

- Do not download papers automatically in Phase 1 ingestion.
- Do not commit PDFs.
- Do not commit extracted full text from copyrighted sources.
- Do not import full text unless usage status allows local use.
- Record source URL, access date, license type, license URL, and usage status.
- Preserve whether a row is metadata-only, candidate, included, or excluded.
- Keep legal status human-curated and machine-enforced.
- Treat missing legal approval as a blocking error for real import.
- Keep all local paths relative.
- Never write private absolute paths into committed files or generated reports.

## Security Considerations

- Reject absolute paths in manifests.
- Reject path traversal such as `..`.
- Resolve metadata files relative to the directory containing `corpus.json`.
- Resolve local document files relative to `default_local_papers_directory`,
  which itself is relative to the repository/project root.
- Resolve paths canonically before containment checks.
- Reject symlink or canonical-resolution escapes from the allowed local papers
  directory.
- Avoid printing private absolute paths in committed documentation or reports.
- Do not follow remote URLs or download files in M7.
- Do not execute content from PDFs.
- Avoid logging full extracted text.
- Keep generated reports ignored unless intentionally sanitized.
- Treat manifest files as untrusted input.
- Validate CSV field sizes to avoid accidental huge values later.
- Preserve deterministic validation order for reviewability.

## Testing Strategy

M7 tests should cover:

- Valid corpus JSON and CSV.
- Missing corpus JSON.
- Malformed JSON.
- Unsupported manifest version.
- Missing source CSV.
- Missing required corpus fields.
- Missing required CSV columns.
- Non-integer `manifest_version`.
- Duplicate source IDs.
- Invalid `source_id`.
- Invalid `usage_status`.
- Invalid `inclusion_status`.
- Canonical `publication_year`.
- Legacy `year` accepted with deterministic deprecation warning.
- Redundant `year` plus matching `publication_year` warning.
- Conflicting `year` and `publication_year` blocking error.
- Absolute local path rejection.
- Path traversal rejection.
- Repeated local papers directory in `local_path`.
- Symlink or canonical-resolution escape rejection where practical.
- Missing local file with and without `--check-files`.
- Valid and invalid expected content hashes.
- DOI normalization for duplicate detection warnings.
- Included rows missing legal provenance.
- Manifest validity versus import readiness output.
- Valid but import-blocked output.
- Deterministic human-readable output with counts.

Later tests should cover:

- Import run status transitions.
- Import item status transitions.
- Duplicate exact hash.
- Duplicate DOI with different file hash.
- Parser failure item handling.
- Partial success.
- Rerun and resume behavior.
- Manifest snapshot comparison.

## Pilot Milestone Sequence

### M7 - Manifest Validation Foundation

Objective:
Implement validation for corpus JSON and source CSV files.

Implementation scope:
- Add manifest parsing types.
- Add validation service.
- Add `ke corpus-validate <corpus.json> [--check-files]`.
- Validate paths, legal-use fields, required columns, controlled vocabularies,
  duplicate source IDs, DOI normalization, `publication_year` compatibility, and
  optional file presence.
- Produce deterministic human-readable output.
- Separate manifest validity from import readiness.

Tests:
- Unit tests for validators.
- CLI tests for success, warnings, and blocking errors.

Success criteria:
- GLP-1 corpus manifest validates.
- Invalid manifests fail clearly.
- Structurally valid but import-blocked manifests are reported clearly.
- No database writes occur.

Non-goals:
- PDF parsing.
- Database import.
- Import-run persistence.
- Metadata enrichment.

Principal risks:
- Overbuilding the manifest model before real pilot feedback.
- Letting `cli.py` absorb too much validation logic.

Expected branch name:
- `feature/m7-manifest-validation-foundation`

Likely release impact:
- `v0.2.0-alpha.2`

### M8 - Import-Run and Import-Item Persistence

Objective:
Persist import run and import item state without importing a large corpus.

Implementation scope:
- Add migration strategy decision.
- Add minimal run/item tables.
- Persist manifest snapshot.
- Persist validation results, warnings, and errors.
- Add tests for status transitions.

Tests:
- Repository tests for run and item creation.
- Status transition tests.
- Manifest snapshot tests.

Success criteria:
- A validated manifest can create run/item records.
- Failed validation can be recorded.
- No PDF parsing required.

Non-goals:
- Large imports.
- Metadata enrichment adapters.

Principal risks:
- Schema changes before migration strategy is settled.

Expected branch name:
- `feature/m8-import-run-persistence`

Likely release impact:
- `v0.2.0-alpha.3`

### M9 - Small 10-25 Paper Ingestion Pilot

Objective:
Import a small legally usable pilot corpus through the run/item workflow.

Implementation scope:
- Use existing parser and repository.
- Process 10 to 25 local PDFs.
- Record item outcomes, parser failures, and warnings.
- Generate run summary.

Tests:
- Tiny generated corpus tests.
- Integration-style test with simulated parser failures.

Success criteria:
- Partial success is represented.
- Successful items are searchable.
- Failures are visible and retryable where appropriate.

Non-goals:
- 100-paper scale.
- Parallelism.
- Enrichment adapters.

Principal risks:
- Parser metadata weakness creates noisy imports.

Expected branch name:
- `feature/m9-small-ingestion-pilot`

Likely release impact:
- `v0.2.0-alpha.4`

### M10 - Duplicate Detection and Resumability

Objective:
Make reruns safe and duplicate outcomes explicit.

Implementation scope:
- Implement exact hash duplicate detection.
- Implement normalized DOI duplicate detection.
- Add possible duplicate warnings for title/year.
- Add rerun skip behavior.
- Add retry behavior for failed items.

Tests:
- Exact duplicate tests.
- DOI duplicate tests.
- Same DOI with different hash tests.
- Resume tests.

Success criteria:
- Re-running the same manifest does not duplicate papers.
- Uncertain duplicates require review.

Non-goals:
- Fuzzy merge automation.
- Replacement/supersession UI.

Principal risks:
- Over-aggressive automatic duplicate handling.

Expected branch name:
- `feature/m10-duplicate-detection-resumability`

Likely release impact:
- `v0.2.0-alpha.5`

### M11 - Metadata Enrichment Adapters

Objective:
Add external metadata candidates without making network access required.

Implementation scope:
- Define metadata provider interface.
- Add optional Crossref and/or PubMed adapter.
- Preserve provider provenance.
- Preserve conflicts.

Tests:
- Adapter contract tests.
- Mocked provider tests.
- Conflict preservation tests.

Success criteria:
- Enriched values are candidates with provenance.
- Curated metadata is not silently overwritten.

Non-goals:
- Mandatory network access.
- Full citation graph.

Principal risks:
- Treating provider metadata as automatically authoritative.

Expected branch name:
- `feature/m11-metadata-enrichment-adapters`

Likely release impact:
- `v0.2.0-alpha.6` or `v0.3.0-alpha.1` depending on scope.

### M12 - 100-Paper Rehearsal

Objective:
Run a controlled 100-paper rehearsal and document operational issues.

Implementation scope:
- Use legally usable sources only.
- Measure import time, failures, duplicates, and metadata conflicts.
- Produce run report.
- Update technical debt.

Tests:
- Existing automated tests plus manual rehearsal checklist.

Success criteria:
- 100-paper run completes with understandable partial-success behavior.
- No committed PDFs or databases.

Non-goals:
- Claim extraction.
- Synthesis.
- Parallel workers.

Principal risks:
- Local environment variance and parser quality.

Expected branch name:
- `feature/m12-100-paper-rehearsal`

Likely release impact:
- `v0.2.0-beta.1` if ingestion is stable enough.

### M13 - Scale-Readiness Review

Objective:
Decide whether the ingestion architecture is ready for larger corpora.

Implementation scope:
- Review run history.
- Review duplicate behavior.
- Review parser failures.
- Review legal/provenance completeness.
- Identify required fixes before scale.

Tests:
- Full validation suite.
- Rehearsal reproduction checks.

Success criteria:
- Clear go/no-go decision for larger ingestion.

Non-goals:
- New ingestion features unless defects require fixes.

Principal risks:
- Declaring scale readiness too early.

Expected branch name:
- `feature/m13-scale-readiness-review`

Likely release impact:
- Release candidate for `v0.2.0` if findings are acceptable.

### M14 - Larger Corpus Ingestion

Objective:
Ingest a larger focused corpus only after M13 succeeds.

Implementation scope:
- Import larger corpus with approved legal provenance.
- Preserve run state, summaries, duplicates, failures, and review needs.
- Confirm search and stats remain usable.

Tests:
- Existing automated tests plus documented ingestion rehearsal.

Success criteria:
- Larger corpus ingestion is reproducible, auditable, and recoverable.

Non-goals:
- Evidence extraction.
- AI.
- Knowledge graph.
- Public API.

Principal risks:
- Scale exposes parser, database, and manifest weaknesses.

Expected branch name:
- `feature/m14-larger-corpus-ingestion`

Likely release impact:
- `v0.2.0` final only if bulk corpus ingestion and import manifests are truly
  implemented.

## Risks

- Manifest complexity may grow faster than implementation experience.
- Legal-use status may be too nuanced for a small controlled vocabulary.
- Existing `papers` uniqueness constraints may be too blunt for multiple
  document versions of the same source.
- SQLite schema changes need migration discipline before users accumulate local
  databases.
- Parser failures may dominate early pilot work.
- DOI-based duplicate detection can miss preprints, author manuscripts, and
  papers without DOI.
- Title normalization can create false positives.
- Run summaries may become too verbose unless they distinguish blocking errors
  from review warnings.
- Contributors may confuse a validated manifest with legal or scientific
  approval.
- The GLP-1 demo corpus is useful but too small to be the only pilot.

## Open Questions

- Should import run reports be Markdown, JSON, or both?
- Should import run persistence wait for a migration framework?
- Should the first migration strategy be Alembic or a smaller custom schema
  version table?
- Should DOI conflicts be hard errors in validation mode or only import mode?
- Should local-only institutional access be allowed in public corpus manifests,
  or should public manifests prefer open access only?
- How should multiple source documents for the same paper be represented before
  a generalized source/document schema exists?

## ADR Candidates

### Manifest Format

Decision:
Use corpus JSON plus source CSV, or a single JSON/JSONL manifest.

Likely options:
- JSON plus CSV.
- Single JSON.
- JSONL.

Before M7:
Yes. M7 needs a concrete format.

Current recommendation:
Resolve now in favor of JSON plus CSV.

### Corpus Folder Convention

Decision:
Standardize where corpus definitions, source manifests, local PDF directories,
and generated reports live.

Likely options:
- Keep current `data/corpora/<corpus_id>/` and `papers/corpora/<corpus_id>/`.
- Move all corpus metadata under `docs/`.
- Introduce a new top-level `corpora/`.

Before M7:
Yes.

Current recommendation:
Keep current convention for now.

### Import-Run Persistence

Decision:
Persist import runs in SQLite, JSON reports, or both.

Likely options:
- SQLite only.
- JSON only.
- Hybrid.

Before M7:
No. M7 can validate without persistence.

Current recommendation:
Resolve before M8, likely hybrid.

### Manifest Snapshot Strategy

Decision:
How to preserve the exact manifest used by an import run.

Likely options:
- Store raw JSON/CSV text in SQLite.
- Store file hashes only.
- Copy snapshots to ignored run directories.
- Hybrid.

Before M7:
No.

Current recommendation:
Resolve before M8.

### Duplicate Hierarchy

Decision:
Which duplicate signals are automatic and which require human review.

Likely options:
- Exact hash only.
- Hash plus DOI.
- Full hierarchy with possible duplicate records.

Before M7:
Partially. M7 should validate duplicate source IDs and duplicate DOI warnings.

Current recommendation:
Resolve full hierarchy before M10.

### Metadata Precedence

Decision:
How curated, external, manifest, and parser-derived values are selected.

Likely options:
- Single global precedence.
- Field-level precedence.
- Manual-only preferred values until enrichment exists.

Before M7:
Conceptually yes, implementation can wait.

Current recommendation:
Use field-level precedence with curated values protected from parser overwrite.

### Retry and Idempotency Semantics

Decision:
How reruns skip, retry, or reprocess items.

Likely options:
- Always skip successful items.
- Always reprocess.
- User-selectable retry policy.

Before M7:
No.

Current recommendation:
Resolve before M10.

### Local Path Security

Decision:
Which paths are valid in manifests and how they are resolved.

Likely options:
- Metadata paths relative to `corpus.json`, with local document paths relative
  to a project-root local papers directory.
- Project-relative only for every path.
- Corpus-directory-relative only for every path.
- Allow absolute paths.

Before M7:
Yes.

Current recommendation:
Resolve now: `source_manifest` and `license_policy` are relative to the
directory containing `corpus.json`; `default_local_papers_directory` is relative
to the repository/project root; source-row `local_path` is relative to
`default_local_papers_directory` and must not escape it after canonical
resolution.

### Legal-Use Gating

Decision:
Which usage statuses block import.

Likely options:
- Import any local file.
- Block unless approved.
- Warn only.

Before M7:
Yes.

Current recommendation:
Validation may warn, real import must block unless usage status is approved.

### External Metadata Adapter Boundaries

Decision:
How adapters provide metadata candidates and provenance.

Likely options:
- Direct database writes.
- Candidate objects returned to ingestion service.
- Separate enrichment workflow.

Before M7:
No.

Current recommendation:
Resolve before M11; adapters should return candidates and never overwrite
curated fields directly.

### Schema Migration Strategy

Decision:
How to evolve SQLite schema for import tables.

Likely options:
- Alembic.
- Custom schema version table.
- Recreate pre-1.0 databases manually.

Before M7:
No.

Current recommendation:
Resolve before M8.

## Exact Recommended M7 Scope

M7 should implement only:

- A small `knowledge_engine.corpus` or `knowledge_engine.ingestion` module for
  corpus manifest models and validation.
- Parsing of corpus JSON.
- Parsing of source CSV.
- Integer `manifest_version` validation for supported value `1`.
- Required field validation.
- Controlled vocabulary validation.
- Duplicate `source_id` detection.
- DOI normalization for comparison.
- Canonical path validation and path escape rejection using the M6 path
  semantics.
- `publication_year` validation with temporary M7 compatibility for legacy
  `year`.
- Optional local file presence checks with `--check-files`.
- Legal/provenance validation sufficient to say whether real import would be
  blocked.
- Separate reporting of manifest validity and import readiness.
- Deterministic human-readable CLI output.
- Focused tests.

Recommended command:

```text
ke corpus-validate <corpus.json> [--check-files]
```

M7 must not:

- Import PDFs.
- Parse PDFs.
- Write to the database.
- Add import-run tables.
- Download papers.
- Add external metadata adapters.
- Add evidence extraction.
- Add synthesis, consensus, confidence scoring, AI, embeddings, graph databases,
  APIs, or web interfaces.
