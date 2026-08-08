# Exclusion and Hold Criteria

A source is rejected or held from the Oncology: Checkpoint Inhibitors in
Advanced NSCLC Corpus when any condition below applies.

## Deterministic Scientific Rejection or Hold Conditions

- The title does not identify non-small-cell lung cancer, NSCLC, lung
  cancer, lung carcinoma, or lung adenocarcinoma.
- The title does not identify a treatment, therapy, therapeutic,
  immunotherapy, checkpoint inhibitor, or a named checkpoint-inhibitor agent
  covered by the active ruleset.
- The source is limited to pediatric populations.
- The source studies a cancer type other than NSCLC, even when the same
  checkpoint inhibitors are the intervention (out of this corpus's bounded
  scope -- see `scientific_question.md`).
- The source is mechanism-only and does not address a named therapeutic or
  clinical intervention/trial.
- The source is an editorial, news article, marketing page, or unsupported
  opinion piece rather than primary or synthesized evidence.

Insufficient title evidence produces `held`, not an invented scientific
conclusion. Held records are automatically deferred while discovery
continues.

## Identity and Duplicate Conditions

- Required identity evidence (DOI, PMID, or PMCID as applicable to the
  discovery source) is missing or conflicting.
- The identifier duplicates an already selected record.
- A probable study-level duplicate remains unresolved by deterministic
  evidence.
- The source is retracted or has a serious correction that makes it
  unsuitable.

## Legal and Practical Conditions

- Open access status is not verified under the discovery source's own
  evidence (PMC OA, Europe PMC, or CORE).
- The license is missing, ambiguous, unsupported, or not allowlisted.
- The full-text URL is missing or is not an approved official HTTPS
  resource.
- The PDF cannot be acquired reproducibly.
- The file is not a readable PDF payload or fails bounded file validation.

Records with no verified reusable full text are explicitly `rejected` for
the current acquisition path. Conflicting or incomplete evidence is `held`.
Neither outcome requires owner action before discovery continues, and
neither can authorize acquisition on its own.
