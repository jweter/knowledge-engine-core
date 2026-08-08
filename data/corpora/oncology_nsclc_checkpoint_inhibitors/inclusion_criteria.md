# Inclusion Criteria

A source may be included in the Oncology: Checkpoint Inhibitors in Advanced
NSCLC Corpus when it meets every required criterion.

## Required Scientific Criteria

- The source is a scientific paper, systematic review, meta-analysis, or
  clinical research report.
- The title identifies non-small-cell lung cancer, NSCLC, lung cancer, lung
  carcinoma, or lung adenocarcinoma.
- The title identifies a treatment, therapy, therapeutic, immunotherapy,
  checkpoint inhibitor, or a named checkpoint-inhibitor agent covered by the
  active adjudication rules (see
  `knowledge_engine.scientific_scope.ONCOLOGY_NSCLC_CHECKPOINT_SCOPE`).
- The studied population includes adults or reports evidence applicable to
  adult treatment.
- The source has enough bibliographic and identifier evidence to reconcile
  its identity (DOI, PMID, or PMCID as applicable to the discovery source).

## Required Legal and Operational Criteria

- PMC Open Access evidence is verified (PubMed/PMC and Europe PMC pipelines),
  or the source is verified open access under CORE's own evidence (CORE
  pipeline).
- The reusable-license basis is explicit and allowlisted by the active
  ruleset -- see `license_policy.md`.
- The full-text PDF is available from an approved official HTTPS source.
- The record has no unresolved exact identifier duplicate.
- Every decision input records provider-specific provenance.
- The deterministic adjudication result is `accepted` under the recorded
  rules version.

## Preferred Evidence Characteristics

These characteristics improve corpus balance but are not mandatory when all
required criteria pass:

- randomized controlled trial;
- systematic review or meta-analysis;
- clear comparator arm (chemotherapy, placebo, or another active treatment);
- clear checkpoint-inhibitor agent and follow-up duration;
- quantitative overall-survival or progression-free-survival outcome;
- DOI and complete author/journal metadata;
- explicit limitations, adverse-event, or safety findings.

## Initial Corpus Balance

The first discovery batches should include multiple checkpoint-inhibitor
agents (pembrolizumab, nivolumab, atezolizumab, durvalumab, cemiplimab) and
study designs, mirroring the GLP-1 corpus's own initial-balance policy. No
fixed quota may be filled by weakening the legal, identity, provenance, or
scientific rules. Held and rejected records remain in adjudication evidence
and do not block continued discovery.
