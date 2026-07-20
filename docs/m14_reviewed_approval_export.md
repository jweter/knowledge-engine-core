# M14 Adjudicated Approval Export

## Purpose

This step exports only records that have passed the complete deterministic M14 acceptance contract into the exact approval schema consumed by `pmc-oa-acquire`.

The exporter does not invent scientific, identity, or licensing evidence. It validates and transforms accepted adjudication records whose rule results, provenance, and reusable-license basis already reconcile. Held and rejected records are automatically excluded rather than waiting for human resolution.

The implementation retains the historical module name `reviewed_approval` for compatibility, but no human review is required.

## Command

```bash
python -m knowledge_engine.reviewed_approval_cli export \
  --worksheet work/m14/review-000.json \
  --output work/m14/approvals-000.json
```

## Accepted-record requirements

Every accepted item must include:

- `decision: accepted`;
- passing scientific inclusion and exclusion results;
- reconciled PMID, PMCID, title, DOI, and document identity evidence;
- `open_access: true` and `discovery_status: oa_verified`;
- an explicit reusable-license basis;
- an approved official HTTPS full-text URL;
- no unresolved exact or probable duplicate condition;
- provider-specific provenance for each decision input;
- explicit decision reason codes;
- an adjudication-rules version;
- a timezone-aware processing timestamp.

Rejected and held records are omitted with their evidence preserved in the adjudication worksheet. Unsupported decision values, malformed accepted records, or contradictory accepted evidence stop export.

## Output boundary

The exported file contains the acquisition fields required by the acquisition service:

- PMID;
- PMCID;
- license;
- approved PDF URL;
- deterministic `PMCID.pdf` filename.

Detailed evidence remains in the local adjudication worksheet and is not copied into the minimal acquisition approval file.

## Workflow progress

1. Discover bounded PubMed/PMC candidates.
2. Generate the adjudication worksheet.
3. Run deterministic scientific, identity, license, source, and duplicate rules.
4. Automatically defer held records and exclude rejected records.
5. Export complete accepted records with this command.
6. Acquire the resulting approval batch transactionally.
7. Continue discovery when the accepted count remains below 500.

No reviewer identity, manual approval, review note, or owner timestamp is required.

Candidate pages, worksheets, approval files, receipts, PDFs, and databases remain ignored local work products and must not be committed.
