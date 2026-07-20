# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one review-only JSON file and prepares a deterministic candidate worksheet while preserving legal, provenance, and approval boundaries.

Discovery and worksheet preparation do not download PDFs, modify `sources.csv`, create acquisition approvals, or perform ingestion. Later adjudication may automatically accept, reject, or hold records only under the evidence contract defined in `docs/roadmap.md` and `docs/m14_candidate_review_worksheet.md`.

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
9. writes one candidate worksheet without acquisition approvals;
10. reconciles discovery and worksheet counts before artifact upload.

The summary records the requested candidate count, worksheet-item count, fetched page count, duplicate PMID count, verified PMC Open Access count, and whether the PubMed result set was exhausted.

## Temporary artifact

The GitHub workflow uploads exactly:

- `pubmed-candidates.json` — provider-derived discovery and OA evidence;
- `candidate-review.json` — deterministic candidate worksheet;
- `summary.txt` — sanitized aggregate counts.

The artifact is temporary and must not be committed. The worksheet is not itself an acquisition approval file.

## Adjudication boundary

Automated adjudication is a separate repeatable stage after discovery. It may:

- accept records whose scientific, identity, reusable-license, source, and duplicate rules all pass;
- reject records when an explicit exclusion or legal-ineligibility rule fires;
- hold records when evidence is missing, ambiguous, or conflicting.

No record may be silently dropped. Every result must preserve reason codes, provider provenance, rule version, processing timestamp, and supporting evidence. `oa_verified` is evidence used by the rules; it is not sufficient by itself for acceptance.

PubMed, PMC, Crossref, Europe PMC, OpenAlex, and publisher evidence must remain separately attributed. Adding or combining a new provider requires a separate measured design decision and must not silently change the trust category of existing evidence.

## Safety boundary

- Output symbolic links are rejected.
- Existing output is rejected unless `--force` is provided.
- Output is written atomically in the destination directory.
- Provider failures remain sanitized.
- No PDF, provider payload, local database, approval file, completed worksheet, receipt, or generated manifest is committed.
- Free access, a publisher landing page, or a relevance score alone cannot establish reusable-license eligibility.
- Ambiguous evidence produces `held`, never a guessed acceptance.

## M14 use

For the current ramp, discover at least 500 candidates and process them through bounded deterministic adjudication batches. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- accepted records;
- rejected records;
- held records;
- probable study-level duplicates;
- acquisition-approved records;
- acquired full texts;
- manifest-ready rows.

If the defensible evidence base is smaller than 500, record the measured evidence ceiling and a `HOLD` decision rather than padding the corpus with duplicate, weak, or legally unusable records.
