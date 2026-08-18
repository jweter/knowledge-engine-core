# Federated Research Discovery Adoption

Status: adopted guiding architecture and roadmap direction, 2026-08-15.

This document records what Knowledge Engine learned from reviewing
`surendranb/find-research-papers-mcp` and converts only the useful ideas into
Knowledge Engine-native requirements. It is intentionally not a dependency
adoption plan. The external project is a reference implementation and source of
engineering lessons; Knowledge Engine keeps its own architecture, provenance
model, epistemic policy, security posture, and interfaces.

## Adoption rule

The project may learn aggressively from external systems, but it does not inherit
their identity, assumptions, product boundaries, telemetry, policy, or runtime
coupling. Useful ideas are translated into Knowledge Engine contracts and tested
against Knowledge Engine's own goals.

For this review the rule is:

- borrow provider-adapter and orchestration patterns;
- keep or improve existing PubMed and Crossref implementations rather than
  replacing them merely because another repository has equivalents;
- add missing provider families behind our own contracts;
- preserve immutable source/provenance records before interpretation;
- expose partial failure and search coverage honestly;
- keep research doctrine and evidence interpretation inside Knowledge Engine;
- reject third-party telemetry, remote bootstrap installers, hidden analytics,
  and provider-specific policy as core requirements.

## What the external project demonstrated well

### 1. One research query can fan out across multiple scholarly indexes

A discovery broker should be able to execute one normalized query against a
configured set of providers and return a common candidate schema. The reviewed
project uses arXiv, OpenAlex, Crossref, PubMed, and Semantic Scholar. Knowledge
Engine already has substantial PubMed/PMC and Crossref infrastructure; the main
new value is the normalized multi-provider orchestration pattern and the missing
provider families.

Knowledge Engine version:

```text
research question / discovery query
                |
                v
        Discovery Broker
                |
     +----------+----------+-----------+----------+
     |          |          |           |          |
   PubMed    Crossref   OpenAlex      arXiv   Semantic Scholar
     |          |          |           |          |
     +----------+----------+-----------+----------+
                |
                v
      provider-native results
                |
                v
       canonical candidate model
                |
                v
   identity resolution + provenance
                |
                v
      Source Vault / evidence flow
```

The broker is ours. MCP may later expose it, but MCP is an interface, not the
internal architecture.

### 2. Provider adapters should share a stable result contract

Every provider should map its native response into a common discovery candidate
without erasing provider-native identifiers or provenance.

Minimum normalized candidate fields should include, when genuinely available:

- canonical candidate ID;
- source/provider name;
- provider-native ID;
- DOI;
- PMID/PMCID;
- arXiv ID;
- OpenAlex ID;
- Semantic Scholar ID;
- title;
- authors;
- publication year/date;
- venue;
- abstract;
- landing-page URL;
- open-access/full-text URL when known;
- citation count as provider-reported metadata, never treated as evidence quality;
- open-access status with source of that assertion;
- retraction/correction status and which provider supplied it;
- retrieval timestamp;
- raw provider receipt or durable normalized provenance sufficient to reproduce
  the interpretation.

A missing field stays missing. Providers must not fabricate substitutes to make
the schema look complete.

### 3. Graceful degradation must be explicit

A failed provider must not erase successful results from other providers, but a
partial search must never masquerade as a complete search.

Every federated search run should report provider status such as:

```text
pubmed: success
crossref: success
openalex: success
arxiv: success
semantic_scholar: rate_limited
```

The run record should preserve:

- providers requested;
- providers attempted;
- providers completed;
- providers skipped and why;
- provider latency;
- provider result counts before and after deduplication;
- query parameters and time bounds;
- whether a search result is complete, partial, degraded, or failed.

This information belongs in deterministic run state and should be visible to
later AI and Web layers. No LLM should infer whether a provider was searched.

### 4. Citation and reference traversal is a first-class discovery mode

Discovery is not only keyword search. Given a known work, Knowledge Engine should
be able to expand outward through references and citing works when the provider
supports it. This should produce ordinary provenance-bearing discovery
candidates, not special untracked objects.

Useful modes include:

- references of a known paper;
- works citing a known paper;
- related works through shared references;
- citation-chain expansion from landmark studies;
- bounded snowball discovery for contradiction and replication searches.

