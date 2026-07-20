# M14 Mass PubMed Candidate Discovery

## Purpose

This workflow performs bounded PubMed/PMC discovery, deterministic adjudication, and exactly-500 approval selection while preserving legal and acquisition boundaries.

The corpus remains **Obesity and Metabolic-Disease Therapeutics**. The default query uses `pubmed pmc open access[filter]`, but every record still requires PMCID, PMC OA, license, identity, scientific-scope, duplicate, and direct-PDF validation.

The workflow does not download PDFs, create receipts or manifests, or run ingestion.

## Commands

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query '(obesity OR overweight OR "type 2 diabetes" OR "metabolic syndrome") AND (treatment OR therapy OR intervention OR pharmacotherapy OR semaglutide OR liraglutide OR tirzepatide OR metformin OR "SGLT2 inhibitor") AND pubmed pmc open access[filter]' \
  --limit 3250 \
  --page-size 100 \
  --output work/m14/pubmed-candidates.json

python -m knowledge_engine.candidate_review_cli \
  --candidates work/m14/pubmed-candidates.json \
  --output work/m14/candidate-review.json

python -m knowledge_engine.reviewed_approval_cli export \
  --worksheet work/m14/candidate-review.json \
  --output work/m14/approvals-500.json \
  --limit 500
```

## Deterministic sequence

1. Discover PMIDs in stable PubMed order.
2. Fetch PubMed metadata.
3. Resolve PMID-to-PMCID mappings through bounded PMC ID Converter requests.
4. Query PMC OA evidence separately.
5. Preserve provider-specific provenance.
6. Remove exact duplicate PMIDs while preserving first occurrence.
7. Adjudicate every candidate as accepted, rejected, or held.
8. Validate every accepted record.
9. Preserve accepted worksheet order.
10. Select the first exactly 500 accepted records using `accepted_in_worksheet_order`.
11. Fail closed when fewer than 500 accepted records exist.
12. Reconcile discovery, adjudication, selection, resolver, and OA counts.

## Measured supply

Exact-head M14 run `29764185659` produced:

- candidates: 3,250;
- accepted: 589;
- rejected: 24;
- held: 2,637;
- PMCID resolution: 100%;
- PMC OA verification: 99.2615%;
- exhausted: false.

The supply prerequisite is met with 89 accepted records above the required 500. Excess accepted records remain in the worksheet but are not selected automatically.

## Temporary artifact

The workflow uploads:

- `discovery.log`;
- `pubmed-candidates.json`;
- `candidate-review.json`;
- `approvals-500.json`;
- `summary.txt`.

All are temporary and must not be committed.

## Safety boundary

No PDF, provider payload, local database, receipt, generated manifest, or private path is committed. Held and rejected records never enter selection. The approval exporter validates all accepted rows before selecting the requested prefix. The exactly-500 artifact is only the acquisition-candidate boundary; acquisition and ingestion remain separate tasks.
