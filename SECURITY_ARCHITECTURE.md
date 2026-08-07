# Knowledge Engine Security Architecture

Status: Master security blueprint  
Scope: Knowledge Engine Core, Web, AI, ingestion, hosted infrastructure, and security operations  
Audience: project owner, contributors, reviewers, and future operators  

## 1. Purpose

Knowledge Engine is an evidence-first scientific research platform. Its security architecture must protect user data, preserve scientific provenance, constrain AI behavior, limit the blast radius of software defects, and remain realistic for an independently built open-source project.

The goal is not to claim that the system can never be compromised. The goal is defense in depth:

- prevent common attacks;
- make exploitation difficult;
- prevent one compromise from becoming total compromise;
- detect suspicious activity quickly;
- preserve evidence during incidents;
- recover from a known-good state;
- keep security controls understandable and maintainable by a small team.

This document defines the desired finished production state and the staged path to reach it.

## 2. Project-Specific Security Philosophy

Knowledge Engine already separates evidence, provenance, retrieval, review, graph relationships, and AI interpretation. Security should preserve that same discipline.

The central security invariant is:

> Evidence may influence conclusions, but evidence never receives authority.

A paper, PDF, webpage, abstract, metadata record, retrieved passage, embedding result, or other external source is data. It never gains permission to override application policy, disclose private data, invoke unauthorized tools, alter credentials, or change security rules.

Additional core principles:

1. **Untrusted by default.** Internet traffic, uploaded files, retrieved content, metadata, model output, and client-supplied identifiers are untrusted until validated.
2. **Least privilege.** Every user, process, service, credential, and tool receives only the permissions required for its task.
3. **Deny by default.** Missing authorization, ambiguous identity, malformed input, uncertain file type, unsupported network target, or unclear tool request should fail closed.
4. **No single catastrophic boundary.** A parser exploit, AI mistake, web vulnerability, stolen token, or dependency defect should not automatically expose the entire system.
5. **Deterministic controls around probabilistic systems.** AI may propose or reason; deterministic application code decides permissions.
6. **Provenance is a security property.** Source identity, content hashes, import receipts, review state, and evidence lineage must not be silently rewritten.
7. **Security must be testable.** Important controls require automated tests where practical.
8. **Security must be recoverable.** Backups, revocation, lockdown, and rebuild procedures are part of security, not separate operational concerns.
9. **Complexity is itself a risk.** Prefer boring, well-understood controls over unnecessary microservices or custom security infrastructure.

## 3. Current Architectural Context

The current system is intentionally evolving in stages.

- `knowledge-engine-core` is offline-first and owns scientific source ingestion, provenance, evidence structures, retrieval foundations, and graph data.
- Core currently supports local PDF ingestion, SQLite persistence, deterministic validation, evidence extraction/review workflows, lexical and semantic retrieval, external metadata/discovery integrations, and bounded acquisition workflows.
- `knowledge-engine-web` exposes a read-only public laboratory over published point-in-time data.
- `knowledge-engine-ai` consumes evidence and retrieval outputs rather than owning scientific truth.
- A persistent read-only host boundary is designed but deliberately gated until operational and network-security prerequisites are met.

Security work must strengthen this architecture rather than prematurely converting Core into an always-online service.

## 4. Desired Production Architecture

The realistic mature production topology is:

```text
Internet
   |
   v
Edge provider / CDN / WAF
   - TLS
   - DDoS mitigation
   - bot controls
   - coarse rate limits
   |
   v
Reverse proxy / hosted web entry
   |
   v
Knowledge Engine Web / FastAPI
   - authentication
   - authorization
   - request validation
   - session controls
   - application rate limits
   |
   +----------------------+----------------------+
   |                      |                      |
   v                      v                      v
Core services          AI/RAG boundary       Ingestion worker
read-focused           restricted tools      isolated parser
business logic         no implicit trust      hostile-file model
   |                      |                      |
   +----------------------+----------------------+
                          |
                          v
                 Private data services
                 - PostgreSQL
                 - vector index
                 - object storage
                 - backups

Separate operational plane:

GitHub/CI -> tests, dependency scanning, SAST, secret scanning
Logs -> centralized monitoring and alerts
Secrets -> managed secret store / platform secrets
Backups -> encrypted, versioned, isolated retention
```

