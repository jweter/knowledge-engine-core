# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one local JSON file and prepares a deterministic adjudication worksheet while preserving legal and approval boundaries.

The M14 rehearsal scope is **Obesity and Metabolic-Disease Therapeutics**. GLP-1 receptor agonists remain the first named subtopic, but discovery also covers treatment evidence for overweight, type 2 diabetes, and metabolic syndrome so the project can reach its first 500 legally reusable full texts without weakening evidence standards.

The default query includes PubMed's `pmc open access[filter]`. This moves the reusable-full-text constraint into discovery instead of spending most of each batch on metadata-only records that the acquisition policy must reject.

The workflow does not download PDFs, modify `sources.csv`, create acquisition approvals, or perform ingestion.

## Command

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query '(obesity OR overweight OR "type 2 diabetes" OR "metabolic syndrome") AND (treatment OR therapy OR intervention OR pharmacotherapy OR semaglutide OR liraglutide OR tirzepatide OR metformin OR "SGLT2 inhibitor") AND pmc open access[filter]' \
  --limit 500 \
  --page-size 100 \
  --retstart 0 \
  --output work/m14/pubmed-candidates.json

python -m knowledge_engine.candidate_review_cli \
  --candidates work/m14/pubmed-candidates.json \
  --output work/m14/candidate-review.json
```

The requested unique-candidate limit may be between 1 and 5,000. The GitHub workflow enforces a minimum of 150 for mass-discovery runs. Every provider request remains bounded to at most 100 PubMed records.

## Deterministic aggregation

The workflow:

1. requests PubMed pages in stable result order using the explicit PMC OA filter;
2. fetches metadata and PMC Open Access evidence through the existing production service;
3. preserves the first occurrence of each PMID;
4. removes cross-page duplicate PMIDs;
5. continues until the requested unique count is reached;
6. stops early when PubMed returns a short or empty page;
7. writes one deterministic discovery document;
8. validates that document through the production candidate-adjudication boundary;
9. writes explicit accepted, rejected, and held decisions;
10. reconciles discovery and adjudication counts before artifact upload.

The summary records candidate count, adjudication-item count, accepted, rejected, and held counts, fetched page count, duplicate PMID count, verified PMC Open Access count, and whether the PubMed result set was exhausted.

## Temporary artifact

The GitHub workflow uploads:

- `pubmed-candidates.json` — provider-derived discovery and OA evidence;
- `candidate-review.json` — deterministic adjudication worksheet;
- `summary.txt` — sanitized aggregate counts.

The artifact is temporary and must not be committed. The worksheet is not itself an acquisition file.

## Safety boundary

- Output symbolic links are rejected.
- Existing output is rejected unless `--force` is provided.
- Output is written atomically in the destination directory.
- Provider failures remain sanitized.
- No PDF, provider payload, local database, approval file, receipt, or generated manifest is committed.
- Every candidate receives an explicit decision.
- `oa_verified` is evidence consumed by deterministic rules, not a blanket legal assumption.
- Held records are automatically deferred and rejected records are automatically excluded.
- The PubMed filter narrows discovery but does not replace the per-record PMC OA, license, identity, and URL checks.
- The broader scientific scope does not broaden the legal trust category: only approved PMC OA evidence can authorize acquisition in this stage.

## M14 use

Discover and adjudicate candidates in bounded pages. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- accepted records;
- rejected records;
- held records;
- acquired full texts;
- manifest-ready rows.

When fewer than 500 records are accepted, continue controlled discovery from the next offset or refine the query within the committed obesity and metabolic-disease domain. Do not wait for owner review of held records. If the defensible evidence base is smaller than 500 after measured scope expansion, record the evidence ceiling and a `HOLD` rehearsal decision rather than padding the corpus with duplicate, weak, or legally unusable records.
