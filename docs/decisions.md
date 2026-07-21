# Decisions

This file is a lightweight index of significant project decisions. Larger
decisions should also receive an Architecture Decision Record under
`docs/architecture/adr/`.

## Decision Log

### Use Python for Phase 0

Python is familiar to scientific computing contributors and has strong libraries
for PDFs, databases, CLIs, testing, and future data workflows.

See: `docs/architecture/adr/0001-use-python-poetry-and-typed-service-boundaries.md`

### Use Poetry as the intended dependency manager

Poetry provides project metadata, dependency groups, virtual environment
management, and package scripts. A pip/venv fallback is documented while local
Windows certificate behavior is investigated.

See: `docs/architecture/adr/0001-use-python-poetry-and-typed-service-boundaries.md`

### Use SQLite before PostgreSQL

SQLite keeps Phase 0 offline and beginner friendly. PostgreSQL remains a likely
future backend once corpus scale and concurrent workflows require it.

See: `docs/architecture/adr/0002-use-sqlite-and-fts5-for-phase-0.md`

### Use FTS5 before vector search

Lexical search is transparent, offline, and easy to verify. Embeddings can be
added later after the source vault and metadata model are reliable.

See: `docs/architecture/adr/0002-use-sqlite-and-fts5-for-phase-0.md`

### Keep AI out of Phase 0

The project must first preserve and search source documents. AI layers should
build on traceable source data rather than becoming the foundation.

### Use ADRs for durable architecture choices

The project is intended to last. Future contributors need to know why decisions
were made, not only what the current code does.

### Use lightweight schema versioning for early SQLite migrations

M8 introduces import-run persistence before the project needs a full migration
framework. A small `schema_versions` table gives the local SQLite app explicit
additive migration behavior while preserving room to adopt Alembic later.

See: `docs/architecture/adr/0003-use-lightweight-schema-versioning-for-import-runs.md`

### Migrate PMC OA discovery and acquisition to NCBI's Cloud Service

NCBI is retiring both the PMC OA Web Service API (`oa.fcgi`) and the PMC FTP
Service in August 2026, including the temporary `/pub/pmc/deprecated/`
relocation this project had already bridged to once. The documented durable
replacement is NCBI's PMC Article Datasets Cloud Service: a public,
world-readable S3 bucket reachable with ordinary unsigned HTTPS requests, no
AWS account or new dependency required. Migrated ahead of the removal date
rather than patching reactively when it happens.

See: `docs/architecture/adr/0004-migrate-pmc-oa-acquisition-to-cloud-service.md`