This is intentionally simpler than a large-enterprise microservice platform. Logical boundaries may remain separate Python packages or services until scale or isolation requirements justify additional infrastructure.

## 5. Threat Model

### 5.1 Protected Assets

High-value assets include:

- private or unpublished user documents;
- user account identities and sessions;
- API credentials and service secrets;
- production database contents;
- source documents and their provenance records;
- reviewed Evidence Records and relationship records;
- scientific audit trails and content hashes;
- infrastructure credentials;
- administrative privileges;
- model/tool permissions;
- backups and security logs;
- application integrity and public trust.

### 5.2 Expected Attackers

The production system should assume exposure to:

- automated Internet scanners;
- credential-stuffing bots;
- scraping and resource-abuse bots;
- opportunistic attackers searching for known vulnerabilities;
- malicious uploaders;
- prompt-injection authors;
- users attempting horizontal or vertical privilege escalation;
- dependency/supply-chain attackers;
- attackers specifically targeting Knowledge Engine because of its data or visibility;
- compromised user accounts;
- compromised third-party services.

The architecture does not assume that all attacks will be sophisticated. Many successful attacks exploit basic configuration mistakes, stale dependencies, weak access controls, leaked secrets, or unsafe parsing.

### 5.3 Primary Trust Boundaries

1. Internet -> edge provider.
2. Edge provider -> application.
3. Anonymous client -> authenticated identity.
4. Authenticated identity -> authorized resource.
5. Uploaded file -> parser/sanitized representation.
6. External metadata provider -> internal normalized record.
7. Retrieved scientific content -> AI context.
8. AI model output -> application tool request.
9. Application -> database/storage.
10. Application -> outbound network.
11. Development environment -> production.
12. CI/CD -> deployment environment.
13. Production -> backup account/storage.

### 5.4 Attacker-Controlled Inputs

Treat the following as attacker-controlled or potentially hostile:

- HTTP paths, headers, bodies, cookies, query parameters, and forms;
- filenames and uploaded bytes;
- PDFs and embedded PDF objects;
- DOI strings, URLs, search strings, metadata values, titles, abstracts, and authors;
- provider API responses;
- HTML and XML from external systems;
- retrieved full text;
- vector-search results and RAG context;
- LLM responses;
- tool arguments proposed by an LLM;
- user-supplied structured data;
- import manifests not produced by a trusted deterministic pipeline;
- environment and configuration values supplied outside controlled deployment.

## 6. Security Invariants

The following properties must remain true in the finished system.

### Identity and access

- Authentication never implies authorization.
- Every private resource is checked against the requesting principal.
- Administrative privileges are explicit and auditable.
- Privileged actions cannot be authorized solely by LLM output.
- Production administrative accounts use phishing-resistant MFA or equivalent strong MFA where supported.

### Files and ingestion

- User-controlled filenames never become trusted filesystem paths.
- Uploads receive generated internal identifiers.
- Supported file type is verified independently of extension.
- Upload size, page count, extraction time, CPU, memory, and temporary-storage usage are bounded.
- High-risk parsing occurs in a constrained execution environment before public multi-user uploads are enabled.
- Parsing workers do not receive production database or infrastructure credentials unless strictly required.
- Parsing workers do not receive unrestricted network access.

### AI and retrieval

- Retrieved content is always lower trust than system/application policy.
- A document cannot grant itself tool permissions.
- Model-generated tool requests pass deterministic authorization and validation.
- High-impact operations require explicit application policy and, when appropriate, user confirmation.
- Model prompts never contain unnecessary production secrets.
- Untrusted content cannot directly construct executable shell commands, SQL, filesystem paths, or network destinations.

### Data

- Production databases are not exposed directly to the public Internet.
- Parameterized queries/ORM bindings are required for user-controlled values.
- Cross-user data isolation is enforced server-side.
- Sensitive data is encrypted in transit and at rest using platform-supported controls.
- Backups are encrypted and separated from normal application deletion privileges.

