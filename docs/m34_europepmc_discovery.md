# M34 Europe PMC Candidate Discovery

## Purpose

The project owner asked for more automated discovery sources and pipelines
beyond M14's PubMed/PMC-only pipeline. M34 adds Europe PMC as the second
source, using the same discovery-then-adjudication shape as M14: bounded,
reviewable candidate output first, deterministic accept/reject/hold
adjudication second. Neither step downloads papers, approves licenses, or
performs ingestion. **M34 is discovery and adjudication only -- it is not
wired into acquisition, and using it does not resume corpus growth.** The
corpus remains intentionally frozen at 605 papers by the project owner's
prior decision (`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2
tuning").

## Why a second, independent pipeline rather than one reused engine

Europe PMC's REST API is genuinely different from PubMed/PMC's in ways that
matter for correctness, not just naming:

- **Single call, not a three-step dance.** `resultType=core` returns
  bibliographic metadata, open-access status, license, and full-text URLs in
  one response. M14's pipeline needs three round trips (PubMed search,
  PubMed metadata, PMC ID conversion, PMC Cloud Service lookup) because
  NCBI's services are split that way; Europe PMC's are not.
- **Cursor pagination, not an offset.** Europe PMC uses a Solr-style
  `cursorMark`/`nextCursorMark` pair, not PubMed's `retstart`. There is no
  way to jump to an arbitrary page; each page's cursor comes from the
  previous response. `EuropePmcDiscoveryService.discover` takes
  `cursor_mark` (default `"*"`, the first page) and returns
  `next_cursor_mark` (`None` once exhausted -- Europe PMC signals this by
  returning the same cursor back).
- **No single official PDF bucket.** PMC's OA PDFs all live in one
  documented, world-readable S3 bucket (NCBI's PMC Article Datasets Cloud
  Service), which M14's adjudication allowlists directly. Europe PMC
  candidates instead carry a `fullTextUrlList` with multiple OA PDF
  mirrors at different hosts -- Europe PMC's own hosted repository
  (`europepmc.org/api/fulltextRepo?...`) alongside third-party mirrors
  (Unpaywall, publisher sites, preprint servers). Verified empirically
  against the real API (not assumed from documentation): a preprint's
  `fullTextUrlList` typically has both an `Unpaywall`-hosted PDF and a
  `Europe_PMC`-hosted one for the same document.
- **No PMCID to anchor identity for the content this pipeline targets.**
  M34 is scoped to what Europe PMC adds beyond PMC (see below), so the
  candidates it cares about mostly lack a PMCID by construction. DOI is
  the identity anchor instead.

Given these real differences, `europepmc_candidate_review.py` is a
deliberately separate, independently versioned adjudication engine
(`EUROPEPMC_ADJUDICATION_RULES_VERSION`) rather than a retrofit of M14's
mature, heavily-rehearsed `candidate_review.py`. What genuinely is shared
-- because the underlying criteria are identical regardless of which
pipeline found a candidate -- is scientific-scope evaluation
(`scientific_scope.py`) and license evaluation (`license_rules.py`),
extracted out of `candidate_review.py` in this same change with zero
behavior change (verified: the existing M14 test suite passes unmodified).

## Avoiding duplication of M14's own pipeline

For a record already in PMC (`pmcid` set, `inPMC: "Y"`), Europe PMC's own
"PDF" link is a rendered view of the *exact same* PMC content M14 already
acquires via NCBI's official S3 bucket. Re-acquiring it here would only
duplicate M14's pipeline through a less-official endpoint (Europe PMC's own
web frontend, not a documented bulk-download API). `EuropePmcDiscoveryService`
still discovers and reports these candidates -- never silently drops
evidence -- but `europepmc_candidate_review.py` explicitly rejects them with
reason code `DUPLICATE_OF_PMC_PIPELINE_SCOPE`, the same way a
scope-insufficient PubMed candidate is rejected rather than dropped.

## Commands

```bash
ke europepmc-candidate-discover \
  --query 'semaglutide AND OPEN_ACCESS:Y' \
  --limit 25 \
  --cursor-mark '*' \
  --output work/m34/candidates-000.json
```

Prints the `next_cursor_mark` to pass as `--cursor-mark` for the next page,
when more results remain. The maximum page size is 100 candidates, matching
M14's limit.

```bash
ke europepmc-candidate-review-prepare \
  --candidates work/m34/candidates-000.json \
  --output work/m34/review-000.json
```

Both commands refuse to overwrite an existing output unless `--force` is
supplied. Symbolic-link inputs and outputs are rejected.

## Network boundary

`europepmc-candidate-discover` contacts only `www.ebi.ac.uk` (Europe PMC's
official REST API host) over HTTPS. Redirects, URL credentials, non-HTTPS
URLs, nonstandard ports, oversized responses, and unsupported hosts are
rejected, mirroring `ncbi_http.py`'s transport (`europepmc_http.py`).

## Adjudication rules (`EUROPEPMC_ADJUDICATION_RULES_VERSION = "m34-europepmc-candidate-adjudication-v1"`)

A candidate is:

- **rejected** if it is not open access (`NO_VERIFIED_REUSABLE_FULL_TEXT`,
  mirroring M14's `metadata_only` case) or already in PMC
  (`DUPLICATE_OF_PMC_PIPELINE_SCOPE`, see above);
- **held** if any of scientific scope, DOI identity, license, or full-text
  location is ambiguous or unsupported. Full-text location specifically:
  a PDF hosted at `europepmc.org` (Europe PMC's own repository) passes;
  a PDF only available at a third-party host (Unpaywall, a publisher, a
  preprint server) is held (`held_third_party_host`), never auto-accepted
  -- this project has not vetted arbitrary external repository hosts for
  reliability or terms of service the way it vetted PMC's S3 bucket;
- **accepted** only when scope, identity, license, and full-text location
  (at `europepmc.org`) all pass.

Held and rejected records never authorize acquisition and never require
owner intervention before a working-version acceptance review, matching
M14's policy.

## Output contract

Discovery JSON records the normalized query, `cursor_mark`, `next_cursor_mark`,
page limit, candidate count, and one entry per candidate: Europe PMC ID,
source (`MED` for indexed literature, `PPR` for preprints, etc.), PMID, PMCID,
DOI, title, abstract, authors, publication year, venue, `in_pmc`,
`open_access`, license, and the best available `pdf_url`/`pdf_host` pair
(see "No single official PDF bucket" above).

Review JSON adds, per candidate: `decision` (`accepted`/`rejected`/`held`),
`reason_codes`, `rules_version`, `adjudicated_at`, and each individual rule
result (`inclusion_rule_result`, `identity_rule_result`,
`license_rule_result`, `full_text_rule_result`, `pmc_overlap_rule_result`,
`duplicate_rule_result`).

## What is deliberately not built yet

Acquisition (actually downloading a candidate's PDF) is out of scope for
M34. Unlike PMC's single S3 bucket, Europe PMC's own hosted repository
(`europepmc.org/api/fulltextRepo?...`) is a real, narrower target that could
plausibly get its own acquisition service later, but that is a separate,
not-yet-authorized milestone -- consistent with M14's own phased history
(discovery and adjudication shipped before acquisition).
