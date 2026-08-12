# Long-Term Zero-Cost-to-Scale Architecture

## Status

**Roadmap horizon:** later-stage / post-release scaling architecture.

This document preserves the project's current best-case infrastructure strategy for growing Knowledge Engine from a low-cost release into a very large, continuously expanding scientific platform without forcing an early rewrite around expensive hosted services.

It is deliberately **not an immediate implementation plan**. The current project path remains focused on retrieval quality, evidence-map quality, domain-general extraction, analytical verification, and the persistent-host trigger defined elsewhere in the roadmap. This document becomes actionable when release usage, corpus size, hosted access, or operational requirements justify a larger deployment surface.

The core principle is:

> **Do not build a free-tier stack. Build a portable architecture that happens to fit inside free tiers for as long as practical.**

Free tiers are temporary economic advantages, not architectural dependencies.

---

## Why This Matters

Knowledge Engine is intended to keep growing. The corpus, evidence records, claim relationships, provenance, model-assisted extractions, derived analytical data, and user-created research state do not have a natural fixed endpoint.

A naive architecture could therefore create costs that rise simply because the knowledge base grows, even when user activity is low. The better design is to make the largest parts of the system inexpensive, append-oriented, compressed, local or object-backed, and rebuildable while reserving expensive compute for the moments when real reasoning is needed.

The long-term economic target is:

- **very low or near-zero idle cost**;
- **scale-to-zero compute where practical**;
- **local-first inference for routine work**;
- **cloud reasoning only as an escalation path**;
- **cheap storage for immutable evidence**;
- **relational databases reserved for data that benefits from relational access**;
- **large analytical datasets stored in compact columnar formats**;
- **rebuildable search/vector indexes rather than proprietary sources of truth**;
- **clear provider adapters so any SaaS dependency can be replaced**.

---

## Best-Case Product Architecture

The strongest long-term shape is one Knowledge Engine codebase with two deployment profiles.

### Knowledge Engine Local

A researcher or developer can run the system without paying Knowledge Engine or an external AI provider.

```text
Knowledge Engine Local
        |
        +-- SQLite
        +-- DuckDB
        +-- local files / object cache
        +-- FTS / rebuildable vector indexes
        +-- Ollama or other local runtime
        +-- deterministic Python analysis
```

Target monthly infrastructure cost: **$0** beyond the user's own hardware and connectivity.

### Knowledge Engine Cloud

The same domain models and APIs can run behind scalable hosted adapters.

```text
Internet
   |
Edge / CDN / protection
   |
Web application
   |
Read-only / public API surface
   |
Knowledge Engine Python services
   |
+-- relational metadata store
+-- object storage
+-- queue / async jobs
+-- analytical Parquet datasets
+-- model router
      |
      +-- local/self-hosted models
      +-- hosted model escalation
```

The local and cloud products should share:

- Evidence Record semantics;
- claim and relationship models;
- provenance requirements;
- retrieval contracts;
- model-provider interfaces;
- analytical verification rules;
- API schemas wherever practical.

The deployment adapters may differ. The scientific truth model should not.

---

## Long-Term Candidate Stack

The following services are candidates, not permanent commitments. Each must remain replaceable behind a project-owned interface.

### Edge and Web

**Cloudflare** is a strong future candidate for DNS, CDN, static/frontend delivery, edge functions, bot protection, lightweight edge state, object storage, and asynchronous queues.

Potential roles:

- DNS/CDN;
- Pages/static web hosting;
- Workers for lightweight edge/API logic;
- Turnstile for bot protection;
- R2 for low-cost object storage;
- D1 for small edge-local relational state where appropriate;
- Queues for asynchronous handoff;
- optional AI Gateway for provider analytics/rate limiting later.

Important architectural boundary: **Cloudflare should surround Knowledge Engine, not become Knowledge Engine.** The scientific core remains Python/provider-neutral.

### Relational Database

**Neon Postgres** is a strong hosted candidate for server-side relational data while free allowances remain useful.

Good relational candidates include:

- users and projects;
- evidence metadata;
- claims and relationships;
- provenance pointers;
- research runs;
- access-control data;
- job metadata.

Large PDFs and bulk analytical data should not be stored directly in the relational database merely because it is convenient.

### Python Compute

A scale-to-zero container service such as **Google Cloud Run** is a strong future candidate for FastAPI/Python workloads that need a real online runtime while usage is intermittent.

Knowledge Engine should continue to support self-hosted Python services as an alternative.

### Transactional Email

A provider such as **Resend** can handle low-volume transactional email while a free allowance is sufficient.

Potential messages:

- verification;
- password reset;
- completed research/export notifications;
- security/account notifications.

### Product Analytics

Evaluate **PostHog versus Mixpanel** when product analytics becomes operationally useful.

PostHog is especially attractive if analytics, feature flags, experiments, and session diagnostics can replace several separate vendors.