### Secrets

- Secrets are never committed to source control.
- Development, staging, and production secrets are separate.
- Credentials are scoped, revocable, and rotatable.
- Logs never intentionally record passwords, session tokens, private keys, or full secret values.

### Provenance

- Imported source identity and hashes cannot be silently replaced.
- Scientific evidence state changes remain attributable and reviewable.
- Security sanitization must not silently rewrite scientific content without retaining provenance of the transformation.

## 7. Security Control Domains

### 7.1 Edge and Network Security

**Required before public production**

- HTTPS only.
- Managed edge/CDN/WAF provider where practical.
- DDoS mitigation supplied by the hosting/edge provider.
- Request-body limits.
- Basic bot and abuse controls.
- IP- and account-aware rate limiting where appropriate.
- Origin services configured so direct bypass of the edge layer is minimized where supported.
- Database ports private.

**Recommended as usage grows**

- endpoint-specific WAF rules;
- reputation-based bot controls;
- automated temporary blocks for abusive patterns;
- outbound egress restrictions by workload.

### 7.2 Authentication and Session Security

Do not build a custom password/cryptography stack when a mature managed identity or established library can be used.

**Required when accounts exist**

- standards-based authentication;
- secure, HttpOnly, SameSite cookies for browser sessions where applicable;
- CSRF protection for state-changing browser actions;
- short and documented session/token lifetimes;
- logout and server-side revocation strategy;
- rate limits on login and recovery flows;
- secure account-recovery process;
- MFA support, mandatory for administrators;
- generic authentication error messages that do not disclose account existence unnecessarily.

### 7.3 Authorization

Authorization is a server-side policy decision.

Each protected operation should resolve:

1. authenticated principal;
2. requested action;
3. requested resource;
4. resource owner/tenant;
5. role/permission;
6. final allow/deny result.

Never rely on hidden UI controls as authorization.

Tests must explicitly cover horizontal access attempts, such as User A requesting User B's document identifier.

### 7.4 Input Validation

Use typed Pydantic schemas and bounded fields at API boundaries.

Define maximum lengths and accepted formats for:

- identifiers;
- DOI values;
- search strings;
- URLs;
- filenames/display names;
- metadata fields;
- pagination;
- filters;
- model/tool arguments.

Reject invalid values before they reach persistence, filesystem operations, parsers, outbound requests, or tool execution.

### 7.5 Secure File Handling

For local/offline Core, retain and strengthen existing path-safety rules.

For public upload capability, add:

- generated UUID or content-addressed internal names;
- extension + MIME + magic-byte validation;
- maximum compressed and extracted sizes;
- maximum page count;
- quarantine before processing;
- content hash before and after processing where appropriate;
- temporary working directories;
- no executable upload directories;
- no path construction from raw filenames;
- explicit cleanup behavior;
- parser timeout;
- CPU/memory/disk quotas;
- sandbox/container boundary before public untrusted uploads.

Malware scanning can be added as an additional signal, not as a substitute for sandboxing and validation.

### 7.6 Scientific Ingestion and External Providers

External discovery and metadata sources are separate trust categories.

Provider responses must:

- be schema validated;
- retain source/provenance identity;
- never silently override canonical data without defined policy;
- use explicit timeouts;
- use bounded retries;
- enforce response-size limits;
- restrict redirect behavior where acquisition security requires it;
- use allowlisted hosts for automated acquisition when the workflow depends on known hosts;
- reject private, loopback, link-local, metadata-service, and otherwise disallowed network destinations.

Existing provider-specific adjudication boundaries should remain explicit rather than collapsing all external data into one trusted metadata source.

### 7.7 SSRF and Outbound Network Security

Any user-influenced URL fetch is high risk.

Production fetchers should:

- allow only necessary schemes;
- validate hostnames before connection;
- resolve and reject private/internal IP ranges;
- protect against DNS rebinding where relevant;
- disable unrestricted redirects;
- revalidate redirect destinations;
- enforce connect/read timeouts;
- cap response bytes;
- use allowlists for high-trust acquisition pipelines when practical;
- separate general research retrieval from privileged internal services.

