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

The exporter fills only fields supported by reviewed discovery, authoritative PubMed metadata, or receipt evidence:

- deterministic source ID;
- title and DOI when present;
- author names supplied by PubMed;
- publication year supplied by PubMed;
- journal title supplied by PubMed;
- PMID and PMCID;
- official PMC article and PDF URLs;
- local PDF filename;
- reviewed license text;
- approved-open-access usage status;
- included status and reviewed inclusion reason;
- receipt SHA-256;
- source type.

PubMed metadata is collected during the existing `efetch` request. No additional per-paper request is needed, and the values remain visible in the review worksheet before promotion.

## Explicit curation still required

The exporter intentionally leaves these fields blank:

- access date;
- license URL;
- study type;
- population;
- intervention;
- comparator;
- outcome notes.

These fields require explicit policy, scientific interpretation, or operator evidence before rows are promoted into `sources.csv`.

## Fail-closed reconciliation

Export stops on unresolved reviews, count mismatches, duplicate identifiers, unsafe filenames, receipt rows without accepted reviews, license or PMCID disagreement, malformed author/year metadata, malformed inputs, or missing verified PMC OA evidence.

Rejected records are not expected in the receipt and cannot become manifest rows.

## Repository boundary

Review worksheets, acquisition receipts, curation drafts, PDFs, and databases remain ignored local work products. Never commit a generated curation draft containing incomplete or operator-specific data.