Analytics must remain non-authoritative. Scientific evidence, user projects, and provenance never depend on an analytics vendor.

### Source Control, CI, and Distribution

GitHub remains a strong zero/low-cost layer for:

- source control;
- Actions-based CI for public repositories;
- tests and validation;
- documentation builds;
- release artifacts;
- versioned public data/index packages when appropriate.

GitHub Releases can distribute versioned binaries, starter corpora, benchmark fixtures, and prebuilt public indexes. They should not become the primary scientific data lake.

---

## Storage Architecture: Hot, Warm, and Cold Knowledge

The largest long-term cost savings come from putting each class of data in the correct storage layer.

### Hot: relational and frequently queried

Use SQLite locally and Postgres or another SQL engine when hosted.

Examples:

- Evidence Record identifiers and metadata;
- DOI/source identity;
- claim records;
- claim-to-evidence relationships;
- project/user state;
- provenance pointers;
- research-run state;
- compact aggregate metrics.

### Warm: analytical and retrieval data

Use open, compressed, portable formats such as Parquet and query them with DuckDB where appropriate.

Examples:

- large paper metadata tables;
- citation edges;
- extracted result tables;
- author/concept tables;
- precomputed research maps;
- bulk embedding metadata;
- historical analytical outputs.

DuckDB + Parquet is attractive because it permits large local or object-backed datasets to be queried without operating a permanent analytics server.

### Cold: immutable original evidence

Store content-addressed objects in local files, R2/S3-compatible storage, or an equivalent replaceable object store.

Examples:

- PDFs where storage and licensing permit;
- source XML;
- HTML snapshots where appropriate;
- downloaded datasets;
- API response snapshots;
- supplementary files.

A relational evidence record should point to the immutable object through a stable URI/hash rather than embedding large binary payloads in the database.

Example:

```text
evidence_id = EVD-2848273
doi         = ...
content_hash = ...
storage_uri = object://evidence/ab/cd/...
```

---

## Source-of-Truth Rule

The retrieval index is never the source of truth.

Vector indexes, FTS indexes, semantic caches, ranking features, and model-generated summaries are derived products.

If an index disappears, rebuild it.

If a model changes, re-extract from immutable evidence.

If a conclusion changes, retain the prior conclusion and its supporting evidence/provenance rather than overwriting history.

This extends the project's existing append-first and provenance-first direction: original evidence is captured first; interpretation remains reproducible and replaceable.

---

## AI Cost Architecture

The largest variable cost risk is model inference. The long-term policy should therefore minimize unnecessary LLM calls rather than merely choosing a cheaper LLM.

### Tier 0: deterministic code

Use no LLM when deterministic software can reliably perform the operation.

Examples:

- DOI normalization;
- hashing and deduplication;
- citation resolution;
- sorting and filtering;
- database retrieval;
- statistical verification;
- provenance validation;
- exact quote/source-span retrieval;
- schema validation;
- known metadata transformations.

### Tier 1: inexpensive local inference

Use local models for repetitive, privacy-sensitive, or highly structured language tasks.

Examples:

- document classification;
- metadata/PICO proposals subject to grounding verification;
- query expansion;
- topic/entity labeling;
- chunk summarization;
- extraction assistance;
- preliminary contradiction candidate detection;
- local synthesis when measured quality is sufficient.

Ollama is a runtime, not a model identity. Knowledge Engine's model router should treat Qwen, Gemma, gpt-oss, future scientific models, and other compatible models as replaceable implementations of capability roles.

### Tier 2: hosted reasoning escalation

Use cloud reasoning only when task complexity, uncertainty, or value justifies the cost and the data policy allows cloud egress.

Examples:

- difficult multi-paper synthesis;
- adversarial review;
- methodological critique;
- ambiguous causal reasoning;
- complex architecture/research planning;
- independent verification when local models disagree or fall below a measured threshold.

### Tier 3: asynchronous batch reasoning

Large non-interactive workloads should prefer asynchronous/batch processing when a provider offers materially lower cost.

Examples:

- bulk classification;
- large-scale extraction refreshes;
- corpus-wide contradiction screening;
- offline enrichment;
- scheduled re-evaluation against improved models.

The economic hierarchy is therefore:

```text
Deterministic code
      |
Local inference
      |
Stronger local inference
      |
Hosted reasoning escalation
      |
Hosted batch processing for large offline jobs
```

---

## Knowledge Engine Cost Constitution

These are proposed long-term engineering invariants.

### KE-ECON-001 — Portability over free-tier lock-in

No hosted service should become a mandatory architectural dependency when a practical open/local alternative or clean provider abstraction is possible.

### KE-ECON-002 — Scale to zero

Prefer infrastructure that incurs little or no compute cost while idle.

### KE-ECON-003 — Deterministic before generative

Do not invoke an LLM for work that reliable deterministic code can perform.

### KE-ECON-004 — Local inference first

Routine AI work defaults to local inference when measured quality is adequate.