Ingestion workers that do not need network access should have none.

### 7.8 Database Security

**Local edition**

- SQLite remains acceptable for offline/local use.
- Restrict database path handling.
- Continue atomic transactions and rollback behavior.
- Treat local database corruption and untrusted database replacement as integrity risks.

**Hosted production**

- Prefer managed PostgreSQL once multi-user persistent hosting requires it.
- No public database endpoint where avoidable.
- TLS to database.
- separate application credential from administrative/migration credential;
- least-privilege database roles;
- parameterized ORM/database access;
- migration-controlled schema changes;
- automated backups;
- restoration testing;
- ownership/tenant identifiers on private resources;
- indexes and query limits that reduce trivial resource exhaustion.

### 7.9 AI/RAG Security Boundary

The model is not a trusted security principal.

The application must distinguish:

```text
System policy               highest trust
Application security rules  high trust
Authenticated user request  authorized but untrusted content
Retrieved evidence          untrusted content
External webpage/document   untrusted content
Model output                untrusted proposal
```

Prompt-injection defenses should include:

- explicit separation of instructions from retrieved evidence;
- retrieval labels/provenance passed alongside evidence;
- no secrets in model context unless absolutely necessary;
- no direct shell or unrestricted filesystem access;
- no direct raw database credential access;
- allowlisted tools;
- strict tool schemas;
- deterministic authorization before each tool call;
- bounded tool results;
- output encoding before rendering model-generated content;
- tests containing indirect prompt injections embedded in scientific-looking documents.

### 7.10 Tool Authorization Firewall

If AI tools are enabled, every call passes through a deterministic gate.

Minimum decision fields:

- authenticated user;
- requested tool;
- requested resource;
- normalized arguments;
- permission policy;
- rate/quota state;
- risk class;
- confirmation requirement;
- audit event.

Example risk classes:

**Low risk**

- search indexed public evidence;
- retrieve a public Evidence Record;
- query approved metadata providers.

**Medium risk**

- ingest user-owned file;
- write user-owned annotation;
- start bounded background analysis.

**High risk**

- delete private data;
- export large private datasets;
- change account permissions;
- send external communications;
- execute code;
- access arbitrary URLs;
- change production configuration.

High-risk tools should remain unavailable unless the product genuinely needs them.

### 7.11 Secrets Management

Repository controls:

- `.env` and credential files ignored;
- `.env.example` contains placeholders only;
- GitHub secret scanning enabled where available;
- push protection enabled where available;
- no credentials in fixtures, notebooks, documentation, screenshots, or test outputs.

Deployment controls:

- environment/platform secret store;
- separate secrets per environment;
- service-specific credentials;
- key rotation procedure;
- immediate revocation procedure;
- avoid long-lived broad cloud credentials.

If a secret is ever committed, assume compromise and rotate it. Removing it from the latest Git commit is not sufficient.

### 7.12 Dependency and Supply-Chain Security

Required CI controls should progressively include:

- Dependabot or equivalent dependency update automation;
- `pip-audit` for Python dependency vulnerabilities;
- CodeQL where supported;
- Bandit for Python security-oriented static analysis;
- secret scanning;
- locked dependency resolution;
- test suite;
- Ruff and mypy quality gates already used by the project;
- container-image vulnerability scanning once production images exist;
- SBOM generation for production releases once release packaging stabilizes.

Avoid adding dependencies solely for convenience when the same behavior can be implemented safely with existing trusted libraries.

### 7.13 CI/CD and Repository Protection

Before production deployment:

- protect `main`;
- require pull requests for normal changes;
- require automated tests;
- require security checks for security-sensitive changes;
- prevent deployment from untrusted fork contexts with production secrets;
- minimize GitHub Actions token permissions;
- pin high-risk third-party actions to trusted versions/commit SHAs where practical;
- separate build credentials from runtime credentials;
- maintain a rollback path;
- do not automatically deploy a change when required security checks fail.

