# M14 Adjudicated Approval Export

## Purpose

This step exports only records that have passed the complete deterministic M14 acceptance contract into the exact approval schema consumed by `pmc-oa-acquire`.

The exporter does not invent scientific, identity, or licensing evidence. It validates and transforms accepted adjudication records whose rule results, provenance, and reusable-license basis already reconcile. Held or unresolved records cannot be exported.

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

Rejected records are omitted with their reasons preserved in the worksheet. Held, pending, malformed, or otherwise unresolved records stop export so a partial or ambiguous batch cannot silently become an acquisition batch.

## Output boundary

The exported file contains the acquisition fields required by the acquisition service, including:

- PMID;
- PMCID;
- license;
- approved PDF URL;
- deterministic `PMCID.pdf` filename;
- adjudication decision identifier or ruleset reference required for traceability.

Detailed evidence and exception-review notes remain in the local adjudication worksheet and are not copied into the minimal acquisition approval file.

## Workflow progress

1. Discover bounded PubMed/PMC candidates.
2. Prepare an adjudication worksheet.
3. Run deterministic scientific, identity, license, source, and duplicate rules.
4. Route ambiguous records to exception review as `held`.
5. Export only complete accepted records with this command.
6. Acquire the resulting approval batch transactionally.

Candidate pages, worksheets, approval files, receipts, PDFs, and databases remain ignored local work products and must not be committed.
