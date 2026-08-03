# Persistent Host Design

Status: design decision only. `knowledge-engine-web` currently consumes
committed snapshot files, and `knowledge-engine-ai` invokes `ke` as a new
subprocess for each core query. This document defines the persistent-host
boundary that can replace those two integrations when operating experience
justifies it. It does not implement a server, add a dependency, or change the
current CLI and snapshot workflows.

## Mission

Define the smallest durable way for Knowledge Engine Core to answer repeated
read requests as a long-running process without making its database schema,
filesystem layout, or CLI output into a network contract.

The host exists to expose core's existing read capabilities. It does not move
scientific judgment into an HTTP layer, turn core into a public write service,
or imply that retrieved or displayed evidence is a scientific conclusion.

## Current State

Core is a command-line application. Each command initializes its own process,
opens the configured SQLite database and supporting evidence files, performs
one operation, and exits. There is no HTTP server, RPC server, process manager,
authentication layer, or persistent connection lifecycle in this repository.

The two concrete consumers have different temporary integrations:

- `knowledge-engine-web` reads a generated SQLite snapshot plus evidence and
  relationship JSONL files. Its `docs/service_boundary_design.md` deliberately
  chose event-triggered snapshot refreshes until core has a persistent host.
  The web application independently reads graph summaries, claim lists,
  unconfirmed claims, relationship candidates, claim details, paper details,
  and retrieval results.
- `knowledge-engine-ai` invokes `ke evidence-report --format json` and
  `ke evidence-intelligence --format json` with `subprocess.run` for every
  request. This preserves package independence, but repeats process startup
  and requires the `ke` executable and core data to be local to the AI process.

These integrations are honest and useful today. A persistent host should
replace them only when its additional operational cost buys measured freshness,
latency, or deployment value.

## Definition

For this project, a **persistent host** is a long-running, read-only HTTP
process that:

1. owns the lifecycle of core's database engine and configured read sources;
2. calls the same domain readers and repositories used by core's CLI;
3. returns versioned, typed JSON contracts rather than terminal text;
4. exposes health and readiness signals to an operator; and
5. remains available across many requests under a process supervisor.

The recommended implementation is a small ASGI application using FastAPI or a
similarly mature framework, served by a production ASGI server. FastAPI is the
leading option because typed request and response models, OpenAPI generation,
input bounds, and testing support fit this boundary. The framework choice is
not made executable by this document: no dependency should be added until the
build trigger is met.

The HTTP layer must wrap domain services, not reimplement SQL or scientific
logic. `GraphRepository`, evidence readers, retrieval services, and Evidence
Intelligence remain the authorities. CLI and HTTP adapters should call the
same application services wherever they expose equivalent operations.

## Requirements

The first host must:

- serve deterministic JSON from the configured core database and evidence
  files;
- preserve stable identifiers, provenance, review status, extraction tier,
  and the project's no-synthesis boundaries;
- keep database sessions and read transactions request-scoped;
- bound pagination, query length, and response size;
- use a versioned API prefix and explicit schema contracts;
- avoid private filesystem paths, raw SQL details, tracebacks, PDF bytes, and
  unrestricted extracted text in responses;
- fail readiness when configured data is absent, incompatible, or internally
  inconsistent; and
- be deployable under the same systemd-oriented operator model already used by
  `knowledge-engine-web`.

## Non-Goals

The first persistent host will not provide:

- corpus import, evidence editing, relationship review, graph rebuilds, or any
  other write endpoint;
- a generic database CRUD API;
- direct database access for web or AI;
- AI inference, answer synthesis, confidence scoring, consensus, or truth
  determination;
- PDF download or delivery;
- user accounts, browser sessions, or a public anonymous API;
- multi-node coordination, horizontal scaling, or distributed job execution;
- websocket or streaming protocols; or
- compatibility guarantees for internal ORM models or database tables.

## Options Considered

### Option A: In-process read-only HTTP host

Run a small ASGI process in the core package and call existing repositories and
reader services directly.

Advantages:

- one domain implementation serves CLI, web, and AI;
- typed HTTP responses form an intentional boundary instead of exposing the
  SQLite schema;
- persistent database setup removes repeated subprocess startup;
- health, readiness, authentication, request limits, and observability have a
  natural home; and
- consumers can deploy separately from the machine holding core's data.

Costs:

- core gains a network-facing runtime and its associated security and
  operations responsibilities;
- mixed SQLite and JSONL state needs an explicit publication policy; and
- endpoint schemas require compatibility discipline.

### Option B: Long-running subprocess gateway

Keep the CLI as the interface and place a daemon in front of repeated `ke`
subprocess calls.

This reduces no architectural coupling: it preserves process startup, command
availability, stderr parsing, and CLI-to-machine-contract pressure while adding
another process. It is not recommended.

