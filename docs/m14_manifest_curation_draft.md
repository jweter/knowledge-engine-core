# M14 Manifest Curation Draft

## Purpose

This step removes manual transcription between automated adjudication, transactional acquisition, and final manifest generation.

It reconciles an adjudication worksheet against an acquisition receipt and produces a CSV with the same columns as the production manifest. It does not modify `sources.csv` and it does not invent unsupported scientific metadata.

## Command

```bash
python -m knowledge_engine.manifest_curation_cli export \
  --worksheet work/m14/review-000.json \
  --receipt work/m14/acquisition-000.json \
  --output work/m14/curation-000.csv
```

## Automatically populated evidence

The exporter fills fields supported by deterministic adjudication, authoritative PubMed metadata, or receipt evidence:

- deterministic source ID;
- title and DOI when present;
- author names supplied by PubMed;
- publication year supplied by PubMed;
- journal title supplied by PubMed;
- PMID and PMCID;
- official PMC article and PDF URLs;
- local PDF filename;
- validated license text;
- canonical Creative Commons deed URL for the validated license (see below);
- access date, derived from the adjudication timestamp;
- approved-open-access usage status;
- included status and adjudication reason code;
- receipt SHA-256, written as `sha256:<64 lowercase hexadecimal characters>`;
- source type;
- adjudication ruleset reference.

PubMed metadata is collected during the existing `efetch` request. No additional per-paper request or owner review is required.

### License URL derivation

`license_url` is derived deterministically from `license_type` via `knowledge_engine.candidate_review.license_deed_url`, the same module that defines which licenses are allowed (`_ALLOWED_LICENSE_PATTERN`). Every accepted row's license already matched that pattern during adjudication, so the mapping never guesses: `CC BY` (optionally versioned) maps to `https://creativecommons.org/licenses/by/<version>/` and `CC0` (optionally versioned) maps to `https://creativecommons.org/publicdomain/zero/<version>/`, defaulting to the current version (`4.0` for CC BY, `1.0` for CC0) when the reported license text has no explicit version. This keeps license-matching logic in one place instead of a second, independently drifting copy.

### Access date derivation

`access_date` is the date portion (`YYYY-MM-DD`) of the accepted adjudication's `adjudicated_at` timestamp — the moment the automated pipeline captured PMC OA evidence for that paper, not a fabricated or estimated value.

## Deferred optional metadata

The exporter may leave these non-blocking fields blank when no authoritative automated source supplied them:

- study type;
- population;
- intervention;
- comparator;
- outcome notes.

Blank optional fields do not create a manual prerequisite for the M14 working version. They may be enriched later through roadmap-approved deterministic adapters.

## Fail-closed reconciliation

Export stops on contradictory accepted evidence, count mismatches, duplicate identifiers, unsafe filenames, receipt rows without accepted adjudications, license or PMCID disagreement, malformed author/year metadata, malformed inputs, or missing verified PMC OA evidence.

Held and rejected records are automatically excluded from acquisition receipts and cannot become manifest rows. They do not require human resolution before accepted records proceed.

## Repository boundary

Adjudication worksheets, acquisition receipts, curation drafts, PDFs, and databases remain ignored local work products. Never commit generated curation output containing local paths or provider payloads.
