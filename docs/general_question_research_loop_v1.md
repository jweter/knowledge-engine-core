# General Question Research Loop v1 - Core responsibilities

Status: active cross-repository build plan  
Tracking issue: #402  
Parent AI tracking issue: `knowledge-engine-ai` #69

## Purpose

Core must support a general-purpose research loop, not a fixed-question corpus workflow. The GLP-1/body-weight data remains a golden regression corpus, but new user questions must be able to discover, acquire, validate, and reuse evidence outside that corpus.

Core remains the deterministic evidence authority. It does not decide what evidence means for the user; it provides validated, traceable material that the AI layer can reason over.

## Required pipeline

```text
federated discovery run
  -> normalized candidates
  -> bounded acquisition queue
  -> identity/deduplication
  -> access/license checks
  -> acquisition receipt
  -> paper/source persistence
  -> parsing
  -> grounded evidence extraction
  -> validation/promotion
  -> reusable evidence store
```

## Existing components to reuse

The repository already contains substantial pieces required by this feature:

- federated discovery providers and persisted search-run ledgers;
- PubMed/PMC and Europe PMC discovery/acquisition services;
- CORE discovery;
- Unpaywall lookup;
- paper/source persistence and import-run provenance;
- PDF parsing;
- grounded local-LLM extraction with source verification;
- Evidence Record validation;
- graph and retrieval infrastructure.

General Question v1 is primarily a composition and contract problem: connect these pieces behind one bounded acquisition path without weakening provenance or access rules.

## New Core contract

A new acquisition bridge should consume a persisted federated search run and an explicit bounded selection policy. It must not accept arbitrary model-authored full text or bypass source eligibility checks.

### Request

Minimum logical fields:

```json
{
  "schema_version": 1,
  "search_run_id": "uuid",
  "research_question_id": "stable-thread-id",
  "candidate_ids": ["provider-neutral-id"],
  "max_candidates": 10,
  "max_full_text_acquisitions": 5,
  "max_elapsed_seconds": 120,
  "allow_metadata_only": true
}
```

Candidate selection may be performed by the AI layer, but every selected candidate must resolve back to the persisted search-run snapshot.

### Result

Per candidate:

- stable candidate identity;
- DOI/PMID/arXiv/provider IDs when available;
- existing paper/source match if already indexed;
- acquisition status;
- access/license provenance;
- local persisted paper ID when acquired;
- parser/import-run identity;
- evidence extraction result count;
- validation/rejection reason.

Stable statuses:

- `already_indexed`
- `acquired_full_text`
- `metadata_only`
- `license_or_access_unavailable`
- `duplicate`
- `failed`
- `skipped_budget`

These statuses describe acquisition, not scientific support.

## Safety and scientific invariants

1. Never treat a discovery candidate as an Evidence Record.
2. Never download non-permitted full text merely because a provider returned a URL.
3. Never bypass stable identity/deduplication.
4. Never promote ungrounded extracted fields.
5. Never silently mutate or replace existing reviewed Evidence Records.
6. Every acquisition must produce a durable receipt.
7. Every newly promoted Evidence Record must retain source-span provenance.
8. Unknown domains use the domain-general grounded extraction path, not a GLP-1-specific regex fallback.

## Build slices

### CORE-GQR-1 - Acquisition request/result schema
- define typed request/result models;
- stable JSON serialization;
- schema-version tests;
- persisted search-run candidate resolution.

**Status:** complete, including the CLI boundary. `ke
general-question-acquisition-plan <request.json> --ledger-root <dir>
[--output <path.json>] [--no-database]` is now the reachable surface for
`build_acquisition_plan` (see `docs/core_interface_contract.md`) — until
this command existed, the schema/planner were built and unit-tested but
callable only from a test file, unreachable to `knowledge-engine-ai` even
though that layer consumes Core strictly through this CLI's JSON boundary.

### CORE-GQR-2 - Candidate identity and reuse
- DOI/PMID/arXiv/provider identity resolution;
- detect already indexed sources;
- return `already_indexed` instead of reacquiring;
- idempotency tests.

**Status:** identity resolution now covers DOI, PMID, and arXiv ID.
`build_acquisition_plan` accepts an optional SQLAlchemy `session`; when
supplied, each candidate's DOI, then PMID, then arXiv ID (whichever is known
for the candidate) is checked against the persisted corpus
(`DuplicateQueryRepository.paper_by_normalized_doi` /
`.paper_by_pmid` / `.paper_by_arxiv_id`) before any budget/eligibility logic
runs, and the first match is reported as `already_indexed` with the existing
`Paper.id` attached and a reason naming which identity matched — it never
competes with genuinely new candidates for the full-text acquisition budget,
and omitting `session` preserves the prior snapshot-only behavior exactly.
Schema version 13 (`knowledge_engine/database.py`) added `papers.pmid` and
`papers.arxiv_id` as nullable, uniquely indexed columns so those lookups have
something to query; the migration is purely additive (existing rows have
`NULL` for both until backfilled). PMCID-based reuse detection remains future
work: `Paper` still has no persisted PMCID column.

