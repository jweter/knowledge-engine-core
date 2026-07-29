# M38 Phase 2 Extraction Scale-Readiness Assessment

## Purpose

`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
named an explicit, never-executed prerequisite: M16-M28's deterministic
extraction rules (structured-section detection, claim-candidate signals,
study-type classification, limitations, PICO) were built and unit-tested
against synthetic fixtures, and exercised by hand against individual real
papers via `ke extraction-review-generate`, but detection coverage had never
been measured in aggregate across the real corpus at scale -- exactly the
kind of pattern a 500-paper sample was expected not to reveal. That
prerequisite (a real corpus large enough to show it) is now met at 943
papers. `knowledge_engine/extraction_corpus_report.py` and
`scripts/m38_extraction_corpus_report.py` run the same deterministic
pipeline across every persisted paper and report coverage counts --
read-only, no draft items written, no extraction runs recorded, no
`EvidenceRecord` rows produced.

## Decision

The deterministic extraction pipeline is usable at this corpus's current
scale as-is: it degrades safely (a missing signal is `None`/empty, never a
guessed value), and its coverage gaps are explainable rather than random.
No emergency fix was required. Two concrete, well-diagnosed recall gaps are
documented below; both interact with corpus-inclusion-philosophy-adjacent
tradeoffs (how aggressively to relax section-heading matching, and whether
to broaden the closed-vocabulary study-type list) that this project reserves
for explicit owner decision, the same way `evaluate_scientific_scope`'s
documented ruleset weakness was flagged rather than unilaterally changed --
the project owner has since reviewed and authorized fixing both; see
"Resolved follow-up" below for what changed and the resulting numbers.

## Evidence (943 papers, all with persisted pages)

| Signal | Papers with coverage | Rate |
| --- | --- | --- |
| Any section detected | 940 / 943 | 99.7% |
| Results section detected | 595 / 943 | 63.1% |
| Conclusion section detected | 607 / 943 | 64.4% |
| At least 1 claim candidate | 596 / 943 | 63.2% |
| Study type classified | 383 / 943 | 40.6% |
| Limitations detected | 112 / 943 | 11.9% |
| PICO: population | 425 / 943 | 45.1% |
| PICO: intervention | 563 / 943 | 59.7% |
| PICO: comparator | 695 / 943 | 73.7% |
| PICO: outcome | 533 / 943 | 56.5% |
| PICO: all four fields | 220 / 943 | 23.3% |

Section-type detection breakdown (any occurrence per paper):
`abstract` 643, `introduction` 743, `methods` 602, `results` 595,
`discussion` 657, `limitations` 115, `conclusion` 607, `references` 929.

## Root-cause analysis: the 347 zero-claim-candidate papers

`detect_claim_candidates` only scans `results`/`conclusion`-type sections
(M17's deliberate scoping, to avoid pulling background claims from the
Introduction or Discussion). Splitting the 347 zero-candidate papers by
whether a `results` or `conclusion` section was even detected:

- **196 (56%)** have neither a `results` nor a `conclusion` section
  detected at all -- claim-candidate detection cannot run because its
  input section types don't exist for these papers. A sample check found
  these are disproportionately narrative reviews and mechanism papers
  (e.g. `PMC12758192.pdf`, "Gut-heart axis: emerging therapies targeting
  trimethylamine N-oxide production", a review synthesizing others' findings
  rather than reporting the paper's own quantitative results under a
  `Results` heading) -- a real absence, not a detection failure, for at
  least some of this group.
- **151 (44%)** *do* have a `results` or `conclusion` section detected, but
  still produce zero candidates -- a genuine recall gap. Traced one
  concretely: `PMC13366639.pdf` ("Efficacy and safety of SGLT2 inhibitors in
  elderly patients with type 2 diabetes") contains, in its own body text,
  `"reduced risk of 30% eGFR decline (HR 0.69, 95% CI 0.59-0.80, p < 0.001)"`
  -- a textbook match for the `confidence_interval`/`p_value` signal
  patterns. `detect_sections` never recognizes this text as its own
  `results` span, because the PDF's extracted text renders `"Results:"` as
  an inline label at the start of a paragraph (`"Results: SGLT2 inhibitor
  use was associated with..."`) rather than as a standalone heading line --
  `_SECTION_HEADING_PATTERNS["results"]` requires a full trimmed line
  matching `^\s*results\s*$`, by design (M16's own docstring: "missing a
  section is safe, mislabeling one is not"). The quantitative content ends
  up folded into this paper's `discussion` span instead, which
  `detect_claim_candidates` never scans. This is a structured-discussion or
  structured-abstract-style layout pattern (label-and-colon inline with
  body text, not a separate heading line) that M16's conservative
  full-line-only heading match was never designed to catch -- an accepted,
  documented tradeoff at the time (recall loss over mislabeling risk), now
  concretely observed at scale rather than theorized.

## Root-cause note: study-type coverage (40.6%)

`classify_study_type`'s pattern list is a closed vocabulary of 8 named
designs (meta-analysis, systematic review, RCT, cohort, case-control,
cross-sectional, pilot, observational). The 59.4% "none" rate is expected
given that vocabulary's size relative to this corpus's actual diversity --
narrative reviews, case reports/series, animal/in-vitro mechanism studies,
retrospective analyses not phrased as "cohort study," and cross-over trials
all commonly appear in this corpus (per the README's own documented
false-positive/inclusion history) and none of them match any of the 8
patterns. Not a bug -- this is a real, honest limit of a closed-vocabulary
classifier, sized to the study designs M26 was originally tuned against.

## What this does not do

This assessment does not promote anything to `EvidenceRecord`, does not
change any extraction rule, and does not re-run `ke extraction-review-*`
against any of these 943 papers. It measures coverage; it does not act on
what it measured. Whether to relax `detect_sections`'s heading-matching
strictness (accepting some mislabeling risk for better recall), broaden
`classify_study_type`'s vocabulary, or leave both as documented, honest
limitations is the project owner's call -- flagged here, not decided here.

## Resolved follow-up: both flagged gaps fixed

The project owner authorized fixing both gaps above. Three rule changes were
made, each with its own version bump for provenance:

- **`SECTION_DETECTION_RULES_VERSION` v1 -> v2**: a heading now matches
  either alone on its own line (the original v1 behavior) or immediately
  followed by a colon and further text on the *same* line (e.g. `"Results:
  SGLT2 inhibitor use was associated with..."`), closing the exact
  `PMC13366639.pdf`-style gap diagnosed above. The colon requirement keeps
  this narrow: `"results"` mid-sentence, or a combined heading like `"Results
  and Discussion"`, still matches neither alternative.
- **`STUDY_DESIGN_RULES_VERSION` v1 -> v2**: added `narrative_review`,
  `cross_over_trial`, `retrospective_study`, `case_series`, and
  `case_report` to the closed vocabulary, ordered so the existing
  more-specific patterns still win (`narrative_review`/`cross_over_trial`
  checked before `randomized_controlled_trial` so a review discussing RCTs,
  or a crossover trial's own "randomized...crossover trial" phrasing, isn't
  misclassified as a plain RCT; `retrospective_study` checked after
  `cohort_study` so "retrospective cohort study" still matches the
  more-specific pattern).
- **`PICO_EXTRACTION_RULES_VERSION` v1 -> v2 (an unplanned but necessary
  third fix)**: re-running the M38 report after the section-detection fix
  alone showed every PICO field's coverage *regressed* -- population
  425->364, intervention 563->510, comparator 695->665, outcome 533->503,
  all-four 220->184. Root cause: a structured abstract's inline
  `"Background: ... Methods: ... Results: ... Conclusion: ..."` layout used
  to stay one undivided `abstract` span, which every PICO field already
  scanned; the section-detection fix now correctly splits it into separate
  `methods`/`results`/`conclusion` spans, orphaning cues in section types
  PICO's original scoping never covered. Fixed by widening scoping
  (population/intervention now also scan `results`; comparator/outcome now
  also scan `conclusion`) to restore that reachability without loosening the
  cue patterns themselves.

### Evidence after the fix (same 943 papers)

| Signal | Before (v1) | After (v2) |
| --- | --- | --- |
| Any section detected | 940 / 943 (99.7%) | 942 / 943 (99.9%) |
| Results section detected | 595 / 943 (63.1%) | 683 / 943 (72.4%) |
| Conclusion section detected | 607 / 943 (64.4%) | 713 / 943 (75.6%) |
| At least 1 claim candidate | 596 / 943 (63.2%) | 679 / 943 (72.0%) |
| Study type classified | 383 / 943 (40.6%) | 412 / 943 (43.7%) |
| Limitations detected | 112 / 943 (11.9%) | 115 / 943 (12.2%) |
| PICO: population | 425 / 943 (45.1%) | 494 / 943 (52.4%) |
| PICO: intervention | 563 / 943 (59.7%) | 590 / 943 (62.6%) |
| PICO: comparator | 695 / 943 (73.7%) | 711 / 943 (75.4%) |
| PICO: outcome | 533 / 943 (56.5%) | 544 / 943 (57.7%) |
| PICO: all four fields | 220 / 943 (23.3%) | 247 / 943 (26.2%) |

Every signal improved or held steady -- including PICO, once the scoping fix
offset the section-detection fix's side effect. New study-type breakdown:
`meta_analysis` 96, `cohort_study` 89, `cross_sectional_study` 50,
`randomized_controlled_trial` 47, `systematic_review` 39, `retrospective_study`
20, `narrative_review` 18, `observational_study` 17, `pilot_study` 15,
`case_report` 13, `case_series` 4, `cross_over_trial` 3, `case_control_study`
1, `none` 531 (56.3%, down from 59.4%).

No rule change here promotes anything to `EvidenceRecord` or re-runs `ke
extraction-review-*`; this remains a read-only measurement pass, now against
an updated ruleset.