Citation counts remain metadata. A highly cited paper is not automatically
better evidence.

### 5. Retraction and resolution checks belong in source validation

The external project usefully surfaces retraction flags and can check whether a
landing page resolves. Knowledge Engine should adopt the capability but make the
semantics more precise.

Rules:

- `retracted=true` is a critical status, not an automatic deletion. The source
  remains in the historical record and must be excluded or specially handled by
  evidence synthesis policy.
- `resolves=false` means a network/resource check failed under known conditions;
  it does not prove the scholarly work is invalid.
- `resolves=unknown` is different from false.
- correction, expression-of-concern, withdrawal, and retraction states should be
  modeled distinctly where provider data permits.
- all status assertions retain provider and checked-at provenance.

### 6. Capability discovery should be deterministic

The reviewed project exposes source-list and research-method helper tools. We
keep the capability-discovery idea but not an external project's research
method as authority.

Knowledge Engine should eventually expose a deterministic discovery-capability
report containing:

- configured providers;
- provider health;
- supported identifier types;
- supported search filters;
- citation/reference traversal support;
- open-access metadata support;
- retraction/correction metadata support;
- rate-limit state where measurable;
- whether API credentials are optional, configured, missing, or deliberately
  disabled.

This complements the existing capability/Doctor direction adopted from the
LifeOS review.

## Knowledge Engine-native provider roadmap

### Keep and strengthen existing providers

**PubMed/PMC**

Keep the current `pubmed_discovery.py`, `pubmed_batch_discovery.py`, NCBI
transport, PMC OA acquisition, review/approval, license, and provenance
boundaries. Compare external implementations only for test cases, normalization
ideas, failure handling, and query ergonomics.

**Crossref**

Keep the current Crossref service/provider boundary. Extend it only where a
measured gap exists: richer references, correction/retraction metadata,
identifier normalization, or federated broker compatibility.

### Add missing providers behind our contracts

**OpenAlex -- high priority**

Why it matters:

- broad scholarly coverage;
- citation graph;
- work and author identifiers;
- useful open-access metadata;
- useful cross-provider identity signals.

Behavior requirements:

- no OpenAlex-specific object may leak through the public core contract;
- preserve OpenAlex IDs as provenance/identity aliases;
- citation counts are descriptive metadata only;
- source/citation expansion is bounded and reproducible;
- provider failures degrade the federated search honestly.

**Semantic Scholar -- high priority but optional provider**

Why it matters:

- independent discovery path;
- citation graph;
- useful paper metadata and related-work signals.

Behavior requirements:

- the system must work without a Semantic Scholar API key;
- optional credentials may increase capacity but cannot become a hidden
  requirement for baseline discovery;
- provider-generated summaries/TLDRs are metadata from the provider, never
  treated as source-paper text;
- rate limiting is surfaced, not hidden.

**arXiv -- useful domain-specific provider**

Why it matters:

- open-access preprints in several scientific and technical domains;
- fast access to emerging work before journal publication.

Behavior requirements:

- `preprint` status must remain explicit;
- later journal versions should be identity-linked when defensible rather than
  silently merged;
- preprint status must be available to Evidence Intelligence and synthesis.

## Canonical identity and deduplication

Federated search greatly increases duplicate representations of the same
scholarly work. Provider aggregation must therefore feed the existing duplicate
and provenance philosophy rather than performing opaque title-string merging.

Identity evidence should be ordered roughly as:

1. exact normalized DOI;
2. exact PMID/PMCID or other authoritative crosswalk;
3. explicit provider cross-reference;
4. version-of/journal-version relationship;
5. high-confidence bibliographic match requiring review or transparent
   probabilistic status;
6. weak title similarity alone is never enough for silent canonical merge.

The system should preserve both:

- the canonical scholarly-work identity when established; and
- each provider observation that contributed metadata.

This supports later conflict detection when two providers disagree about year,
open-access status, citation count, or retraction state.

## Search-run provenance contract

Federated discovery must become reproducible scientific workflow state, not a
transient HTTP result.

A future search-run record should be able to answer:

- what query was executed;
- who/what initiated it;
- which project/research question it served;
- when it ran;
- which providers were configured and attempted;
- each provider's outcome;
- normalized filters/date range;
- result counts per provider;
- deduplicated candidate count;
- identifiers for persisted raw/provider receipts where retained;
- software/provider-adapter version;
- whether the run was complete or degraded;
- which later evidence/source records were acquired from it.

