# M14 PubMed/PMC Candidate Discovery

## Purpose

This command creates a bounded, reviewable candidate list for the GLP-1 corpus using official NCBI services. It is a discovery and legal-evidence preparation step. It does not download papers, approve licenses, modify the curated source manifest, or perform ingestion.

## Command

```bash
ke pubmed-candidate-discover \
  --query 'GLP-1 receptor agonist obesity weight loss' \
  --limit 25 \
  --retstart 0 \
  --output work/m14/candidates-000.json
```

Use `--retstart` to request the next deterministic page. The maximum page size is 100 candidates.

The command refuses to overwrite an existing output unless `--force` is supplied. Symbolic-link outputs are rejected.

## Network boundary

The command contacts only allowlisted official NCBI HTTPS hosts:

- `eutils.ncbi.nlm.nih.gov` for PubMed search, record retrieval, and PubMed-to-PMC linkage;
- `pmc.ncbi.nlm.nih.gov` for PMC identifier conversion;
- `pmc-oa-opendata.s3.amazonaws.com` for the PMC Article Datasets Cloud Service, which resolves OA verification, license evidence, and PDF/XML download URLs (see `docs/architecture/adr/0004-migrate-pmc-oa-acquisition-to-cloud-service.md` for the full API contract and why this replaced the retired PMC OA Web Service).

Redirects, URL credentials, non-HTTPS URLs, nonstandard ports, oversized responses, and unsupported hosts are rejected. Provider failures are returned as sanitized messages without raw payloads.

## Candidate states

- `oa_verified`: the PubMed record links to a PMC record and the PMC Cloud Service confirmed it is part of the PMC Open Access Subset (`is_pmc_openaccess`), with downloadable-resource evidence.
- `metadata_only`: PubMed metadata was found, but reusable PMC OA evidence was not established.

`oa_verified` is evidence for review, not automatic legal approval. A reviewer must still confirm the license, inclusion criteria, document identity, and intended use before promoting a source into `sources.csv`.

## Output contract

The JSON output records:

- the normalized query;
- `retstart` and page limit;
- candidate count;
- PMID;
- title;
- DOI when present;
- PMCID when linked;
- OA verification status;
- reported license text;
- PMC resource URLs when available;
- review status.

The output is deterministic for the same NCBI response sequence and preserves PubMed result ordering.

## M14 workflow

1. Run bounded discovery pages.
2. Review candidates against the committed GLP-1 inclusion and exclusion criteria.
3. Verify license evidence and document identity.
4. Select exactly 500 accepted sources with unique stable IDs.
5. Curate accepted rows into `sources.csv`.
6. Acquire matching full text only from approved public sources into the ignored local papers directory.
7. Validate the immutable corpus manifest and file readiness.
8. Execute the controlled M14 fresh import and linked resume.

## Prohibited shortcuts

Do not:

- use personal Google Drive or other private storage as a substitute corpus source;
- treat PubMed indexing as proof that full text is reusable;
- treat free-to-read access as a redistribution license;
- scrape unsupported publisher sites;
- automatically promote candidates into the source manifest;
- commit PDFs, provider payloads, or local databases to Git.
