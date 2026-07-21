# M14 PMC Open Access Acquisition

This step is the deterministic bridge between accepted PubMed/PMC adjudications and local corpus ingestion.

## Trust boundary

Candidate discovery is evidence, not acquisition authority. Acquisition requires the separate exactly-500 approval artifact produced from accepted adjudications. Every approval must exactly match the discovered:

- PMID;
- PMCID;
- reported license;
- official PMC OA PDF URL.

A mismatch stops before network access. Duplicate PMIDs, PMCIDs, or output filenames are also rejected before network access.

## Approval file

The M14 approval artifact retains acquisition schema version 1 and records deterministic selection evidence:

```json
{
  "schema_version": 1,
  "rules_version": "m14-candidate-adjudication-v3",
  "selection_rule": "accepted_in_worksheet_order",
  "source_candidate_count": 3250,
  "source_accepted_count": 589,
  "selected_count": 500,
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

The acquisition service validates `selected_count` against the approval-array length. Before the acquisition command is allowed to make any network request, the controlled M14 workflow separately requires schema version 1, `selected_count` equal to 500, exactly 500 approval rows, and 500 unique PMIDs, PMCIDs, and filenames.

## Command

```bash
ke pmc-oa-acquire \
  --candidates work/m14/pubmed-candidates.json \
  --approvals work/m14/approvals-500.json \
  --papers-dir work/m14/papers \
  --receipt work/m14/acquisition-receipt.json
```

The command:

1. validates both JSON inputs;
2. cross-checks every approval against provider-derived candidate evidence;
3. rejects unsafe URLs, duplicate identifiers, duplicate filenames, symlinks, and existing outputs;
4. downloads only from the official `ftp.ncbi.nlm.nih.gov` HTTPS host;
5. requires a `%PDF-` payload signature;
6. stages the complete approved batch before making final PDF names visible;
7. rolls back staged and committed PDFs when any batch item fails;
8. records PMID, PMCID, license, filename, byte count, and SHA-256 in a sanitized receipt;
9. removes acquired PDFs if the receipt cannot be persisted.

The workflow then reconciles exactly 500 approval rows, exactly 500 receipt items, and exactly 500 local PDF files. Each local file's byte count and SHA-256 must match the receipt.

The batch is successful only when every approved PDF and the receipt are written and reconciled. A failed command must not be counted as a completed acquisition batch.

## Temporary artifacts

The M14 workflow uploads:

- discovery/adjudication/approval/receipt evidence for 14 days;
- the 500 approved PDFs for 3 days so the next bounded manifest/import task can consume the immutable batch.

These artifacts are temporary workflow outputs. They must not be committed to Git.

## Repository boundaries

- Keep PDFs under ignored local or temporary workflow directories.
- Do not commit candidate pages, approval files, receipts, PDFs, extracted full text, or databases.
- Do not use personal Drive, publisher scraping, institutional tokens, or private URLs.
- Acquisition does not generate a manifest and does not run ingestion.

## Next M14 step

After exactly 500 PDFs and the sanitized receipt reconcile, generate an immutable 500-row manifest from the same approval/receipt snapshot, validate local paths and identifiers, then execute the controlled fresh import and linked-resume rehearsal in a separate bounded task.