The real ingestion-time caller gap is now closed: `sources.csv` already
documents `pmid`/`arxiv_id` columns (see `docs/core_interface_contract.md`),
and `CorpusIngestionService`/`LinkedCorpusIngestionService` -- the corpus
manifest ingestion path behind `ke corpus-import`, the only caller that
persists real `Paper` rows with manifest-sourced metadata -- now read,
normalize (`normalize_pmid`/`normalize_arxiv_id`), and pass them through as
`manifest_pmid`/`manifest_arxiv_id` to `PaperRepository._build_paper`,
mirroring exactly how `manifest_doi` already populates `papers.doi`. Schema
version 14 added the carrier columns this needed:
`import_items.normalized_pmid`/`.normalized_arxiv_id` (nullable,
non-uniquely indexed, additive). A manifest row with no `pmid`/`arxiv_id`
value behaves exactly as before (`NULL`, same as a row with no `doi`).
Backfilling `papers.pmid`/`papers.arxiv_id` for *already*-persisted papers
(imported before this change) is separate follow-up work, not attempted
here -- same as `papers.doi` was never backfilled for pre-existing rows
either. A real database session is now wired into the CLI caller (`ke
general-question-acquisition-plan`, on by default, `--no-database` to
opt out); wiring a session into `build_acquisition_plan()` for a real
acquisition-bridge caller (as opposed to the CLI's already-existing wiring)
arrives with CORE-GQR-4 (persist and parse), which is also where an
`acquired_full_text` disposition and durable acquisition receipt first
become meaningful.

### CORE-GQR-3 - Acquisition routing
Route eligible candidates through existing mechanisms where possible:
- PMC OA acquisition;
- Europe PMC OA acquisition;
- CORE-accessible material;
- Unpaywall-resolved OA locations;
- metadata-only fallback when full text cannot be acquired.

No provider gets an implicit trust exemption.

**Status:** deterministic route selection is complete at the acquisition-plan
boundary. Every `eligible_full_text` item now names one supported
`acquisition_route` (`pmc_oa`, `europe_pmc_oa`, `core`, or
`unpaywall`). PMC, Europe PMC, and CORE routes require their official
allowlisted full-text hosts; an otherwise OA/licensed URL from an unsupported
provider degrades to `metadata_only` instead of becoming an implicit direct
download. Route priority is stable (PMC, Europe PMC, CORE, Unpaywall), and the
existing provider-specific services remain responsible for independently
validating access evidence before acquisition. Executing the routes and
persisting their durable receipts belongs to CORE-GQR-4.

### CORE-GQR-4 - Persist and parse
- create/import paper/source records;
- parse newly acquired full text;
- attach import-run/acquisition receipt provenance;
- keep failures independently inspectable.

**Status:** complete. All four provider routes are implemented and reachable
for the success path. PMC and Europe PMC are complete and reachable. The CORE
provider execution/persistence library merged in PR #420 and is reachable
through the supported `ke` command surface. Unpaywall merged in PR #422 and
is described below. This section's own "keep failures independently
inspectable" bullet is now met by all four routes -- see the note after the
Unpaywall command below.

`ke general-question-acquire-pmc <request.json> --ledger-root <dir>
--papers-dir <dir> --receipt <path.json>` rebuilds the bounded plan with
database-backed reuse detection, resolves the exact selected PMIDs against
current PMC Cloud OA evidence without running a new search, requires a supported
reusable license, and invokes the existing approval-gated atomic downloader.
Before parsing, Core reconciles the receipt to the original search run and
candidate identities, rejects unsafe filenames, and rechecks byte counts and
SHA-256 digests. It then persists parsed text with DOI/PMID/arXiv identity or
reuses an existing Paper by content hash or stable identity. The persistence
receipt retains search-run, research-question, candidate, PMID, PMCID, file
digest, Paper ID, and persisted/reused disposition. The same transaction now
adds one immutable `ImportRun` snapshot of the bounded plan, acquisition
receipt, and persistence outcomes plus one `ImportItem` per candidate linked
to its Paper; the public receipt exposes those import-run/item IDs additively.
Receipt-output or persistence failure rolls back both the batch's database
transaction and its newly acquired PDFs.

`ke general-question-acquire-europe-pmc <request.json> --ledger-root <dir>
--papers-dir <dir> --receipt <path.json>` provides the same contract for
`europe_pmc_oa` items using DOI identity and Europe PMC IDs. Because Europe
PMC search results can retain expired preprint PDF URLs, Core resolves each
exact DOI and immediately refreshes it through Europe PMC's live full-text
metadata endpoint. Only the resulting official `plus.europepmc.org/download/`
PDF is admitted to the approval batch; redirects, third-party hosts, ambiguous
DOI results, PMC-overlap records, missing reusable licenses, and stale metadata
all fail closed. Persistence records the same byte/digest/Paper/search-run/
candidate facts and immutable ImportRun/ImportItem lineage as the PMC path.

`ke general-question-acquire-core <request.json> --ledger-root <dir>
--papers-dir <dir> --receipt <path.json>` executes only `eligible_full_text`
items routed to `core`. The command rebuilds the bounded plan with local reuse
detection, re-resolves every planned DOI through current CORE discovery, and
requires the current CORE work to resolve uniquely to the exact planned
`https://core.ac.uk/...` PDF URL. Because CORE's API does not provide per-work
license metadata, the persisted plan itself must carry an explicit supported
reusable license; provider-wide open-access aggregation is never treated as a
license exemption. The existing #420 executor then performs bounded no-redirect
PDF acquisition, byte/signature/digest verification, atomic rollback,
Paper persistence/reuse, and immutable ImportRun/ImportItem lineage. This CLI
registration is additive and does not weaken the existing PMC or Europe PMC
commands.

`ke general-question-acquire-unpaywall <request.json> --ledger-root <dir>
--papers-dir <dir> --receipt <path.json>` executes only `eligible_full_text`
items routed to `unpaywall`. Because Unpaywall is a per-DOI OA-location/license
locator rather than a full-text host, the command re-resolves every planned
DOI through Unpaywall's live per-DOI API immediately before acquisition,
requires current `is_oa=true` plus a reusable license accepted by Core's
shared license policy, and requires the current direct-PDF URL to reconcile
exactly with the persisted GQR plan. An arbitrary Unpaywall-returned URL is
never treated as network authority: direct PDF bytes are admitted only from
Core's existing reviewed full-text host set (PMC, PMC OA S3, Europe PMC/Plus,
CORE), over HTTPS/default port, with no credentials or redirects and a 100 MB
bound. The batch is staged, PDF signatures verified, and rolled back
atomically on failure; byte count/SHA-256 are rechecked before parsing;
content-hash and DOI/PMID/arXiv Paper identities are reconciled fail-closed
before reuse. Persistence records the same search-run/candidate/license/
source-host provenance and immutable ImportRun/ImportItem lineage as the
other three routes. See `docs/security/unpaywall_gqr_acquisition_boundary.md`
for the full fail-closed security boundary.

