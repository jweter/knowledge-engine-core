# M14 PMC Open Access Acquisition

This command is the explicit-review bridge between PubMed/PMC candidate discovery and local corpus ingestion.

## Trust boundary

Candidate discovery is evidence, not approval. Acquisition requires a separate operator-reviewed JSON file. Every approval must exactly match the discovered:

- PMID;
- PMCID;
- reported license;
- official PMC OA PDF URL.

A mismatch stops before network access. Duplicate PMIDs or output filenames are also rejected before network access.

## Approval file

```json
{
  "schema_version": 1,
  "approvals": [
    {
      "pmid": "12345678",
      "pmcid": "PMC1234567",
      "license": "CC BY",
      "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
      "filename": "PMC1234567.pdf"
    }
  ]
}
```

The approval file is a deliberate operator decision record. Do not generate it automatically from discovery output.

## Command

```bash
ke pmc-oa-acquire \
  --candidates work/m14/candidates-000.json \
  --approvals work/m14/approvals-000.json \
  --papers-dir papers/corpora/glp1_weight_loss \
  --receipt work/m14/acquisition-000.json
```

The command:

1. validates both JSON inputs;
2. cross-checks approval evidence exactly;
3. rejects unsafe URLs, duplicate filenames, symlinks, and existing outputs;
4. downloads only from the official `ftp.ncbi.nlm.nih.gov` HTTPS host;
5. requires a `%PDF-` payload signature;
6. stages the complete approved batch before making final PDF names visible;
7. rolls back staged and committed PDFs when any batch item fails;
8. records filename, byte count, and SHA-256 in a sanitized receipt;
9. removes the acquired PDFs if the receipt cannot be persisted.

The batch is successful only when every approved PDF and the receipt are written. A failed command must not be counted as a completed acquisition batch.

## Repository boundaries

- Keep PDFs under the ignored local papers directory.
- Do not commit candidate pages, approval files, receipts, PDFs, or extracted full text unless a later policy explicitly authorizes a sanitized metadata artifact.
- Do not use personal Drive, publisher scraping, institutional tokens, or private URLs.
- Acquisition does not modify `sources.csv` and does not complete M14.

## Next M14 step

After enough approved PDFs are acquired, reconcile acquisition receipts against the curated `sources.csv`, validate exactly 500 accepted rows and files, then execute the controlled fresh import and linked-resume rehearsal.
