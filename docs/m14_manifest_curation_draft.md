# M14 Manifest Curation Draft

## Purpose

This step removes manual transcription between completed review, transactional acquisition, and final `sources.csv` curation.

It reconciles a completed review worksheet against an acquisition receipt and produces a CSV with the same columns as the production manifest. It does not modify `sources.csv` and it does not invent scientific metadata.

## Command

```bash
python -m knowledge_engine.manifest_curation_cli export \
  --worksheet work/m14/review-000.json \
  --receipt work/m14/acquisition-000.json \
  --output work/m14/curation-000.csv
```

## Automatically populated evidence

The exporter fills only fields supported by reviewed discovery or receipt evidence:

- deterministic source ID;
- title and DOI when present;
- PMID and PMCID;
- official PMC article and PDF URLs;
- local PDF filename;
- reviewed license text;
- approved-open-access usage status;
- included status and reviewed inclusion reason;
- receipt SHA-256;
- source type.

## Explicit curation still required

The exporter intentionally leaves these fields blank:

- authors;
- publication year;
- venue;
- access date;
- license URL;
- study type;
- population;
- intervention;
- comparator;
- outcome notes.

These fields must be curated from authoritative metadata and scientific review before rows are promoted into `sources.csv`.

## Fail-closed reconciliation

Export stops on unresolved reviews, count mismatches, duplicate identifiers, unsafe filenames, receipt rows without accepted reviews, license or PMCID disagreement, malformed inputs, or missing verified PMC OA evidence.

Rejected records are not expected in the receipt and cannot become manifest rows.

## Repository boundary

Review worksheets, acquisition receipts, curation drafts, PDFs, and databases remain ignored local work products. Never commit a generated curation draft containing incomplete or operator-specific data.
