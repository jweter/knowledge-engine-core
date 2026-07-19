# M14 Reviewed Approval Export

## Purpose

This step removes manual retyping between completed human review and PMC OA acquisition. It exports only accepted, fully reviewed worksheet items into the exact approval schema consumed by `pmc-oa-acquire`.

The exporter does not make scientific, identity, or license decisions. It validates and transforms decisions already recorded by a reviewer.

## Command

```bash
python -m knowledge_engine.reviewed_approval_cli export \
  --worksheet work/m14/review-000.json \
  --output work/m14/approvals-000.json
```

## Accepted-review requirements

Every accepted item must include:

- `decision: accepted`;
- nonblank inclusion, identity, and license review evidence;
- a reviewer identifier;
- a timezone-aware review timestamp;
- PMID and PMCID;
- `open_access: true` and `discovery_status: oa_verified`;
- a reported license;
- an official HTTPS `ftp.ncbi.nlm.nih.gov` PDF URL.

Rejected records are omitted. Pending or otherwise unresolved records stop the export so a partial review page cannot silently become an acquisition batch.

## Output boundary

The exported file contains only the acquisition fields:

- PMID;
- PMCID;
- license;
- PDF URL;
- deterministic `PMCID.pdf` filename.

Reviewer identity and review notes remain in the local worksheet and are not copied into the acquisition approval file.

## Workflow progress

1. Discover bounded PubMed/PMC candidates.
2. Prepare a pending review worksheet.
3. Complete scientific, identity, and license review.
4. Export accepted completed reviews with this command.
5. Acquire the resulting approval batch transactionally.

Candidate pages, worksheets, approval files, receipts, PDFs, and databases remain ignored local work products and must not be committed.