### 7.14 Browser and API Hardening

Before public multi-user production:

- strict CORS allowlist;
- secure cookies;
- CSRF protection where cookie-authenticated state changes exist;
- Content-Security-Policy appropriate to the frontend;
- HSTS after HTTPS deployment is stable;
- `X-Content-Type-Options: nosniff`;
- frame restrictions / `frame-ancestors` policy;
- safe cache headers for private responses;
- output encoding for user/model/provider-controlled content;
- no stack traces or secrets in production error responses;
- API request and response size limits;
- pagination caps.

### 7.15 Rate Limiting, Quotas, and Abuse Controls

Rate limiting is both a security and cost-control requirement.

Apply limits by endpoint and risk:

- login/recovery;
- search;
- LLM requests;
- uploads;
- external acquisition;
- expensive analytical operations;
- exports.

Use account limits in addition to IP limits for authenticated users.

The system should return controlled errors rather than allowing unlimited queue growth or memory exhaustion.

### 7.16 Logging and Auditability

Security-relevant events should use structured logging.

Examples:

- authentication success/failure;
- MFA failure;
- authorization denial;
- admin action;
- upload accepted/rejected/quarantined;
- parser timeout/resource violation;
- rate-limit event;
- outbound URL rejection;
- tool authorization denial;
- suspicious bulk export;
- secret/configuration failure;
- deployment event.

Never intentionally log:

- passwords;
- session cookies;
- bearer tokens;
- private keys;
- complete API secrets;
- unnecessary full private documents.

Use request/event correlation IDs without leaking sensitive user content.

### 7.17 Monitoring and Detection

The realistic small-project production target is centralized logs plus actionable alerts, not a custom enterprise SIEM.

Alert on conditions such as:

- sustained authentication failures;
- unusual authorization denials;
- large spikes in 4xx/5xx responses;
- parser failures or sandbox terminations;
- unusual upload volume;
- rate-limit spikes;
- outbound request blocks;
- unexpected admin activity;
- dependency vulnerability alerts;
- backup failure;
- storage/database capacity risk.

Alert thresholds should be tuned from observed normal behavior.

### 7.18 Backups and Recovery

Backups must be designed for compromise, not only hardware failure.

Production requirements:

- automated database backups;
- important object/document metadata backed up according to retention policy;
- encryption;
- versioning/retention where supported;
- backup credentials separated from normal application credentials;
- application cannot casually erase all historical backups;
- documented restoration procedure;
- periodic restore test.

Do not claim disaster recovery capability until restoration has been demonstrated.

### 7.19 Administrative Security

Administrative capability should be small and explicit.

- minimum number of admins;
- MFA required;
- privileged actions audited;
- admin sessions shorter than standard sessions where practical;
- no shared administrator accounts;
- normal browsing/research should use a normal account, not an admin account;
- production secrets not visible in normal admin UI;
- destructive bulk operations require additional confirmation.

### 7.20 Privacy and Data Lifecycle

If users can upload private documents, the product must define:

- what is stored;
- where it is stored;
- retention period;
- deletion behavior;
- whether model providers receive content;
- whether content is used for training by any third party;
- backup retention after deletion;
- audit/legal limitations.

The application should collect the minimum personal data needed for operation.

## 8. Production Isolation Strategy

Keep four environments conceptually separate:

```text
Local development
      |
      v
Development/test hosting
      |
      v
Staging
      |
      v
Production
```

They should not share production credentials.

Production user data should not be copied into development by default.

A production deployment should be reproducible from version-controlled source, dependency locks, configuration templates, migration history, and platform configuration rather than from undocumented manual server changes.

## 9. Secure Ingestion End State

The finished public upload path should follow this sequence:

```text
Upload
  |
  v
Request limit
  |
  v
Quarantine
  - generated identifier
  - hash
  - extension/MIME/magic validation
  - size/page policy
  |
  v
Isolated parser worker
  - no shell exposed to user input
  - no production credentials
  - no unrestricted network
  - CPU/RAM/disk/time limits
  |
  v
Validated extraction artifact
  |
  v
Core normalization/provenance checks
  |
  v
Persistence
```

