# Unpaywall GQR acquisition boundary

Status: implementation contract for CORE-GQR-4  
Parent policy: `docs/security/outbound_http_inventory.md`

## Purpose

Unpaywall is a DOI-to-open-access-location evidence service. It is **not** a
full-text host and it does not grant arbitrary network authority to URLs it
returns. General Question Research Loop acquisition therefore uses Unpaywall in
two separate trust domains:

1. `api.unpaywall.org` supplies current DOI/OA/location/license metadata; and
2. a separate bounded PDF transport may fetch bytes only when the resolved
   direct-PDF URL falls inside Core's explicit reviewed full-text host set.

A successful metadata lookup is never sufficient by itself to download or to
promote scientific evidence.

## Required execution checks

`general-question-acquire-unpaywall` must fail closed unless every selected
item satisfies all of the following:

- the persisted search-run item has stable DOI identity and explicit reusable
  license evidence;
- the item is explicitly routed to `unpaywall` and retains Unpaywall provider
  provenance;
- Core re-runs the official per-DOI Unpaywall lookup immediately before
  acquisition;
- the lookup resolves the same normalized DOI;
- Unpaywall reports the work as open access;
- the current best location supplies a distinct direct-PDF URL, not merely a
  landing-page URL;
- the current Unpaywall license normalizes to a license accepted by
  `license_rules.evaluate_license`;
- the current direct-PDF URL exactly matches the planned full-text URL;
- the PDF transport independently requires HTTPS, rejects URL credentials,
  rejects non-default ports, blocks redirects, applies finite timeout/byte
  limits, and accepts only the reviewed host set; and
- the response begins with a PDF signature before any batch commit.

The reviewed GQR Unpaywall PDF host set is intentionally narrow:

- `pmc.ncbi.nlm.nih.gov`
- `pmc-oa-opendata.s3.amazonaws.com`
- `europepmc.org`
- `plus.europepmc.org`
- `core.ac.uk`

These are existing Core full-text acquisition boundaries. Unpaywall locations
on arbitrary publisher, institutional-repository, personal, cloud-storage, or
other third-party hosts remain non-acquired. Adding another destination is a
separate outbound-security change requiring explicit code, tests, and inventory
review; provider metadata alone cannot expand this set.

## Persistence boundary

After download, Core rechecks byte count and SHA-256 before parsing. Paper
creation/reuse and `ImportRun` / `ImportItem` lineage occur in one database
transaction. The durable receipt preserves:

- search run and research question;
- candidate ID and DOI;
- current direct-PDF URL and source host;
- planned and current reusable-license evidence;
- filename, byte count, and SHA-256;
- persisted/reused Paper ID; and
- import-run/item identifiers.

Paper reuse is also fail-closed. Core compares the acquired content hash with
all available DOI, PMID, and arXiv Paper matches before recording reuse. If
stable identities resolve to different Papers, if content identity and stable
identity resolve to different Papers, or if an identity-matched Paper carries a
different content hash, persistence aborts rather than linking the acquisition
to an unrelated Paper.

Receipt-output or persistence failure must roll back newly acquired PDFs and
restore a pre-existing forced receipt when applicable. Discovery/Unpaywall
metadata and acquired Papers remain **non-Evidence-Record material** until
CORE-GQR-5 grounded extraction and validation/promotion complete.

## Verification status

After the first PR review, three P1 findings were repaired: fail-closed Paper
identity reconciliation, preservation of planned/current license plus byte-count
evidence in the exported persistence receipt, and backward-compatible optional
`best_oa_location_pdf_url` lookup evidence. A branch-local one-shot preflight
then passed Ruff formatting/checks, mypy for the repaired acquisition module,
and the affected Unpaywall/manual-preview regression tests, including a new
cross-Paper content/identity conflict case.

That branch-local preflight is diagnostic evidence only. Merge authority remains
fresh exact-head PR CI: Quality, Security - Bandit, and Security - pip-audit
must all pass after the final human-authored head.
