# M34 Europe PMC Candidate Discovery and Acquisition

## Purpose

The project owner asked for more automated discovery sources and pipelines
beyond M14's PubMed/PMC-only pipeline. M34 adds Europe PMC as the second
source, using the same discovery-then-adjudication-then-acquisition shape
as M14: bounded, reviewable candidate output first, deterministic
accept/reject/hold adjudication second, approval-gated PDF acquisition
third. None of the three steps performs corpus ingestion -- acquired PDFs
land on disk with a sanitized receipt, exactly like M14's
`pmc-oa-acquire`, and still require a separate, explicit ingestion run
(`ke corpus-import`) to enter the queryable corpus.

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

After the worksheet's `held`/`rejected` decisions are settled (working-version
policy: this can run with no manual edits, since every record already carries
an explicit deterministic decision), export the accepted subset as
acquisition-ready approvals:

```bash
poetry run python -m knowledge_engine.europepmc_reviewed_approval_cli export \
  --worksheet work/m34/review-000.json \
  --output work/m34/approvals-000.json \
  --limit 25
```

`export` re-verifies every rule result on each `accepted` record (not just
its `decision` label), rejects any unresolved ambiguity, and selects exactly
`--limit` records in worksheet order -- mirroring `reviewed_approval_cli.py`'s
contract for M14. Then acquire only those explicitly approved PDFs:

```bash
ke europepmc-oa-acquire \
  --candidates work/m34/candidates-000.json \
  --approvals work/m34/approvals-000.json \
  --papers-dir work/m34/papers \
  --receipt work/m34/receipt-000.json
```

`europepmc-oa-acquire` cross-checks every approval against its source
candidate record (DOI, license, PDF URL must match exactly), stages every
PDF to a temporary file, verifies the `%PDF-` signature, and only then
commits the whole batch -- any single failure rolls back every file already
staged or written, exactly like `pmc-oa-acquire`'s all-or-nothing contract.

All three commands refuse to overwrite an existing output unless `--force`
is supplied. Symbolic-link inputs and outputs are rejected.

## Network boundary

`europepmc-candidate-discover` and `europepmc-oa-acquire` contact only
`www.ebi.ac.uk` (Europe PMC's official REST API host) and `europepmc.org`
(Europe PMC's own hosted full-text repository) over HTTPS, sharing one
transport (`europepmc_http.py`'s `UrllibEuropePmcTransport`, allowlisting
`EUROPEPMC_HOSTS`). Redirects, URL credentials, non-HTTPS URLs, nonstandard
ports, oversized responses, and unsupported hosts are rejected, mirroring
`ncbi_http.py`'s transport and its `PMC_CLOUD_PDF_HOST` precedent.

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

## Acquisition (`EuropePmcOaAcquisitionService`, `europepmc_acquisition.py`)

Acquisition is approval-gated, exactly like M14's `pmc_acquisition.py`: it
never re-derives which candidates to fetch from discovery output alone, and
it never trusts a candidate's own `open_access`/`in_pmc` claims without an
explicit, matching approval record. `_build_plans` cross-checks every
approval's `doi`/`license`/`pdf_url` against its source candidate and
additionally requires `open_access is True` and `in_pmc is False` on that
candidate -- the latter enforces the "no single official PDF bucket"
Europe-PMC-specific scope boundary (see above) at acquisition time too, not
just during adjudication. Every approved `pdf_url` must resolve to
`europepmc.org` over HTTPS with no credentials and a standard port; a
non-`%PDF-` response, a non-200 status, or any single failure anywhere in
the batch rolls back every file staged or committed so far, leaving the
output directory exactly as it was before the run.

## Known live-verification gap (found during a bounded smoke test)

A bounded live smoke test (discover -> adjudicate -> export approvals ->
acquire, against real preprint candidates with `in_pmc: false`,
`open_access: true`, and a `europepmc.org`-hosted `pdf_url`) surfaced a
real, reproducible problem: every `https://europepmc.org/api/fulltextRepo?
pprId=...` URL Europe PMC's own REST API reports as an "Open access" PDF
link returned HTTP 403 with the JSON body
`{"error":"PDF link has expired or is invalid"}` -- for every candidate
tried, immediately after discovery (so not a caching/staleness issue),
with or without cookies, a `Referer` header, or a browser-like
`User-Agent`, and across both curl and this service's own transport. The
Europe PMC REST API itself (`www.ebi.ac.uk`) and the `europepmc.org`
article HTML pages both responded normally throughout, so this is
specific to the `fulltextRepo` endpoint, not a general connectivity
problem.

This was tested from this project's sandboxed execution environment,
which routes all outbound HTTPS through a fixed pre-configured proxy egress
point. A plausible, unconfirmed explanation is that Europe PMC's frontend
applies bot/WAF protection to this internal repo-proxy endpoint (built for
its own web app's in-browser PDF viewer, not documented as a public bulk
API the way PMC's S3 bucket is) that flags this environment's egress IP;
an equally plausible alternative is that the endpoint no longer serves
unauthenticated automated requests at all, regardless of caller. This
service's code, host-allowlisting, and error handling are correct and
fully unit-tested against the documented contract; whether the *endpoint
itself* is reliably reachable for real automated acquisition, from a
normal (non-sandboxed) network, is unverified and should be re-checked by
the project owner before this pipeline is relied on for real corpus
growth -- unlike M14's PMC S3 bucket, which this same kind of live check
already confirmed works.

## What is deliberately not built yet

Corpus ingestion of acquired Europe PMC PDFs is a separate, not-yet-wired
step: `europepmc-oa-acquire` writes PDFs and a receipt, matching M14's
`pmc-oa-acquire` contract exactly, but does not itself invoke
`ke corpus-import` or update `sources.csv`/the compressed corpus library.
Folding Europe PMC's acquired PDFs into the same queryable corpus M14 grows
is a future milestone's decision, not an automatic consequence of building
acquisition.
