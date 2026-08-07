# Outbound HTTP Security Inventory and Policy

Status: Stage 0 security review artifact  
Scope: `knowledge-engine-core` outbound HTTP and local HTTP transports  
Baseline reviewed: `main` after PR #272 (`90bfc08c9c5ac017f7ca88e16be6c6c130fbf20f`)  
Purpose: document current network trust boundaries, record demonstrated controls and gaps, and define the policy future outbound clients must satisfy.

## 1. Security invariant

Outbound network access is a privileged capability.

External evidence and provider data may influence Knowledge Engine records, but external content never receives authority to select arbitrary network destinations, weaken transport policy, disclose credentials, or cross into private/internal services.

The default rule is:

> A caller may influence the path/query of an approved provider request only inside a transport whose scheme, host, port, redirects, timeout, and response size are independently constrained.

Provider content is still untrusted after a successful HTTPS request. Transport approval means only that the destination and resource cost were bounded; it does not make the response scientifically authoritative or safe to execute.

## 2. Review method

The inventory was produced from repository code search and direct inspection of outbound transport modules on `main`.

Primary search indicators included:

- `urllib.request.Request`;
- `urlopen`;
- `build_opener`;
- provider-specific `*_http.py` modules;
- configurable `timeout_seconds` / `max_response_bytes` controls; and
- recovery/acquisition utilities with their own network clients.

This is a source-code inventory, not a packet capture. A future production deployment must separately verify infrastructure-level egress controls.

## 3. Required outbound HTTP policy

### 3.1 Destination policy

Internet-facing provider transports must:

1. require `https`;
2. compare the parsed hostname against a narrow explicit allowlist;
3. reject embedded URL usernames/passwords;
4. reject non-default ports unless a documented provider requires one;
5. never accept a raw arbitrary URL from retrieved evidence as sufficient authorization to fetch it;
6. validate any redirect destination to the same standard if redirects are intentionally supported; and
7. prefer blocking redirects when the workflow does not require them.

Local-only transports are a separate category. Loopback/LAN access may be allowed only when explicitly documented as a local integration boundary and must never be reused as a general Internet fetch primitive.

### 3.2 Resource bounds

Every network operation must have:

- a finite connect/read timeout or equivalent total timeout;
- a finite maximum response size appropriate to the endpoint;
- bounded pagination or caller-controlled result counts;
- bounded retries; and
- a failure mode that does not silently continue with partial or malformed data.

`response.read()` without a byte cap is not considered a complete response-size control even if the payload is checked after the entire body has already been loaded.

### 3.3 Redirect policy

Redirects are security-relevant because a trusted provider can redirect a client to an untrusted host.

Default policy:

- block redirects for fixed-host metadata APIs and acquisition endpoints;
- if a provider requires redirects, re-validate scheme, hostname, port, and credentials on every hop;
- impose a small redirect-count limit; and
- never forward Authorization headers across an untrusted host transition.

### 3.4 Credential policy

- Bearer tokens, API keys, OAuth assertions, and refresh tokens must only be sent to approved provider hosts.
- Credential-bearing URLs must not be configurable from untrusted document/provider content.
- Secrets must not appear in exception text, logs, receipts, or provenance records.
- OAuth token endpoints loaded from credential files must be validated before use rather than trusted solely because they came from a JSON field.

### 3.5 Retry policy

Retries are application behavior, not transport trust.

- Transports may classify a response as retryable, but retry loops must be explicitly bounded.
- `429` and transient `5xx` responses may be retryable when provider terms permit it.
- Authentication failures, malformed payloads, unsupported hosts, redirect-policy violations, and oversized responses must not be retried blindly.
- Exponential backoff and jitter should be used if automated retries are later introduced at scale.

### 3.6 Provenance policy

The transport layer must not collapse provider identity.

For evidence/discovery workflows, callers must retain enough information to determine:

- which provider supplied the response;
- the canonical record/source identifier;
- retrieval time when relevant;
- acquisition URL or approved host category where appropriate;
- license/open-access state where required; and
- whether the result was discovery metadata, acquired source bytes, or non-evidence reference context.

Network success never promotes a record into scientific evidence by itself.

## 4. Current inventory

### 4.1 Strong bounded provider transports

The following dedicated transports already implement the preferred Stage 0 pattern: HTTPS-only destination validation, explicit host allowlists, rejection of URL credentials and unsupported ports, blocked redirects, caller-supplied finite timeout, and bounded response reads.