### Option C: Shared database access

Let web and AI connect directly to core's live SQLite database or a future
managed database.

This is operationally small but makes internal tables the cross-repository API,
duplicates reader logic, and creates migration and write-ownership ambiguity.
It also does not cover evidence and relationship JSONL sources cleanly. It is
not recommended as the service boundary.

### Option D: Continue snapshot publication

Keep event-triggered snapshots as the only integration.

This remains the correct current choice. It is simple, inspectable, and works
without an always-on core process. It cannot provide request-time freshness or
remove AI's subprocess dependency, so it is an interim integration rather than
the persistent-host design.

### Option E: gRPC or a message broker

Neither current consumer needs bidirectional streaming, durable command queues,
or generated multi-language clients. Those protocols add deployment machinery
without solving a demonstrated problem better than HTTP JSON. They should be
reconsidered only if a future workload supplies those requirements.

## Decision

**When the build trigger is met, implement Option A: a read-only, versioned
HTTP JSON API in a long-running ASGI process, localhost-bound by default, over
the same core reader services used by the CLI. Continue Option D until then.**

The first host is read-only. All imports, evidence promotion, relationship
review, graph builds, and maintenance remain explicit operator-run CLI
workflows. This avoids introducing remote mutation authorization, idempotency,
concurrent SQLite writers, and audit semantics before there is a concrete
consumer for them.

A query endpoint may use HTTP `POST` when its structured input is too rich for
a stable query string. Such an endpoint remains semantically read-only: it
must not mutate scientific or operational state.

Read-write hosting should receive a separate design only after a real remote
write workflow exists. That design must address authorization by operation,
idempotency, audit identity, conflict handling, background work, and recovery;
none may be inferred from this read-only decision.

## API Contract Principles

- Prefix domain endpoints with `/v1`. Health endpoints may remain unversioned.
- Define request and response models independently of ORM classes and CLI
  rendering.
- Return stable IDs and safe domain fields, never local absolute paths.
- Preserve deterministic ordering and require bounded pagination for lists.
- Use one error envelope containing a stable code, a human-readable message,
  and a request ID. Do not return tracebacks or database errors.
- Reject unknown or oversized inputs predictably. Server-side configuration,
  not client parameters, selects the database and evidence files.
- Include a `data_revision` in domain responses so consumers can detect a
  change of published read generation.
- Preserve the existing meanings of review status, extraction tier,
  provenance, and evidence direction. HTTP transport must not reinterpret
  these fields.
- State explicitly on retrieval and intelligence responses that the output is
  retrieval/evidence analysis, not legal approval, scientific review, or a
  synthesized conclusion where that boundary applies.

## Minimal Endpoint Surface

The following surface is the minimum that replaces the current consumer
boundaries rather than creating a generic API.

### Operations

| Method and path | Consumer need | Contract |
| --- | --- | --- |
| `GET /healthz` | systemd, container, and load-balancer liveness | Process is running; no corpus details. |
| `GET /readyz` | safe traffic admission | Configured database and evidence sources are readable and compatible; returns only safe revision/status data. |
| `POST /v1/evidence-reports` | AI `evidence_report`; web `/ask` retrieval | Accepts a bounded question and result limit; returns the existing structured evidence-report data. Configured source paths are never client input. |
| `GET /v1/evidence/{evidence_record_id}/intelligence` | AI `evidence_intelligence`; claim detail | Returns the existing Evidence Intelligence JSON contract, including extraction tier and provenance. |
| `GET /v1/graph` | web graph and dashboard summaries | Returns graph population counts and the current data revision. |
| `GET /v1/claims` | web claim list and unconfirmed-claim view | Paginated claims; an explicit `relationship_status=unconfirmed` filter replaces the separate unconfirmed reader. |
| `GET /v1/claims/{evidence_record_id}` | web claim detail | Returns the graph claim, evidence record, concept edges, authored relationship records with provenance, and related claim references. |
| `GET /v1/papers/{paper_id}` | web paper detail | Returns paper metadata, citations, and linked evidence-record summaries. |
| `GET /v1/relationships` | web relationship list/report | Returns reviewed relationships with deterministic filters and pagination. |
| `GET /v1/relationship-candidates` | web relationship-candidate workflow | Returns the existing candidate projection with bounded ranking/filter parameters; it does not classify relationships. |

This deliberately omits generic report-file endpoints. Web can render its
Markdown/HTML reports from the same structured graph, claim, and relationship
responses it uses for pages. The web-specific "what changed" baseline remains
a web concern until core owns a durable revision history that can answer it.

It also omits a general search endpoint beyond `evidence-reports`. The current
AI client and web `/ask` path need that exact evidence-oriented operation; a
broader search contract should be added only for a concrete consumer.

## Consumer Migration

### knowledge-engine-ai

