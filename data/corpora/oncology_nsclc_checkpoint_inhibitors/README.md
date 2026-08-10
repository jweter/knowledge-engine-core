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

**Fourth batch (2026-08-08, same day): 300 more records promoted.**
`evidence_records.jsonl` now holds 900 draft records (100 + 200 + 300 +
300). `ke graph-build` processed all 300 new records: graph totals now
1,054 claims, 100 concepts (63 mesh, 37 rxnorm), 932 claim-concept edges,
up from 754/97/645. Spot-checked `claim_text` across the new batch
against real source text -- accurate. 622 further eligible drafts remain
unpromoted.

**Fifth batch (2026-08-08, same day): 299 more records promoted.**
`evidence_records.jsonl` now holds 1,199 draft records (900 + 299; one
of the 300-item slice was already promoted and correctly skipped).
`ke graph-build` processed the 299 new records: graph totals now 1,353
claims, 104 concepts (64 mesh, 40 rxnorm), 1,305 claim-concept edges, up
from 1,054/100/932. Spot-checked `claim_text` across the new batch
against real source text -- accurate. 323 further eligible drafts remain
unpromoted.

**Sixth and final batch (2026-08-08, same day): 322 more records
promoted -- the full 1,522-item m28-pico-v5 eligible pool is now
promoted.** `evidence_records.jsonl` holds 1,521 draft records (1,199 +
322). `ke graph-build` processed the final 322 records: graph totals now
1,675 claims, 109 concepts (66 mesh, 43 rxnorm), 1,597 claim-concept
edges, up from 1,353/104/1,305. Spot-checked `claim_text` across the
final batch against real source text -- accurate. This is still bulk
draft-tier evidence (`m52-evidence-classification-v1`, `review_status:
draft`), not a reviewed evidence base or golden map -- individual review
and a golden evidence map for this corpus remain future, separate work,
mirroring GLP-1's own progression.

