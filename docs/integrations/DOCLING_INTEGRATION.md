# Docling Integration Plan

Last reviewed: 2026-08-20
Upstream: `docling-project/docling`
Integration posture: **Preferred advanced parser candidate behind a Knowledge Engine-owned adapter**

## Why this exists

Knowledge Engine already has a parser boundary and a working PyMuPDF baseline. Docling should be evaluated as an advanced structured-document parser so the project can improve reading order, tables, formulas, images, OCR, Office-document handling, and structured export without turning document parsing into the product's main engineering burden.

Docling must not become the canonical Knowledge Engine document model. Its output is an upstream representation that is normalized into Knowledge Engine-owned types.

## License and dependency gate

The Docling codebase is currently MIT licensed. Individual models may have separate licenses and must be reviewed independently before they are downloaded, packaged, invoked, or used for commercial output.

Before implementation:

- record the exact Docling version;
- record every model used and its source/license;
- record whether model weights are downloaded at runtime or provisioned separately;
- document CPU/GPU requirements and cache locations;
- add required notices if redistribution ever occurs;
- rerun this review on each material version upgrade.

## Target architecture

```text
Source file
  -> ingestion/legal/path validation
  -> parser selection
      -> PyMuPDFParser
      -> DoclingParser
  -> Knowledge Engine ParsedDocument normalization
  -> parser diagnostics + provenance
  -> existing metadata/duplicate/review pipeline
  -> persistence/indexing
```

The `DoclingParser` adapter should expose the same stable parser contract as other parsers. Docling-specific classes must not leak into repositories, database models, web APIs, or AI-layer contracts.

## Canonical fields to preserve

At minimum normalize:

- source file identity and hash;
- parser name/version;
- parse timestamp;
- page count;
- normalized text in reading order;
- structural blocks/sections where useful;
- tables and table provenance;
- formulas and formula provenance;
- image references/captions where useful;
- OCR-used flag and OCR engine/model information;
- warnings, recoverable failures, and confidence/quality signals;
- raw parser artifact location when retained locally for diagnostics.

## Phased implementation

### Phase 0 - Benchmark fixture

Create a fixed 20-50 document scientific test corpus containing:

- born-digital single-column papers;
- multi-column papers;
- tables;
- equations;
- figures/captions;
- scanned pages;
- difficult reading order;
- malformed or partially unreadable PDFs.

Do not use copyrighted fixture files in the public repository unless redistribution rights are explicit. Store hashes/manifests and local fixture instructions when necessary.

### Phase 1 - Isolated adapter spike

Implement a minimal `DoclingParser` that:

- accepts one validated local file;
- runs locally;
- returns the canonical parser result;
- captures warnings/errors rather than swallowing them;
- cannot write directly to the database;
- does not perform metadata enrichment or scientific synthesis.

### Phase 2 - Comparative benchmark

Compare PyMuPDF and Docling on:

- reading-order correctness;
- section recovery;
- table extraction;
- formula retention;
- OCR behavior;
- parse success/failure rate;
- runtime;
- peak memory;
- output stability across repeated runs;
- diagnostics quality.

Store benchmark methodology and machine-readable results. Do not declare Docling the default from anecdotal examples.

### Phase 3 - Parser policy

If the benchmark supports adoption, define deterministic parser-selection rules. Preferred initial policy:

1. PyMuPDF remains the fast baseline.
2. Docling is selected when structured extraction is required or the baseline is insufficient.
3. Automatic fallback must be explicit in provenance and must not silently replace one parser's output with another.
4. A parser change invalidates downstream derived artifacts that depend on parsed text/structure.

### Phase 4 - Production hardening

Add:

- version pinning;
- timeout/resource limits;
- model-cache configuration;
- structured error classes;
- regression fixtures;
- provenance persistence;
- CLI diagnostics;
- repeatability checks;
- upgrade compatibility tests.

## Acceptance criteria

Adopt Docling beyond experiment status only if:

- it materially improves the benchmark on important scientific document classes;
- failures are observable and reviewable;
- output can be normalized without contaminating the domain model;
- local/offline operation remains viable for the intended mode;
- model and package licenses are acceptable;
- performance is tolerable on supported hardware;
- existing PyMuPDF workflows remain available as a fallback/baseline;
- tests demonstrate that switching parsers cannot silently change persisted scientific evidence.

## Non-goals

- replacing Knowledge Engine provenance or metadata authority with Docling metadata;
- letting Docling write directly to canonical persistence;
- depending on a cloud service for the core parse path;
- shipping arbitrary model weights without license review;
- removing the simple parser baseline;
- coupling the AI layer directly to Docling objects.

## Rollback strategy

The adapter boundary must allow disabling Docling through configuration and returning to PyMuPDF without schema migration. Any Docling-derived persisted record must retain enough parser provenance to identify and selectively reparse it later.

## Agent implementation rule

Future coding agents must treat this document as an integration constraint. They may improve the adapter and benchmark, but must not spread Docling-specific types through the application, remove provenance, or make Docling mandatory without an explicit architecture decision supported by benchmark evidence.
