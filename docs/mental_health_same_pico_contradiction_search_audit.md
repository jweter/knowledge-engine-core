# Mental Health Same-PICO Contradiction Search Audit

## Decision

No source-verified, direction-reversing result was identified for the
direct SSRI/SNRI-versus-placebo depressive-symptom-severity-reduction PICO
in adults with MDD in this bounded, local-corpus search. This confirms and
formalizes the golden map's existing `contradiction_assessment`, which
already correctly treated Ju's null agomelatine-augmentation result as a
qualifier (a different augmentation agent added to ongoing SSRI/SNRI
treatment, not SSRI/SNRI monotherapy efficacy itself) rather than a
contradiction.

This is a reproducible negative search result over this corpus's own 133
Evidence Records. It is not proof that no contradictory literature exists
more broadly, and it is not a consensus or truth claim. Unlike the GLP-1
search this mirrors, it does not yet include a live PubMed literature layer
-- see Remaining Uncertainty below.

## Search Contract

The direct target: SSRI or SNRI treatment (monotherapy or as the base
treatment for an adjunctive/augmentation strategy) compared with placebo or
an active-comparator antidepressant, with depressive-symptom-severity
reduction (response/remission on HDRS, HAMD, or MADRS) measured in adults
with MDD -- this corpus's own defined research question. A specific
augmentation agent's null result (e.g. Ju's agomelatine finding) is treated
as a qualifier on that specific agent, not a same-PICO contradiction of
SSRI/SNRI efficacy itself, matching the map's own existing framing and
GLP-1's precedent for agent-specific qualifiers.

## Search Executed

The audit was run on 2026-08-10 in two layers, all against this corpus's own
committed records (no live literature search yet -- see Remaining
Uncertainty):

1. Screened all 133 committed Evidence Records' `claim_text`/
   `result_summary` text for the same negative-signal phrase set used in the
   oncology audit ("no significant", "not significant", "no difference",
   "did not", "failed to", "no benefit", "no improvement", etc.),
   case-insensitive. 13 records matched.
2. Read all 13 matches in full, including each match's `evidence_direction`
   field (M52's deterministic classification for the automated records; the
   6 manually-reviewed golden-map matches were already directly read in
   full during this same day's record-to-source fidelity check).

A third layer -- shared-concept relationship candidates among the golden
map's 9 manually-reviewed records -- was already covered by the same day's
fidelity check, which read every one of those 9 records' full PICO/result
fields directly and found no contradiction among them; not repeated here.

## Candidate Disposition

| Candidate | Disposition | Reason |
| --- | --- | --- |
| `ev-mh-ju-2025-agomelatine-adjunctive-ssri-snri-rct-001` | Already a reviewed qualifier, not a new finding | Null result for agomelatine specifically added to ongoing SSRI/SNRI treatment; already correctly represented in the golden map as an `agent_population_qualifier` node and via `rel-mh-schmidt-contextualizes-ju-adjunctive-heterogeneity-001`/`rel-mh-ju-qualifies-perez-second-line-strategies-001`. Does not test SSRI/SNRI monotherapy against placebo. |
| 5 records from one MRI/neuroimaging sub-study (`auto-a92133acd86cb964`, `auto-12e2fd8c805cb723`, `auto-5098e9fb415ff9b1`, `auto-948546280b82d92b`, `auto-abdbb515ec8f1bb7`) | No new record | All report null findings on neuroimaging biomarker measures (amygdala/orbito-frontal-cortex activation contrasts) comparing an SSRI (citalopram) or an experimental 5-HT4 agonist/antagonist to placebo. The outcome variable is a neuroimaging contrast, not depressive-symptom-severity reduction -- a different outcome from this corpus's own defined PICO, not a same-PICO contradiction. |
| 2 records comparing vortioxetine to fluoxetine on a medication-adherence scale (`auto-7ed7755a86cead14`, `auto-2f46b0e416e0dad8`) | No new record | Both concern the Medication Adherence Rating Scale (MARS) and a chi-square correlation test, not depressive-symptom-severity reduction; an active-comparator, different-outcome finding, not a same-PICO contradiction. |
| Remaining 5 golden-map records already captured above (Yin, Santi, Yan, Kishi, Baradaran) | No new finding | All already fully read during this same day's fidelity check; none report a same-PICO direction reversal. |

## Map Effect

This audit adds no new Evidence Record and no new relationship. The
mental-health golden map's `contradiction_assessment` is updated to record
this executed search (see `golden_evidence_map.json`), replacing the prior
informal absence-of-search statement with a dated, reproducible negative
result.

## Remaining Uncertainty

This audit did not run a live PubMed literature search (GLP-1's audit's
Layers 4-5), for the same reason named in the oncology audit's equivalent
section: this corpus's core PICO is a well-studied area, and a live search
needs deliberate scoping rather than an unbounded query. Named here as
explicit follow-up work. This query should be rerun periodically and
whenever the map's PICO changes; any future candidate must still pass
source, license, PICO, result, and relationship review before it changes
the map.
