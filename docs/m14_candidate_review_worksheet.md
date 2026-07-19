# M14 Candidate Review Worksheet

## Purpose

This step converts one bounded PubMed/PMC discovery page into a deterministic worksheet for explicit human scientific, identity, and license review.

It advances the M14 workflow from discovery evidence to an operator-reviewable decision record. It does not approve candidates, create an acquisition approval file, download PDFs, modify `sources.csv`, or perform ingestion.

## Command

```bash
python -m knowledge_engine.candidate_review_cli prepare \
  --candidates work/m14/candidates-000.json \
  --output work/m14/review-000.json
```

Use `--force` only when intentionally replacing an existing worksheet. Output replacement is atomic and refuses symbolic-link outputs or stage collisions.

## Output boundary

Every item begins with:

- `decision: pending`;
- blank inclusion review;
- blank license review;
- blank identity review;
- blank reviewer;
- blank review timestamp.

The worksheet preserves discovered PMID, title, DOI, PMCID, OA status, reported license, PDF URL, and discovery status. It contains no `approvals` collection and cannot be passed directly to `pmc-oa-acquire`.

## Human review sequence

For each candidate:

1. evaluate the committed scientific inclusion and exclusion criteria;
2. verify PMID, PMCID, title, DOI, and document identity;
3. inspect the reported license and confirm the intended reuse basis;
4. record the reviewer and review timestamp;
5. record an explicit accepted or rejected decision with reasons;
6. independently construct the acquisition approval file only from accepted, fully reviewed records.

## Validation

Preparation rejects malformed discovery JSON, count mismatches, duplicate PMIDs, duplicate PMCIDs, unsupported discovery states, and inconsistent OA status evidence.

## Repository boundaries

Candidate pages, worksheets, approval files, receipts, PDFs, and databases remain local ignored work products. Do not commit completed review worksheets containing operator-specific review data.
