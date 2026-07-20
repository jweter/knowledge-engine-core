# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one review-only JSON file and prepares a deterministic pending-only human-review worksheet while preserving the existing legal and approval boundaries.

It does not download PDFs, approve licenses, modify `sources.csv`, create acquisition approvals, or perform ingestion.

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
7. writes one deterministic review-only discovery document;
8. validates that document through the production candidate-review boundary;
9. writes one pending-only review worksheet with no accepted or rejected decisions;
10. reconciles discovery and worksheet counts before artifact upload.

The summary records the requested candidate count, review-item count, fetched page count, duplicate PMID count, verified PMC Open Access count, and whether the PubMed result set was exhausted.

## Temporary artifact

The GitHub workflow uploads exactly:

- `pubmed-candidates.json` — provider-derived discovery and OA evidence;
- `candidate-review.json` — deterministic pending-only human-review worksheet;
- `summary.txt` — sanitized aggregate counts.

The artifact is temporary and must not be committed. The worksheet is not an approval file and cannot authorize acquisition.

## Safety boundary

- Output symbolic links are rejected.
- Existing output is rejected unless `--force` is provided.
- Output is written atomically in the destination directory.
- Provider failures remain sanitized.
- No PDF, provider payload, local database, approval file, completed worksheet, receipt, or generated manifest is committed.
- Every generated worksheet item must remain `decision: pending` at artifact creation.
- `oa_verified` remains evidence for human review, not automatic legal approval.

## M14 use

For the current ramp, discover at least 500 candidates, then validate them in bounded scientific and legal review slices. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- pending review items;
- study-level duplicate reports;
- rejected records;
- held records;
- accepted review queue;
- acquired full texts;
- manifest-ready rows.

If the defensible evidence base is smaller than 500, record the measured evidence ceiling and a `HOLD` decision rather than padding the corpus with duplicate, weak, or legally unusable records.