The original file remains untrusted even after successful parsing.

## 10. AI Attack Model

The system should explicitly test scenarios including:

- paper contains hidden prompt injection;
- abstract instructs model to ignore policy;
- webpage asks model to reveal secrets;
- retrieved document requests a tool call;
- model invents a privileged tool argument;
- user asks model to access another user's resource;
- poisoned retrieval result attempts to rewrite provenance;
- external text embeds shell/SQL/path payloads;
- malicious citation metadata includes HTML/JavaScript;
- model attempts repeated expensive calls to exhaust quota.

Expected outcome: the content may be quoted or analyzed as evidence, but it cannot acquire authorization.

## 11. Security Testing Strategy

### Unit tests

Examples:

- path traversal rejected;
- unsupported URL schemes rejected;
- private/internal SSRF targets rejected;
- oversized search strings rejected;
- upload limits enforced;
- unauthorized cross-user resource access denied;
- invalid tool arguments denied;
- sensitive values redacted from logs.

### Integration tests

- auth + authorization across real API routes;
- upload -> sandbox -> extraction boundaries;
- database ownership checks;
- restricted outbound fetch behavior;
- token/session revocation;
- restore procedure in non-production environment.

### Fuzz/property tests

Use selectively for parsers, URL normalization, identifier validation, and other high-risk boundary code.

### Security regression tests

Every confirmed security bug should receive a regression test when feasible.

### Pre-release adversarial review

Before public multi-user release, perform a focused security review covering:

- access control;
- file ingestion;
- SSRF;
- injection;
- secret exposure;
- deployment configuration;
- AI prompt injection/tool misuse;
- private-data isolation.

Professional external penetration testing becomes recommended once real users, valuable private research, revenue, institutional adoption, or materially increased exposure justify the cost.

## 12. Incident Response

The project should maintain a short operator playbook.

### Detect

Confirm suspicious behavior using logs and alerts.

### Contain

Available actions should eventually include:

- revoke user sessions;
- revoke API tokens;
- rotate compromised credentials;
- disable new uploads;
- disable AI tools;
- disable outbound acquisition/fetching;
- switch selected functions to read-only;
- block abusive sources at edge/application layers;
- isolate affected worker/service.

### Preserve

Preserve relevant logs, timestamps, affected identifiers, hashes, deployment versions, and other evidence before destructive cleanup.

### Eradicate

Patch the root cause, remove unauthorized persistence, rotate affected credentials, and rebuild affected workloads from trusted artifacts where necessary.

### Restore

Restore service from a known-good version and verified data/backups.

### Review

Document:

- initial access vector;
- affected assets;
- duration;
- detection method;
- control failures;
- remediation;
- new regression tests;
- architecture changes.

## 13. Emergency Lockdown Mode

The mature application should support configuration-level emergency controls without requiring a code rewrite during an incident.

Potential switches:

- disable account creation;
- disable uploads;
- disable external network retrieval;
- disable AI tool execution;
- disable exports;
- force reauthentication;
- revoke all sessions;
- read-only application mode;
- maintenance mode.

These controls should be authenticated, audited, and unavailable to normal users.

## 14. Security Delivery Tiers

Controls are classified as **Required**, **Recommended**, or **Future** based on the product stage.

### Stage 0 - Current / Local-First Development

**Required**

- maintain `SECURITY.md`;
- maintain this security architecture;
- secret-free repository;
- `.env` exclusion and placeholder-only examples;
- dependency lockfiles;
- path-safety tests;
- bounded external requests;
- schema validation;
- tests for existing trust boundaries;
- GitHub dependency/secret alerts where available;
- preserve provider provenance boundaries;
- no silent scientific data rewriting.

**Recommended**

- add `pip-audit`;
- add Bandit;
- add CodeQL;
- Dependabot configuration;
- explicit security test directory/tagging.

### Stage 1 - Public Read-Only Alpha

The current web alpha is intentionally read-only. Do not add write-oriented security complexity until the product actually adds writes.