This is the discovery equivalent of the project's existing import-run discipline.

## Security and privacy decisions

### Rejected: default third-party telemetry

Knowledge Engine will not adopt the reviewed project's default anonymous usage
telemetry, persistent analytics installation UUID, agent/harness fingerprinting,
tool-sequence reporting, or remote analytics endpoint as part of discovery.

If Knowledge Engine ever adds optional telemetry, it must be:

- off by default;
- explicit opt-in;
- documented;
- locally inspectable;
- incapable of transmitting research queries, source content, identifiers,
  paths, credentials, unpublished data, or user-specific research history;
- removable without breaking scientific functionality.

Local operational metrics may be stored locally as ordinary observable run
state without being transmitted anywhere.

### Rejected: remote `curl | bash` bootstrap as a project dependency path

External research providers or adapters should be introduced through reviewed,
pinned code and normal dependency management. Knowledge Engine will not require
a remote convenience installer that modifies harness configuration or reports
installation analytics.

### Secrets stay outside evidence and model context

Optional provider API keys belong in environment/secret-management boundaries.
They are never written into evidence records, provider receipts, prompts, logs,
or committed configuration.

## Epistemic policy boundary

The reviewed MCP exposes its own `get_research_method()` helper. Knowledge
Engine should never delegate its scientific interpretation rules to a provider
or transport plugin.

Provider adapters answer questions such as:

- what records were returned;
- what identifiers and metadata did the provider report;
- what citation/reference links did it report;
- what retraction/open-access status did it report;
- did the provider call succeed.

Knowledge Engine's own evidence and AI layers decide, under explicit and
inspectable policy:

- whether a preprint is adequate for a particular claim;
- how a retraction affects a synthesis;
- what constitutes support, contradiction, qualification, or context;
- whether search coverage is adequate;
- how evidence quality is assessed;
- when uncertainty is too large for a conclusion;
- when a search must be widened or repeated.

Transport does not define truth.

## MCP decision

MCP is useful as an interoperability surface, not as the internal source of
truth.

Possible future direction:

```text
MCP client / agent
       |
       v
Knowledge Engine MCP facade
       |
       v
Knowledge Engine services
       |
       +-- Discovery Broker
       +-- Evidence retrieval
       +-- Source inspection
       +-- Research-session capabilities
```

The internal Discovery Broker should remain directly callable by Core/AI/Web
without requiring an MCP process. If an MCP facade is added, it must expose our
contracts and policy, not re-export a third party's server unchanged.

## Roadmap milestones introduced by this review

These are ordered by leverage, not necessarily immediate implementation date.

### FRD-1 -- Federated discovery contract

**Status: implemented, and reachable.** `federated_discovery.py`'s
`DiscoveryQuery`/`FederatedCandidate`/`FederatedSearchResult`/
`ProviderStatus`/`ProviderOutcome` contracts, `discovery_broker.py`'s
`FederatedDiscoveryBroker`, and `discovery_provider_registry.py`'s
`DiscoveryProviderRegistry` were already built and unit-tested when this
status line was added, composing PubMed (`pubmed_federated_adapter.py`,
wrapping the existing `pubmed_discovery.py` service unchanged) and
Crossref (`crossref_federated_adapter.py`, wrapping the existing
`crossref_provider.py`, DOI-lookup-only by design) through the common
contract. The real gap closed here: none of it had a CLI command, so it
was built and tested but unreachable outside a test file -- the same
"orchestrator built but nothing calls it" gap this project's own
`knowledge-engine-ai` AI-O12 milestone named and fixed for its own
orchestrator. `ke federated-discover`/`ke federated-coverage-report` are
that CLI surface now. Live-verified: a real
`semaglutide weight loss randomized trial` query returned 5 real PubMed
candidates while Crossref correctly, explicitly reported itself
`failed`/`unsupported_query` for a non-DOI query -- exactly the graceful,
labeled degradation this milestone's exit criteria require, not a
contrived test fixture.

Define typed provider, query, result, provider-status, and search-run contracts.
Do not change existing PubMed/Crossref behavior until parity tests exist.

Exit criteria:

