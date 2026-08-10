# Mental Health Toxicity/Adverse-Event and Discontinuation-Syndrome Synthesis

## Purpose

The mental-health golden evidence map's `known_gaps` named
toxicity/adverse-event and discontinuation-syndrome synthesis across the
represented SSRI/SNRI agents as a qualifier layer not yet built. This
document builds it: a deterministic, source-linked collation of the
safety/tolerability data already present in the golden map's own 9 Evidence
Records' `result_summary`/`limitations` fields, plus a bounded corpus-wide
signal scan for scale context. It mirrors
`docs/oncology_toxicity_adverse_event_synthesis.md`'s shape, applied to this
corpus.

This is a **qualifier layer, not a pooled safety analysis**. No
adverse-event rate is recomputed, pooled, or compared across agents as if
the underlying trials used comparable AE definitions or ascertainment
windows -- they do not.

## Method

1. Read all 9 golden-map Evidence Records' `result_summary`, `limitations`,
   `claim_text`, and `uncertainty_notes` fields directly (already-committed
   text) and identified every record containing safety/tolerability
   content.
2. Ran a deterministic phrase-set scan (`adverse event`, `toxicit*`,
   `discontinu* (adverse|toxic|safety)`, `treatment-emergent adverse`,
   `safety profile`, `tolerab*`, `side effect`, case-insensitive) across all
   133 committed Evidence Records for corpus-wide scale context.
3. Grouped the golden-map records with safety content by agent/strategy and
   wrote the found figures side by side without pooling them.

## Golden-Map Safety Findings (5 of 9 records report safety/tolerability content)

| Record | Agent/strategy | Safety finding |
| --- | --- | --- |
| `ev-mh-kishi-2024-japan-older-adults-meta-001` | Antidepressants (multi-class) vs placebo, older adults | Significantly higher discontinuation due to AEs (RR 1.94, 95% CI 1.30-2.88, p=0.001) and higher incidence of >=1 AE (RR 1.11, 95% CI 1.02-1.21, p=0.02) vs placebo. This is the map's clearest efficacy-tolerability trade-off finding: the same record reports significant efficacy AND significantly worse tolerability versus placebo in the same population, and its own authors concluded only a "weak recommendation" on that basis. |
| `ev-mh-schmidt-2024-aticaprant-adjunctive-ssri-snri-rct-001` | Aticaprant added to SSRI/SNRI | Most common TEAEs vs placebo: headache (11.8% vs 7.1%), diarrhea (8.2% vs 2.4%), nasopharyngitis (5.9% vs 2.4%), pruritus (5.9% vs 0%); discontinuation due to AEs low and similar between arms (1.2% each) -- a detailed, agent-specific AE table, the most granular in this map. |
| `ev-mh-perez-2025-depre5-second-line-strategies-001` | Second-line strategies after SSRI non-response (lithium, nortriptyline, venlafaxine switch, SSRI+PST) | Nortriptyline combination showed markedly more adverse effects than SSRI+problem-solving-therapy (75% vs 28.1%, p<0.01) -- named explicitly by this record's own `limitations` as a safety trade-off its efficacy-focused `result_summary` does not fully capture. |
| `ev-mh-yan-2024-escitalopram-vs-sertraline-poststroke-rct-001` | Escitalopram vs sertraline, post-stroke depression | Adverse-effect incidence significantly lower with escitalopram (chi-squared 9.097, p<0.05) -- a comparative safety finding between two specific SSRIs in a medically comorbid population. |
| `ev-mh-ju-2025-agomelatine-adjunctive-ssri-snri-rct-001` | Agomelatine added to SSRI/SNRI | Reported qualitatively only: "generally well tolerated with a safety profile comparable to placebo" -- no quantified AE rate captured in this record. |

Four golden-map records (`ev-mh-yin-2023-escitalopram-vs-other-antidepressants-meta-001`,
`ev-mh-santi-2024-vilazodone-escitalopram-vortioxetine-rct-001`,
`ev-mh-zandifar-2024-empagliflozin-adjunctive-citalopram-rct-001`,
`ev-mh-baradaran-2024-escitalopram-cabg-quality-of-life-rct-001`) contain no
safety/tolerability content at all in their currently-extracted fields.

## Cross-Agent Observations (qualifying context, not a pooled claim)

- **The clearest, best-evidenced safety signal in this map is class-wide, not
  agent-specific**: Kishi's meta-analysis (9 trials, n=2,145, older adults)
  is the only record with both a placebo comparator and formal
  discontinuation-due-to-AE statistics, and it shows a real
  efficacy-tolerability trade-off. Because this is an age-restricted
  (older-adult) subgroup, it should not be generalized to general-population
  MDD tolerability without caution -- exactly the caution this record's own
  `limitations` already states for its efficacy claim.
- **Augmentation-strategy records** (Perez, Schmidt, Ju, Zandifar) report
  safety inconsistently: Perez names a specific, large safety difference
  between two named second-line strategies (nortriptyline vs SSRI+PST);
  Schmidt gives full per-symptom TEAE percentages; Ju and Zandifar report no
  quantified safety data at all despite being RCTs where such data was
  presumably collected. This inconsistency in what gets extracted/reported
  is itself part of the gap, not just the underlying clinical variance.
- **Comorbid-population records** (Yan: post-stroke; Baradaran: post-CABG)
  are exactly where safety data matters most (drug-interaction and frailty
  risk is elevated), yet only one of the two (Yan) reports a quantified
  safety comparison; Baradaran's record has none.
- **No discontinuation-syndrome-specific data** (the abrupt-cessation
  withdrawal phenomenon the gap statement specifically names, distinct from
  on-treatment adverse events) was found in any of the 9 golden-map records
  -- this remains a fully open gap, not partially addressed by the
  discontinuation-due-to-AE figures above (which measure a different thing:
  stopping the drug because of a side effect while still on it, not
  symptoms from stopping it).

## Corpus-Wide Signal Scan (context, not an audit)

17 of the corpus's 133 committed Evidence Records (12.8%) match the
adverse-event/toxicity phrase set in Method step 2. Reported for scale
context only, not individually re-read record-by-record -- see Remaining
Uncertainty.

## Map Effect

This synthesis adds no new Evidence Record and changes no `result_summary`.
It is a new standalone document, referenced from the golden map's
`known_gaps` (replacing the "not yet built" language with a pointer to this
synthesis and an honest statement of what it does and does not establish).

## Remaining Uncertainty

- This synthesis reads only the golden map's own 9 records' currently
  extracted fields, plus a phrase-set count over the other 124 records. It
  does not re-read the 17 phrase-matched records' full source PDFs and does
  not compute a pooled AE rate for any agent or class.
- The gap statement's specific mention of "discontinuation-syndrome"
  (withdrawal on stopping an antidepressant, a well-documented SSRI/SNRI
  phenomenon, particularly for short-half-life agents like paroxetine and
  venlafaxine) is **not addressed by this synthesis at all** -- none of the
  9 golden-map records discuss it, and this document does not manufacture
  that coverage. It remains a fully open item, named here explicitly rather
  than silently folded into the broader "safety" heading above.
- A future, more rigorous version of this qualifier layer -- with
  per-agent, MedDRA-coded AE and discontinuation-syndrome extraction as its
  own Evidence Record field -- remains a real, larger follow-up milestone,
  not something this document claims to have built.
