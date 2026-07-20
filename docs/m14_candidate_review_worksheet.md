# M14 Candidate Adjudication Worksheet

## Purpose

This step converts bounded PubMed/PMC discovery output into a deterministic adjudication worksheet. The worksheet supports repeatable machine evaluation of scientific scope, identifier consistency, reusable-license evidence, approved full-text location, and duplicate risk.

It advances M14 from discovery evidence to explicit `accepted`, `rejected`, or `held` decisions. It does not itself download PDFs, modify `sources.csv`, perform ingestion, or collapse evidence from separate providers into one trust category.

## Command

```bash
python -m knowledge_engine.candidate_review_cli \
  --candidates work/m14/candidates-000.json \
  --output work/m14/review-000.json
```

Use `--force` only when intentionally replacing an existing worksheet. Output replacement is atomic and refuses symbolic-link outputs or stage collisions.

## Decision contract

Every candidate must receive one explicit result:

- `accepted` when every required deterministic rule passes with complete, non-conflicting evidence;
- `rejected` when a deterministic exclusion or legal-ineligibility rule fires;
- `held` when identity, licensing, scientific relevance, full-text eligibility, or duplicate status remains incomplete, ambiguous, or conflicting.

No candidate may be silently dropped. Held records require exception review before they can be accepted or rejected.

## Required evidence

Every adjudication record must preserve:

- PMID, PMCID, DOI, title, authors, venue, and publication year when available;
- provider-specific provenance for every evidence value;
- PMC Open Access status and the exact reusable-license basis;
- approved full-text location and source category;
- scientific inclusion and exclusion rule results;
- exact and probable duplicate evidence;
- decision reason codes;
- adjudication-rules version;
- processing timestamp;
- unresolved ambiguity indicators.

An automated decision must never infer a license from free access, a publisher landing page, or a relevance score alone.

## Deterministic sequence

For each candidate:

1. normalize and reconcile identifiers without overwriting conflicting provider evidence;
2. evaluate committed scientific inclusion and exclusion rules;
3. validate PMC Open Access membership, reported license, and approved full-text source;
4. detect exact identifier duplicates and flag probable study-level duplicates;
5. emit `accepted`, `rejected`, or `held` with explicit reason codes and evidence;
6. route only held records to exception review;
7. generate acquisition approval records only from accepted records satisfying the complete acceptance contract.

## Validation

Preparation and adjudication must reject malformed discovery JSON, count mismatches, duplicate PMIDs, duplicate PMCIDs, unsupported discovery states, inconsistent OA evidence, missing rule versions, and decision records that do not reconcile with their evidence.

## Repository boundaries

Candidate pages, adjudication worksheets, approval files, receipts, PDFs, and databases remain local ignored work products. Do not commit completed worksheets containing provider payloads, local paths, or operator-specific exception-review data.