| Transport | Approved host(s) | Methods | Redirects | Timeout | Response bound | Current assessment |
| --- | --- | --- | --- | --- | --- | --- |
| `knowledge_engine/crossref_http.py` | `api.crossref.org` | GET | blocked | caller-supplied; provider default 10 s | caller-supplied; provider default 1 MB | strong |
| `knowledge_engine/core_http.py` | `api.core.ac.uk` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/ncbi_http.py` | `eutils.ncbi.nlm.nih.gov`, `pmc.ncbi.nlm.nih.gov`, `www.ncbi.nlm.nih.gov`, `pmc-oa-opendata.s3.amazonaws.com` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/europepmc_http.py` | `www.ebi.ac.uk`, `europepmc.org` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/unpaywall_http.py` | `api.unpaywall.org` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/reference_lookup_http.py` | `en.wikipedia.org` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/rxnorm_http.py` | `rxnav.nlm.nih.gov` | GET | blocked | caller-supplied | caller-supplied | strong |
| `knowledge_engine/pubchem_http.py` | `pubchem.ncbi.nlm.nih.gov` | GET | blocked | caller-supplied | caller-supplied | strong |

These transports also use dependency-injected transport/opening seams so tests can exercise URL and failure behavior without requiring live network access.

### 4.2 Crossref provider orchestration

`knowledge_engine/crossref_provider.py` adds useful policy above the transport:

- fixed base URL `https://api.crossref.org/works/`;
- DOI is quoted into the path rather than treated as a destination;
- default timeout is 10 seconds;
- default response limit is 1,000,000 bytes;
- `404`, `429`, `5xx`, malformed JSON, oversized responses, timeouts, and transport failures are classified deterministically; and
- retryability is represented as metadata rather than an unbounded automatic retry loop.

Assessment: **strong**. This is a good reference shape for future provider clients.

### 4.3 Corpus PDF reacquisition utility

`tools/reacquire_corpus_pdfs.py` contains its own bounded `HttpClient` for recovery work.

Current controls:

- HTTPS required;
- embedded credentials rejected;
- only port 443/default accepted;
- allowlist limited to `www.ebi.ac.uk`, `europepmc.org`, and `pmc-oa-opendata.s3.amazonaws.com`;
- redirects blocked;
- default timeout 30 seconds;
- metadata response cap 8 MB;
- PDF cap 100 MB;
- `Content-Length` precheck where available plus `max_bytes + 1` streaming read;
- provider-returned PMC PDF URLs are rechecked against the expected S3 host;
- Europe PMC PDF candidates must match the expected Europe PMC host; and
- successful acquisition does not mutate Evidence Records or imply scientific review.

Assessment: **strong for a bounded recovery tool**.

Follow-up: if this utility becomes a long-lived production worker, move the duplicated host/transport rules behind shared reviewed transport primitives so policy cannot drift.

## 5. Identified gaps

These are code-review findings, not claims of exploitability. They identify places where current implementation does not yet satisfy the preferred policy as completely as the dedicated provider transports.

### 5.1 Google Drive HTTP transport

File: `knowledge_engine/google_drive_http.py`

Current positives:

- production URLs are constructed from fixed Google Drive API constants;
- caller-supplied file/folder IDs are URL-quoted rather than used as hosts;
- Authorization failures are sanitized;
- access token is not placed in the URL; and
- provider metadata is structurally validated before use.

Current gaps:

1. The default opener is raw `urlopen` with no explicit timeout.
2. Response bodies use unbounded `response.read()`.
3. Redirect behavior is the stdlib default rather than an explicit reviewed policy.
4. The transport does not independently parse and assert the Google API host before sending the bearer token.
5. Download size is not bounded at the HTTP layer; the caller currently relies on later workflow-level validation.

Risk class: **medium architectural gap** because this transport carries an OAuth bearer token and can download bytes.

Recommended remediation slice:

- add fixed host allowlists for `www.googleapis.com` (and only any additional Google host proven necessary);
- add a finite timeout;
- add endpoint-appropriate response caps, including a separate larger bound for file downloads;
- block redirects unless a tested Google API behavior requires them;
- preserve dependency injection for deterministic tests; and
- add tests proving bearer credentials cannot be sent to a non-allowlisted host.

### 5.2 Google OAuth refresh-token exchange

File: `knowledge_engine/google_drive_oauth_refresh.py`

Current positives:

- default token URI is Google's official `https://oauth2.googleapis.com/token`;
- secrets are sent in an encoded POST body, not a query string;
- failures are sanitized; and
- credential file shape is validated.

Current gaps:

