# Exclusion and Hold Criteria

A source is rejected or held from the Obesity and Metabolic-Disease
Therapeutics Corpus when any condition below applies.

## Deterministic Scientific Rejection or Hold Conditions

- The title does not identify obesity, overweight, type 2 diabetes, metabolic
  syndrome, or another approved metabolic-disease scope term.
- The title does not identify a treatment, therapy, intervention,
  pharmacotherapy, or named therapeutic agent covered by the active ruleset.
- The source is limited to pediatric populations.
- The source is type 1 diabetes-specific without evidence applicable to the
  committed Phase 1 scope.
- The source is mechanism-only and does not address a named therapeutic or
  clinical intervention.
- The source is an editorial, news article, marketing page, or unsupported
  opinion piece rather than primary or synthesized evidence.

Insufficient title evidence produces `held`, not an invented scientific
conclusion. Held records are automatically deferred while discovery continues.

## Identity and Duplicate Conditions

- Required PubMed or PMC identity evidence is missing or conflicting.
- The PMID or PMCID duplicates an already selected record.
- A probable study-level duplicate remains unresolved by deterministic evidence.
- The source is retracted or has a serious correction that makes it unsuitable.

## Legal and Practical Conditions

- PMC Open Access membership is not verified.
- The license is missing, ambiguous, unsupported, or not allowlisted.
- The full-text URL is missing or is not an approved official HTTPS resource.
- The PDF cannot be acquired reproducibly.
- The file is not a readable PDF payload or fails bounded file validation.

Records with no verified reusable full text are explicitly `rejected` for the
current acquisition path. Conflicting or incomplete evidence is `held`. Neither
outcome requires owner action before the first working version, and neither can
authorize acquisition.