All four routes (PMC, Europe PMC, CORE, Unpaywall) are reachable and tested
for the success path. On a resolver, download, or parsing failure, each
command (`general_question_acquire_pmc` / `_europe_pmc` in `entrypoint.py`,
`_core` / `_unpaywall` in `command_surface.py`, and the `ke-research`-slim
duplicates of the PMC/Europe PMC executors in `research_acquisition_surface.py`)
still prints a console error and rolls back the batch, but now also writes a
durable, sanitized `GeneralQuestionAcquisitionFailureRecord`
(`knowledge_engine/general_question_acquisition_failures.py`) to
`<receipt-path>.failure.json` before exiting non-zero. The record captures the
search-run and research-question IDs, the acquisition route, the failure
stage (`build_plan`, `acquire`, or `persist`), a sanitized reason, the
requested candidate IDs, and a timestamp -- giving a caller an auditable,
retryable trace instead of only ephemeral stderr/CI-log output. A stale
failure record from an earlier failed attempt at the same receipt path is
removed once a retried batch succeeds. This closes this section's "keep
failures independently inspectable" bullet, completing CORE-GQR-4. Discovery
metadata and acquired Papers remain non-Evidence-Record material until
CORE-GQR-5 grounded extraction and validation/promotion.

### CORE-GQR-5 - Grounded extraction and promotion
- invoke domain-general grounded extraction;
- verify proposed fields against source text;
- validate Evidence Record schema;
- append/promote only valid records;
- persist rejection reasons for failed proposals.

### CORE-GQR-6 - Reuse and query visibility
- newly promoted evidence becomes visible to normal retrieval immediately or through one explicit documented refresh step;
- repeat-question tests prove no duplicate acquisition;
- corpus-library export/import preserves the newly acquired evidence.

## Acceptance test

Starting with no indexed creatine/strength evidence, a persisted federated discovery run containing eligible creatine papers can be passed to the acquisition bridge. At least one accessible source is acquired, parsed, grounded, promoted to a valid Evidence Record, and becomes retrievable by the normal evidence search path. Re-running the same acquisition request reuses the persisted paper instead of duplicating it.

## Definition of done

Core's portion is complete when a federated discovery lead can become reusable, validated evidence through one bounded, auditable command/API contract while preserving all existing provenance, access, and grounding rules.
