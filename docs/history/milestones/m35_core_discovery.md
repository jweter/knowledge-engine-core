# M35 CORE Candidate Discovery

## Purpose

Following M34 (Europe PMC), the project owner asked to keep adding automated
discovery sources without pausing for permission at each step ("Add CORE as
a third discovery source and more if possible... I don't see why we should
gate this part"). M35 adds CORE (https://core.ac.uk, operated by The Open
University) as the third source, using the same discovery-then-adjudication
shape as M14 and M34: bounded, reviewable candidate output first,
deterministic accept/reject/hold adjudication second. Neither step
downloads papers, approves licenses, or performs ingestion. **M35 is
discovery and adjudication only -- it is not wired into acquisition, and
using it does not resume corpus growth.** The corpus remains intentionally
frozen at 605 papers by the project owner's prior decision (`docs/roadmap.md`'s
"Scaling beyond 500 papers for Phase 2 tuning").

CORE is a materially different source from either prior pipeline: it
aggregates open-access content from thousands of repositories and journals
worldwide, not just biomedical literature. That breadth is also why its API
carries much thinner per-record evidence than PMC or Europe PMC -- see below.

## Why a third, independent pipeline rather than one reused engine

All findings below were verified empirically against the live CORE API
(`https://api.core.ac.uk/v3/search/works/`), not assumed from documentation:

- **Offset pagination, not a cursor.** CORE's response echoes back
  `totalHits`/`limit`/`offset`, closer to PubMed's `retstart` than to Europe
  PMC's `cursorMark`. `CoreDiscoveryService.discover` takes `offset` (default
  `0`) and returns `next_offset` (`None` once `offset + candidate_count >=
  total_hits`).
- **An API key is optional, not required.** Unauthenticated requests work
  but are capped at a low rate limit (~10 requests per ~10-minute rolling
  window, confirmed via live `429` responses and `x-ratelimit-*` headers); a
  bearer token raises that limit. `CoreDiscoveryService`'s `api_key`
  parameter (wired to the optional `KE_CORE_API_KEY` setting) is `None` by
  default and discovery still works without one -- unlike
  `OpenAiEmbeddingGenerator`, which unconditionally requires
  `KE_OPENAI_API_KEY`.
- **No license field at all.** Confirmed by enumerating every key in a real
  captured response: there is no `license`, `rights`, or `isOpenAccess`-style
  field anywhere in a CORE work record. CORE's OA-ness comes from only
  aggregating OA repositories and deposits, not from a per-record flag. This
  is the most consequential difference -- see the adjudication section below.
- **No PMCID.** CORE's response never includes a PMCID, so there is no
  signal this pipeline could use to detect overlap with M14's PMC pipeline
  the way `europepmc_candidate_review.py` detects overlap via `inPMC`/`pmcid`.
  See "What is deliberately not built yet."

Given these real differences, `core_candidate_review.py` is a third,
independently versioned adjudication engine
(`CORE_ADJUDICATION_RULES_VERSION`) rather than a retrofit of either prior
engine. What genuinely is shared -- because the underlying criteria are
identical regardless of which pipeline found a candidate -- is
scientific-scope evaluation (`scientific_scope.py`) and license evaluation
(`license_rules.py`).

## PMC/Europe PMC overlap is not detected (known, deliberate limitation)

Unlike Europe PMC's `DUPLICATE_OF_PMC_PIPELINE_SCOPE` rule, this milestone
does not attempt to detect whether a CORE candidate duplicates a record
already reachable through the PMC or Europe PMC pipelines. Doing so would
require an extra network round-trip per candidate against a different
service, adding real complexity and cross-pipeline coupling for a milestone
scoped to discovery and adjudication only. Human reviewers should
sanity-check obviously-duplicate DOIs during working-version acceptance
review, per the project's existing corpus-review process
(`docs/roadmap.md`'s "Human evaluation is reserved for working-version
acceptance").

## Commands

```bash
ke core-candidate-discover \
  --query 'semaglutide obesity' \
  --limit 25 \
  --offset 0 \
  --output work/m35/candidates-000.json
```

Prints the `next_offset` to pass as `--offset` for the next page, when more
results remain. The maximum page size is 100 candidates, matching M14 and
M34's limit. Set `KE_CORE_API_KEY` to use a CORE API key (optional; raises
the unauthenticated rate limit).

```bash
ke core-candidate-review-prepare \
  --candidates work/m35/candidates-000.json \
  --output work/m35/review-000.json
```

Both commands refuse to overwrite an existing output unless `--force` is
supplied. Symbolic-link inputs and outputs are rejected.

## Network boundary

`core-candidate-discover` contacts only `api.core.ac.uk` (CORE's official
REST API host) over HTTPS. Redirects, URL credentials, non-HTTPS URLs,
nonstandard ports, oversized responses, and unsupported hosts are rejected,
mirroring `europepmc_http.py`'s transport (`core_http.py`).

## Adjudication rules (`CORE_ADJUDICATION_RULES_VERSION = "m35-core-candidate-adjudication-v1"`)

Because CORE never supplies license evidence, `evaluate_license(None)` is
called for every candidate and always returns `"incomplete_missing_license"`.
**No CORE candidate can ever auto-accept.** A candidate is:

- **held** if scientific scope, DOI identity, license (always), or full-text
  location is ambiguous or unsupported -- which, given the license rule
  above, is every candidate that reaches adjudication. Full-text location
  specifically: a PDF hosted at `core.ac.uk` (CORE's own `downloadUrl`
  mirror) passes; a PDF only available at a third-party host (from
  `sourceFulltextUrls`) is held (`held_third_party_host`), never
  auto-accepted -- this project has not vetted arbitrary external
  repository hosts for reliability or terms of service the way it vetted
  PMC's S3 bucket.

This is a deliberate, honest consequence of CORE's real API contract, not a
bug to work around: every CORE candidate requires a human to visit the
original source and confirm reuse terms before it could ever be considered
for acquisition. Held records never authorize acquisition and never require
owner intervention before a working-version acceptance review, matching M14
and M34's policy.

## Output contract

Discovery JSON records the normalized query, `offset`, `next_offset`,
`limit`, `total_hits`, candidate count, and one entry per candidate: CORE
ID, DOI, title, abstract, authors, publication year, venue (CORE's
`publisher` field), document type, the best available `pdf_url`/`pdf_host`
pair (preferring `core.ac.uk`), and the full `source_fulltext_urls` list for
transparency.

Review JSON adds, per candidate: `decision` (`held` or `rejected` --
`accepted` is unreachable given the always-missing license), `reason_codes`,
`rules_version`, `adjudicated_at`, and each individual rule result
(`inclusion_rule_result`, `identity_rule_result`, `license_rule_result`,
`full_text_rule_result`, `duplicate_rule_result`).

## What is deliberately not built yet

- Acquisition (actually downloading a candidate's PDF) is out of scope for
  M35, as it was for M14 and M34.
- PMC/Europe PMC overlap detection (see above) is a known limitation, not an
  oversight -- it can be revisited as a later milestone if duplicate CORE
  candidates prove to be a real problem in practice.
- License verification automation: since CORE never reports license text,
  any future automation here would need a different evidence source (e.g.
  visiting the CORE work's own landing page or its underlying repository)
  rather than a field CORE's API will ever return.
