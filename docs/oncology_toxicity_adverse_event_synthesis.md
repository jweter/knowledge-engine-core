# Oncology Toxicity/Adverse-Event Synthesis

## Purpose

The oncology golden evidence map's `known_gaps` named toxicity/adverse-event
synthesis across the represented ICI regimens as a qualifier layer not yet
built. This document builds it: a deterministic, source-linked collation of
the safety/tolerability data already present in the golden map's own 13
Evidence Records' `result_summary`/`limitations` fields, plus a bounded
corpus-wide signal scan for scale context. It mirrors
`docs/oncology_same_pico_contradiction_search_audit.md`'s shape (Method,
Findings, Map Effect, Remaining Uncertainty) applied to a synthesis task
instead of a contradiction search.

This is a **qualifier layer, not a pooled safety analysis**. No adverse-event
rate is recomputed, pooled, or compared across regimens as if the underlying
trials/cohorts used comparable AE definitions, grading, or ascertainment
windows -- they do not. See Limitations below.

## Method

1. Read all 13 golden-map Evidence Records' `result_summary`, `limitations`,
   `claim_text`, and `uncertainty_notes` fields directly (already-committed
   text, no new extraction) and identified every record containing
   safety/tolerability content.
2. Ran a deterministic phrase-set scan (`adverse event`, `toxicit*`,
   `grade [3-5]`, `pneumonitis`, `hepatitis`, `colitis`,
   `immune-related adverse`, `treatment-related death`, `safety profile`,
   `tolerab*`, etc., case-insensitive) across all 1,534 committed Evidence
   Records for corpus-wide scale context (see Remaining Uncertainty for why
   this is context, not a full audit).
3. Grouped the golden-map records with safety content by regimen/agent and
   wrote the found figures side by side without pooling them.

## Golden-Map Safety Findings (9 of 13 records report safety/tolerability content)

| Record | Regimen | Safety finding |
| --- | --- | --- |
| `ev-oncology-tsuboi-2026-keynote671-stageii-efs-os-001` | Perioperative pembrolizumab + chemo (KEYNOTE-671, stage II subgroup) | Grade 3-4 treatment-related AEs more frequent with pembrolizumab (50.0%) than chemotherapy alone (40.5%). |
| `ev-oncology-weber-2026-nic-vs-pc-realworld-001` | Nivolumab+ipilimumab+chemo (NIC) vs pembrolizumab+chemo (PC) | No significant difference in clinically significant AEs, related discontinuations, or treatment-related deaths (p=0.885/1.000/0.709). Immune-related AEs more frequent with NIC (p=0.001); chemotherapy-related AEs more frequent with PC (p<0.001) -- a real, class-consistent difference between dual- and single-ICI regimens, not a null result. |
| `ev-oncology-machado-2026-pembrolizumab-realworld-meta-001` | First-line pembrolizumab monotherapy (12-cohort real-world pooled analysis) | Any-grade AEs in 52% of patients; grade >=3 AEs in 12%. |
| `ev-oncology-selke-2026-durvalumab-pdl1-subgroup-001` | Durvalumab consolidation after chemoradiotherapy | Immunotherapy-related pneumonitis of grade >=1 in 15.7% of durvalumab-treated patients. |
| `ev-oncology-esen-2026-induction-chemoimmunotherapy-realworld-001` | Induction chemoimmunotherapy + consolidative radiotherapy + maintenance immunotherapy | No grade 4-5 radiotherapy-related toxicity; 1 grade 5 immune-related pneumonitis (of 34 patients). |
| `ev-oncology-dang-2026-icichemo-vs-chemo-os-001` | PD-1/PD-L1 inhibitors + chemo vs chemo alone (28-RCT meta-analysis) | This record's own `limitations` explicitly state the source review "does not independently assess ... adverse events" for the OS comparisons it reports -- named as a gap by the record itself, not silently omitted. |
| `ev-oncology-stuschke-2026-durvalumab-crisp-realworld-001` | Durvalumab consolidation (CRISP real-world registry) | Limitations note this record "does not independently assess ... adverse events ... beyond the reported follow-up window" -- the underlying paper was not read for a safety endpoint by this record's own scope. |
| `ev-oncology-katsarolis-2026-greek-realworld-os-001` | Immunotherapy at any line (Greek real-world cohort) | Limitations note this record "does not independently assess ... adverse events." |
| `ev-oncology-nodbrant-2026-ecogps-real-world-os-001` | Palliative ICI, any agent (Swedish registry) | Limitations state the registry itself had "no data on ... immune-related adverse events." |