1. `token_uri` can come from the credential JSON and is not URL-validated before the client secret and refresh token are sent.
2. No explicit timeout is supplied.
3. Response body is read without a byte cap.
4. Redirect behavior is implicit.

Risk class: **high-priority hardening gap** because an altered credential file could redirect long-lived OAuth secrets to an unintended endpoint.

Recommended remediation slice:

- require HTTPS;
- require host `oauth2.googleapis.com` and default port 443;
- reject URL credentials;
- block redirects;
- use a short finite timeout;
- cap token responses to a small size (for example tens or hundreds of KiB, not MB); and
- add tests for malicious `token_uri` values.

### 5.3 Google service-account token exchange

File: `knowledge_engine/google_drive_service_account.py`

Current positives:

- default token URI is Google's official OAuth token endpoint;
- JWT assertion lifetime is one hour;
- local key parsing is strict;
- failures are sanitized; and
- private-key material is not intentionally logged or persisted by the module.

Current gaps mirror the refresh-token client:

1. credential-file `token_uri` is accepted without independent host validation;
2. no explicit timeout;
3. unbounded response read; and
4. implicit redirect behavior.

Risk class: **high-priority hardening gap** because the signed assertion is a credential and the audience is derived from the same unvalidated token URI.

Recommended remediation: use the same shared bounded Google OAuth token transport as the refresh-token flow rather than maintaining two independent network-policy implementations.

### 5.4 OpenAI embedding generator

File: `knowledge_engine/vector_search/openai_generator.py`

Current positives:

- destination URL is fixed to `https://api.openai.com/v1/embeddings`;
- model IDs are allowlisted;
- a finite default timeout of 30 seconds is passed by the default opener;
- errors are sanitized;
- API key is sent in the Authorization header; and
- a nominal 10 MB response-size ceiling exists.

Current gaps:

1. `_read_bounded()` calls `response.read()` with no byte limit and checks length only after the body is fully loaded.
2. Redirect behavior is implicit; an Authorization-bearing request should have an explicit redirect policy.
3. The fixed URL makes SSRF unlikely in this implementation, but the transport does not itself assert the host before transmitting the API key.

Risk class: **medium hardening gap**.

Recommended remediation slice:

- perform `Content-Length` precheck when present;
- read at most `_MAX_RESPONSE_BYTES + 1`;
- block redirects;
- assert HTTPS/host/default port immediately before the request; and
- test that Authorization is never sent to a different host.

### 5.5 Local Ollama transport

File: `knowledge_engine/llm.py`

Current intent:

- local/offline model integration;
- default host `http://127.0.0.1:11434`;
- finite 120-second default timeout;
- success response limited to 8 MiB after reading at most limit + 1; and
- no cloud API key required.

Important distinction: this is intentionally a **local integration**, not an Internet provider transport.

Current gaps / boundary conditions:

1. `host` is configurable and not restricted to loopback or an explicit LAN allowlist.
2. The stdlib opener may follow redirects.
3. `HTTPError` bodies are read without the normal 8 MiB cap.
4. Error strings include the configured URL, which is acceptable for ordinary localhost values but should not be allowed to expose embedded credentials.

Risk class: **conditional**. Low for the documented loopback default; higher if untrusted configuration or a hosted deployment can set the Ollama host.

Policy decision:

- Core may retain HTTP (not HTTPS) only for explicitly local loopback Ollama use.
- Hosted/public configurations must not turn this class into an arbitrary URL fetcher.
- Before persistent hosting, either constrain the hostname to loopback/explicitly approved private model hosts or move model transport behind a separately authorized service boundary.

### 5.6 Shared pattern duplication

The repository has several nearly identical secure `urllib` provider transports. Their duplication is currently understandable and auditable, but it creates future policy-drift risk.

Do **not** refactor them into a complex generic networking framework merely for elegance.

A future consolidation is justified only if it remains small and explicit, for example a shared helper that enforces:

- scheme;
- exact host set;
- port;
- embedded-credential rejection;
- redirect blocking; and
- bounded reads.

Provider-specific hosts, response types, diagnostics, and provenance should remain explicit.

## 6. Retry inventory

The reviewed low-level transports do not implement unbounded automatic retry loops.

Crossref orchestration explicitly marks selected failures as retryable (`timeout`, `429`, selected provider failures) without automatically retrying inside the transport.

Policy result: **acceptable**. Future retry orchestration must remain separately bounded and testable.

## 7. Host-control matrix

