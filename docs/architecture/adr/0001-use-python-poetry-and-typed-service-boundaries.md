# ADR 0001: Use Python, Poetry, and Typed Service Boundaries

## Status

Accepted

## Context

Knowledge Engine Core needs to be approachable for contributors while remaining
durable enough to support future ingestion, search, graph, and AI systems.
Phase 0 must stay offline and avoid premature infrastructure complexity.

## Decision

Use Python 3.12 or newer, Poetry project metadata, strict type checking with
mypy, and explicit service boundaries:

- CLI code adapts user input.
- Parser code extracts typed document results.
- Repository code owns persistence.
- Search code owns query behavior.

## Consequences

- Contributors get a familiar Python workflow.
- The project can add alternate interfaces without rewriting core services.
- The project can later swap persistence/search implementations behind the same
  boundaries.
- Poetry remains the intended workflow, but a pip/venv fallback is documented
  while local Poetry certificate issues are investigated.

## Alternatives Considered

- A single script: rejected because it would make testing and future extension
  harder.
- A web app first: rejected because Phase 0 should prove the source vault before
  adding interface complexity.
- A distributed worker system first: rejected as premature for local Phase 0.
