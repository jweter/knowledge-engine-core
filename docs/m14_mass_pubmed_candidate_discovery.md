# M14 Mass PubMed Candidate Discovery

## Purpose

This workflow performs bounded PubMed/PMC discovery, deterministic adjudication, exactly-500 approval selection, and transactional acquisition of the approved PDFs while preserving legal and ingestion boundaries.

The corpus remains **Obesity and Metabolic-Disease Therapeutics**. The default query uses `pubmed pmc open access[filter]`, but every record still requires PMCID, PMC OA, license, identity, scientific-scope, duplicate, and direct-PDF validation.

The workflow does not generate a manifest, create a database, or run ingestion.

## Commands

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query '(obesity OR overweight OR "type 2 diabetes" OR "metabolic syndrome") AND (treatment OR therapy OR intervention OR pharmacotherapy OR semaglutide OR liraglutide OR tirzepatide OR metformin OR "SGLT2 inhibitor") AND pubmed pmc open access[filter]' \
  --limit 3250 \
  --page-size 100 \
  --output work/m14/pubmed-candidates.json

python -m knowledge_engine.candidate_review_cli prepare \
  --candidates work/m14/pubmed-candidates.json \
  --output work/m14/candidate-review.json

python -m knowledge_engine.reviewed_approval_cli export \
  --worksheet work/m14/candidate-review.json \
  --output work/m14/approvals-500.json \
  --limit 500

ke pmc-oa-acquire \
  --candidates work/m14/pubmed-candidates.json \
  --approvals work/m14/approvals-500.json \
  --papers-dir work/m14/papers \
  --receipt work/m14/acquisition-receipt.json
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
12. Cross-check all 500 approvals against discovery evidence before network access.
13. Stage all 500 PDF payloads and require `%PDF-` signatures.
14. Commit the complete batch transactionally or roll it back.
15. Write a sanitized receipt with byte counts and SHA-256 hashes.
16. Reconcile exactly 500 approvals, receipt items, and local PDF files.

## Measured supply

Exact-head M14 run `29781225743` for PR #74 produced:

- candidates: 3,250;
- accepted: 589;
- rejected: 24;
- held: 2,637;
- selected: 500;
- PMCID resolution: 100%;
- PMC OA verification: 99.2615%;
- exhausted: false.

The supply and exactly-500 selection prerequisites are met. Excess accepted records remain in the worksheet and are not acquired automatically.

## Workflow capacity

The prior discovery-and-selection workflow required more than 30 minutes, so PR #74 raised its timeout to 45 minutes. The acquisition stage adds 500 bounded HTTPS PDF requests plus checksum and artifact work. The combined workflow timeout is therefore 120 minutes. This is execution headroom for the same fixed corpus and unchanged evidence rules, not a scope or architecture expansion.

## Temporary artifacts

The workflow uploads a 14-day evidence artifact containing:

- `discovery.log`;
- `pubmed-candidates.json`;
- `candidate-review.json`;
- `approvals-500.json`;
- `acquisition-receipt.json`;
- `summary.txt`.

On full success it also uploads the exactly 500 approved PDFs as a separate 3-day artifact. PDFs remain temporary workflow data and must not be committed.

## Safety boundary

No PDF, provider payload, local database, receipt, generated manifest, or private path is committed. Held and rejected records never enter selection. The acquisition command validates every approval against provider-derived evidence, rejects duplicate identifiers and unsafe destinations, verifies PDF signatures, and rolls back the complete batch on failure.

The successful acquisition artifact is only the immutable local-file boundary for the next task. Manifest generation, preflight validation, fresh import, linked resume, and final M14 reporting remain separate work.
