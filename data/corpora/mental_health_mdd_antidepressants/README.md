# Mental Health: Antidepressants in Major Depressive Disorder Corpus

The third research domain (`docs/roadmap.md`'s "Decision: the extraction
and discovery framework must be domain-general, not per-field-patched"),
added alongside continued GLP-1 and oncology work, not instead of it.
Mirrors `data/corpora/glp1_weight_loss` and
`data/corpora/oncology_nsclc_checkpoint_inhibitors`'s exact file shape and
the same deterministic, legally-traceable discovery/adjudication pipeline
-- see `docs/mental_health_corpus_scoping.md` for why this specific
population/intervention pair was chosen.

## Scientific Question

Do selective serotonin reuptake inhibitors (SSRIs) and
serotonin-norepinephrine reuptake inhibitors (SNRIs) reduce depressive
symptom severity in adults with major depressive disorder (MDD)?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: source manifest, header-only (see Status below).
- `scientific_question.md`: human-readable question definition and
  rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.

## Status

**Scoped, not yet seeded (2026-08-08).** Corpus definition, scope
vocabulary (`knowledge_engine.scientific_scope.MENTAL_HEALTH_MDD_ANTIDEPRESSANT_SCOPE`),
and inclusion/exclusion criteria exist. No `ke discovery-cycle-run` cycles
have been run yet; `sources.csv` is header-only. Seeding this corpus with
real papers (mirroring the GLP-1 and oncology corpora's own bulk-acquisition
milestone), then individually authoring and reviewing Evidence Records,
remain future, separate work.
