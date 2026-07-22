# Phase 2: Evidence Records

Phase 2 begins converting source documents into structured scientific knowledge.

The detailed design is maintained in `docs/phase2_design.md`. Its first
concrete prerequisite is page/span-level extraction provenance in the parser,
which does not exist yet (see `docs/technical_debt.md`); no claim/evidence
extraction logic should be written before it does.

## Goals

- Extract claims, methods, results, limitations, and evidence markers.
- Preserve source text spans for every extracted structure.
- Add human review workflows.
- Track uncertainty and evidence quality separately from source metadata.

## Principle

The Knowledge Engine should never decide truth. It should organize evidence,
show disagreement, expose uncertainty, and preserve links back to sources.