**Reviewed-evidence-layer bootstrap (2026-08-09): first manually-authored
record.** `ev-oncology-dang-2026-icichemo-vs-chemo-os-001` is the first
`review_status: reviewed` Evidence Record for this corpus, hand-authored
(not promoted from the automated draft pool) by reading the local PDF
for Dang et al. 2026 (PeerJ, PMC13353234), a meta-analysis of 28 RCTs
(14,758 patients). It records the paper's own vs-chemotherapy-alone
overall-survival hazard ratios for both checkpoint-inhibitor classes
(PD-L1 + chemo: HR 0.82 [0.75-0.90]; PD-1 + chemo: HR 0.65 [0.61-0.71]),
which directly answers this corpus's scientific question, alongside the
paper's own headline PD-L1-vs-PD-1 class comparison (HR 1.26
[1.13-1.41]) as secondary context. `evidence_records.jsonl` now holds
1,522 records (1,521 draft + 1 reviewed). `ke graph-build` processed the
one new record: graph totals now 1,676 claims, 109 concepts (66 mesh, 43
rxnorm; the new record's PICO fields did not resolve to a new concept),
1,597 claim-concept edges, 17 relationship edges, 5 citation edges (all
carried over from the prior claim -- no relationship/citation record
exists for this new claim yet). This is a first bootstrap step toward an
eventual golden evidence map for this corpus (see
`docs/glp1_body_weight_golden_evidence_map.md` for the model this will
follow), not yet a bounded, externally-audited map of its own -- see
this record's `provenance.secondary_review.caveat` for the honest
same-session-self-audit limitation on its current review status.

**Reviewed-evidence-layer growth (2026-08-09): 3 more hand-authored
records (4 total).** Added three more manually-authored,
source-audited Evidence Records, each read directly from its local
PDF: `ev-oncology-tsuboi-2026-keynote671-stageii-efs-os-001` (a
genuine subgroup analysis of the named landmark phase 3 KEYNOTE-671
trial, restricted to clinical stage II NSCLC -- EFS HR 0.50
[0.34-0.74]; OS HR 0.69 [0.43-1.11], directionally favorable but not
independently significant in this subgroup; MPR/pCR both improved);
`ev-oncology-nodbrant-2026-ecogps-real-world-os-001` (a large Swedish
registry-based real-world cohort of ICI-treated lung cancer patients,
stratified by baseline ECOG performance status -- lung-cancer-specific
mOS of 21.5 vs 9.6 vs 4.3 months for PS 0-1/2/3, deliberately using the
paper's NSCLC-specific Table 2 values rather than its pooled
across-cancer-types abstract figures); and
`ev-oncology-gandara-2026-cemiplimab-composite-pro-os-001` (a
secondary analysis of the EMPOWER-Lung 1 and EMPOWER-Lung 3 phase 3
cemiplimab trials, showing composite patient-reported-outcome burden
predicts OS more strongly than any single PRO scale -- top composite
HR 2.52 [1.75-3.64] vs top single-scale HR 1.92 [1.43-2.58]).
`evidence_records.jsonl` now holds 1,525 records (1,521 draft + 4
reviewed). `ke graph-build` processed the 3 new records: graph totals
now 1,679 claims, 111 concepts (67 mesh, 44 rxnorm), 1,602
claim-concept edges. Same same-session-self-audit caveat applies to
all four reviewed records; a future independent audit remains
warranted.

**Reviewed-evidence-layer growth (2026-08-09, same day): 3 more
hand-authored records (7 total).** Added three more manually-authored,
source-audited Evidence Records:
`ev-oncology-stuschke-2026-durvalumab-crisp-realworld-001` (a
real-world, propensity-weighted German CRISP registry cohort
validating durvalumab consolidation after chemoradiotherapy in
unresectable stage III NSCLC -- PFS HR 0.52 [0.37-0.73]; OS HR 0.67
[0.44-1.02], directionally favorable but not statistically significant,
"effect sizes comparable to PACIFIC" per the paper's own framing);
`ev-oncology-katsarolis-2026-greek-realworld-os-001` (a large
684-patient real-world Greek cohort: immunotherapy at any line vs
chemotherapy alone, OS 17.5 vs 8.6 months, HR 0.51 [0.42-0.61]); and
`ev-oncology-liao-2026-icpscore-predictive-biomarker-001` (a novel
9-gene predictive biomarker derived from the phase 3 ORIENT-11 trial:
high-ICPscore patients benefit substantially from ICI plus
chemotherapy -- PFS HR 0.15 [0.07-0.32], OS HR 0.32 [0.15-0.67] -- while
low-ICPscore patients show no significant benefit -- PFS HR 0.90
[0.55-1.46], OS HR 1.31 [0.81-2.12] -- included per this project's
established precedent of counting biomarker studies with real
treatment-outcome data, distinct from mechanism-only biomarker studies
excluded elsewhere in this corpus). `evidence_records.jsonl` now holds
1,528 records (1,521 draft + 7 reviewed). `ke graph-build` processed
the 3 new records: graph totals now 1,682 claims, 111 concepts (67
mesh, 44 rxnorm), 1,604 claim-concept edges. Same
same-session-self-audit caveat applies to all seven reviewed records.

**Reviewed-evidence-layer growth (2026-08-09, same day): 3 more
hand-authored records (10 total).** Added three more manually-authored,
source-audited Evidence Records: `ev-oncology-weber-2026-nic-vs-pc-realworld-001`
(a real-world head-to-head German cohort comparing nivolumab+
ipilimumab+chemo vs pembrolizumab+chemo -- no significant OS
difference, 13.6 vs 14.1 months, but differing adverse-event profiles
by regimen); `ev-oncology-machado-2026-pembrolizumab-realworld-meta-001`
(a systematic review/meta-analysis of 12 real-world cohorts, 17,506
patients, first-line pembrolizumab in PD-L1>=50% NSCLC -- pooled mean
OS 21.0 months, 60-month OS rate 29.0%, durability data not otherwise
represented in this corpus); and
`ev-oncology-selke-2026-durvalumab-pdl1-subgroup-001` (a real-world
PD-L1-stratified cohort showing durvalumab consolidation's benefit is
concentrated in PD-L1-positive patients -- median OS 27.3 vs 15.1
months with vs without durvalumab in PD-L1+ patients, p=0.043 --
complementing the Stuschke CRISP-registry record's pooled,
non-stratified population). `evidence_records.jsonl` now holds 1,531
records (1,521 draft + 10 reviewed). `ke graph-build` processed the 3
new records: graph totals now 1,685 claims, 111 concepts (67 mesh, 44
rxnorm), 1,608 claim-concept edges. Same same-session-self-audit
caveat applies to all ten reviewed records.

**Reviewed-evidence-layer growth (2026-08-09, same day): 3 more
hand-authored records (13 total).** Added three more manually-authored,
source-audited Evidence Records: `ev-oncology-wu-2026-liver-mets-network-meta-pfs-os-001`
(a Bayesian network meta-analysis of 20 RCTs in driver-gene-negative
NSCLC with liver metastases: PD-1 inhibitor plus chemotherapy improved
PFS, HR 0.572 [0.435-0.754], and OS, HR 0.681 [0.559-0.830], versus
chemotherapy alone, with camrelizumab plus chemotherapy ranking
highest by SUCRA -- diversifying this corpus's population coverage to
a poor-prognosis metastatic site);
`ev-oncology-mao-2026-pd1-vegf-antibody-meta-pfs-os-001` (a
meta-analysis of 11 RCTs, 4,426 patients: antibody-based regimens
combining PD-1/PD-L1 inhibition with VEGF/VEGFR-targeting antibodies
improved PFS, HR 0.65 [0.57-0.75], and OS, HR 0.79 [0.71-0.87], versus
control regimens, with favorable subgroup estimates in liver
metastases, high PD-L1 expression, and EGFR-mutant patients); and
`ev-oncology-esen-2026-induction-chemoimmunotherapy-realworld-001` (a
small 34-patient real-world cohort of induction chemoimmunotherapy
followed by consolidative hypofractionated radiotherapy in
unresectable locally advanced NSCLC: 1- and 2-year OS 86%/81%, PFS
76%/54%, with favorable locoregional control and acceptable toxicity
-- included as real-world feasibility evidence, explicitly flagged as
weaker than this corpus's RCT/meta-analysis records given its small,
uncontrolled, single-arm design). `evidence_records.jsonl` now holds
1,534 records (1,521 draft + 13 reviewed). `ke graph-build` processed
the 3 new records: graph totals now 1,697 claims, 115 concepts (68
mesh, 47 rxnorm), 1,623 claim-concept edges. Same
same-session-self-audit caveat applies to all thirteen reviewed
records.

**Relationship graph: first 5 edges authored (2026-08-09).** This
corpus previously had no `relationship_records.jsonl` at all --
`ke graph-relationship-candidates` output for the reviewed tier was
read directly and reasoned about by hand (not via automated matching,
which is dominated by noise from same-paper automated-tier fragment
pairs), mirroring the discipline already used for the GLP-1 corpus's
graph. Authored 5 real relationships among the 13 reviewed records:
Selke's PD-L1-stratified durvalumab-consolidation cohort qualifies
Stuschke's whole-population durvalumab-consolidation finding;
Katsarolis's real-world Greek cohort supports Dang's pooled-RCT
ICI-plus-chemotherapy-vs-chemotherapy-alone OS finding; Liao's
ICPscore biomarker analysis qualifies that same Dang finding by
showing it doesn't hold in the low-ICPscore subgroup; Wu's liver-
metastasis network meta-analysis contextualizes it by extending the
same comparison into a harder-to-treat subgroup; and Machado's
pembrolizumab real-world meta-analysis supports Nodbrant's ECOG-
performance-status survival finding. All 5 passed
`ke relationship-validate` and are now in the graph (22 relationship
edges corpus-wide, up from 17 before this corpus had any).

**Relationship graph: 3 more edges authored (2026-08-09, same day).**
Re-read all 13 reviewed records exhaustively (not just the pairs the
first pass already used) for any further genuine relationships: found
3 more. Gandara's composite patient-reported-outcome risk score
contextualizes Liao's genomic ICPscore -- both show a composite
baseline score meaningfully stratifies OS on checkpoint-inhibitor
therapy, in different measurement domains (PRO vs. genomic). Esen's
induction-chemoimmunotherapy-before-radiotherapy cohort contextualizes
Stuschke's standard durvalumab-consolidation-after-chemoradiotherapy
cohort -- an alternative treatment sequencing in a similar
unresectable/locally-advanced disease-stage population. Mao's PD-1/
VEGF-antibody meta-analysis supports Wu's dedicated liver-metastasis
network meta-analysis -- both independently find checkpoint-inhibitor-
based combination therapy retains real benefit in the liver-metastasis
subgroup, via different combination partners (VEGF-targeting antibody
vs. chemotherapy). All 3 passed `ke relationship-validate`. Corpus
relationship graph is now 8 edges (was 5); graph-wide total is 30 (was
27).

**First golden evidence map: provisional (2026-08-10).**
`golden_evidence_map.json` now exists, organizing all 13 manually-
reviewed records and all 8 relationship edges into population/
comparator groupings and a bounded contradiction assessment (none
identified). Passes `ke evidence-map-validate`. Unlike the GLP-1
golden map, this one is honestly `map_status: "provisional"` --
compiled in a single AI-assisted session from the corpus's own
already-manually-reviewed records, not independently re-audited
against source PDFs by a second reviewer the way GLP-1's map was. See
the map's own `review`/`known_gaps` fields for exactly what independent
audit work remains before it could move to `"reviewed"`.

**Relationship graph: 1 more edge closing a connectivity gap
(2026-08-10).** The golden map's own `limitations` field flagged that
2 of the 13 reviewed records (Tsuboi, Weber) had zero relationship
edges. A direct `evidence_nodes`-vs-`relationship_ids` connectivity
check confirmed this. Authored one new relationship: Tsuboi's
randomized KEYNOTE-671 stage-II subgroup (EFS HR 0.50, significant;
OS HR 0.69, directionally favorable but not independently significant)
qualifies Dang's pooled-RCT advanced-disease OS finding -- it extends
the same ICI-plus-chemotherapy intervention to a resectable,
perioperative population, without contradicting Dang's result, since
EFS and pathologic response are the clearly significant endpoints in
this subgroup while OS remains underpowered rather than reversed.
Weber was deliberately left unconnected: its nivolumab+ipilimumab-vs-
pembrolizumab active-comparator finding doesn't cleanly map onto any
other node's actual comparison axis, and forcing a relationship there
would not meet this project's own "human judgment, not automated
matching, and exclude conservatively when uncertain" discipline. Passed
`ke relationship-validate` and `ke evidence-map-validate`. Corpus
relationship graph is now 9 edges (was 8); graph-wide total is 42
(was 41).

**Record-fidelity check against source PDFs (2026-08-10, same day).**
The golden map's own `known_gaps` named an independent source-by-source
audit, matching GLP-1's, as the next step toward `"reviewed"` status.
Performed the record-to-source half of that check: read the extracted
source-PDF page text at each of the 13 records' own
`source_span.page_number` and cross-checked every `claim_text`/
`result_summary` numerical figure (hazard ratios, confidence intervals,
p-values, sample sizes) against it, and read all 9 relationship
rationales for scientific coherence. Result: all 13 records faithfully
represent their sources, and all 9 relationships are scientifically
sound and conservatively typed (`qualifies`/`contextualizes` used
rather than an overreaching `supports` wherever a population,
regimen, or measurement-domain difference existed). Two specific,
non-error findings: Liao's source PDF itself shows a likely internal
typo in one confidence interval (its running prose and its own figure
legend render the same number two different ways; the record correctly
used the figure-legend value), and Nodbrant's cited CI/n/mortality
figures live in a table that did not extract as machine-readable text,
so only its three headline median-OS figures were independently
re-confirmed. This check was performed by the same AI system (Claude)
that compiled the map, not a genuinely independent reviewer the way
GLP-1's audit used a different AI system (OpenAI Codex) -- so
`map_status` stays `"provisional"` and `review.status` stays
`"secondary_review_required"`. A genuinely independent (human or
different-AI-system) pass remains the one thing standing between this
map and GLP-1's `"reviewed"` bar. See the map's `review`/`limitations`/
`known_gaps` fields for the full detail.
