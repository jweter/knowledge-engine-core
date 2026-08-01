# M14 Adjudicated Approval Export

## Purpose

This step exports only records that have passed the complete deterministic M14 acceptance contract into the approval schema consumed by `pmc-oa-acquire`.

The exporter validates every accepted adjudication record. Held and rejected records are excluded automatically. The historical module name `reviewed_approval` remains for compatibility; no human review is required.

## Command

```bash
python -m knowledge_engine.reviewed_approval_cli export \
  --worksheet work/m14/candidate-review.json \
  --output work/m14/approvals-500.json \
  --limit 500
```

The command fails closed when fewer than 500 accepted records exist.

## Deterministic selection rule

The rule is `accepted_in_worksheet_order`.

The worksheet preserves bounded PubMed discovery order. The exporter validates all accepted records, preserves their relative worksheet order, then selects the first requested number. It never sorts by mutable metadata, provider timing, or filesystem order. The same immutable worksheet and limit produce the same selected identifiers.

## Required evidence

Every accepted item must include passing scientific, identity, license, full-text, and duplicate rules; reconciled PMID and PMCID; verified PMC OA status; reusable-license evidence; an approved HTTPS PDF URL; reason codes; provider provenance; rules version; timezone-aware adjudication time; and no unresolved ambiguity.

Malformed, contradictory, duplicate, unsupported, or insufficient accepted evidence stops export.

## Output boundary

The output remains acquisition schema version 1 and includes:

- `rules_version`;
- `selection_rule`;
- `source_candidate_count`;
- `source_accepted_count`;
- `selected_count`;
- `approvals`, containing PMID, PMCID, license, approved PDF URL, and `PMCID.pdf` filename.

The acquisition reader consumes the existing `schema_version` and `approvals` fields and tolerates the additional top-level audit metadata.

Candidate files, worksheets, approval files, receipts, PDFs, and databases remain ignored local work products and must not be committed.