| Boundary | Destination influence | Current host control | Credential exposure | Priority |
| --- | --- | --- | --- | --- |
| Crossref | DOI controls path only | exact fixed host | none | maintain |
| CORE | provider URL passed to strict transport | explicit allowlist | optional bearer header | maintain |
| NCBI/PMC | provider URL passed to strict transport | explicit allowlist | typically none | maintain |
| Europe PMC | provider URL passed to strict transport | explicit allowlist | none | maintain |
| Unpaywall | DOI/query controls path/query only | explicit allowlist | contact email query, no API secret | maintain |
| Wikipedia reference | term controls path only | explicit allowlist | none | maintain |
| RxNorm | term controls path/query only | explicit allowlist | none | maintain |
| PubChem | term controls path only | explicit allowlist | none | maintain |
| Corpus recovery | provider-resolved PDF URL | explicit allowlist + revalidation | none | maintain |
| Google Drive API | IDs control path/query | fixed constructors but no final transport assertion | bearer access token | harden |
| Google OAuth refresh | token URI from credentials file | **not independently validated** | client secret + refresh token | harden first |
| Google service-account exchange | token URI from key file | **not independently validated** | signed JWT assertion | harden first |
| OpenAI embeddings | fixed constant | fixed by construction, not asserted in transport | bearer API key | harden |
| Ollama local LLM | configurable host | none beyond default | no API key | constrain before hosted use |

## 8. Prioritized remediation queue

This inventory deliberately does not modify runtime behavior. Recommended next implementation slices are independent and should each receive focused tests.

### Priority 1 — Google OAuth token endpoint boundary

Create one small shared bounded Google token transport and use it for both refresh-token and service-account exchanges.

Acceptance criteria:

- only `https://oauth2.googleapis.com:443/token` (default port representation accepted) is permitted;
- embedded URL credentials rejected;
- redirects blocked;
- finite timeout;
- small bounded response;
- sanitized exceptions;
- existing auth behavior preserved; and
- malicious token-URI regression tests.

### Priority 2 — Google Drive bearer-token transport bounds

Acceptance criteria:

- explicit Google API host allowlist;
- finite timeout;
- bounded metadata responses;
- bounded file download responses appropriate to the backup contract;
- explicit redirect policy;
- credential-forwarding regression tests; and
- existing backup/restore tests remain green.

### Priority 3 — OpenAI embeddings bounded reader / redirect policy

Acceptance criteria:

- actual streaming read cap;
- fixed-host assertion;
- redirect block;
- existing model/dimension/error tests preserved.

### Priority 4 — Ollama local-host policy

Acceptance criteria should be decided against deployment architecture before code is changed. The local developer workflow must remain easy to use, while hosted deployments must not inherit arbitrary URL-fetch capability.

## 9. Definition of compliant outbound client

A new Internet provider client is not ready to merge unless tests demonstrate:

- HTTPS-only behavior;
- explicit host allowlist;
- default/approved port only;
- embedded URL credentials rejected;
- redirect behavior explicitly tested;
- timeout > 0 and finite;
- bounded response read;
- malformed payload handling;
- sanitized failures;
- bounded retry behavior or no automatic retries;
- provider identity/provenance retained; and
- externally supplied identifiers cannot escape from path/query data into network authority.

Credential-bearing transports additionally require a regression test proving the credential cannot be sent to a non-approved destination.

## 10. Relationship to AI/prompt-injection security

Outbound network policy and prompt-injection policy reinforce each other but solve different problems.

A future prompt-injection boundary must ensure that retrieved papers, webpages, abstracts, metadata, and model output remain untrusted content. Instructions embedded in evidence such as "ignore previous instructions", "send this document to another host", or "call this URL" must not gain network authority.

The deterministic application layer, not the model or retrieved text, decides whether an outbound request is allowed. Even if a model proposes a URL or tool call, the normal host/authorization/size/timeout policy must run independently.

This inventory therefore supplies the network-side enforcement requirements for the later prompt-injection/tool-authorization slice.

## 11. Stage 0 conclusion

The repository already has a notably strong pattern for scientific provider traffic: narrow dedicated transports with host allowlists, HTTPS enforcement, blocked redirects, timeouts, and response bounds.

The main remaining Stage 0 risks are concentrated rather than systemic:

1. Google OAuth token endpoints trust credential-file `token_uri` values too much;
2. Google Drive API calls lack explicit timeout/response/redirect transport policy;
3. OpenAI embedding response limiting occurs after an unbounded read; and
4. Ollama's configurable host must remain a consciously local boundary rather than becoming an arbitrary hosted fetch path.

Recommended disposition: **inventory complete; targeted hardening required before treating all outbound clients as policy-compliant.**
