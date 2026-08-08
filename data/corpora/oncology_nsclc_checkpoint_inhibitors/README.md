# Oncology: Checkpoint Inhibitors in Advanced NSCLC Corpus

The second research domain (`docs/roadmap.md`'s "Decision: domain
diversification beyond GLP-1"), added alongside continued GLP-1 depth work,
not instead of it. Mirrors `data/corpora/glp1_weight_loss`'s exact file
shape and the same deterministic, legally-traceable discovery/adjudication
pipeline -- see `docs/oncology_corpus_scoping.md` for why this specific
population/intervention pair was chosen.

## Scientific Question

Do immune checkpoint inhibitors (anti-PD-1/PD-L1) improve overall survival
in adults with advanced non-small-cell lung cancer?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: source manifest (header row only -- no discovery has run
  yet).
- `scientific_question.md`: human-readable question definition and
  rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.

## Status

Not yet populated. Run discovery with `--corpus
oncology_nsclc_checkpoint_inhibitors` (e.g. `ke discovery-cycle-run --query
"..." --corpus oncology_nsclc_checkpoint_inhibitors ...`) to begin
populating this corpus with the same M14/M34/M35 discovery-and-adjudication
pipeline the GLP-1 corpus uses, scoped to
`knowledge_engine.scientific_scope.ONCOLOGY_NSCLC_CHECKPOINT_SCOPE` instead
of the default GLP-1 vocabulary.
