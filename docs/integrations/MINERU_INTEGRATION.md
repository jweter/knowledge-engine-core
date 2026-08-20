# MinerU Integration Plan

Last reviewed: 2026-08-20
Upstream: `opendatalab/MinerU`
Integration posture: **Benchmark competitor and optional parser/OCR provider, not a canonical dependency by default**

## Purpose

MinerU should be evaluated where Knowledge Engine needs strong layout recovery, OCR, table extraction, formula extraction, and diagnostics for difficult scientific PDFs. Its primary value is to prevent Knowledge Engine from independently rebuilding a complex document-understanding stack.

MinerU is not automatically preferred over Docling. Both must be measured on the same fixed benchmark and against the existing PyMuPDF baseline.

## License gate

MinerU currently uses the MinerU Open Source License: Apache 2.0 plus additional terms, including commercial thresholds and an attribution requirement for online services offered to third parties. This is not equivalent to plain Apache 2.0.

Before any production use:

- archive the exact upstream license text/version reviewed;
- record the MinerU release/version;
- determine whether the intended deployment is local/internal, downloadable software, or an online service;
- satisfy required attribution when applicable;
- separately review licenses for model weights and optional backends;
- re-check terms before commercial deployment or when business/deployment scale changes.

If license terms become incompatible with the project, the adapter must be removable without data migration.

## Target boundary

Preferred boundaries, in order:

1. isolated subprocess/CLI adapter;
2. local service/API adapter;
3. in-process Python adapter only if dependency size and compatibility are acceptable.

Do not copy MinerU source into Knowledge Engine.

```text
validated source
  -> MinerU adapter boundary
  -> MinerU JSON/Markdown/intermediate output
  -> Knowledge Engine normalization
  -> parser provenance + diagnostics
  -> canonical ingestion pipeline
```

## Evaluation focus

MinerU is especially valuable to test on:

- scanned scientific PDFs;
- multi-column layouts;
- headers/footers/page numbers that contaminate text;
- complex tables;
- equations/formulas;
- figure captions;
- mixed image/text pages;
- garbled text layers;
- documents requiring OCR-language support.

## Phased plan

### Phase 0 - Shared parser benchmark

Use the same benchmark corpus, metrics, hardware, and scoring method as Docling. Results are invalid if each parser receives a different test set or different manual cleanup.

### Phase 1 - Adapter spike

Build a small adapter that:

- accepts a validated local document;
- invokes a pinned MinerU version;
- captures stdout/stderr and structured failures;
- returns normalized blocks/text/tables/formulas and diagnostics;
- records runtime and resource metrics;
- performs no canonical database writes.

### Phase 2 - Quality comparison

Compare MinerU, Docling, and PyMuPDF using per-document and aggregate metrics. Keep examples where each parser wins and loses. Include manual review of a blinded sample so the benchmark does not optimize only easy-to-measure text similarity.

### Phase 3 - Selection decision

Possible outcomes:

- **Do not adopt:** Docling/PyMuPDF cover the required corpus.
- **Fallback provider:** use MinerU only for scanned/layout-heavy failure classes.
- **Specialized provider:** route known document classes to MinerU.
- **Primary structured parser:** only if benchmark evidence clearly supports it and licensing/deployment constraints remain acceptable.

### Phase 4 - Hardening if adopted

Add:

- deterministic version pinning;
- resource/time limits;
- local cache/model management;
- health checks for service mode;
- structured error taxonomy;
- parser provenance persisted with outputs;
- integration tests for upgrade compatibility;
- attribution/documentation required by the current license.

## Acceptance criteria

MinerU may enter a production path only if:

- it materially improves difficult-document extraction;
- the exact deployment complies with current license terms;
- model licenses are known and acceptable;
- it remains behind a replaceable adapter;
- failures and fallback choices are visible in provenance;
- no downstream code depends directly on MinerU-specific objects;
- resource use is acceptable for supported machines;
- regression tests prove that parser changes invalidate dependent derivatives safely.

## Non-goals

- adopting MinerU solely because it has more features;
- letting it become a scientific metadata authority;
- silently OCRing/replacing text without recording that OCR occurred;
- exposing a third-party online parsing service as a hidden required dependency;
- vendoring MinerU source into the repository;
- assuming its license remains unchanged over time.

## Rollback

Configuration must be able to disable MinerU completely. Persist parser/version provenance so affected documents can be identified and reparsed by another provider.

## Agent rule

Agents may benchmark and implement the boundary described here. They must not promote MinerU to default, copy upstream code, weaken attribution/license controls, or couple persistence to MinerU formats without a separate explicit architecture decision.