- PubMed and Crossref can be represented through the common contract; **met**
- provider-native IDs and provenance are preserved; **met**
- partial provider failure is representable without exception-driven ambiguity. **met**

### FRD-2 -- OpenAlex adapter

**Status: search implemented and live-verified; work lookup and citation
retrieval not built.** `openalex_provider.py`'s `OpenAlexProvider` (search
and single-work lookup) existed with only a fake-transport unit test --
no concrete HTTPS transport, unlike PubMed/Crossref. New
`openalex_http.py`'s `UrllibOpenAlexTransport` (host-allowlisted to
`api.openalex.org`, the same bounded-read pattern
`crossref_http.py`/`uniprot_http.py` already established) is that
transport, wired into `ke federated-discover`. OpenAlex requires no
credential in reality (a polite-pool `mailto` param, not a secret), but
this adapter's existing, unchanged contract gates it behind an optional
`--openalex-api-key`/`KE_OPENALEX_API_KEY` and reports itself `disabled`
(not an error) when absent -- not revisited here since changing an
already-tested provider contract was out of scope for wiring its
transport. Citation/reference retrieval (this milestone's third exit
criterion) is not implemented.

Implement OpenAlex search and work lookup behind the broker.

Exit criteria:

- deterministic unit fixtures; **met** (pre-existing)
- live integration test separated from offline tests; **not yet -- `ke
  federated-discover` was live-verified manually, not from an automated
  live-tagged test**
- citation/reference retrieval bounded and provenance-bearing; **not met**
- federated search succeeds when OpenAlex fails and marks the run degraded.
  **met** (live-verified: OpenAlex `disabled`, PubMed `success` ->
  `partial` completeness)

### FRD-3 -- Semantic Scholar adapter

**Status: search implemented and live-verified; citation traversal not wired
into the CLI.** `semantic_scholar_provider.py`'s `SemanticScholarProvider`
(search, single-work lookup, and `references`/`citations`/`traverse`
citation traversal via `citation_traversal.py`) existed with only a
fake-transport unit test -- no concrete HTTPS transport, the same gap
OpenAlex had. New `semantic_scholar_http.py`'s
`UrllibSemanticScholarTransport` (host-allowlisted to
`api.semanticscholar.org`, the same bounded-read pattern this project's
other HTTP transports use) is that transport, wired into `ke
federated-discover`. Unlike OpenAlex, Semantic Scholar's public Academic
Graph search genuinely requires no credential by design -- an optional
`--semantic-scholar-api-key`/`KE_SEMANTIC_SCHOLAR_API_KEY` only raises the
rate limit, sent as an `x-api-key` header, never gating search itself.
Live-verified against the real API: a real query hit the public tier's
rate limit (confirmed independently via a direct `curl` to the same
endpoint returning the same `429`/`"Too Many Requests"` body) and the
transport correctly parsed it into `ProviderOutcome.RATE_LIMITED`,
surfaced in `ke federated-discover`'s coverage table as
`failed/unavailable` -- exactly the graceful, labeled degradation this
milestone's fourth exit criterion requires, a real external condition,
not a contrived test fixture. Citation/reference traversal
(`references`/`citations`/`traverse`) is implemented and unit-tested but
has no CLI command yet -- named as real, unfinished follow-up.

Implement optional Semantic Scholar discovery and citation traversal.

Exit criteria:

- no-key degraded/basic behavior defined; **met** (pre-existing --
  `SemanticScholarProvider` never required a key for search)
- optional key supported through secret boundary; **met**
  (`--semantic-scholar-api-key`/`KE_SEMANTIC_SCHOLAR_API_KEY`, sent only as
  a header, never logged)
- provider TLDRs never treated as source text; **met** (pre-existing --
  `_FIELDS` never requests `tldr`)
- rate-limit behavior visible in provider status. **met, live-verified**
  (see above)

### FRD-4 -- arXiv adapter and version identity

