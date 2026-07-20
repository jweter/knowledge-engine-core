# M14 Mass PubMed Candidate Discovery

## Purpose

Use this workflow when M14 needs more than one bounded PubMed page. It aggregates official NCBI discovery pages into one local JSON file and prepares a deterministic adjudication worksheet while preserving legal and approval boundaries.

The M14 rehearsal scope is **Obesity and Metabolic-Disease Therapeutics**. GLP-1 receptor agonists remain the first named subtopic, but discovery also covers treatment evidence for overweight, type 2 diabetes, and metabolic syndrome so the project can reach its first 500 legally reusable full texts without weakening evidence standards.

The default PubMed query includes NCBI's documented `pubmed pmc open access[filter]`. This moves the reusable-full-text constraint into discovery instead of spending most of each batch on metadata-only records that the acquisition policy must reject.

The workflow does not download PDFs, modify `sources.csv`, create acquisition approvals, or perform ingestion.

## Command

```bash
python scripts/m14_pubmed_batch_discover.py \
  --query '(obesity OR overweight OR "type 2 diabetes" OR "metabolic syndrome") AND (treatment OR therapy OR intervention OR pharmacotherapy OR semaglutide OR liraglutide OR tirzepatide OR metformin OR "SGLT2 inhibitor") AND pubmed pmc open access[filter]' \
  --limit 500 \
  --page-size 100 \
  --retstart 0 \
  --output work/m14/pubmed-candidates.json

python -m knowledge_engine.candidate_review_cli \
  --candidates work/m14/pubmed-candidates.json \
  --output work/m14/candidate-review.json
```

The requested unique-candidate limit may be between 1 and 5,000. The GitHub workflow enforces a minimum of 150 for mass-discovery runs. PubMed discovery pages remain bounded to at most 100 records. PMID-to-PMCID conversion uses the official PMC ID Converter in deterministic batches of at most 100 PMIDs, below the service's documented 200-ID limit.

## Deterministic provider sequence

For each bounded page, the workflow:

1. requests PubMed PMIDs in stable result order using the explicit PMC OA Subset filter;
2. fetches bibliographic metadata from PubMed EFetch;
3. submits the page's PMIDs to the official PMC ID Converter in bounded batches;
4. reconciles every returned `requested-id`, PMID, and PMCID before accepting the mapping;
5. merges non-overlapping conversion results back into the original PubMed page order;
6. queries the official PMC OA service separately for each resolved PMCID;
7. records PubMed metadata, PMC identifier conversion, and PMC OA evidence as separate provider sources;
8. preserves the first occurrence of each PMID across discovery pages;
9. removes cross-page duplicate PMIDs;
10. continues until the requested unique count is reached;
11. writes one deterministic discovery document and adjudication worksheet;
12. reconciles discovery, resolver, OA, and decision counts before artifact upload.

The resolver never infers PMCID identity from title or DOI similarity. Missing conversions remain unresolved. Conflicting, duplicate, or malformed mappings fail closed. Transient status codes, timeouts, incomplete response bodies, and other bounded transport failures are retried at most three times with NCBI-compliant request pacing.

## Coverage measurements

The summary records:

- candidate count;
- adjudication-item count;
- accepted, rejected, and held counts;
- fetched page count;
- duplicate PMID count;
- PMIDs with a resolved PMCID;
- PMID-to-PMCID resolution rate;
- records verified by the PMC OA service;
- PMC OA verification rate;
- whether the PubMed result set was exhausted.

Coverage denominators are the filtered candidate count in the same run. A PubMed filter match is not treated as PMC OA evidence until the PMID resolves to a PMCID and the official PMC OA response reconciles to that PMCID.

## Historical measured limitation

The first 500-record run using the official PubMed PMC OA filter returned 500 citations, but the earlier ELink request sent one comma-separated PMID value while parsing the response as if source-specific linksets had been requested. That request shape resolved only five PMCIDs and therefore verified only five PMC OA records. None satisfied the complete title-scope acceptance rule.

Repeated-ID ELink requests then exposed incomplete HTTP reads even after chunking and bounded retry. The resolver now uses the official PMC ID Converter's purpose-built multi-ID endpoint for PMID-to-PMCID mapping, while retaining the PMC OA service as the separate license and downloadable-resource evidence source.

This task repairs the source-to-target linkage contract and measures the resulting coverage. It does not weaken license, identity, URL, provenance, or scientific-scope rules.

## Temporary artifact

The GitHub workflow uploads:

- `discovery.log` — sanitized discovery diagnostics;
- `pubmed-candidates.json` — provider-derived discovery, identifier, and OA evidence;
- `candidate-review.json` — deterministic adjudication worksheet;
- `summary.txt` — sanitized aggregate counts and coverage rates.

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
- The PubMed filter narrows discovery but does not replace the per-record PMC ID Converter, PMC OA, license, identity, and URL checks.
- PubMed metadata, PMC identifier conversion, and PMC OA evidence remain separate provenance categories.
- The broader scientific scope does not broaden the legal trust category: only approved PMC OA evidence can authorize acquisition in this stage.

## M14 use

Discover and adjudicate candidates in bounded pages. Maintain separate counts for:

- discovered candidates;
- exact PMID duplicates removed;
- PMCID-resolved records;
- PMC OA-verified records;
- accepted records;
- rejected records;
- held records;
- acquired full texts;
- manifest-ready rows.

When fewer than 500 records are accepted, continue controlled discovery from the next offset or refine the query within the committed obesity and metabolic-disease domain. Do not wait for owner review of held records. If the defensible evidence base is smaller than 500 after measured scope expansion, record the evidence ceiling and a `HOLD` rehearsal decision rather than padding the corpus with duplicate, weak, or legally unusable records.
