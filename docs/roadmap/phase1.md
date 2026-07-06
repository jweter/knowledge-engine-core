# Phase 1: Focused Corpus Ingestion

Phase 1 should prove the system on a real but bounded scientific corpus.

The detailed design is maintained in `docs/phase1_design.md`.

## Recommended Domain

Start with obesity and metabolic disease because it has large public literature,
clear scientific impact, and many cross-cutting mechanisms.

## Goals

- Ingest 500 to 1,000 legally usable papers.
- Add import manifests and duplicate reports.
- Track source provenance and import failures.
- Improve metadata through PubMed and Crossref enrichment.
- Record parser failures as structured issues.
- Keep bulk ingestion resumable and idempotent.
- Add a migration strategy before schema changes become user-facing.

## Non-Goals

- AI summaries
- Claim extraction
- Vector search
- Knowledge graph construction

Those should wait until the source vault and corpus ingestion workflow are
reliable.