### KE-ECON-005 — Cloud reasoning is escalation

Hosted frontier models are optional high-value reasoning accelerators, not the mandatory execution engine.

### KE-ECON-006 — Cheap storage for large evidence

Large immutable evidence belongs in object/file storage, not expensive relational storage.

### KE-ECON-007 — Columnar analytics at scale

Large analytical datasets should use compact open columnar formats such as Parquet where the access pattern benefits from them.

### KE-ECON-008 — Indexes are disposable

Search/vector/semantic indexes must be rebuildable and must never be the authoritative source of scientific truth.

### KE-ECON-009 — Every SaaS dependency needs an exit adapter

Provider-specific logic must sit behind a project-owned boundary so the provider can be replaced without rewriting scientific business logic.

### KE-ECON-010 — Free tiers are opportunities, not assumptions

Pricing allowances may influence deployment choice but may not define core data models or scientific workflows.

### KE-ECON-011 — Local Knowledge Engine remains viable

A user should be able to run a useful version of Knowledge Engine locally without paying Knowledge Engine or a cloud AI provider.

### KE-ECON-012 — Commercial cost should track value-generating usage

Hosted cost should rise primarily with real user activity/revenue-generating workloads, not merely because the corpus passively grows.

---

## Candidate Best-Case Release-to-Scale Path

### Stage A — Current / near-term

Remain focused on the existing roadmap.

- local source vault;
- SQLite and existing data contracts;
- domain-general extraction;
- grounded local AI;
- deterministic verification;
- public web alpha;
- event-triggered snapshots;
- no premature persistent-host build.

### Stage B — Hosted release

Trigger only when the project's existing persistent-host conditions are met.

Potential deployment:

- Cloudflare edge/frontend;
- scale-to-zero Python/FastAPI host;
- Neon/Postgres or another portable SQL service;
- R2/S3-compatible object store;
- Resend or equivalent email;
- product analytics only if needed;
- local/self-hosted model execution where possible;
- hosted-model escalation behind the model router.

### Stage C — Growing corpus

Adopt explicit hot/warm/cold separation.

- SQL for metadata/relationships;
- object storage for immutable evidence;
- Parquet for large analytical datasets;
- DuckDB for local/object-backed analysis;
- rebuildable FTS/vector indexes;
- asynchronous queues for ingestion and enrichment.

### Stage D — Large multi-user platform

Scale components independently rather than replacing the architecture wholesale.

- horizontally scalable read APIs where measured load requires it;
- background workers for extraction/indexing;
- replicated/cached public metadata;
- provider-neutral model router;
- capability/cost/latency-based inference selection;
- durable provenance/audit ledger;
- optional specialized indexes and graph services only after measured need.

### Stage E — Very large knowledge network

The majority of corpus mass should still be inexpensive objects and compressed datasets rather than permanently hot compute.

At this stage the economic goal remains the same:

> expensive resources run because a researcher is asking the system to do valuable work, not merely because the accumulated knowledge base exists.

---

## Explicit Non-Goals

This roadmap item does **not** authorize the following prematurely:

- rewriting the Python scientific core around Cloudflare Workers;
- migrating from SQLite solely because the project is expected to become large;
- placing PDFs or large raw datasets in hosted Postgres by default;
- making a vector database authoritative;
- forcing all inference through one model vendor;
- adding a microservice boundary without measured ownership/scale need;
- adopting a hosted service because its present free tier appears generous;
- using a cloud LLM for deterministic operations;
- building an always-on server before the existing persistent-host trigger is satisfied.

---

## Activation Triggers

Revisit this document when one or more of the following becomes true:

1. the project is preparing a public release with persistent hosted accounts or projects;
2. the current snapshot/subprocess model reaches the persistent-host trigger;
3. local corpus storage or query patterns show a measured need for hot/warm/cold separation;
4. users require asynchronous jobs, notifications, or multi-user state;
5. model inference becomes a material recurring cost;
6. a hosted database/object-store bill becomes measurable enough to optimize;
7. the corpus grows enough that Parquet/DuckDB materially improves analytical throughput;
8. a provider's pricing/terms create lock-in or migration risk;
9. commercial usage requires an explicit unit-economics model.

At activation time, current pricing and terms must be re-verified. The named vendors in this document are candidates, not promises.

---

## Success Criteria

The long-term architecture is successful if Knowledge Engine can grow dramatically while preserving all of the following:

- scientific provenance and auditability;
- local/offline capability;
- provider neutrality;
- reproducible deterministic verification;
- cheap passive corpus storage;
- replaceable model providers;
- low idle infrastructure cost;
- an upgrade path from one-user local operation to a multi-user hosted platform;
- no forced rewrite of scientific business logic when a hosting vendor changes.

The desired end state is not a single giant free server. It is a system in which most of "huge" consists of inexpensive evidence objects, compressed analytical data, durable metadata, and rebuildable indexes, while expensive compute is invoked selectively for valuable work.