**Status: implemented and live-verified.** `arxiv_provider.py`'s
`ArxivProvider` (Atom-feed search, explicit `preprint`/`preprint_version`
fields, `_normalize_arxiv_identifier` stripping `/abs/`, `/pdf/`, and
`.pdf` suffixes into a canonical `arxiv:<base>v<version>` identity) already
existed with only a fake-transport unit test -- the same gap OpenAlex and
Semantic Scholar had before FRD-2/FRD-3. New `arxiv_http.py`'s
`UrllibArxivTransport` (host-allowlisted to `export.arxiv.org`, the same
bounded-read, no-redirect pattern this project's other HTTP transports use)
is that transport, now wired into `ke federated-discover`'s production
registry -- fully public and keyless, so it takes no credential parameter,
unlike OpenAlex or Semantic Scholar. Live-verified against the real API: a
real `GLP-1 receptor agonist weight loss` query returned 5 real candidates
(`completeness: complete`), and a broader 5-provider run correctly showed
`arxiv` as `completed` alongside a real `pubmed` success and real
`crossref`/`semantic_scholar` degraded conditions in the same run --
exactly the graceful, per-provider labeled coverage this milestone's own
adoption plan requires, not a contrived single-provider fixture.

Implement arXiv discovery with explicit preprint identity/version semantics.

Exit criteria:

- preprint status retained; **met** (pre-existing -- every candidate carries
  `preprint=True`)
- arXiv ID normalized; **met** (pre-existing --
  `_normalize_arxiv_identifier`)
- later-version linking is explicit rather than silent replacement. **met**
  (pre-existing -- `preprint_version` and a version-qualified
  `canonical_id`/`provider_id`, e.g. `arxiv:2301.12345v2`, so a later
  version is a distinct observation rather than an overwrite)

### FRD-5 -- Federated deduplication and provider disagreement

Use canonical scholarly-work identity while preserving provider observations.

**Status: implemented, and reachable.** Deduplication by exact DOI has been
in place since FRD-1. `provider_disagreement.py`'s
`build_provider_disagreement_report` (deterministic, no provider treated as
authoritative) and `federated_result_snapshot.py`'s
`build_public_federated_result_payload` (the provenance-safe join of a
result to its persisted coverage record, rejecting mismatched provenance)
are now wired into `ke federated-discover --output`'s
`provider_disagreements`/`coverage` fields -- not just unit-tested in
isolation. Live-verified: a real two-provider run (`pubmed`, `crossref`)
produced an `--output` file whose `coverage` block matched the console
table exactly and whose `provider_disagreements` block was the deterministic
empty-candidates shape (no candidate had two differing provider
observations in that run, which is itself the correct, non-inferred state,
not a placeholder).

Exit criteria:

- DOI duplicates collapse to one candidate without losing provider provenance; **met**
- conflicting provider metadata is inspectable; **met -- exposed through
  `ke federated-discover --output`'s `provider_disagreements` field**
- weak matches do not silently merge. **met (exact-DOI only; no fuzzy-match
  merging exists to silently misfire)**

### FRD-6 -- Search-run ledger and coverage report

**Status: implemented, and reachable.** `federated_search_ledger.py`'s
`FederatedSearchLedger` (immutable JSON-per-run persistence,
write-once, `coverage_report` re-derivable from any past run) and
`federated_discovery_service.py`'s `FederatedDiscoveryService` (guarantees
a search is persisted before it is ever returned to a caller) already
existed. `ke federated-discover` is the first caller; `ke
federated-coverage-report <search_run_id>` lets anyone -- a person, or
eventually `knowledge-engine-web`/`knowledge-engine-ai` reading this same
ledger directly, per
`knowledge-engine-web/docs/federated_discovery_transparency_roadmap.md`'s
explicit "when Core exposes the data" dependency on this milestone --
re-fetch a run's coverage deterministically after the fact. Live-verified:
a real search run's coverage was re-fetched by ID from the persisted JSON
ledger file and matched the original run exactly.

Persist reproducible federated discovery runs and expose deterministic coverage.

Exit criteria:

- every provider outcome is recorded; **met**
- a caller can distinguish complete from degraded search; **met**
- downstream AI/Web can render coverage without guessing. **the data is now
  exposed and re-fetchable both via `federated-coverage-report <id>` and
  directly in `federated-discover --output`'s `coverage` field on the same
  run that produced it; Web/AI-side rendering is still their own unbuilt
  work, tracked in their own roadmap docs, not this one**

### FRD-7 -- Citation snowball discovery

Add bounded references/citations expansion as a reproducible discovery strategy.

