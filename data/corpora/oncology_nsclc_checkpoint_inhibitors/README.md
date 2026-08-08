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
- `sources.csv`: source manifest, 336 rows (see Status below).
- `discovery_state.json`: `ke discovery-cycle-run` pagination bookmark.
- `scientific_question.md`: human-readable question definition and
  rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.

## Status

**Seeded (2026-08-08).** 10 `ke discovery-cycle-run` cycles scanned ~1000
raw PubMed candidates and produced 478 unique deterministically-accepted
candidates (identity/license/full-text/scope rules passed). A documented,
rule-based title scope screen -- excluding wrong cancer types (e.g. SCLC,
gastric, renal), preclinical/mechanism-only studies, off-topic diagnostic or
surgical-technique papers, and single-patient case reports -- selected 336.
All 336 were acquired as real PMC OA PDFs and imported into the corpus
database (`ke corpus-import`: 335 imported, 1 skipped as a duplicate).

This is bulk ingestion, not a reviewed evidence base: `sources.csv`'s
`study_type`/`population`/`intervention`/`comparator` fields are
intentionally blank, matching the same two-stage discipline already used
for the GLP-1 corpus (bulk acquisition first, individual Evidence Record
authoring and review later, for a much smaller subset). Continue discovery
with `--corpus oncology_nsclc_checkpoint_inhibitors` and
`data/corpora/oncology_nsclc_checkpoint_inhibitors/discovery_state.json` as
`--state` to resume from `retstart=950`.

**First automated Evidence Record batch (2026-08-08).** After the PICO
extraction-accuracy fix (`m28-pico-v5`; see `docs/oncology_corpus_scoping.md`),
a first batch of 100 records was promoted into `evidence_records.jsonl`,
honestly labeled `m52-evidence-classification-v1` and `review_status: draft`
-- the same automated tier the GLP-1 corpus used before individual review,
never claiming human confirmation. A trial run of `ke evidence-review-automate`
(M69's grounding-verified LLM refinement) against the first 25 of those
records improved 2 (`population`/`outcome`/`intervention` fields regrounded
against source text; every other proposed correction was rejected by
grounding verification rather than guessed). `claim_text`/`result_summary`
-- the actual scientific claim quotes -- were spot-checked against real
paper text and are accurate; the `research_question` field (templated from
still-imperfect PICO fields) remains known-unreliable for many records
pending further extraction work or individual secondary review, exactly the
same limitation `docs/oncology_corpus_scoping.md` already documents. This is
still not a reviewed evidence base or a golden map -- both remain future work.

**Second batch (2026-08-08, same day): 200 more records promoted.**
`evidence_records.jsonl` now holds 300 draft records (100 + 200, same
`m52-evidence-classification-v1` tier and honesty discipline as the first
batch). Spot-checked `claim_text` across the new batch against real source
text -- accurate. 1,222 further eligible drafts remain unpromoted.

**Third batch (2026-08-08, same day): 300 more records promoted.**
`evidence_records.jsonl` now holds 600 draft records (100 + 200 + 300).
`ke graph-build` processed all 300 new records: graph totals now 754
claims, 97 concepts (61 mesh, 36 rxnorm), 645 claim-concept edges, up from
454/95/327. Spot-checked `claim_text` across the new batch against real
source text -- accurate. 922 further eligible drafts remain unpromoted.
