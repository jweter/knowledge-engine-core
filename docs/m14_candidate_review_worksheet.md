# M14 Candidate Adjudication Worksheet

## Purpose

This step converts bounded PubMed/PMC discovery output into a deterministic adjudication worksheet. The worksheet supports repeatable machine evaluation of scientific scope, identifier consistency, reusable-license evidence, approved full-text location, and duplicate risk.

The active M14 scientific scope is **Obesity and Metabolic-Disease Therapeutics**. GLP-1 receptor agonists remain a named subtopic alongside treatment evidence for overweight, type 2 diabetes, metabolic syndrome, metformin, SGLT2 inhibitors, and other explicitly allowlisted therapeutic terms.

It advances M14 from discovery evidence to explicit `accepted`, `rejected`, or `held` decisions. It does not download PDFs, modify `sources.csv`, perform ingestion, or collapse evidence from separate providers into one trust category.

## Command

```bash
python -m knowledge_engine.candidate_review_cli prepare \
  --candidates work/m14/candidates-000.json \
  --output work/m14/review-000.json
```

Use `--force` only when intentionally replacing an existing worksheet. Output replacement is atomic and refuses symbolic-link outputs or stage collisions.

## Decision contract

Every candidate receives one explicit result:

- `accepted` when every required deterministic rule passes with complete, non-conflicting evidence;
- `rejected` when a deterministic exclusion or legal-ineligibility rule fires;
- `held` when identity, licensing, scientific relevance, full-text eligibility, or duplicate status remains incomplete, ambiguous, or conflicting.

No candidate is silently dropped. Held records are automatically deferred from approval and acquisition. They do not wait for owner review and do not block accepted records from continuing through the pipeline.

## Required evidence

Every adjudication record preserves:

- PMID, PMCID, DOI, title, PubMed abstract, authors, venue, and publication year when available;
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
2. evaluate committed scientific inclusion and exclusion rules using PubMed title and abstract evidence;
3. validate PMC Open Access membership, reported license, and approved full-text source;
4. detect exact identifier duplicates and flag probable study-level duplicates;
5. emit `accepted`, `rejected`, or `held` with explicit reason codes and evidence;
6. automatically exclude held and rejected records from acquisition;
7. continue bounded discovery until exactly 500 accepted records exist or the measured source ceiling is reached;
8. generate acquisition approval records only from accepted records satisfying the complete acceptance contract.

No reviewer identifier, review note, review timestamp, or owner decision is required by this stage.

## Initial deterministic ruleset

The active ruleset is `m14-candidate-adjudication-v7`.

- `metadata_only` records are rejected for the PMC OA acquisition path with `NO_VERIFIED_REUSABLE_FULL_TEXT`.
- Scientific evidence passes only when the combined PubMed title and abstract contain both a declared metabolic-disease term and a declared treatment or therapeutic term.
- Disease terms include obesity, overweight, type 2 diabetes, and metabolic syndrome.
- Therapeutic terms include general treatment language plus named GLP-1 therapies, metformin, and SGLT2 terminology.
- Missing abstracts do not fail by themselves; title evidence may still satisfy the same two-factor rule.
- A title containing a pediatric-population term (pediatric, paediatric, child, infant, neonat, adolescent, youth) fails scientific evidence -- `exclusion_criteria.md` requires excluding sources "limited to pediatric populations", the corpus's scope is adult treatment. Checked against the title only, not the abstract, since an adult study's abstract can mention pediatric research as background without the study itself being pediatric. (v7; a v6 gap let three pediatric-titled records be accepted before a matching age/population term happened to also satisfy every other rule.)
- PubMed structured abstract sections are preserved in stable source order with their section labels when provided.
- PMC OA records are accepted only when scientific title-plus-abstract evidence, PMCID identity evidence, an allowlisted CC license, and an official PMC Cloud Service HTTPS PDF URL (`pmc-oa-opendata.s3.amazonaws.com`) all pass.
- Incomplete or unsupported OA evidence produces `held`; it does not request human intervention.
- Exact duplicate PMIDs or PMCIDs remain malformed-input errors because the discovery artifact must reconcile before adjudication.

## Validation

Preparation and adjudication reject malformed discovery JSON, count mismatches, duplicate PMIDs, duplicate PMCIDs, unsupported discovery states, inconsistent OA evidence, missing rule versions, and decision records that do not reconcile with their evidence.

## Repository boundaries

Candidate pages, adjudication worksheets, approval files, receipts, PDFs, and databases remain local ignored work products. Do not commit generated worksheets containing provider payloads or local paths.