Four golden-map records (`ev-oncology-wu-2026-liver-mets-network-meta-pfs-os-001`,
`ev-oncology-mao-2026-pd1-vegf-antibody-meta-pfs-os-001`,
`ev-oncology-liao-2026-icpscore-predictive-biomarker-001`,
`ev-oncology-gandara-2026-cemiplimab-composite-pro-os-001`) contain no
safety/tolerability content at all in their currently-extracted fields.

## Cross-Regimen Observations (qualifying context, not a pooled claim)

- **Immune-related pneumonitis** appears as a named, quantified toxicity in
  two independent durvalumab-consolidation contexts (Selke: 15.7% grade >=1;
  Esen: 1 grade-5 event of 34 patients) and is the adverse event most
  consistently named by title across these records -- consistent with
  pneumonitis's known status as a class-characteristic ICI toxicity in this
  clinical setting, but this is a qualitative pattern across two small,
  non-randomized cohorts, not a pooled incidence estimate.
- **Dual-checkpoint-inhibition (nivolumab+ipilimumab) vs single-agent
  regimens**: the one head-to-head record in this map (Weber) found
  significantly more immune-related AEs with the dual-ICI regimen, the
  expected direction given ipilimumab's independent toxicity profile, but
  this is one retrospective, single-center, baseline-imbalanced comparison
  and should not be read as a definitive dual-vs-single safety verdict.
- **Perioperative/consolidation settings** (Tsuboi, Esen) report grade 3-5
  toxicity rates in the 40-50% (any grade 3-4 TRAE) to near-zero
  (grade 4-5 RT-toxicity specifically) range depending on which toxicity
  category is being measured -- these are not the same measurement and must
  not be read as contradictory or averaged together.
- **Four of thirteen records report no safety data**, and three more
  explicitly flag (in their own `limitations`) that they did not assess
  safety even though their source paper may contain it -- this is the
  concrete shape of the gap the golden map's `known_gaps` named: this map's
  safety picture is a partial, heterogeneously-measured sample, not a
  systematic toxicity profile of ICI therapy in NSCLC.

## Corpus-Wide Signal Scan (context, not an audit)

264 of the corpus's 1,534 committed Evidence Records (17.2%) match the
adverse-event/toxicity phrase set in Method step 2. This number is reported
for scale context only -- it was not individually read record-by-record (see
Remaining Uncertainty) and should not be read as "264 records have
comparable, poolable safety data"; the phrase set matches everything from a
one-line "no significant AE difference" mention to a detailed graded-AE
table, and pooling across such heterogeneous reporting would misrepresent
the underlying evidence exactly as the earlier same-PICO contradiction audit
warned against doing for efficacy claims.

## Map Effect

This synthesis adds no new Evidence Record and changes no `result_summary`.
It is a new standalone document, referenced from the golden map's
`known_gaps` (replacing the "not yet built" language with a pointer to this
synthesis and an honest statement of what it does and does not establish).

## Remaining Uncertainty

- This synthesis reads only the golden map's own 13 records' currently
  extracted fields, plus a phrase-set count over the other 1,521 records. It
  does not re-read the 264 phrase-matched records' full source PDFs, does
  not compute a pooled or meta-analytic AE rate for any single agent or
  class, and does not attempt formal pharmacovigilance methodology (e.g.
  MedDRA-coded AE grouping, denominator harmonization across differing
  follow-up windows).
- Real toxicity/AE literature for these regimens is extensive and
  well-characterized in FDA labeling and published ICI-toxicity reviews
  outside this corpus; this document only synthesizes what this specific
  local corpus's committed records already contain, consistent with this
  project's `founding_vision.md` "Knowledge Is Never Final" discipline.
- A future, more rigorous version of this qualifier layer -- with per-agent
  MedDRA-coded AE extraction as its own Evidence Record field -- remains a
  real, larger follow-up milestone, not something this document claims to
  have built.