**Status: implemented and reachable for Semantic Scholar; OpenAlex traversal
still unwired.** `citation_snowball.py`'s `CitationSnowballDiscovery`
(breadth-first expansion under explicit depth/candidate bounds) and
`citation_snowball_ledger.py`'s `CitationSnowballLedger` (write-once JSON
persistence, replayable by ID) already existed but, like FRD-6 before its own
CLI command shipped, were built and unit-tested with no reachable surface
outside a test file. `ke citation-snowball --seeds <ids> --ledger-root <dir>`
is now the first caller, wired to `SemanticScholarProvider`'s existing
`references`/`citations`/`traverse` methods (already used for federated
search); `ke citation-snowball-report <snowball_run_id> --ledger-root <dir>`
re-fetches a persisted run's plan and traversal outcomes by ID, the same
pattern `federated-coverage-report` established for FRD-6. OpenAlex's
`OpenAlexCitationAdapter` implements the same `CitationTraversalProvider`
contract but requires an additional work-hydration lookup not yet wired into
this command -- a follow-up slice, not a change to the contract already
exposed. See `docs/core_interface_contract.md`'s FRD-7 entry.

Exit criteria:

- seed papers and expansion depth are explicit; **met** -- `--seeds`,
  `--directions`, and `--max-depth` are explicit CLI options, validated by
  `CitationSnowballPlan`
- newly discovered works preserve edge provenance; **met** -- every
  discovered candidate carries a `CitationEdge` (provider, seed, direction,
  retrieval timestamp), persisted in the ledger and in `--output` JSON
- expansion can be replayed and compared later. **met for Semantic
  Scholar** -- `ke citation-snowball-report` re-fetches any persisted run's
  deterministic plan/outcome by ID; not yet true for OpenAlex, which has no
  CLI-reachable traversal yet

### FRD-8 -- Optional Knowledge Engine MCP facade

Only after the internal contracts are stable, expose selected read/query
capabilities through MCP if there is a measured integration use case.

Exit criteria:

- no core behavior depends on MCP;
- same service tests pass through direct Python/service calls and MCP facade;
- no telemetry or external research-policy dependency is introduced.

## Additional improvements prompted by this review

The external repository is useful not only for what it built, but for the gaps it
made visible in our own future design.

### Search coverage should become a measurable scientific property

A synthesis should know whether it searched one source or five, whether one was
rate-limited, and when the search occurred. Coverage should therefore become a
first-class input to Evidence/Claim Confidence rather than an invisible
implementation detail.

It must not be reduced to a naive `providers_succeeded / providers_configured`
percentage. Coverage eventually needs to consider provider domain relevance,
query breadth, date limits, identifier/citation expansion, and known blind spots.
The first step is simply preserving the facts needed to calculate it later.

### Provider disagreement is useful evidence about metadata quality

When Crossref, PubMed, OpenAlex, and Semantic Scholar disagree about a record,
that discrepancy should be inspectable. The system should eventually distinguish
source-paper evidence disagreement from provider-metadata disagreement rather
than flattening both.

### Discovery strategies should be composable

Future discovery should support a plan consisting of multiple deterministic
steps, for example:

1. lexical/semantic query across relevant providers;
2. DOI/identifier normalization;
3. citation snowball from landmark papers;
4. contradiction-oriented query expansion;
5. recency sweep;
6. retraction/correction sweep;
7. stop when explicit Research ISA coverage criteria are met or report why they
   are not.

The AI layer may propose such a plan, but Core executes and records each step.

### Search should be continuously refreshable

A research question should be rerunnable later against the same provider set so
Knowledge Engine can report what changed: newly published works, newly linked
citations, corrections/retractions, and changes in provider coverage. This fits
the founding vision that knowledge is never final.

### External projects become comparative test fixtures, not architectural owners

When a useful open-source research tool appears, future reviews should follow the
same discipline used here:

1. inventory the actual behavior;
2. identify capabilities we already own;
3. isolate genuinely new value;
4. inspect privacy/security/runtime assumptions;
5. translate useful ideas into Knowledge Engine contracts;
6. reject everything that conflicts with our principles;
7. add measurable roadmap items rather than vague inspiration;
8. preserve attribution where code or substantial implementation details are
   actually reused.

That lets Knowledge Engine continuously evolve without becoming an accidental
collection of other people's frameworks.