The AI client can replace its two subprocess calls one for one:

- `ke evidence-report --format json` becomes
  `POST /v1/evidence-reports`.
- `ke evidence-intelligence --format json` becomes
  `GET /v1/evidence/{evidence_record_id}/intelligence`.

AI continues to own optional model inference and synthesis. Core returns the
same evidence and intelligence facts it returns today; the host does not gain
an AI endpoint.

### knowledge-engine-web

Web should introduce a reader interface with snapshot and HTTP adapters, then
migrate one view at a time under parity tests. Claim and paper details can move
first, followed by graph lists and candidates, then `/ask`. The committed
snapshot remains a rollback path until every deployed view has parity and the
host meets its availability target. Only then should web retire snapshot reads.

Consumer migration is not part of the core host implementation PR. Each
repository owns its adapter, timeout, fallback, and deployment change.

## Published Read Generation

Core currently combines SQLite state with evidence and relationship JSONL
files. Reading whichever files happen to exist during an update could expose a
database rebuilt from one evidence generation alongside files from another.

The first host should therefore serve one **published read generation**:

- database and supporting file paths are operator configuration, not request
  parameters;
- startup validates all configured sources together and computes a safe
  `data_revision` from schema/version identifiers and content hashes of the
  small manifest-like JSONL inputs, never PDF content;
- the process does not silently hot-reload individual files;
- after a successful corpus/evidence/graph workflow, the operator publishes
  the complete set and performs a graceful restart (or a later, explicitly
  designed atomic reload); and
- readiness fails rather than serving a partially configured generation.

This is intentionally conservative. A later host can support atomic generation
swaps after real update-frequency measurements justify them. The initial host
must document that filesystem replacement between validation and a request is
an operator coordination risk; it must not claim transactional consistency
across SQLite and JSONL that the storage model does not provide.

## Authentication and Security

### Localhost default

The default bind address must be `127.0.0.1`. Localhost operation may run
without application authentication when the host and its consumers share a
trusted machine. The service must not follow URLs, accept filesystem paths,
serve PDFs, or expose mutation commands.

### Non-loopback access

Binding to a LAN or public interface must fail closed unless a machine-to-
machine API token is configured. Web and AI send that token as an
`Authorization: Bearer` credential. Token comparison must be constant-time;
tokens live in environment/secret storage and never appear in source, URLs, or
logs. Browser code should not call core directly, so the first host needs no
permissive CORS policy.

TLS should terminate at a trusted reverse proxy or hosting platform. A shared
Basic Auth gate, like `knowledge-engine-web`'s password-gated Render alpha, is
acceptable only as an additional small-group human testing gate. It is not a
substitute for the service token between web/AI and core, and neither mechanism
is a user-account system.

Any internet-reachable deployment also needs reverse-proxy request limits,
timeouts, rate limiting, secret rotation, firewall rules, and access logs that
exclude query text and evidence content. Until those exist, non-loopback use is
trusted-network or password-gated alpha only, matching web's deployment
precedent rather than implying production hardening.

## Hosting and Operations

The first deployment target is one self-hosted process managed by systemd,
parallel to `knowledge-engine-web`:

