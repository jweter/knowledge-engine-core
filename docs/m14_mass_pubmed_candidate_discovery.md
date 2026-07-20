# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one review-only JSON file and prepares a deterministic adjudication worksheet while preserving legal and approval boundaries.

It does not download PDFs, modify `sources.csv`, create acquisition approvals, or perform ingestion.

## Command

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query 'GLP-1 receptor agonist obesity weight loss' \
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

1. requests PubMed pages in stable result order;
2. fetches metadata and PMC Open Access evidence through the existing production service;
3. preserves the first occurrence of each PMID;
4. removes cross-page duplicate PMIDs;
5. continues until the requested unique count is reached;
6. stops early when PubMed returns a short or empty page;
7. writes one deterministic discovery document;
8. validates that document through the production candidate-adjudication boundary;
9. writes explicit accepted, rejected, and held decisions;
10. reconciles discovery and adjudication counts before artifact upload.

The summary records candidate count, adjudication-item count, fetched page count, duplicate PMID count, verified PMC Open Access count, decision counts, and whether the PubMed result set was exhausted.

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

## M14 use

Discover and adjudicate candidates in bounded pages. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- accepted records;
- rejected records;
- held records;
- acquired full texts;
- manifest-ready rows.

When fewer than 500 records are accepted, continue controlled discovery from the next offset or a separately approved query revision. Do not wait for owner review of held records. If the defensible evidence base is smaller than 500, record the measured evidence ceiling and a `HOLD` rehearsal decision rather than padding the corpus with duplicate, weak, or legally unusable records.
