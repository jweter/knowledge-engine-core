# M14 Candidate Adjudication Worksheet

## Purpose

This step converts bounded PubMed/PMC discovery output into a deterministic adjudication worksheet. The worksheet performs repeatable machine evaluation of scientific scope, identifier consistency, reusable-license evidence, approved full-text location, and exact duplicate risk.

It advances M14 from discovery evidence to explicit `accepted`, `rejected`, or `held` decisions. It does not itself download PDFs, modify `sources.csv`, perform ingestion, resolve probable study-level duplicates, or collapse evidence from separate providers into one trust category.

## Command

```bash
python -m knowledge_engine.candidate_review_cli \
  --candidates work/m14/candidates-000.json \
  --output work/m14/review-000.json
```

Use `--force` only when intentionally replacing an existing worksheet. Output replacement is atomic and refuses symbolic-link outputs or stage collisions.

## Initial ruleset

The first implemented ruleset is `m14-candidate-adjudication-v1`.

It uses only evidence already present in the bounded PubMed/PMC discovery document:

- PubMed title and bibliographic identifiers;
- PubMed-to-PMC identity linkage;
- PMC Open Access service status;
- the reported PMC OA license;
- the official PMC OA PDF URL;
- exact PMID and PMCID uniqueness within the discovery batch.

No external provider evidence is inferred or silently introduced.

## Decision contract

Every candidate receives one explicit result:

- `accepted` when every required deterministic rule passes with complete, non-conflicting evidence;
- `rejected` when the record is `metadata_only` and therefore has no verified reusable full text in the current PMC OA acquisition path;
- `held` when an OA-linked record has incomplete or unsupported scientific-scope, identity, license, or approved-PDF evidence.

No candidate is silently dropped. Held records require exception review or later roadmap-approved evidence expansion before acceptance or rejection.

## Scientific-scope boundary

Version 1 accepts scientific scope only when the title contains both:

- a GLP-1 term (`GLP-1`, `GLP1`, or `glucagon-like peptide-1`); and
- an obesity or weight term (`obesity`, `obese`, `weight loss`, `body weight`, or `adiposity`).

Title evidence that does not satisfy both groups is held as `SCIENTIFIC_SCOPE_INSUFFICIENT`; it is not automatically rejected. Abstract retrieval, semantic classification, and additional-provider evidence are outside this ruleset.

## License and full-text boundary

Version 1 accepts only:

- PMC OA evidence with a reported license beginning with `CC BY` or `CC0`; and
- an HTTPS PDF URL hosted at `ftp.ncbi.nlm.nih.gov` whose path ends in `.pdf`.

Free access, publisher landing pages, missing license strings, unrecognized license bases, and non-PMC PDF hosts do not qualify. OA-linked records with those conditions are held rather than guessed.

## Required output evidence

Every adjudication record preserves:

- PMID, PMCID, DOI, title, authors, venue, and publication year when available;
- provider categories (`pubmed_metadata` and `pmc_oa_service`);
- discovery status, reported license, and PDF URL;
- scientific, identity, license, full-text, and exact-duplicate rule results;
- explicit decision reason codes;
- adjudication-rules version;
- timezone-aware processing timestamp;
- unresolved ambiguity categories.

The worksheet contains no `approvals` collection and cannot itself authorize acquisition.

## Validation

Preparation and adjudication reject malformed discovery JSON, count mismatches, duplicate PMIDs, duplicate PMCIDs, unsupported discovery states, inconsistent OA evidence, and conflicting discovery limits.

## Repository boundaries

Candidate pages, adjudication worksheets, approval files, receipts, PDFs, and databases remain local ignored work products. Do not commit completed worksheets containing provider payloads, local paths, or operator-specific exception-review data.
