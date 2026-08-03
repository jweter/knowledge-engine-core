# Phase 1: Focused Corpus Ingestion

Phase 1 proved the system on a real but bounded scientific corpus. Its durable
ingestion, validation, provenance, duplicate-handling, metadata, and scale
rehearsal milestones are complete; ongoing corpus growth is operational work,
not the current strategic priority.

The detailed design is maintained in `docs/phase1_design.md`.

## Recommended Domain

Start with obesity and metabolic disease because it has large public literature,
clear scientific impact, and many cross-cutting mechanisms.

## Delivered

- Versioned corpus manifests and validation.
- Durable import runs, items, snapshots, warnings, and failures.
- Legally gated, resumable, idempotent ingestion with conservative duplicate
  handling.
- PubMed, Crossref, and Europe PMC metadata/acquisition boundaries.
- Controlled 500-paper rehearsal and subsequent bounded growth to the corpus
  size used for Phase 2 tuning.
- Additive schema migration and recovery behavior for local databases.

See `docs/roadmap.md` for the completed M6-M14 sequence and later operational
growth milestones. The Current Project Path now prioritizes retrieval quality
and one complete GLP-1 evidence map over additional corpus breadth.

## Non-Goals

- AI summaries
- Claim extraction
- Vector search
- Knowledge graph construction

These were correct sequencing constraints for Phase 1. They have since been
implemented in later phases and are not current Phase 1 work.
