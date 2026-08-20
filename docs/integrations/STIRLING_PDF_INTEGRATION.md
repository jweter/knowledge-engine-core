# Stirling-PDF Integration Plan

Last reviewed: 2026-08-20
Upstream: `Stirling-Tools/Stirling-PDF`
Integration posture: **Optional external preprocessing service; never a canonical Knowledge Engine subsystem**

## Purpose

Stirling-PDF can prevent Knowledge Engine from rebuilding generic PDF manipulation features such as repair, OCR-oriented preprocessing, page extraction, conversion, compression, redaction, metadata operations, and other document hygiene tasks.

Its role is preprocessing. It does not decide scientific meaning, legal-use status, canonical metadata, evidence quality, or persistence.

## License gate

The upstream root license currently states MIT for content outside specifically identified proprietary/saas/engine/editor directories, which may have separate licenses. Treat Stirling-PDF as a mixed-license repository and review the exact components/endpoints used before packaging or copying anything.

Preferred deployment avoids code copying entirely: run a pinned Stirling-PDF instance separately and call only documented APIs or CLI/process boundaries.

## Target architecture

```text
incoming document
  -> legal/path/hash validation
  -> preprocessing-needed decision
      -> no: parser
      -> yes: Stirling-PDF local service/process
  -> transformed temporary artifact
  -> new hash + transformation provenance
  -> parser (PyMuPDF / Docling / MinerU)
  -> canonical ingestion
```

The original document remains authoritative and must not be overwritten.

## Transformation provenance

Every preprocessing operation that changes bytes must record:

- source content hash;
- output content hash;
- Stirling-PDF version;
- operation name;
- parameters;
- execution timestamp;
- whether OCR, repair, page removal, conversion, or metadata mutation occurred;
- temporary/output path policy;
- warning/error result.

Scientific claims must remain traceable back to the original source file and page context where possible.

## Phased plan

### Phase 0 - Capability inventory

List only operations Knowledge Engine actually needs. Initial candidates:

- repair malformed PDFs;
- normalize PDFs that parsers reject;
- OCR/preprocess scans when parser-native OCR is inadequate;
- split/extract page ranges for diagnostics;
- inspect/remove problematic metadata only when policy allows;
- convert supported inputs to a parseable archival/intermediate form.

Do not expose Stirling's entire tool surface simply because it exists.

### Phase 1 - Local experimental service

Run Stirling-PDF outside the Knowledge Engine Python environment. Add a small client boundary with:

- configured base URL;
- health check;
- explicit timeouts;
- no internet exposure by default;
- temporary-file isolation;
- failure-safe behavior when unavailable.

### Phase 2 - Deterministic preprocessing policy

Define named preprocessing profiles such as:

- `repair_only`;
- `scan_ocr`;
- `normalize_for_parser`.

Each profile must be versioned and have fixed parameters. Avoid ad-hoc UI-driven transformations in reproducible ingestion runs.

### Phase 3 - Benchmark and parser interaction

Measure whether preprocessing actually improves downstream parse quality. A preprocessing operation is not useful merely because it completes successfully.

### Phase 4 - Production hardening

Add:

- container/version pinning;
- checksums where practical;
- temporary-file cleanup;
- size/page limits;
- malicious-document handling assumptions;
- audit/provenance records;
- integration tests for service-unavailable and malformed-output cases.

## Acceptance criteria

Use Stirling-PDF in a production workflow only when:

- the operation has a demonstrated parser/reliability benefit;
- the original source is preserved;
- every transformation is reproducible and recorded;
- the service can be removed without changing canonical schemas;
- exact component licensing is acceptable;
- unavailability degrades gracefully rather than corrupting ingestion state.

## Security rules

Documents are untrusted input. Keep the service isolated, updated, and minimally exposed. Never send private/copyright-restricted documents to a public Stirling instance by default. Prefer loopback/private container networking and explicit local storage boundaries.

## Non-goals

- embedding Stirling's UI into Knowledge Engine;
- making it mandatory for ordinary PDFs;
- using it to bypass legal-use restrictions;
- overwriting originals;
- treating transformed files as if they were the original source;
- copying mixed-license source directories into this repository.

## Rollback

Disable the preprocessing provider and route validated originals directly to parser selection. Because transformed outputs retain source hashes and operation provenance, affected items can be identified and regenerated.

## Agent rule

Agents may add narrow preprocessing profiles and adapters only when backed by a documented need and tests. They must not make generic PDF manipulation a core Knowledge Engine responsibility or bypass provenance through convenience transformations.