```ini
# /etc/systemd/system/knowledge-engine-core-host.service
[Unit]
Description=Knowledge Engine Core Read Host
After=network.target

[Service]
Type=simple
User=knowledge-engine
WorkingDirectory=/path/to/knowledge-engine-core
Environment=KE_HOST_BIND=127.0.0.1
Environment=KE_HOST_PORT=8100
Environment=KE_DATABASE_URL=sqlite:////path/to/data/knowledge_engine.sqlite3
Environment=KE_EVIDENCE_RECORDS_PATH=/path/to/evidence_records.jsonl
Environment=KE_RELATIONSHIP_RECORDS_PATH=/path/to/relationship_records.jsonl
ExecStart=/path/to/poetry run ke-host
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

The names and executable above are proposed contracts, not existing code. As
with web's systemd guidance, deployed file paths should be explicit absolute
operator configuration so a changed working directory cannot silently select
an empty database. Those paths must never be returned to clients.

Start with one worker. SQLite reads and in-process evidence indexes make a
single process the easiest consistency model; add workers only after load
testing demonstrates a need and verifies generation consistency. The process
must support graceful shutdown, request IDs, bounded timeouts, liveness and
readiness probes, and structured operational logs without scientific query
payloads.

A public Render-style core deployment is not recommended while the authoritative
database and evidence files live on a self-hosted machine. Web's Render alpha
should reach a secured core host only after network ingress, TLS, credentials,
backup, and availability are deliberately operated. Otherwise snapshots remain
the safer deployment boundary.

## Failure Behavior

- Liveness reports only process health; readiness reports source usability.
- Missing, unsupported, or mismatched configured sources make readiness fail.
- Unknown stable IDs return `404`; invalid input returns `422` or the selected
  framework's equivalent stable client-error response.
- Busy or unavailable storage returns a sanitized `503`, not a traceback.
- Timeouts and response limits fail the request without changing state.
- No endpoint falls back to a different database or corpus implicitly.
- Consumer clients use explicit timeouts and may choose their own documented
  fallback. Core does not silently serve stale snapshots under a live revision.

## Compatibility Policy

`/v1` is a consumer contract, not a promise that internal data models stop
evolving. Additive response fields are permitted. Removing or reinterpreting a
field requires a new API version and a measured consumer migration. Contract
fixtures should be shared as checked-in examples or generated schemas, not by
importing one repository's Python models into another.

The CLI remains supported. Hosting must not force local users to run a server,
and the CLI must not become an HTTP client when local domain services are
available.

## Testing Strategy When Built

- Unit-test HTTP adapters against domain-service fakes; keep domain behavior
  covered outside the framework.
- Add contract tests for every endpoint, error envelope, ordering rule,
  pagination bound, extraction tier, and no-synthesis disclaimer.
- Run parity fixtures against CLI JSON, snapshot readers, and HTTP responses
  before migrating each consumer.
- Test startup/readiness against missing files, unsupported schemas, mismatched
  generations, and read-only database permissions.
- Test localhost defaults, non-loopback fail-closed behavior, token rejection,
  Rich/HTML-like user text, path redaction, size limits, and log redaction.
- Test concurrent reads and graceful restart against a representative corpus.
- Verify that no endpoint writes database rows or changes configured files.

## Build Trigger

Do not build the host merely because this design exists. Begin implementation
only when all of the following are true:

1. an always-on machine or hosted environment has a named operator, backup
   policy, monitoring owner, and a supported way to reach the authoritative
   core data;
2. either web has an approved HTTP-reader migration or AI has an approved
   subprocess-replacement migration, backed by a measured freshness, latency,
   or deployment problem in the current integration;
3. that consumer accepts the relevant `/v1` request/response fixtures and has
   an adapter/fallback plan;
4. the published-read-generation and restart procedure is tested against the
   real database and evidence files; and
5. binding, TLS termination, machine credentials, secret rotation, and request
   limits are decided for the target network.

The first qualifying consumer determines the first implementation slice. If AI
is first, build health/readiness plus the two evidence endpoints. If web is
first, add only the graph/detail endpoints needed by the first migrated views.
Do not implement the entire endpoint table speculatively.

## Suggested Implementation Sequence

1. Extract or confirm framework-independent application services for the first
   consumer operations and freeze representative JSON fixtures.
2. Add the ASGI host, configuration, health/readiness, request limits, and
   localhost-safe defaults.
3. Implement only the first consumer's endpoints and parity tests.
4. Deploy under systemd, measure latency and reliability, and exercise graceful
   generation publication.
5. Migrate that consumer behind an adapter while retaining its current
   snapshot or subprocess fallback.
6. Add the second consumer's endpoints only after the first slice is stable.
7. Revisit public exposure and read-write needs as separate decisions.

## Risks

- **False consistency:** SQLite and JSONL are not one transaction. The published
  generation and restart rule must remain visible until storage changes.
- **Schema leakage:** hurried endpoints could expose ORM/table details and make
  migrations externally breaking. Explicit response models prevent this.
- **Security expansion:** a localhost reader can become internet-reachable with
  one bind change. Non-loopback startup must fail closed.
- **Scientific-boundary drift:** an endpoint named "answer" could imply
  synthesis or truth. Contracts should retain existing evidence/retrieval
  names and disclaimers.
- **Operational duplication:** running web and core under different patterns
  creates needless burden. The systemd and reverse-proxy model should remain
  aligned.
- **Premature breadth:** implementing every CLI command over HTTP would create
  a large compatibility surface with no consumer. The endpoint list is a
  ceiling for replacement work, not one mandatory first PR.

## Open Questions at Implementation Time

- Which consumer meets the build trigger first, and which exact endpoint subset
  does its adapter require?
- What availability and latency target has been measured as necessary?
- Should the first deployed generation be restart-only, or has update frequency
  justified an atomic reload mechanism?
- Which reverse proxy and secret store are available on the selected host?
- At what corpus size do list pagination and evidence-response limits need
  adjustment?

These questions depend on a real deployment and consumer migration. They are
not reasons to add speculative host code now.

## Final Recommendation

Keep event-triggered web snapshots and AI subprocess calls as the current
working boundaries. When the stated trigger is met, build a small read-only
ASGI host in core, localhost-first and systemd-managed, backed by existing
domain readers and a coherent published data generation. Migrate one concrete
consumer operation at a time under contract parity tests. Treat remote writes,
public launch hardening, and broader APIs as separate future designs.