**Required**

- HTTPS;
- production secrets separated from repository;
- read-only published snapshot/data boundary;
- no database credentials in browser/client code;
- request-size caps;
- safe error handling;
- secure headers;
- basic rate limiting;
- dependency scanning;
- logging of application failures;
- deployment rollback path.

**Recommended**

- managed edge/CDN/WAF;
- staging environment;
- automated deployment security checks.

### Stage 2 - Persistent Read-Only Host

Activate only after the project's existing persistent-host trigger conditions are satisfied.

**Required**

- private production database/network boundary;
- least-privilege read-only consumer credentials where architecture allows;
- TLS to backing services;
- automated backups;
- restore test;
- outbound network controls;
- deployment identity separation;
- monitoring and alerts;
- protected main branch / required CI checks.

### Stage 3 - Public Accounts / Private User Data

**Required before launch**

- managed/standards-based authentication;
- server-side authorization;
- cross-user isolation tests;
- MFA for administrators;
- secure sessions;
- account recovery protections;
- privacy/data-retention policy;
- audit events;
- encrypted storage and transport;
- user deletion workflow;
- production PostgreSQL or equivalent multi-user database architecture.

### Stage 4 - Public Document Uploads

**Required before untrusted public uploads**

- quarantine;
- file signature/MIME validation;
- generated internal names;
- size/page/resource limits;
- parser timeouts;
- isolated parser worker/container;
- no parser production secrets;
- restricted parser network;
- cleanup policy;
- upload quotas;
- malicious-input regression corpus;
- security monitoring for parser failures.

### Stage 5 - Public AI/RAG

**Required before AI can access private data or tools**

- explicit instruction/evidence trust separation;
- model output treated as untrusted;
- deterministic tool authorization;
- allowlisted tools;
- strict tool schemas;
- per-user resource authorization inside tools;
- prompt-injection regression tests;
- private-data leakage tests;
- AI request quotas;
- no unnecessary secrets in context;
- bounded tool results;
- audit events for tool use.

### Stage 6 - Production Maturity

**Required**

- documented incident-response process;
- emergency lockdown controls;
- periodic dependency/security review;
- periodic restore test;
- alert review;
- credential rotation practice;
- security regression tests maintained with code.

**Recommended when exposure justifies it**

- independent penetration test;
- external architecture review;
- stronger bot management;
- container image signing/verification;
- formal SBOM release artifacts;
- coordinated vulnerability disclosure process with a stable private contact.

### Stage 7 - High-Value / Institutional Scale

These controls are intentionally **Future**, not current requirements.

Consider when user count, private-data value, revenue, institutional adoption, contractual requirements, or attack volume justify the complexity:

- paid recurring penetration testing;
- formal bug bounty;
- dedicated SIEM;
- dedicated security staff/consultant retainer;
- multi-region disaster recovery;
- hardware-backed production key management;
- advanced behavioral detection;
- tenant-specific encryption keys;
- formal compliance programs;
- sophisticated zero-trust service networking.

## 15. Practical Milestone Checklist

### Now

- [ ] Expand security tests around existing path and ingestion boundaries.
- [ ] Add Dependabot.
- [ ] Add `pip-audit` CI.
- [ ] Add Bandit CI.
- [ ] Add CodeQL if compatible with repository settings.
- [ ] Confirm secret scanning / push protection settings.
- [ ] Review GitHub Actions token permissions.
- [ ] Inventory outbound HTTP clients and define host/timeout/size policy.
- [ ] Inventory every filesystem path built from external values.
- [ ] Record security invariants in contributor/review guidance.

### Before Public Beta

- [ ] Managed edge protection.
- [ ] Explicit API rate limits.
- [ ] strict CORS/security headers.
- [ ] staging/prod secret separation.
- [ ] centralized structured logging.
- [ ] alerting for repeated failures/abuse.
- [ ] production backup automation.
- [ ] successful non-production restore drill.
- [ ] protected branch and required CI checks.

### Before Accounts / Private Documents

