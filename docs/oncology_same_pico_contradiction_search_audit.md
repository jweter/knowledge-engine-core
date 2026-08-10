# Oncology Same-PICO Contradiction Search Audit

## Decision

No source-verified, direction-reversing result was identified for the direct
immune-checkpoint-inhibitor-versus-non-ICI overall-survival PICO in adults
with **advanced** NSCLC (this corpus's own defined research question) in this
bounded, local-corpus search. One automated record's `evidence_direction`
classifier flagged a genuine candidate; investigation found it references a
real trial in a population outside this corpus's own scope (early-stage,
SBRT-treated NSCLC, not advanced disease), not a same-PICO contradiction.

This is a reproducible negative search result over this corpus's own 1,534
Evidence Records. It is not proof that no contradictory literature exists
more broadly, and it is not a consensus or truth claim. Unlike the GLP-1
search this mirrors, it does not yet include a live PubMed literature layer
-- see Remaining Uncertainty below.

## Search Contract

The direct target: PD-1/PD-L1 checkpoint inhibitor therapy (alone or
combined with chemotherapy/other agents) compared with a non-ICI comparator
(chemotherapy alone, placebo, or no consolidation), with overall survival
measured in adults with **advanced/metastatic** NSCLC -- this corpus's own
defined research question (`corpus.json`: "Do immune checkpoint inhibitors
... improve overall survival in adults with advanced non-small-cell lung
cancer?"). The golden map additionally covers resectable stage II and
unresectable stage III (perioperative/consolidation) as population
extensions of that core question. Early-stage (SBRT-eligible, typically
medically inoperable stage I-IIA) NSCLC is outside this corpus's own defined
population and is treated as out of scope, not a same-PICO target, matching
how the corpus's own scoping decision (`docs/oncology_corpus_scoping.md`)
never claims early-stage coverage.

## Search Executed

The audit was run on 2026-08-10 in three layers, all against this corpus's
own committed records (no live literature search yet -- see Remaining
Uncertainty):

1. Screened all 1,534 committed Evidence Records' `claim_text`/
   `result_summary` text for a negative-signal phrase set ("no significant",
   "not significant", "no difference", "did not", "failed to", "no benefit",
   "no improvement", "worse survival/outcome", "inferior", "shorter overall
   survival/progression-free survival/survival", "increased mortality/risk of
   death", "higher risk of death"), case-insensitive. 108 records matched.
2. Cross-referenced each of the 108 matches against its own
   `evidence_direction` field (M52's deterministic cue-pattern
   classification, already computed and stored, not newly invented for this
   audit): 79 `supports`, 28 `qualifies`, 1 `contradicts`.
3. Read the full record for the single `contradicts`-labeled match
   (`auto-36c94bb2ece9b5ac`) and a representative sample of the 28
   `qualifies` matches to confirm none conceal a same-PICO direction
   reversal the deterministic classifier mislabeled.

A fourth layer -- the manually-reviewed golden-map records' own relationship
candidates (the shared-concept-based layer GLP-1's audit ran as its Layer 3)
-- was effectively already covered by this same day's record-to-source
fidelity check (see `CHANGELOG.md`'s 2026-08-10 entry), which read every one
of the golden map's 13 records' full PICO/result fields directly and found
no contradiction among them; that check is not repeated here.

## Candidate Disposition

| Candidate | Disposition | Reason |
| --- | --- | --- |
| `auto-36c94bb2ece9b5ac` (PD-L1 expression prognostic study in early-stage NSCLC after SBRT, citing SWOG/NRG S1914) | Investigated, not added | This record's own paper is a PD-L1-prognostic-biomarker study in SBRT-treated early-stage NSCLC; its `claim_text` cites (not reports as its own finding) the phase 3 SWOG/NRG S1914 trial's result that adding immunotherapy to SBRT did not improve survival (HR 1.15, 95% CI 0.65-2.01, p=0.63) in early-stage NSCLC. Two independent reasons this is not a same-PICO contradiction: (1) SWOG/NRG S1914's population (early-stage, SBRT-eligible NSCLC) is outside this corpus's own defined research question (advanced NSCLC) -- see Search Contract; (2) this Evidence Record's own PICO fields (`population`/`intervention`/`comparator`) are misextracted/broadcast from unrelated sentences in the source paper, a known bug class this project has previously documented (the M52-tier PICO-broadcast issue M69's per-candidate grounded extraction was built to fix) -- the record's own PICO cannot be trusted as written, independent of the scope question. No new Evidence Record was authored from this secondary citation; doing so would mean extracting from a citing paper's characterization rather than the primary source, which this project's sourcing discipline does not permit. |
| 28 `qualifies`-labeled candidates (biomarker associations, adverse-event-rate comparisons, secondary-endpoint subgroup differences, active-ICI-vs-ICI comparisons) | No new record | Sampled and confirmed: each concerns a secondary endpoint, biomarker correlation, or an active-comparator (ICI-vs-ICI, not ICI-vs-non-ICI) finding, not a same-PICO OS direction reversal. One (`auto-592ce1d7c9511f45`) reports a numerically strongly favorable HR (0.36) that narrowly misses significance (p=0.060) -- an underpowered supportive trend, not an adverse finding. |
| 79 `supports`-labeled candidates | No new record | Already classified as supporting the core direction; not independently re-read individually for this audit. |

## Map Effect

This audit adds no new Evidence Record and no new relationship. The
oncology golden map's `contradiction_assessment` is updated to record this
executed search (see `golden_evidence_map.json`), replacing the prior
informal absence-of-search statement with a dated, reproducible negative
result.

## Remaining Uncertainty

This audit did not run a live PubMed literature search (GLP-1's audit's
Layers 4-5). This corpus's core PICO -- ICI vs non-ICI OS in advanced NSCLC
-- is an extremely well-studied area with a correspondingly large published
literature; a live search comparable in scope to GLP-1's would need to be
scoped carefully (this corpus's own 1,534-record local base already samples
that literature far more heavily than GLP-1's did at the time of its
search) rather than run as an unbounded query. This is named here as
explicit follow-up work, not silently skipped. As with GLP-1's search, this
query should be rerun periodically and whenever the map's PICO changes; any
future candidate must still pass source, license, PICO, result, and
relationship review before it changes the map.
