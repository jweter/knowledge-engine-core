# Architect Review

This review evaluates Knowledge Engine Core as if it were being assessed by
senior engineers from large open-source and infrastructure organizations.

## Strengths

- Clear Phase 0 scope.
- Offline-first local workflow.
- Typed Python modules with focused responsibilities.
- Tests and quality gates from the first public release.
- Governance, ADRs, roadmap, technical debt, and pain-point tracking are already
  present.
- Architecture leaves room for PostgreSQL, vector search, graph storage, OCR,
  and AI without implementing them prematurely.

## Weaknesses

- No database migration strategy yet.
- No bulk import manifest or provenance model yet.
- Parser metadata extraction is intentionally heuristic.
- No realistic legal corpus fixtures yet.
- Poetry has a local Windows certificate issue that should be resolved or
  documented more deeply.
- CI currently tests only one Python version and one operating system.

## Technical Debt

High-impact debt:

- Add migration strategy before schema evolution.
- Add import manifests before Phase 1 bulk ingestion.
- Improve Windows setup reliability.

Medium-impact debt:

- Add deterministic snippet generation if FTS snippets prove weak.
- Add parser diagnostics.
- Add realistic legal fixtures.

Low-impact debt:

- Remove stale local machine PATH entries for Python312.
- Add diagrams once the Phase 1 pipeline is implemented.

## Architectural Risks

1. Schema changes without migrations could break early users.
2. Bulk ingestion without idempotency could create duplicate or partial records.
3. Metadata enrichment without provenance could reduce scientific trust.
4. Parser heuristics could silently produce misleading metadata.
5. Large corpus scale could outgrow SQLite sooner than expected.
6. Future AI features could obscure evidence if traceability is not enforced.
7. Contributor setup friction could limit community growth.
8. Search ranking could become opaque if not documented as it evolves.
9. Legal ambiguity around paper redistribution could slow corpus work.
10. Premature abstraction could make the code harder for beginners to join.

## Recommended Improvements

High priority:

- Design and implement import manifests.
- Add migration strategy.
- Add provenance fields for sources and enriched metadata.
- Expand CI to a Python version matrix after the Poetry lock/setup path is
  stable.

Medium priority:

- Add parser diagnostics and structured parser failure issues.
- Add a tiny legal sample corpus or fixture generator.
- Add architecture diagrams after Phase 1 design settles.

Low priority:

- Add benchmarking scripts after correctness is established.
- Add optional pre-commit hooks for contributors who want them.

## Overall Assessment

The repository is unusually mature for an initial public release. The main
engineering risk is not current code quality; it is maintaining traceability and
schema discipline as the project moves from single-paper ingestion to real corpus
work.