- [ ] standards-based authentication.
- [ ] authorization matrix.
- [ ] tenant/owner isolation tests.
- [ ] admin MFA.
- [ ] privacy/retention/deletion policy.
- [ ] encrypted private storage.
- [ ] audit trail for private-resource access.

### Before Public Uploads

- [ ] quarantine.
- [ ] MIME/magic verification.
- [ ] generated internal filenames.
- [ ] resource limits.
- [ ] isolated parser.
- [ ] restricted parser egress.
- [ ] malicious PDF regression fixtures.
- [ ] upload quotas.

### Before AI Tool Use

- [ ] tool allowlist.
- [ ] deterministic tool firewall.
- [ ] user/resource authorization in every private-data tool.
- [ ] prompt-injection test corpus.
- [ ] tool-abuse tests.
- [ ] model-context secret review.
- [ ] emergency AI/tool disable switch.

### Before Production Launch

- [ ] threat model reviewed against actual deployed architecture.
- [ ] security scan clean or risks explicitly accepted.
- [ ] restore drill successful.
- [ ] incident playbook tested with tabletop exercise.
- [ ] credentials rotated from development/test values.
- [ ] admin MFA verified.
- [ ] dependency and image scans pass.
- [ ] logs and alerts verified.
- [ ] backup retention verified.
- [ ] public vulnerability-reporting path verified.

## 16. Security Review Questions for Every New Feature

Every security-sensitive feature should answer:

1. What new input becomes attacker-controlled?
2. What asset can this feature read or modify?
3. Does it cross a trust boundary?
4. Which identity performs the action?
5. Where is authorization checked?
6. What is the maximum CPU, memory, time, storage, and network cost?
7. Can untrusted content influence a filesystem path, SQL query, URL, HTML, shell command, or tool call?
8. What secrets are available to this component?
9. What happens if this component is compromised?
10. Can the action be logged without leaking private data?
11. How is the feature disabled during an incident?
12. What automated security test proves the key invariant?

## 17. Explicit Non-Goals

The project should not prematurely build:

- a custom authentication protocol;
- custom cryptographic algorithms;
- a custom WAF;
- a custom DDoS network;
- a custom enterprise SIEM;
- dozens of microservices solely for perceived security;
- expensive multi-region infrastructure before product demand requires it;
- unrestricted autonomous AI agents;
- shell access for model-driven workflows without an exceptional, isolated use case.

## 18. Definition of Secure Enough to Launch

Knowledge Engine is ready for a given public capability only when the controls required for that capability's stage are implemented and tested.

Examples:

- A read-only public demonstration does not require public-upload sandboxing if public uploads do not exist.
- Public document uploads do require isolation before arbitrary users can submit files.
- Private research storage requires real authentication, authorization, tenant isolation, and privacy controls.
- AI tool execution requires deterministic permission enforcement before tools are exposed.

This staged rule prevents both under-securing real attack surfaces and over-engineering hypothetical ones.

## 19. Long-Term Target State

The mature Knowledge Engine should be able to withstand the following without catastrophic compromise:

- automated scanning and common web exploitation attempts;
- credential stuffing and basic account abuse;
- malicious PDFs and parser crashes;
- malformed metadata and provider responses;
- prompt injection embedded inside papers and webpages;
- an LLM requesting unauthorized tools;
- one compromised low-privilege service;
- dependency vulnerabilities caught before deployment where tooling can detect them;
- deletion/corruption of a production workload followed by recovery from protected backups.

No architecture can promise immunity from every zero-day or targeted attacker. The finished system should instead make attacks expensive, contain failures, surface evidence of compromise, and support clean recovery.

## 20. Maintenance

Review this document whenever any of the following changes:

- public exposure model;
- authentication architecture;
- private data is introduced;
- file upload behavior changes;
- new parser/file format is supported;
- persistent hosting is activated;
- a new outbound network integration is added;
- AI gains a new tool or write capability;
- database/storage architecture changes;
- a meaningful security incident occurs;
- an external security review identifies a new threat class.

`SECURITY.md` remains the vulnerability-reporting and repository security-policy entry point. This document is the deeper architecture and delivery blueprint.
