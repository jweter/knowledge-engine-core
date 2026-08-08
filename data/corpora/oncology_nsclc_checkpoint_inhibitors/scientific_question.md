# Scientific Question

## Question

Do immune checkpoint inhibitors (anti-PD-1/PD-L1) improve overall survival in
adults with advanced non-small-cell lung cancer (NSCLC)?

## Rationale

`docs/roadmap.md`'s "Decision: domain diversification beyond GLP-1" (2026-08-08)
records the project owner's decision to add a second, unrelated research
domain so the corpus does not look like infrastructure built to promote one
drug class. This corpus is that second domain.

Advanced NSCLC with anti-PD-1/PD-L1 checkpoint inhibitors was chosen, not
oncology broadly, for the same reason the GLP-1 corpus stayed bounded to
obesity/metabolic-disease pharmacotherapy rather than "all disease": a narrow,
well-studied population/intervention/outcome triple is what makes an
evidence-map-defensible corpus possible (see
`glp1_body_weight_golden_evidence_map.md`). This specific pairing was picked
because it has the same evidence shape GLP-1 does -- large, well-known
randomized trials (e.g. KEYNOTE, CheckMate, IMpower-family studies), a clear
comparator (chemotherapy or placebo), and a measurable primary endpoint
(overall survival, progression-free survival) -- so the same golden-map,
statistical-verification, and relationship-graph tooling built for GLP-1
should apply here with no new architecture, only a new `ScopeVocabulary` (see
`knowledge_engine/scientific_scope.py`).

## Question Frame

- Population: adults with advanced (locally advanced or metastatic)
  non-small-cell lung cancer.
- Intervention: an immune checkpoint inhibitor targeting PD-1 or PD-L1
  (e.g. pembrolizumab, nivolumab, atezolizumab, durvalumab, cemiplimab),
  alone or in combination with chemotherapy.
- Comparator: chemotherapy alone, placebo, or another active treatment
  described by the source.
- Outcomes: overall survival, progression-free survival, objective response
  rate, adverse events, and clinically relevant limitations.
- Time scope: any clearly reported treatment or follow-up duration.

## Initial Subtopics

- PD-1 inhibitors (pembrolizumab, nivolumab, cemiplimab) in advanced NSCLC.
- PD-L1 inhibitors (atezolizumab, durvalumab) in advanced NSCLC.
- Checkpoint inhibitor plus chemotherapy combination regimens.
- Checkpoint inhibitor monotherapy versus chemotherapy.

## Out of Scope for Initial Discovery

- Pediatric-only populations.
- Cancer types other than NSCLC (even when the same checkpoint inhibitors
  are studied there -- a future corpus, not this one, if pursued).
- Mechanism-only papers without a named clinical intervention or trial.
- Cost-effectiveness or policy-only papers without treatment-outcome evidence.
- Editorials, news, marketing material, and unsupported opinion pieces.
- Records without verified reusable full text under an approved source
  policy (same PMC OA / Europe PMC / CORE trust boundaries as the GLP-1
  corpus -- see `license_policy.md`).

## Status

No discovery has run against this corpus yet. `sources.csv` contains only
the header row; `evidence_records.jsonl` and `relationship_records.jsonl` do
not exist yet. Run discovery with `--corpus oncology_nsclc_checkpoint_inhibitors`
(see `knowledge_engine/scientific_scope.py`'s `ONCOLOGY_NSCLC_CHECKPOINT_SCOPE`)
to begin populating this corpus.
