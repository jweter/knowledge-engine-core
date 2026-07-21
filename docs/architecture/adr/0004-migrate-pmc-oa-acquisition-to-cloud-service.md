# ADR 0004: Migrate PMC OA Discovery and Acquisition to the PMC Cloud Service

## Status

Accepted.

## Context

M14 candidate discovery (`knowledge_engine/pubmed_discovery.py`) and PDF
acquisition (`knowledge_engine/pmc_acquisition.py`) depended on two pieces of
NCBI infrastructure that NCBI has announced it will remove entirely in
**August 2026**:

- The **PMC OA Web Service API** (`oa.fcgi`), queried during discovery to
  resolve a PMCID's license, PDF URL, and XML URL.
- The **PMC FTP Service**, where `oa.fcgi`'s returned URLs pointed
  (`ftp.ncbi.nlm.nih.gov/pub/pmc/...`), used during acquisition to download
  the actual PDF bytes.

This was already partially broken once. `oa.fcgi` returned links at
pre-migration FTP paths that 404'd, because NCBI had relocated the underlying
files to a temporary `/pub/pmc/deprecated/` directory ahead of full removal.
That was fixed with a single retry-on-404 fallback (see the
`docs/error_resolution_ledger.md` entry "M14 PMC OA acquisition failed on
NCBI's FTP path migration"), but the fix was explicitly documented as a
temporary bridge, not a durable answer — the `deprecated/` copies are
themselves scheduled for removal on the same August 2026 date.

NCBI's own announcements make the real scope of the problem clearer than the
original bridge fix assumed:

- [NCBI Insights, Feb 12 2026](https://ncbiinsights.ncbi.nlm.nih.gov/2026/02/12/pmc-article-dataset-distribution-services/):
  "In August 2026, you will need to access full text article data files
  through the PMC Cloud Service instead of the PMC FTP Service." The same
  post states plainly that **the PMC OA Web Service API will no longer be
  available** after August 2026, that the PMC FTP Service's Article Dataset
  files will be removed, and that even the *current* PMC Cloud Service layout
  is being replaced by a new one.
- [`https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/`](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/)
  (fetched 2026-07-21, confirmed live): documents the exact structure of the
  *new* PMC Cloud Service, already available today during the Feb–Aug 2026
  transition window.

So this was not only an acquisition-layer problem (the file named in the
original tracking issue): **discovery's `oa.fcgi` call breaks too**, on the
same date, independent of the FTP path bridge. Fixing acquisition alone would
have left discovery broken.

## Decision

Migrate both discovery and acquisition off `oa.fcgi`/FTP entirely, onto
NCBI's documented PMC Article Datasets Cloud Service — **before** the August
2026 removal date, not as an emergency patch when it happens.

### Why this option

NCBI's `readme.txt` names two future-facing options: the Cloud Service, or
waiting for `oa.fcgi` to be fixed. `oa.fcgi` is being retired outright, not
fixed, so that option does not exist. The Cloud Service is the only
NCBI-documented durable path forward.

Concretely, the service is a single **public, world-readable S3 bucket**:

```text
Resource type: S3 Bucket, world-readable
ARN:           arn:aws:s3:::pmc-oa-opendata
Region:        us-east-1
```

Critically, per NCBI's own documentation and confirmed by direct
reproduction: *"content from these datasets is accessible to users on Amazon
Web Services (AWS), without charge, through either an HTTPS or S3 URL, and
without any log-in requirement for retrieval."* This means the bucket is
reachable with **ordinary unsigned HTTPS GET requests** — no AWS account, no
credentials, no signing, no `boto3`/AWS CLI dependency. That fits this
project's existing minimal `urllib`-based transport
(`knowledge_engine/ncbi_http.py`) with only an allowlist addition; it does
not require a new dependency or a new transport implementation.

### API contract (confirmed live, 2026-07-21)

**Bucket layout** (from NCBI's schematic, reproduced and verified):

```text
s3://pmc-oa-opendata/
|-- PMC10009416.1/                    # one prefix per article *version*
|   |-- PMC10009416.1.json            # metadata (also under metadata/)
|   |-- PMC10009416.1.pdf
|   |-- PMC10009416.1.txt
|   |-- PMC10009416.1.xml
|   `-- <media/supplementary files>
|-- metadata/
|   `-- PMC10009416.1.json            # metadata objects, collected here too
|-- inventory-reports/                # daily S3 Inventory CSV (not used here)
`-- deprecated/                       # legacy layout; removed August 2026
```

**1. Discover an article's version(s).** A PMCID can have more than one
version (e.g. successive preprint revisions). NCBI's own documented workflow
always looks this up rather than assuming version `1`, using the S3
`ListObjectsV2` REST API — which, like everything else in this bucket, works
as a plain unsigned HTTPS GET:

```text
GET https://pmc-oa-opendata.s3.amazonaws.com/?list-type=2&prefix=PMC11370360.&delimiter=/
```

Confirmed responses for three real cases:

```xml
<!-- Nonexistent PMCID: zero results, no error -->
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>pmc-oa-opendata</Name><Prefix>PMC99999999999.</Prefix>
  <KeyCount>0</KeyCount><MaxKeys>1000</MaxKeys><Delimiter>/</Delimiter>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>

<!-- Single-version PMCID (the common case) -->
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>pmc-oa-opendata</Name><Prefix>PMC12855588.</Prefix>
  <KeyCount>1</KeyCount>
  <CommonPrefixes><Prefix>PMC12855588.1/</Prefix></CommonPrefixes>
</ListBucketResult>

<!-- Multi-version PMCID -->
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>pmc-oa-opendata</Name><Prefix>PMC11370360.</Prefix>
  <KeyCount>2</KeyCount>
  <CommonPrefixes><Prefix>PMC11370360.1/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>PMC11370360.2/</Prefix></CommonPrefixes>
</ListBucketResult>
```

`knowledge_engine/pubmed_discovery.py`'s `_latest_pmc_cloud_version()` parses
this (namespace-aware — S3's XML declares `xmlns="http://s3.amazonaws.com/doc/2006-03-01/"`,
so `ElementTree` lookups must use that namespace or they silently match
nothing) and picks the **highest** version number when more than one exists,
favoring the most recent/corrected content over an unconditional "assume
version 1" shortcut.

**2. Fetch that version's metadata.** Once the version is known:

```text
GET https://pmc-oa-opendata.s3.amazonaws.com/metadata/PMC12855588.1.json
```

Real response (fetched live):

```json
{
  "pmcid": "PMC12855588", "version": 1, "pmid": 41623473,
  "doi": "10.1016/j.isci.2025.114581",
  "title": "Study on sodium ion supplementation performance of CNT-coated sodium oxalate in sodium ion batteries",
  "is_pmc_openaccess": true, "is_manuscript": false,
  "is_historical_ocr": false, "is_retracted": false,
  "license_code": "CC BY",
  "xml_url": "s3://pmc-oa-opendata/PMC12855588.1/PMC12855588.1.xml?md5=99210445a56f3315af7e95797556bd6b",
  "pdf_url": "s3://pmc-oa-opendata/PMC12855588.1/PMC12855588.1.pdf?md5=8546223bd7ec0f01313ec7c4903fb9dc",
  "text_url": "s3://pmc-oa-opendata/PMC12855588.1/PMC12855588.1.txt?md5=590fcd8e17b801e33197cb6f408e3f78",
  "media_urls": ["..."]
}
```

`is_pmc_openaccess` is the field this migration relies on to decide OA
status. This is a **stricter, more accurate signal than the old proxy**: the
old code treated "`oa.fcgi` returned any matching record" as proof of open
access. The unified Cloud Service bucket holds three datasets together (the
OA Subset, the Author Manuscript Dataset, and the Historical OCR Dataset), so
an object existing in the bucket no longer implies OA reuse rights by itself
— `is_pmc_openaccess` is the field NCBI documents as the actual gate, and
`_fetch_oa_record()` checks it explicitly before treating anything as OA
evidence.

`license_code` values (`CC BY`, `CC BY-NC`, `CC BY-NC-ND`, `TDM`, or `null`)
are compatible with this project's existing license-prefix allowlist in
`knowledge_engine/candidate_review.py` without changes.

`pdf_url`/`xml_url` are `s3://` URIs, each carrying an `md5` query parameter
— the object's checksum, asserted by NCBI at the source. `_s3_uri_to_https()`
converts these to the equivalent `https://pmc-oa-opendata.s3.amazonaws.com/...`
form used for the actual download in `pmc_acquisition.py`. The `md5`
parameter is preserved through this conversion (S3 ignores unrecognized
query parameters on a plain GET); this project does not currently verify
against it beyond the existing PDF-signature and SHA-256-in-receipt checks it
already performs, but it is available for exactly that purpose if a future
change wants source-asserted integrity verification rather than only
after-the-fact hashing of what was received. See Deferred below.

**3. Download.** The converted HTTPS URL is a normal, unauthenticated GET
returning the PDF bytes directly — confirmed live (`HTTP/1.1 200 OK`,
`Accept-Ranges: bytes`, standard S3 response headers).

### What changed in code

- `knowledge_engine/ncbi_http.py`: added `PMC_CLOUD_PDF_HOST =
  "pmc-oa-opendata.s3.amazonaws.com"` as the **single source of truth** for
  the expected PMC PDF host, replacing three independent hardcoded copies of
  `"ftp.ncbi.nlm.nih.gov"` that had drifted out of sync with each other
  during this same audit (`candidate_review.py`, `reviewed_approval.py`, and
  `pmc_acquisition.py` each had their own copy). Removed
  `ftp.ncbi.nlm.nih.gov` from `NCBI_HOSTS` since nothing constructs URLs
  there anymore.
- `knowledge_engine/pubmed_discovery.py`: `_fetch_oa_record()` now performs
  the two-step S3 lookup above instead of querying `oa.fcgi`. The
  `oa_source` provenance label changed from `"pmc_oa_service"` to
  `"pmc_cloud_service"` to describe the real provider (and the corresponding
  `evidence_provenance` entry in `candidate_review.py`).
- `knowledge_engine/pmc_acquisition.py`: `PDF_HOST` now points at the Cloud
  Service bucket. The `/pub/pmc/deprecated/` 404-retry bridge
  (`_deprecated_pmc_fallback_url`) was **removed outright** — it only ever
  matched legacy FTP-style paths, which no acquisition plan can produce
  anymore, so keeping it would be dead code masquerading as a safety net.
- `knowledge_engine/candidate_review.py`: `_full_text_result()`'s hardcoded
  host check now uses `PMC_CLOUD_PDF_HOST`. `ADJUDICATION_RULES_VERSION`
  bumped `v3` → `v4`, since this changes what counts as a valid "approved
  full-text location" — a real adjudication-rule change, which is exactly
  what that version string exists to track.
- `.github/workflows/m14-mass-discovery.yml`: the acquisition-reconciliation
  step's provenance check updated to match (`'pmc_oa_service'` →
  `'pmc_cloud_service'`).

## Consequences

**Positive:**

- Both of the infrastructure dependencies scheduled for removal in August
  2026 are gone from this codebase months ahead of the deadline, not patched
  reactively when they break.
- `is_pmc_openaccess` is a more precise OA signal than the old "did
  `oa.fcgi` return a matching record" proxy.
- Three independently-drifting copies of the expected PDF host collapsed
  into one constant, closing off the exact class of bug this migration
  surfaced while auditing (`candidate_review.py`'s copy was found only by
  grepping the whole repository, not by reading `pmc_acquisition.py` in
  isolation).
- No new runtime dependency: the Cloud Service is reachable with the same
  minimal `urllib`-based transport already in use.

**Tradeoffs:**

- Discovery's OA lookup is now two HTTP requests per candidate with a
  PMCID (list, then metadata-fetch) instead of one `oa.fcgi` call. This is a
  deliberate correctness choice — always discovering the real version number
  rather than guessing version `1` — and matches NCBI's own documented
  pipeline pattern; it was not benchmarked against the old single-request
  cost, since discovery is already rate-limited far below this difference's
  significance (see `request_interval_seconds` pacing in
  `PubmedPmcDiscoveryService`).
- This is still NCBI's *current* Cloud Service structure. NCBI's own
  announcement is explicit that this structure is itself an update to a
  prior Cloud Service layout, meaning it is possible (though not currently
  announced) that NCBI iterates again in the future. Unlike the FTP bridge
  this replaces, there is no announced removal date for the structure
  documented here as of this writing.

## Deferred

- **Source-asserted MD5 verification.** The metadata JSON's `md5` query
  parameter on every object URL is a genuine integrity-verification
  opportunity beyond the current PDF-signature-and-SHA256-in-receipt checks,
  but wiring it in is a real behavior change (parse the parameter, decide
  what a mismatch means, test it) that this migration did not need in order
  to keep working. Worth a dedicated follow-up if stronger acquisition
  integrity guarantees are wanted.
- **Retraction filtering.** The metadata JSON exposes `is_retracted`, which
  this codebase has never had a way to act on. Not implemented here — adding
  retraction-aware filtering is a new capability, not part of migrating the
  transport this ADR is about.
- **S3 Inventory-based bulk lookup.** NCBI publishes a daily CSV inventory of
  the entire bucket (`inventory-reports/pmc-oa-opendata/`), which could
  replace the per-candidate `ListObjectsV2` + metadata-fetch pattern with a
  single bulk download for very large discovery runs. Not pursued here since
  the per-candidate approach is simpler, already bounded by this project's
  existing rate limiting, and matches NCBI's own recommended per-ID workflow;
  worth revisiting only if discovery request volume becomes a real
  bottleneck.
