# Phase 1 Design: Focused Corpus Ingestion

## Mission

Phase 1 turns Knowledge Engine Core from a single-paper local source vault into
a repeatable focused-corpus ingestion system. The goal is to import hundreds of
legally usable scientific papers in one domain while preserving provenance,
deduplication evidence, parser failures, and recovery information.

## Goals

- Ingest 500 to 1,000 legally usable papers for one scientific domain.
- Track every import through a manifest.
- Detect duplicate files and likely duplicate papers.
- Enrich metadata through modular adapters.
- Preserve source provenance and import errors.
- Keep the system offline-capable, with network enrichment optional.
- Produce enough structured failure data to improve parsers responsibly.

## Success Criteria

- A contributor can run a bulk import from a manifest.
- Interrupted imports can be resumed safely.
- Duplicate PDFs are skipped or reported without corrupting the database.
- Parser failures are recorded with enough context to reproduce them.
- Imported corpus statistics are visible from the CLI.
- Tests cover happy paths, duplicates, malformed PDFs, and resumable failures.

## Out of Scope

- AI summaries
- Claim extraction
- Embeddings
- Vector search
- OCR
- Knowledge graph construction
- Web interface
- Public API

These belong after corpus ingestion is reproducible.

## Architecture

Phase 1 should add a thin ingestion layer above the existing parser and
repository services.

```text
Manifest
  -> Import planner
  -> Duplicate detector
  -> Parser
  -> Metadata enrichment adapters
  -> Repository
  -> Import run report
```

Existing parser, database, and search modules should remain usable for single
paper imports. Bulk ingestion should compose them rather than replace them.

## Database Evolution

Likely new tables:

- `import_runs`: one row per bulk import attempt.
- `import_items`: one row per manifest item with status and error details.
- `source_records`: source URL, license, retrieval date, and provenance.
- `external_identifiers`: DOI, PubMed ID, arXiv ID, patent ID, or other stable
  identifiers.

Before adding tables, introduce a migration strategy. Alembic is the likely
choice, but the project should evaluate whether a lightweight migration layer is
sufficient for early pre-1.0 releases.

## Import Pipeline

1. Read manifest.
2. Validate paths, source metadata, and licensing fields.
3. Create an `import_run`.
4. For each manifest item:
   - compute content hash;
   - check for duplicates;
   - parse the PDF;
   - enrich metadata if optional adapters are enabled;
   - store paper and text;
   - update FTS index;
   - record item status.
5. Emit a human-readable report.

## Bulk Ingestion

The first manifest format should be simple and text-reviewable, likely CSV or
JSONL. Avoid inventing a complex workflow language.

Minimum fields:

- local file path
- source URL
- license or usage note
- expected DOI, if known
- optional keywords
- optional collection name

## Duplicate Detection

Use layered duplicate checks:

- exact content hash;
- DOI match;
- normalized title plus first author, where available;
- source URL match.

Exact hash and DOI duplicates can be automatic skips. Fuzzy title duplicates
should be reported for review before destructive or merging behavior exists.

## Metadata Enrichment

Metadata enrichment should be adapter based:

- `MetadataProvider` interface;
- PubMed provider;
- Crossref provider;
- optional offline provider from manifest fields.

Enrichment should never overwrite locally parsed metadata without preserving the
source of the enriched value.

## Parser Abstraction

Keep `DocumentParser` as the parser contract. Add parser result diagnostics
rather than making parsers write directly to the database.

Potential additions:

- parser warnings;
- text extraction confidence;
- per-page extraction stats;
- source text spans for abstract and DOI.

## Logging

Use structured application logs for ingestion runs. Logs should include import
run ID, item ID, source path, status, and exception class. Avoid logging full
paper text.

## Recovery

Import runs should be resumable. A retry should skip completed items, retry
failed items when requested, and never duplicate already stored papers.

## Error Handling

Errors should be categorized:

- missing file;
- unsupported file type;
- unreadable PDF;
- parser failure;
- duplicate detected;
- metadata enrichment failure;
- database failure.

Parser and enrichment failures should not abort an entire import run unless the
user requests fail-fast behavior.

## Performance Considerations

Phase 1 can remain single-process initially. Prioritize correctness and
observability before parallelism.

Measure:

- files per minute;
- parser time per PDF;
- database write time;
- FTS update time;
- memory use on large PDFs.

Parallel workers can be considered after import manifests and error recovery are
stable.

## Testing Strategy

- Unit tests for manifest parsing.
- Repository tests for import run status transitions.
- Duplicate detection tests.
- Parser failure tests with generated malformed inputs where practical.
- CLI tests for bulk import commands.
- Integration tests using a tiny generated corpus.

Do not commit copyrighted papers as fixtures.

## Future Compatibility

Phase 1 should keep room for:

- PostgreSQL;
- distributed workers;
- object storage;
- OCR;
- citation extraction;
- vector search;
- knowledge graph construction.

Do this through stable interfaces and persisted provenance, not large abstract
frameworks before they are needed.

## Open Questions

- Should the first manifest format be CSV or JSONL?
- Should import runs live in the same SQLite database as papers?
- How should license metadata be represented?
- Which metadata source should be preferred when PubMed and Crossref disagree?
- Should failed imports be retried by default?
- How much parser diagnostic data should be stored long term?

## Potential Risks

- Importing papers without clear legal usage rights.
- Treating enriched metadata as authoritative without source tracking.
- Adding parallel ingestion before recovery and idempotency are correct.
- Overfitting parser improvements to a small corpus.
- Creating schema changes before migration strategy exists.
