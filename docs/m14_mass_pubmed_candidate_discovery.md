# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one review-only JSON file while preserving the existing legal and human-review boundaries.

It does not download PDFs, approve licenses, modify `sources.csv`, or perform ingestion.

## Command

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query 'GLP-1 receptor agonist obesity weight loss' \
  --limit 150 \
  --page-size 100 \
  --retstart 0 \
  --output work/m14/candidates-000-149.json
```

The requested unique-candidate limit may be between 1 and 5,000. Every provider request remains bounded to at most 100 PubMed records.

## Deterministic aggregation

The workflow:

1. requests PubMed pages in stable result order;
2. fetches metadata and PMC Open Access evidence through the existing production service;
3. preserves the first occurrence of each PMID;
4. removes cross-page duplicate PMIDs;
5. continues until the requested unique count is reached;
6. stops early when PubMed returns a short or empty page;
7. writes one deterministic review-only JSON document.

The output records the requested limit, page size, fetched page count, candidate count, duplicate PMID count, and whether the result set was exhausted.

## Safety boundary

- Output symbolic links are rejected.
- Existing output is rejected unless `--force` is provided.
- Output is written atomically in the destination directory.
- Provider failures remain sanitized.
- No PDF, provider payload, local database, approval file, worksheet, receipt, or generated manifest is committed.
- `oa_verified` remains evidence for human review, not automatic legal approval.

## M14 use

For the current ramp, discover at least 150 candidates, then validate them in bounded scientific and legal review slices. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- study-level duplicate reports;
- rejected records;
- held records;
- accepted review queue;
- acquired full texts;
- manifest-ready rows.

If the defensible evidence base is smaller than 500, record the measured evidence ceiling and a `HOLD` decision rather than padding the corpus with duplicate, weak, or legally unusable records.
