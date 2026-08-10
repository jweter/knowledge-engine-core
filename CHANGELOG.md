# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`ke corpus-library-import` raised a raw `OperationalError` traceback,
  not an actionable message, when the committed snapshot predates the
  current database schema.** Confirmed as a real incident: the
  committed `data/corpus_library/obesity_metabolic_disease_library.sqlite3.gz`
  was exported before `paper_pages.table_text` existed, silently
  stalling `knowledge-engine-web`'s automated weekly
  alpha-snapshot-refresh Routine with no visible cause. Now catches
  `OperationalError`/`"no such column"` and tells the operator
  precisely what happened and the fix (`ke corpus-library-export
  --output <path>` from a fully-migrated database, then re-commit) --
  there is no automatic schema upgrade for a snapshot *file* itself,
  only for the local database `ke init` builds. Also regenerated the
  stale snapshot itself from the current, fully-migrated local database
  (1,357 papers across all 3 corpora, schema version 11) and verified
  the fix with a real round-trip against the new file: `ke
  corpus-library-import` into a fresh database succeeded, and `ke
  evidence-report` against the freshly-hydrated database returned real
  results.

### Added

- Ran the second weekly discovery cycle (`ke discovery-cycle-run`,
  `retstart=3600`) against the persisted `discovery_state.json`: 50
  candidates discovered, 21 deterministically accepted, 0 already in
  the ledger. The manual scope screen found the same pagination-drift
  failure mode the `retstart=3550` cycle first caught, this time even
  more pronounced: cross-checking every accepted PMID against
  `sources.csv` found 20 of the 21 were exact-title/PMID duplicates
  already present in the corpus (PubMed's `sort=pub_date` ordering
  shifting the same already-included records to `retstart=3600`). The
  remaining 1 was genuinely net-new but off-target (a *Mycolicibacterium
  neoaurum* pulmonary-infection case report naming no
  obesity/T2D/metabolic-syndrome scope term or treatment). All 21
  recorded in `rejected_candidates.csv` with PMID-level provenance (20
  `duplicate_or_already_included`, 1 `off_target_primary_disease`).
  Zero net-new papers accepted; corpus remains at 953, 47 below the
  1,000-paper cap. `discovery_state.json` advanced to `next_retstart:
  3650` for the next cycle. See the corpus README's `retstart=3600`
  batch-history entry.

- **First golden evidence maps for the oncology and mental-health
  corpora.** `data/corpora/oncology_nsclc_checkpoint_inhibitors/golden_evidence_map.json`
  (13 manually-reviewed records, 8 relationship edges) and
  `data/corpora/mental_health_mdd_antidepressants/golden_evidence_map.json`
  (9 records, 7 edges) organize each corpus's already-manually-reviewed
  Evidence Records and Relationship Records into population/comparator
  groupings and a bounded contradiction assessment (none identified in
  either -- oncology's Weber active-comparator null and mental-health's
  Ju null augmentation result are both real negative findings that
  qualify a narrower question, not same-PICO contradictions of either
  corpus's core research question). Both pass `ke evidence-map-validate`
  and render via `ke evidence-map-report`. Honestly `map_status:
  "provisional"`, not `"reviewed"` like GLP-1's golden map -- each was
  compiled in a single AI-assisted session from already-reviewed
  records, not independently re-audited against source PDFs by a second
  reviewer the way GLP-1's map was; each map's own `review`/`known_gaps`
  fields state exactly what that follow-up audit would need to cover.

- **Closed a connectivity gap the oncology golden map's own
  `limitations` field flagged: 1 new relationship edge.** A direct
  `evidence_nodes`-vs-`relationship_ids` connectivity check confirmed 2
  of the 13 reviewed records (Tsuboi, Weber) had zero relationship
  edges. Authored `rel-onc-tsuboi-qualifies-dang-perioperative-os-001`:
  Tsuboi's randomized KEYNOTE-671 stage-II subgroup (EFS HR 0.50,
  significant; OS HR 0.69, directionally favorable but not
  independently significant) qualifies Dang's pooled-RCT advanced-
  disease OS finding, extending the same intervention to a resectable,
  perioperative population without contradicting it. Weber was
  deliberately left unconnected -- its active-comparator finding
  doesn't cleanly map onto any other node's comparison axis, and this
  project's discipline is to exclude conservatively rather than force a
  weak match. Passed `ke relationship-validate` and `ke
  evidence-map-validate`. Corpus relationship graph 8 -> 9 edges,
  graph-wide 41 -> 42.

- **Investigated `detect_sections`' 114-of-1,357-paper "no Abstract/
  Methods section detected at all" gap; found and documented it is not
  a narrow regex fix.** 79% (90/114) have no "abstract" text anywhere
  in their extracted first two pages at all -- reading real examples
  (Frontiers-journal papers) confirmed the abstract paragraph itself
  is present and readable, but the "Abstract" heading label was never
  captured by PDF text extraction (a styled/graphic label, not
  extractable text) -- a parser-level limitation, not a `sections.py`
  pattern-matching gap. Remainder: Cell Press "Graphical abstract"
  layouts (6), non-Latin-script papers (3), and case
  reports/correspondence where a missing Methods section is often the
  structurally correct outcome (9-13). No fix was made; a position-
  based heuristic was considered and rejected as violating the
  module's own explicit "missing is safe, mislabeling is not"
  principle. See `docs/roadmap.md`'s M65 section's third same-day
  addendum for the full breakdown.

- **5 more relationship-graph edges across oncology and mental-health,
  from exhaustively re-reading the same reviewed-record sets.**
  Oncology: Gandara contextualizes Liao (composite PRO score vs.
  genomic biomarker, both stratifying OS on ICI therapy); Esen
  contextualizes Stuschke (alternative induction-before-RT sequencing
  vs. standard post-CRT consolidation); Mao supports Wu (liver-
  metastasis subgroup benefit corroborated across two different
  combination strategies). Oncology graph: 5 -> 8 edges. Mental
  health: Zandifar supports Schmidt (two independent successful
  augmentation strategies); Baradaran supports Yan (escitalopram
  efficacy generalizes across two different comorbid populations).
  Mental health graph: 5 -> 7 edges. Graph-wide total: 27 -> 32. All
  pass `ke relationship-validate`; re-split into `data/db_parts` and
  hash-verified.

- **First relationship-graph edges for the oncology and mental-health
  corpora.** Both previously had zero `relationship_records.jsonl`
  entries -- only GLP-1 had a relationship graph. Read each corpus's
  manually-reviewed evidence records directly (13 for oncology, 9 for
  mental health) and authored 5 real `supports`/`qualifies`/
  `contextualizes` relationships per corpus by hand, the same
  discipline used for GLP-1's graph, rather than relying on the
  automated candidate list (which is dominated by noise from
  same-paper automated-tier fragment pairs at this corpus's scale).
  All 10 pass `ke relationship-validate`. Graph totals: oncology 17 ->
  22 relationship edges, mental health 22 -> 27. Documented in each
  corpus's `README.md`.

- **License/attribution review across all three corpora, closing the
  final `v1.0.0` release gate.** `ke corpus-validate` now re-checks
  every `approved_open_access` row's `license_type` against
  `knowledge_engine.license_rules.evaluate_license` (only unrestricted
  `CC BY`/`CC0` bases pass), not just field presence -- this is a
  permanent, re-run-every-time check, not a one-off manual audit. It
  caught 4 real rows in `glp1_weight_loss/sources.csv` recorded as
  `CC-BY` (hyphenated) instead of `CC BY`; confirmed harmless via each
  row's own notes (real CC BY 4.0 sources, cosmetic typo only) and
  fixed. Also fixed the same latent typo in four test fixtures' "valid
  row" defaults. Corrected all three corpora's `license_policy.md`,
  which described a stale prose usage-note vocabulary that never
  matched the actual enforced `usage_status`/`license_type` schema.
  Verified 100% of evidence records' `source_doi` resolves to a real
  `sources.csv` row across all three corpora (1,824 records total),
  confirming citation-level attribution is traceable project-wide, not
  just for manually-reviewed records. 2 new regression tests in
  `tests/test_corpus_manifest.py`. See `docs/roadmap.md`'s 2026-08-09
  addendum to the `v1.0.0` release-gate section for full findings.

- **GLP-1 Statistical Verification Readiness Gate: re-run confirms
  `not_ready_for_pooling_design` is unchanged, and a targeted OA search
  for newer candidate trials found none.** Re-ran `ke
  statistical-readiness-report`; the verdict and both blockers (STEP
  5-vs-SELECT estimand/timepoint mismatch for continuous pooling; only 1
  of 2+ required binary inputs) are identical to the prior
  2026-08-09 source audit in `docs/glp1_statistical_readiness_gate_plan.md`.
  Extended that audit to two 2026 phase 3b trials not previously
  checked -- STEP UP (PMID 40961952) and STEP UP T2D (PMID 40961953) --
  via `ke pubmed-candidate-discover`; both are closed-access (`Lancet`,
  no PMCID), consistent with every other primary STEP-program result
  paper. Confirms the structural closed-access blocker still holds
  against the newest trials in this drug class; no new gap, no new
  lead, no code change needed. Documented as an addendum in
  `docs/glp1_statistical_readiness_gate_plan.md` rather than a new doc.

- **`ke evidence-validate`: `study_type` now has an enum check.**
  Mirrors the `evidence_direction`/`extraction_status` pattern. Adds
  `ALLOWED_STUDY_TYPES`, the exact set of 19 values verified live in
  use across all three corpora's `evidence_records.jsonl`. Does not
  reopen `docs/roadmap.md`'s already-settled "M65's `study_type`
  vocabulary-granularity question is resolved" decision (near-
  duplicate-looking pairs like `meta_analysis`/
  `systematic_review_meta_analysis` were investigated by reading real
  source text, not just comparing labels, and found not to be a
  uniform naming alias) -- only prevents a *new* typo'd value from
  being introduced going forward. `study_type: null` continues to
  validate cleanly, matching all 639 existing records that legitimately
  carry it. Quantified and cross-referenced that same still-open
  coverage gap with today's exact numbers in `docs/roadmap.md` (39% of
  oncology's `m52-evidence-classification-v1` tier, 594/1,521 records,
  missing `study_type` entirely; every manually-authored record across
  all three corpora is 100% populated) -- confirmed, not guess-filled,
  per this project's established never-guess extraction discipline.
  6 new tests in `test_cli.py`.

- **`tools/detect_non_primary_article.py`: post-acquisition
  non-primary-article-type detector.** Closes a real gap title-only
  screening cannot: "PACIFIC-5 Trial: Refining Patient Selection for
  Consolidation Durvalumab in Unresectable Stage III NSCLC" reads
  exactly like a primary trial report and carries no title-level
  marker at all -- it was a commentary/letter, caught only by reading
  the downloaded PDF's own page-1 "COMMENTARY" label directly. This
  tool checks that same printed, already-published label
  deterministically: a standalone ALL-CAPS article-type line
  (COMMENTARY, EDITORIAL, LETTER, CORRESPONDENCE, PERSPECTIVE,
  VIEWPOINT, NEWS, ERRATUM, RETRACTION, CORRECTION) within the first
  15 lines of page 1, or the "To the Editor,"/"Dear Editor," body-text
  opening convention -- never a guess from prose content, and
  deliberately excludes ambiguous labels (e.g. "Research Letter") that
  sometimes carry real primary data. Retroactively run against all 35
  distinct source PDFs across the three corpora's currently-reviewed
  Evidence Records (13 GLP-1 + 13 oncology + 9 mental-health): no
  contamination found. 9 new tests in
  `tests/tools/test_detect_non_primary_article.py`, including one
  proving a marker word embedded in ordinary prose (not a standalone
  label line) is correctly not flagged.

### Fixed

- **`classify_study_type`: fixed a real precedence false-positive and
  narrowed a real coverage gap, both measured against the live
  1,357-paper corpus.** `meta_analysis`/`systematic_review` (checked
  first, deliberately) had no guard against a paper merely *citing*
  another paper's meta-analysis or *explicitly denying* it performed
  one -- real examples: paper 151 ("no quantitative synthesis,
  meta-analysis... was performed"), paper 220 ("Rather than aiming to
  perform an exhaustive systematic review or meta-analysis, we sought
  to..."), paper 409 (a narrative review citing a different paper's
  meta-analysis), and paper 141 (explicitly denies a meta-analysis but
  is a genuine systematic review) were all misclassified before this
  fix. A new `_describes_own_design` guard rejects a pattern's first
  match when preceded by an explicit negation or prior/other-work cue,
  letting classification correctly fall through to the true design or
  to `None`. Separately, `retrospective_study`'s pattern was widened
  to match the common real phrasing "retrospective chart review"
  (papers 51, 959), narrowing the has-Abstract/Methods-but-no-match
  count from 627 to 619 of 1,357 papers. `STUDY_DESIGN_RULES_VERSION`
  bumped to `m26-study-design-v5`. 6 new regression tests in
  `tests/test_extraction_study_design.py`, each reproducing a real
  paper's exact phrasing. A known, documented residual gap (a citation
  with no negation/prior-work cue word at all nearby) is left for a
  future pass rather than guessed at. See `docs/roadmap.md`'s
  2026-08-09 addendum to the M65 section.

- **PDF author-metadata parsing: degree credentials no longer produce
  duplicate-author `IntegrityError`s.** Some publishers' embedded PDF
  "Author" metadata lists each name followed by its own degree credential
  ("Jane Doe, PhD, John Smith, PhD, ..."), indistinguishable from a name
  boundary by `_extract_authors`'s comma-only split. When the same
  credential (e.g. "PhD") repeats for multiple co-authors, the resulting
  pseudo-author got linked to the paper twice, violating
  `paper_authors`' `(paper_id, author_id)` uniqueness and aborting the
  entire multi-paper import batch -- found live against a real CAN-BIND
  consortium paper. `knowledge_engine/parser.py` now filters exact-match
  degree/credential tokens out of the split author list.
  `knowledge_engine/database.py`'s `_build_paper` also gained a
  defense-in-depth guard: a repeated author for the same paper (any
  cause) is now linked once, not raised as a fatal `IntegrityError`.
- **`ke evidence-validate`: `evidence_direction` now has an enum
  check.** Previously only checked for "is a non-empty string" --
  `extraction_status` had an `ALLOWED_EXTRACTION_STATUSES` allowlist,
  `evidence_direction` had no equivalent. Found live this session: a
  genuine typo (`"refutes"` instead of `"contradicts"`) while authoring
  a real negative-result Evidence Record would have passed validation
  silently, caught only by manually grepping the codebase rather than
  by the tool. Added `ALLOWED_EVIDENCE_DIRECTIONS = {"supports",
  "contradicts", "qualifies", "contextualizes"}` (the real values in
  use across all three corpora's evidence_records.jsonl) and a check
  in `_validate_evidence_record` mirroring the existing
  `extraction_status` pattern exactly. Two new tests in `test_cli.py`:
  one proving `"refutes"` is now rejected, one parametrized over all
  four real values proving they're still accepted.
- **`tools/discovery_scope_prescreen.py`: oncology corpus rule set
  added.** `CORPUS_RULE_SETS` previously had exactly one registered
  entry (mental-health) -- oncology, where a real commentary/letter
  near-miss was caught this session, had zero deterministic
  scope-prescreen coverage. Adds `ONCOLOGY_NSCLC_CHECKPOINT_INHIBITORS`,
  grounded in the corpus's own `inclusion_criteria.md`/
  `exclusion_criteria.md` and `knowledge_engine.scientific_scope`'s
  already-established named-agent vocabulary (pembrolizumab,
  nivolumab, atezolizumab, durvalumab, cemiplimab). Adds two
  oncology-specific hard-exclude rules beyond mental-health's set:
  `pediatric_population` and `mechanism_only`, both directly grounded
  in `exclusion_criteria.md`'s own language, plus `non_primary_content`
  for titles that literally say "commentary"/"editorial"/"letter to
  the editor" -- explicitly documented as *not* sufficient on its own
  (a real test proves the actual PACIFIC-5 near-miss title, which
  carries no title-level marker, still scores `likely_include` here;
  catching that class of case is the separate, post-acquisition
  article-type check). Fixed a real regex bug found while writing this
  rule set: `\bpd.1\b`/`\bpd.l1\b` required exactly one separator
  character and so never matched bare "PD1"/"PDL1" (no hyphen/space);
  changed to `\bpd.?1\b`/`\bpd.?l1\b`. Validated against all 336 real
  titles in oncology's `sources.csv`: no regex false positives found
  (title-level `likely_exclude` verdicts on real included papers all
  trace to genuine abstract-vs-title co-occurrence gaps, the same
  documented pattern as mental-health's tool, or to a genuinely
  different cancer type (SCLC) this corpus's own criteria exclude, not
  to a rule defect). 11 new tests in
  `tests/tools/test_discovery_scope_prescreen.py`.

### Added

- **Mental health corpus: automated draft-evidence layer bootstrapped,
  0 -> 124 draft records.** Closes a structural gap: unlike GLP-1 and
  oncology, this corpus had never been run through the M40/M52
  automated extraction pipeline, so its evidence layer was 100%
  hand-authored with no bulk draft layer underneath. Ran `ke
  extraction-review-batch-generate` against all 62 persisted papers
  (865 candidate items), `ke extraction-review-autoclassify` (M52's
  deterministic classifier), then `ke extraction-review-promote`: 124
  items were eligible (14.3%, in line with oncology's own M52
  eligibility rate), the rest skipped -- never guessed -- for a
  missing/overlong PICO field or missing claim_text/result_summary.
  All 124 are `extraction_method: "m52-evidence-classification-v1"`,
  `review_status: "draft"`, matching the other two corpora's existing
  draft-layer discipline exactly. Graph totals after this batch: 119
  concepts (70 mesh, 49 rxnorm), 1,821 claims, 1,779 claim-concept
  edges.
- **Oncology corpus: reviewed-evidence layer grown, 10 -> 13
  records.** `ev-oncology-wu-2026-liver-mets-network-meta-pfs-os-001`
  (Bayesian network meta-analysis of 20 RCTs in driver-gene-negative
  NSCLC with liver metastases: PD-1 inhibitor plus chemotherapy
  improved PFS, HR 0.572 [0.435-0.754], and OS, HR 0.681
  [0.559-0.830], versus chemotherapy alone);
  `ev-oncology-mao-2026-pd1-vegf-antibody-meta-pfs-os-001`
  (meta-analysis of 11 RCTs, 4,426 patients: PD-1/PD-L1-plus-VEGF/
  VEGFR-antibody regimens improved PFS, HR 0.65 [0.57-0.75], and OS,
  HR 0.79 [0.71-0.87], versus control regimens);
  `ev-oncology-esen-2026-induction-chemoimmunotherapy-realworld-001`
  (34-patient real-world cohort of induction chemoimmunotherapy plus
  consolidative hypofractionated radiotherapy in unresectable locally
  advanced NSCLC: 1-/2-year OS 86%/81%, PFS 76%/54%, explicitly
  flagged as weaker real-world feasibility evidence given its small,
  uncontrolled, single-arm design). Graph totals after this batch:
  115 concepts (68 mesh, 47 rxnorm), 1,697 claims, 1,623 claim-concept
  edges.
- **Mental health corpus: reviewed-evidence layer grown, 6 -> 9
  records.** `ev-mh-schmidt-2024-aticaprant-adjunctive-ssri-snri-rct-001`
  (phase 2 double-blind RCT of aticaprant, a kappa receptor antagonist,
  added to ongoing SSRI/SNRI treatment: significant MADRS improvement
  versus placebo, full-ITT -3.1 [2.21] 1-sided p=0.002 -- a positive
  augmentation result complementing this corpus's existing null
  agomelatine-augmentation record);
  `ev-mh-zandifar-2024-empagliflozin-adjunctive-citalopram-rct-001`
  (8-week RCT of empagliflozin added to citalopram, n=90: significantly
  greater HDRS improvement over time versus placebo+citalopram,
  p=0.0001); `ev-mh-baradaran-2024-escitalopram-cabg-quality-of-life-rct-001`
  (double-blind RCT of escitalopram vs placebo in 50 coronary-artery-
  bypass-grafting patients with comorbid depression: significantly
  reduced depression scores and improved SF-36 quality of life at 8
  weeks, p<0.001). Graph totals after this batch: 115 concepts (68
  mesh, 47 rxnorm), 1,694 claims, 1,622 claim-concept edges.
- **Mental health corpus: reviewed-evidence layer grown, 3 -> 6
  records, including a deliberate null result.**
  `ev-mh-ju-2025-agomelatine-adjunctive-ssri-snri-rct-001` (8-week
  double-blind placebo-controlled RCT of agomelatine augmentation added
  to ongoing SSRI/SNRI treatment, n=123 non-responders: no significant
  benefit on HAMD-17, remission, or response -- a genuine negative
  result, included deliberately so the reviewed layer isn't
  positive-only); `ev-mh-yan-2024-escitalopram-vs-sertraline-poststroke-rct-001`
  (head-to-head RCT, n=60 post-stroke depression patients: escitalopram
  outperformed sertraline on HAMD-24 reduction, F=4.068 p<0.05, with
  faster onset and fewer adverse effects, though response rate did not
  differ significantly); `ev-mh-kishi-2024-japan-older-adults-meta-001`
  (9-trial, n=2,145 systematic review/meta-analysis of antidepressants
  in older adults with MDD: significantly higher response than
  placebo, RR 1.38 [1.04,1.83], and symptom improvement, SMD -0.62
  [-0.92,-0.33], but also significantly higher discontinuation due to
  adverse events, RR 1.94 [1.30,2.88]). Graph totals after this batch:
  115 concepts (68 mesh, 47 rxnorm), 1,691 claims, 1,617 claim-concept
  edges.
- **Mental health corpus: reviewed-evidence layer bootstrapped, 0 -> 3
  records.** First hand-authored, `manual_source_audit`-discipline
  Evidence Records for this corpus (previously 0 despite 62 real draft
  papers), using the same page-cited, same-session-self-audited
  approach established for the oncology corpus:
  `ev-mh-perez-2025-depre5-second-line-strategies-001` (DEPRE'5, a
  5-arm registered RCT of second-line strategies after SSRI
  non-response, n=257: response 28.2% pooled alternative arms vs 14.3%
  continued/optimized SSRI, OR 2.36 [1.0,5.6] p=0.05; HDRS-17 mean
  difference -2.6 [-4.9,-0.4] p=0.021);
  `ev-mh-yin-2023-escitalopram-vs-other-antidepressants-meta-001` (a
  30-RCT meta-analysis: escitalopram beats citalopram on response, RR
  0.67 [0.50,0.87], and remission, RR 0.53 [0.30,0.93]; no significant
  difference vs. other comparator antidepressants);
  `ev-mh-santi-2024-vilazodone-escitalopram-vortioxetine-rct-001` (a
  3-arm open-label RCT, n=96 per-protocol: comparable baseline severity
  across arms, p=0.964, no statistically significant between-group
  16-week HDRS difference across vilazodone/escitalopram/vortioxetine).
  Graph totals after this batch: 114 concepts (68 mesh, 46 rxnorm),
  1,688 claims, 1,612 claim-concept edges.
- **`docs/roadmap/future_ai_orchestration_plan.md` reconciled against
  the real canonical document.** The full team-authored plan (1,056
  lines) is now available in `knowledge-engine-ai`'s own
  `docs/roadmap/future_ai_orchestration_plan.md` (PR #7 there, pending
  merge at time of writing) -- the earlier download link that this
  repo's reconstruction was drafted from had not resolved. Read
  against the real document: no contradictions found; the real
  document is substantially more complete (full field-level schemas
  for `ResearchPlan`/`ResearchSession`/`ResearchEvent`/
  `EvidenceComparison`/`KnowledgeGap`/`HypothesisCandidate`, a Tool
  Permission Model with 5 consequence levels, a 4-layer verification
  pipeline, an evaluation framework, explicit success criteria per
  `AI-O1`-`AI-O11` milestone, and all 16 named design-risk blocks --
  this repo's earlier reconstruction was missing 2: non-deterministic
  research continuation, and autonomous hypothesis generation
  outrunning evidence quality). This repo's copy of the file is now a
  short pointer to the canonical document rather than a duplicate, to
  avoid two divergent copies of the same plan. Cross-references in
  `docs/ai_layer_architecture.md` and `docs/roadmap.md` updated to
  match.
- **`docs/roadmap/future_ai_orchestration_plan.md`: contract-first
  orchestration design, refining the multi-agent proposal below.**
  Relays a project-owner-authored orchestration plan (the source
  download link was inaccessible; drafted from the owner's detailed
  written relay, with an explicit provenance note and an honest gap
  flag for content not described). Proposes four durable domain
  contracts -- `ResearchPlan`, `ResearchSession`, `ResearchTask`,
  `ResearchEvent` -- executed by pluggable engines (deterministic code,
  local Ollama models, external providers, or any future agent
  framework), so no framework becomes Knowledge Engine's architecture.
  Documents 14 named design risks with mitigations (agent error
  compounding, prompt injection, context-window scaling, corpus bias
  vs. consensus, circular AI graph reasoning, canonical evidence
  mutation, evaluation drift, cost explosion, memory poisoning,
  pseudo-replication, publication bias, framework lock-in, and two
  others), an 11-milestone `AI-O1`-`AI-O11` build order, and the
  Skeptic worker's exact evidentiary-honesty reporting requirement
  ("no aligned contradictory evidence found within the searched
  scope," never "there is no contradictory evidence"). Cross-linked
  from `docs/ai_layer_architecture.md`'s Orchestration section and
  `docs/roadmap.md`'s doc index.
- **`docs/ai_layer_architecture.md`: multi-agent orchestration design
  addition.** Documents a project-owner architecture review's proposed
  worker-role taxonomy (Orchestrator, Query Planner, Discovery/Retrieval
  Workers, Evidence Extractor/Analyst, Contradiction/"Skeptic" Worker,
  Statistical Worker, Source/Citation Auditor, Composer), a mandatory
  (not optional) Skeptic step before synthesis, a persistent
  `ResearchSession` state design, and a local-model cost/latency
  routing ladder. Explicitly reconciles the proposal against this
  project's already-decided doctrine ("one assistant, not several
  bots" stays true -- these are internal workers, never user-facing
  personas) and names what a reference multi-agent OSS project's
  pattern was borrowed from (spawn/fan-in concurrency, durable project
  memory) versus explicitly not adopted (Kubernetes-based agent
  isolation -- solves a different problem than this project has).
  States the real sequencing gate: evidence-base thickness, not
  architecture -- a v0.1 four-component build (Orchestrator/
  Retriever/Skeptic/Composer-Auditor) belongs in `knowledge-engine-ai`
  once a second corpus has real reviewed-evidence and relationship
  density, not before.
- **`tools/discovery_scope_prescreen.py`: deterministic scope-screen
  prescreening prototype.** Scores discovery-cycle candidates
  `likely_include`/`likely_exclude`/`needs_manual_review` against a
  corpus's hand-authored rule set (topic terms, named in-scope agents,
  hard-exclude signals), to speed up -- never replace -- the manual
  title/abstract scope screen this project has always required before
  `ke pmc-oa-acquire`. Ships with a mental-health corpus rule set and
  validated against the real cycle-7/8 worksheet already hand-screened
  this session: 0 dangerous false negatives (nothing actually included
  got mis-flagged as exclude); 3 residual false `likely_include`s on
  genuinely hard semantic cases (mechanism/transporter studies,
  imaging/biomarker focus, herbal-adjunct compounds) that still require
  an abstract read, which the tool's own framing already demands.
  10 tests in `tests/tools/test_discovery_scope_prescreen.py`.
- **Mental health corpus: cycle 7, 10 more real papers (47 total),
  including the CAN-BIND paper that surfaced the degree-credential
  parser bug.** New papers include an escitalopram-CABG RCT, an
  escitalopram+sertraline post-stroke-depression RCT, a sertraline-PANDA
  predictors-of-response analysis, a CBASP-vs-escitalopram subgroup
  study, the VESPA vortioxetine-vs-SSRIs tolerability RCT, an
  antidepressants-in-Japan systematic review/meta-analysis, the CAN-BIND
  CYP2C19/CYP2D6/ABCB1 sexual-dysfunction study, an
  empagliflozin-adjunctive-to-citalopram RCT, an antidepressant
  side-effects/adherence systematic review, and a
  vortioxetine-vs-fluoxetine metabolic-parameters RCT.
- **Mental health corpus: cycle 8, 13 more real papers (60 total),
  best yield yet at 20%.** New papers include a probiotic-adjunct-to-
  SSRIs sexual-function RCT, a TMS-plus-escitalopram efficacy/safety
  meta-analysis, a psilocybin-vs-escitalopram personality-change trial,
  an SSRIs-in-multiple-sclerosis systematic review/meta-analysis, a
  CYP2C19-pharmacogenetic-testing citalopram/escitalopram
  tolerability-and-efficacy cohort study, an escitalopram-vs-other-
  antidepressants systematic review/meta-analysis, the TED-trazodone-
  vs-SSRIs naturalistic effectiveness study, an rTMS-plus-sertraline
  somatic-pain study, a psilocybin-for-treatment-resistant-depression
  trial in patients on a concomitant SSRI, two CAN-BIND-1 secondary
  analyses, a CYP2D6/CYP1A2-polymorphism duloxetine-response study, and
  an EMBARC-trial secondary analysis.
- **Mental health corpus: cycle 9, 2 more real papers (62 total).**
  Yield collapsed to 2% this cycle (most candidates failed deterministic
  identity/license/full-text/scope rules outright), possibly signaling
  this query is approaching exhaustion of readily-available PMC-OA
  results. New papers: a bariatric-surgery SSRI/SNRI plasma-concentration
  study, and an EMBARC-trial secondary analysis of brain
  ventricle/choroid plexus morphology as a treatment-response predictor.
- **Mental health corpus: discovery cycle 10 confirms query exhaustion;
  paused further cycles.** A tenth cycle (retstart=800) scanned 100
  candidates and deterministically accepted 0 -- confirming cycle 9's
  yield collapse was a real signal, not noise. Corpus remains at 62 real
  papers. Documented in the corpus README; a future session should
  decide whether to redesign the query or leave the corpus at this size.
- **GLP-1 binary-pooling blocker: source-audited STEP/OASIS/SURMOUNT as
  candidates for a second observed-count binary statistical input.**
  Following up the earlier SELECT investigation (ruled out for using
  imputed rather than observed data), audited the primary STEP program
  trials (1, 2, 3, 4, 6, 8), OASIS oral-semaglutide trials, and SURMOUNT
  tirzepatide trials. Every primary trial paper -- including STEP 1
  itself -- is published in a closed-access venue (NEJM/JAMA/Lancet)
  with no PMC OA record; only secondary/post-hoc analyses are open
  access, and none restate the primary categorical responder counts.
  Documented in `docs/glp1_statistical_readiness_gate_plan.md` as a
  structural publisher-access blocker, not a single missing paper, with
  three explicit paths forward.
- **Oncology corpus: first manually-authored, reviewed Evidence Record
  bootstraps the reviewed-evidence layer.**
  `ev-oncology-dang-2026-icichemo-vs-chemo-os-001`, hand-authored from
  the local PDF of a 28-RCT meta-analysis (Dang et al. 2026, PeerJ),
  records the paper's own vs-chemotherapy-alone overall-survival hazard
  ratios for both checkpoint-inhibitor classes (PD-L1+chemo: HR 0.82
  [0.75-0.90]; PD-1+chemo: HR 0.65 [0.61-0.71]), directly answering this
  corpus's scientific question. `evidence_records.jsonl` now holds 1,522
  records (1,521 draft + 1 reviewed); `ke graph-build` processed the new
  record (graph totals: 1,676 claims, 109 concepts, 1,597 claim-concept
  edges). First bootstrap step toward an eventual golden evidence map
  for this corpus, honestly labeled as a same-session self-audit rather
  than an independently-reviewed record -- see the corpus README.
- **Oncology corpus: 3 more hand-authored reviewed Evidence Records (4
  total).** `ev-oncology-tsuboi-2026-keynote671-stageii-efs-os-001` (a
  KEYNOTE-671 stage II NSCLC subgroup analysis: EFS HR 0.50 [0.34-0.74];
  OS HR 0.69 [0.43-1.11]), `ev-oncology-nodbrant-2026-ecogps-real-world-os-001`
  (a Swedish registry real-world ICI cohort stratified by ECOG PS: mOS
  21.5 vs 9.6 vs 4.3 months for PS 0-1/2/3), and
  `ev-oncology-gandara-2026-cemiplimab-composite-pro-os-001` (EMPOWER-Lung
  1/3 composite PRO risk prediction for OS: top composite HR 2.52
  [1.75-3.64] vs top single-scale HR 1.92 [1.43-2.58]) -- each extracted
  by directly reading its local PDF. `evidence_records.jsonl` now holds
  1,525 records (1,521 draft + 4 reviewed); `ke graph-build` processed
  the 3 new records (graph totals: 1,679 claims, 111 concepts, 1,602
  claim-concept edges).
- **Oncology corpus: 3 more hand-authored reviewed Evidence Records (7
  total).** `ev-oncology-stuschke-2026-durvalumab-crisp-realworld-001`
  (real-world German CRISP registry validation of PACIFIC-regimen
  durvalumab consolidation: PFS HR 0.52 [0.37-0.73]; OS HR 0.67
  [0.44-1.02]), `ev-oncology-katsarolis-2026-greek-realworld-os-001`
  (684-patient real-world Greek cohort: immunotherapy vs chemotherapy
  alone, OS HR 0.51 [0.42-0.61]), and
  `ev-oncology-liao-2026-icpscore-predictive-biomarker-001` (a 9-gene
  predictive biomarker from the phase 3 ORIENT-11 trial: high-score
  patients benefit substantially from ICI plus chemotherapy -- OS HR
  0.32 [0.15-0.67] -- while low-score patients show no significant
  benefit -- OS HR 1.31 [0.81-2.12]). `evidence_records.jsonl` now
  holds 1,528 records (1,521 draft + 7 reviewed); `ke graph-build`
  processed the 3 new records (graph totals: 1,682 claims, 111
  concepts, 1,604 claim-concept edges).
- **Oncology corpus: 3 more hand-authored reviewed Evidence Records
  (10 total).** `ev-oncology-weber-2026-nic-vs-pc-realworld-001`
  (real-world head-to-head German cohort: nivolumab+ipilimumab+chemo
  vs pembrolizumab+chemo, no significant OS difference, 13.6 vs 14.1
  months), `ev-oncology-machado-2026-pembrolizumab-realworld-meta-001`
  (systematic review/meta-analysis of 12 real-world cohorts, 17,506
  patients: pooled mean OS 21.0 months, 60-month OS rate 29.0% for
  first-line pembrolizumab in PD-L1>=50% NSCLC), and
  `ev-oncology-selke-2026-durvalumab-pdl1-subgroup-001` (PD-L1-stratified
  real-world cohort: durvalumab consolidation benefit concentrated in
  PD-L1-positive patients, median OS 27.3 vs 15.1 months, p=0.043).
  `evidence_records.jsonl` now holds 1,531 records (1,521 draft + 10
  reviewed); `ke graph-build` processed the 3 new records (graph
  totals: 1,685 claims, 111 concepts, 1,608 claim-concept edges).

- **Mental health corpus: cycle 6, 10 more real papers (18% yield, best
  yet).** Corpus now holds 37 real papers, up from 27. New papers
  include a trazodone-vs-SSRIs study, a comparative-effectiveness study
  of antidepressants and rehospitalization, a sertraline-in-dialysis
  meta-analysis, a TMS+paroxetine post-stroke-depression study, a
  mirtazapine/SSRIs/amitriptyline patient-level meta-analysis, a
  venlafaxine adverse-events meta-analysis with Trial Sequential
  Analysis, an insulin-resistance/SSRI-SNRI-resistance study, a
  vilazodone/escitalopram/vortioxetine metabolic-parameters RCT, an
  aticaprant-adjunctive-to-SSRI/SNRI phase 2 RCT, and the ASCERTAIN-TRD
  comparative-effectiveness RCT.

- **Oncology corpus fully seeded from the 1,522-item eligible-drafts
  pool; mental health cycle 5 (9 more real papers, best yield yet).**
  Promoted the final 322 oncology drafts -- `evidence_records.jsonl` now
  holds all 1,521 records the m28-pico-v5 extraction pass produced. Ran
  `ke graph-build` on the final batch: 1,675 claims, 109 concepts,
  1,597 claim-concept edges, up from 1,353/104/1,305.
  Mental health's fifth discovery cycle (56 accepted) yielded 9 real
  papers (16%, the best cycle yet): systematic reviews of
  citalopram/escitalopram metabolic effects, SSRI/SNRI post-stroke
  depression, and fluoxetine oral side effects; a paroxetine-olanzapine
  interaction PK study; an escitalopram combined-treatment analysis; a
  fluoxetine+probiotics RCT; an agomelatine+SSRI/SNRI RCT; a
  pharmacological-interventions meta-analysis; and a
  vortioxetine-vs-escitalopram comparative study. Corpus now holds 27
  real papers.

- **Oncology corpus batch 5 (299 more records); mental health cycle 4.**
  Promoted 299 more oncology drafts (1,199 total, 323 eligible remain)
  and ran `ke graph-build` (1,353 claims, 104 concepts, 1,305
  claim-concept edges, up from 1,054/100/932). Ran mental health's
  fourth discovery cycle (48 accepted, 4 passed screen: the DEPRE'5
  post-SSRI-failure RCT, a sertraline inflammatory-markers meta-analysis,
  a paroxetine+sulpiride study, and an antidepressant-comorbidity
  network meta-analysis); corpus now holds 18 real papers.

- **Mental health corpus: tightened-query cycle 2, 4 more real papers.**
  A third discovery cycle scanned 100 candidates (50 accepted); 4 passed
  scope screen (8% yield, up from 3.8%): a desvenlafaxine network
  meta-analysis, a vortioxetine-vs-sertraline PD-comorbid-depression
  comparison, a venlafaxine pharmacovigilance analysis, and a
  bupropion+sertraline precision-medicine trial. Corpus now holds 14
  real papers. Acquired via a new local batch-runner script
  (`work/run_paper_batch.sh`) that collapses acquire/import/split/verify
  into one call.

- **Oncology corpus batch 4 (300 more records); investigated SELECT as a
  second binary statistical input.** Promoted 300 more oncology drafts
  into `evidence_records.jsonl` (now 900 total, 622 eligible drafts
  remain) and ran `ke graph-build` (1,054 claims, 100 concepts, 932
  claim-concept edges, up from 754/97/645). Separately, investigated
  whether the SELECT trial paper already in the corpus could supply a
  second production binary statistical input to unblock GLP-1 pooling
  readiness -- confirmed via the paper's own body text that its
  categorical weight-loss percentages are multiple-imputation-model
  results over the full ITT population with no reported raw observed
  count, so no compatible integer event/total pair can be derived
  without fabricating one. Documented as a negative finding in
  `docs/glp1_statistical_readiness_gate_plan.md` rather than forcing a
  non-source-audited entry.

- **Mental health corpus: tightened discovery query, 2 more real papers.**
  A tightened query (drops the noisy bare `antidepressant` term, keeps
  `SSRI`/`SNRI`/named agents) improved cycle yield from 1.5% to ~3.8%.
  Acquired and imported a paroxetine pharmacovigilance analysis and a
  trazodone-vs-SSRIs comparative-effectiveness study; corpus now holds 10
  real papers.

- **Mental health corpus: first real papers acquired and imported; oncology
  batch 3 (300 more records).** Manually scope-screened the mental-health
  corpus's first two discovery cycles (54 then 64 deterministically-
  accepted candidates), selecting 7 then 1 -- a collapsing yield (13% then
  1.5%) traced to the discovery query's bare `antidepressant` term
  matching any depression-treatment-mechanism paper. 8 real PMC OA papers
  acquired and imported (`ke corpus-import`: 0 failed). A tightened query
  is documented for future cycles in
  `docs/mental_health_corpus_scoping.md`. Separately, promoted 300 more
  oncology draft items into `evidence_records.jsonl` (now 600 total) and
  ran `ke graph-build` (754 claims, 97 concepts, 645 claim-concept edges,
  up from 454/95/327); 922 further eligible drafts remain.

### Fixed

- **Chunked database growth persisted for the 200-record oncology
  graph-build.** Re-split and round-trip-verified `data/db_parts/*` after
  `ke graph-build` processed the second oncology batch (454 claims, 95
  concepts, 327 claim-concept edges, up from 254/92/199).

- **Oncology corpus: second automated Evidence Record batch (200 more
  records).** `data/corpora/oncology_nsclc_checkpoint_inhibitors/evidence_records.jsonl`
  now holds 300 `draft`/`m52-evidence-classification-v1` records (100 + 200),
  same honesty discipline as the first batch. Spot-checked `claim_text`
  across the new batch against real source text -- accurate. 1,222 further
  eligible drafts remain unpromoted. Also ran the mental-health corpus's
  first live discovery cycle (`ke discovery-cycle-run --corpus
  mental_health_mdd_antidepressants`): 100 PubMed candidates scanned, 54
  deterministically accepted, ready for the same human/AI title-and-abstract
  scope screen this project has always required before acquisition.

- **Mental health corpus scoped (third research domain) and oncology's
  first automated Evidence Record batch.** Per `docs/roadmap.md`'s
  "Decision: the extraction and discovery framework must be domain-general,
  not per-field-patched," scoped a third corpus --
  `mental_health_mdd_antidepressants` (SSRIs/SNRIs in adult major
  depressive disorder), chosen by the project owner over cardiovascular
  disease and infectious disease/vaccines -- with the same file shape as
  the GLP-1 and oncology corpora (`corpus.json`, inclusion/exclusion
  criteria, `license_policy.md`) and a new
  `MENTAL_HEALTH_MDD_ANTIDEPRESSANT_SCOPE` vocabulary in
  `knowledge_engine/scientific_scope.py`. No discovery has run yet;
  `sources.csv` is header-only. Separately, promoted the oncology corpus's
  first 100 `m28-pico-v5`-extracted draft items into real, honestly-labeled
  `draft`/`m52-evidence-classification-v1` Evidence Records, ran the
  graph-population pipeline (100 claims, 42 claim-concept links, 92
  concepts resolved against RxNorm/MeSH), and ran a first `ke
  evidence-review-automate` (M69) grounding trial (2 of 25 records
  improved; the rest correctly rejected by grounding verification rather
  than guessed). `claim_text`/`result_summary` were spot-checked against
  real source text and are accurate; `research_question` (templated from
  still-imperfect PICO fields) remains known-unreliable for many records,
  disclosed rather than hidden -- see `docs/oncology_corpus_scoping.md`
  and `docs/mental_health_corpus_scoping.md`.

### Fixed

- **PICO extraction cue patterns matched statistical-result sentences,
  not comparator/outcome statements, in the oncology corpus.** Found
  while trial-running `ke extraction-review-batch-generate` +
  `extraction-review-autoclassify` against the 335 imported
  `oncology_nsclc_checkpoint_inhibitors` papers (see
  `docs/oncology_corpus_scoping.md`'s 2026-08-08 status entries for the
  full finding). `PICO_EXTRACTION_RULES_VERSION` bumped `m28-pico-v4` ->
  `m28-pico-v5`: a candidate sentence carrying an explicit
  statistical-result marker (a p-value, a `95% CI`, or an effect-measure
  abbreviation like `OR:`/`HR:` followed by a number) is now skipped for
  every PICO field, the same "skip, never guess" precedent
  `is_table_derived` already established. Re-running the trial batch
  confirmed zero of the resulting 1,522 eligible draft items retain a
  statistical-result marker in `comparator`/`outcome` (down from
  widespread leakage), with no regression to the existing test suite.
  This is a real, measured, but partial fix -- comparator/outcome still
  sometimes capture a named statistical-method or tool phrase with no
  numeric marker (e.g. "assessed using the Wilcoxon rank-sum test"), so
  no oncology automated Evidence Record was promoted.

### Added

- **Persistent-host build-trigger status decision and a fresh-clone backup
  restore verification.** `docs/persistent_host_design.md`'s five build
  trigger conditions (named operator, approved consumer migration, accepted
  fixtures, tested restart procedure, decided network security) are each
  checked against the project's actual current state and confirmed unmet;
  the project explicitly commits to the current event-triggered-snapshot-
  plus-subprocess model for the near term (see its new "2026-08-08
  Build-Trigger Status" section). Separately, exercised the chunked-database
  backup/restore runbook from a genuinely fresh, network `git clone` of
  `main` for the first time (not this working directory): reassembled a
  507,453,440-byte database from the committed `data/db_parts/`, verified
  every part hash, `PRAGMA integrity_check = ok`, and 1,295-row `papers`
  count, then independently confirmed the output file's SHA-256 with
  `sha256sum`. Both satisfy `docs/roadmap.md`'s `v0.5.0-beta` tag
  prerequisites. See `docs/corpus_database_chunked_versioning.md`'s
  "2026-08-08 fresh-clone verification" section.

- **Statistical Verification Readiness Gate.** New `ke
  statistical-readiness-report` command and
  `knowledge_engine/statistical_readiness.py` module implement the
  pre-approved design in `docs/glp1_statistical_readiness_gate_plan.md`.
  Validates a curated readiness classification
  (`data/corpora/glp1_weight_loss/statistical_readiness_map.json`) against
  the reviewed golden evidence map's actual coverage and already-validated
  typed statistical inputs, computes each declared pooling-compatibility
  group's `candidate`/`no`/`undetermined` status, and renders a
  deterministic Markdown report with an overall readiness verdict. Run
  against the current 14-record golden map: 2 `exactly_verified`, 3
  `display_only`, 7 `not_selected_for_verification`, 2 `not_applicable`;
  one compatibility group (STEP 5 vs SELECT) blocked by incompatible
  estimands; verdict `not_ready_for_pooling_design`, matching the
  pre-implementation expectation in
  `docs/reviews/glp1_statistical_readiness_gate/compatibility_analysis.md`.
  This is the milestone named by the prespecified zero-cell correction
  audit's own handoff (`docs/glp1_second_binary_edge_case_plan.md`, Decision
  Rule C: no defensible second production result). It never pools studies,
  performs meta-analysis, infers a missing classification, or determines
  scientific truth. The GLP-1 Statistical Pooling Protocol design must not
  begin until a future run reports `ready_for_pooling_design_review`.

- **Oncology corpus first bulk seeding batch (335 papers).** 10
  `ke discovery-cycle-run` cycles against PubMed/PMC OA for the
  `oncology_nsclc_checkpoint_inhibitors` corpus scanned ~1000 raw
  candidates, yielding 478 unique deterministically-accepted candidates. A
  documented, rule-based title scope screen (excluding wrong cancer types,
  preclinical/mechanism-only studies, off-topic diagnostic/surgical papers,
  and single-patient case reports) selected 336, all acquired as real PMC
  OA PDFs and imported (335 imported, 1 skipped as a duplicate; corpus
  database now 1,295 total papers, up from 960). `sources.csv` populated
  for all 336 rows; `data/db_parts/` re-split and committed to persist the
  database growth. This is bulk ingestion metadata, not yet a reviewed
  evidence base -- see `data/corpora/oncology_nsclc_checkpoint_inhibitors/README.md`.

- **Dedicated release assessment and truthful pre-1.0 tag ladder.**
  `docs/roadmap.md`'s Release Milestones section replaces its stale
  `v0.1.0`-`v1.0.0` version ladder with a 2026-08-08 assessment confirming
  Current Project Path goals 1-3 (coherent public journey, measured
  retrieval, defensible golden evidence map) are met, and a new
  `v0.2.0-alpha.2`-`v1.0.0` ladder tying each future tag to a concrete,
  checkable artifact instead of an aspirational phase label. The original
  ladder is preserved below it, marked superseded, for historical context.

- **GLP-1 golden map gap closure: post-bariatric agent coverage and
  real-world adherence.** Promoted two previously `draft` Evidence Records
  (`ev-tirzepatide-post-bariatric-weight-regain-001`,
  `ev-glp1ra-adherence-comorbidity-predictors-001`) to `reviewed` after an
  independent source audit against their local PDFs, and added two reviewed
  Relationship Records connecting them into
  `data/corpora/glp1_weight_loss/golden_evidence_map.json`
  (`contextualizes` and `qualifies`). The map now selects fourteen Evidence
  Records and nineteen Relationship Records. See
  `docs/glp1_map_gap_closure_2026_08_08.md`.

- **First source-audited binary-outcome verification.** Extended
  `ke statistical-verify` with an optional, separately versioned binary-input
  contract. STEP 5's observed week-104 responder counts (`111/144` versus
  `44/128`) reproduce the reported arm percentages within a declared `0.05`
  percentage-point tolerance and yield a deterministic crude risk ratio of
  `2.242424...` with a no-correction log-Wald 95% interval of `1.737001...` to
  `2.894913...`. The source's adjusted OR `5.0` (95% CI `3.0` to `8.4`) remains
  display-only because its logistic-regression, baseline-covariate, and
  multiple-imputation model is not reconstructible from the observed counts.
  No PDF, SQLite, pooling, confidence scoring, AI, or scientific synthesis is
  involved at command runtime.

- **First source-audited confidence-interval approximation.** Extended
  `ke statistical-verify` with statistical-input schema version 2 while
  preserving version 1 compatibility. STEP 5 now uses its explicitly reported
  arm standard errors, sample sizes, a declared `1.96` normal critical value,
  and an independent-arm assumption to approximate the reported week-104 95%
  interval deterministically. Both endpoints are compatible within the
  declared `0.1` percentage-point tolerance. The report labels this as an
  approximation rather than a reconstruction of the source ANCOVA,
  multiple-imputation, covariance, or Rubin-combination procedure. SELECT
  remains display-only because its source does not expose both required
  numerical arm standard errors. No values are parsed from prose, and no
  pooling, confidence scoring, SQLite access, PDF access, or synthesis occurs.

- **SELECT typed statistical-input expansion.** Added a second source-audited
  randomized body-weight identity to `statistical_inputs.jsonl`. SELECT's
  explicit week-208 arm means reproduce its reported `-8.7` percentage-point
  treatment difference exactly. Refined the version 1 provenance contract so a
  typed numerical locator can identify a different source page from its
  Evidence Record claim locator while normalized DOI, reviewed record identity,
  outcome, and both source spans remain enforced. No values were parsed from
  prose and no confidence interval was recomputed.

- **First typed GLP-1 statistical verification.** Added
  `ke statistical-verify` and a version 1 source-linked JSONL contract for one
  supported effect form. The source-audited STEP 5 week-104 input independently
  reproduces the reported `-12.6` percentage-point treatment difference from
  explicit randomized-arm means using Decimal arithmetic. Validation enforces
  reviewed Evidence Record identity, DOI, outcome, source span, estimand,
  units, time point, formula, tolerance, and provenance. The command does not
  parse prose, open PDFs or SQLite, recompute confidence intervals, pool
  effects, score confidence, or perform scientific synthesis.

- **GLP-1 deterministic cross-study comparison foundation.** Added
  `ke evidence-map-report` to render a validated evidence map as a stable,
  source-linked Markdown comparison of study design, PICO, reported results,
  limitations, citations, grouping boundaries, and reviewed relationships.
  The report explicitly identifies the typed statistical-input prerequisite
  delivered by the next bounded milestone and does not parse prose, recompute
  or pool effects, rank studies, calculate consensus or confidence, or perform
  scientific synthesis.

- **Reproducible GLP-1 same-PICO contradiction audit.** Added a written search
  plan and completed audit across committed evidence, source metadata,
  relationship candidates, and bounded PubMed queries. No aligned
  direction-reversing semaglutide result was found. Added the legally reusable,
  underpowered GLIDE liraglutide-after-gastric-banding trial as one reviewed
  agent/population qualifier and one `qualifies` relationship, bringing the
  reviewed map to 12 cited records and 17 relationships without manufacturing
  a contradiction or implying synthesis, consensus, confidence, or truth.

- **GLP-1 golden-map durability and safety qualifiers.** Added a reviewed STEP
  1 withdrawal-extension Evidence Record and a reviewed semaglutide RCT
  safety/discontinuation Evidence Record, linked through three bounded
  `contextualizes`/`qualifies` relationships. The reviewed map now contains 11
  cited records and 16 relationships while explicitly avoiding class-wide
  safety, individual benefit-harm, synthesis, consensus, confidence, or truth
  claims.

- **GLP-1 golden-map secondary source audit.** Reviewed all 9 selected Evidence
  Records and 13 selected Relationship Records against legally usable local
  PDFs, corrected two evidence descriptions and two relationship rationales,
  and advanced the bounded map to `reviewed`. Review provenance explicitly
  identifies the AI-assisted audit and does not claim human domain-expert
  approval, scientific synthesis, consensus, confidence, or truth.

- **Deterministic corpus-library backup snapshots.** Preserve source row
  timestamps during portable snapshot export so unchanged corpus content has
  stable compressed bytes and Drive backups reliably skip duplicate uploads.

- **Provisional GLP-1/body-weight golden evidence map.** Added a versioned map
  selecting 9 cited Evidence Records and 13 reviewer-authored relationships,
  with explicit population, comparator, endpoint, limitation, and
  contradiction boundaries. Added `ke evidence-map-validate` to check map
  structure, references, citation completeness, grouping coverage, and review
  status without inferring evidence, consensus, confidence, or scientific
  truth. The map was introduced as provisional so review could be completed as
  a separate, auditable change.

- **Persistent host architecture decision.** Added
  `docs/persistent_host_design.md`, defining a read-only, localhost-first HTTP
  host over core's existing readers as the eventual replacement for web
  snapshots and AI subprocess calls. The design limits the API to current
  consumer needs, preserves scientific trust boundaries, aligns deployment
  with the existing systemd/password-gated-alpha precedent, and names concrete
  operational and consumer triggers that must be met before server code is
  built. No host, endpoint, dependency, or application behavior is added.

- **Post-M69 relationship graph review, ranks 36-50.** Reviewed the next
  15 similarity-ranked pairs from
  `ke relationship-review-worksheet --rank-by-similarity`
  against both records' full PICO and result fields.
  Authored 3 conservative `contextualizes` relationships: the GLP-1RA
  insulin-resistance-marker cohort with STEP 5 and SELECT respectively,
  and the oral-semaglutide HFrEF cohort with the HFpEF/BNP cohort. These
  records preserve the studies' different populations, comparators, and
  endpoints and do not count contextual evidence as direct support. The
  other 12 pairs were deliberately left unrelated: most shared only a
  generic concept (`Patients`, `Health`, or `placebo`), involved different
  interventions or outcomes, or represented duplicate evidence records
  from the same paper. `ke relationship-validate` passed with 20 records;
  rebuilding the local graph projected 17 -> 20 relationship edges, with
  154 claims and 149 claim-concept edges unchanged.

- **M69: automated evidence review pipeline.** Implements the decision
  in `docs/roadmap/long_term_vision.md`: replaces the human-reading
  review gate with a grounding-verified LLM extraction path.
  `knowledge_engine/llm.py` (new): a local Ollama client ported from
  `knowledge-engine-web`/`-ai`'s own `llm.py` (same established
  small-self-contained-copy-per-package pattern). `knowledge_engine/
  extraction/grounding.py` (new): `verify_grounding` checks an
  LLM-proposed field against the source text -- exact substring, or a
  word-level `difflib` near-match tolerant of light rewording -- before
  it can be accepted; nothing like this existed in the codebase before.
  `knowledge_engine/extraction/llm_grounded_pico.py` (new):
  `extract_pico_for_candidate` runs PICO extraction per claim candidate
  scoped to that candidate's own source page, fixing the PICO-broadcast
  bug M68 found by hand (`build_draft_evidence_items` previously glued
  one paper-level PICO extraction onto every claim in that paper,
  regardless of which sentence it actually came from).
  `knowledge_engine/evidence_intelligence.py`: `compute_evidence_quality`
  gets a third extraction-rigor tier (33 points, between raw-automated
  25 and human-manual 40) and a new `extraction_tier` field so callers
  can render `"llm_grounded"` honestly instead of collapsing it into
  `manually_reviewed`. `knowledge_engine/evidence_review_automate.py`
  (new) plus `ke evidence-review-automate` (new CLI command): batch
  driver that reads the graph's paper pages, runs the pipeline, and
  rewrites only the JSONL lines for records it actually changed --
  `claim_text`/`research_question`/`evidence_direction` are never
  touched. Live-verified against the real GLP-1 corpus DB (Ollama +
  `qwen2.5:1.5b`): dry-run and real runs both correctly regrounded a
  mangled record's `intervention` field (was a wrong study-design
  description, now the actual drug name), Evidence Quality 81->91, only
  the one changed record's JSONL line rewritten, all other 153 lines
  byte-identical. Does not rebuild the graph itself -- prints a
  reminder listing changed `evidence_record_id`s, since `ke
  graph-build`'s M54 incremental design skips any ID that already has a
  `graph_claims` row. Running this against the full 118-record backlog
  is its own follow-up batch, the same pattern M68 established.

### Fixed

- **PDF corpus recovery rejected every PMC-hosted resolution.** `tools/
  reacquire_corpus_pdfs.py` had never been run against real data. Live
  testing against this environment's 951-paper corpus found that PMC's
  Article Datasets Cloud Service now returns `pdf_url` as an `s3://` URI,
  not the `https://` URL the tool's allowlist check expected -- every
  PMC-hosted resolution failed regardless of actual open-access status.
  Added a conversion step that validates the bucket and reconstructs the
  HTTPS URL, plus the test file this tool never had. See
  `docs/error_resolution_ledger.md` (2026-08-08 entry) for the full
  root-cause writeup. Confirmed live: a full 960-row dry run went from
  systemic resolution failures to zero, and the 9 papers genuinely
  missing a local file were recovered and hash-verified.

- **Roadmap truth alignment.** Added one ordered five-goal Current Project
  Path and corrected stale future-facing documentation that still described
  `knowledge-engine-ai`, local synthesis, Evidence Intelligence, relationship
  review tooling, and web dashboard/report features as unbuilt. Historical
  milestone records remain intact; the phase index, long-term ecosystem map,
  and current roadmap now distinguish shipped foundations from the retrieval,
  evidence-map, analytical, and persistent-host work that actually comes next.

- **Evidence Intelligence extraction-tier exports.** The Markdown report
  now renders the same honest three-way extraction label as synthesis
  (`manually reviewed`, `LLM-extracted, grounding-verified`, or
  `automated, pending review`) instead of collapsing the latter two into
  `Manually reviewed: no`. The JSON contract now includes
  `evidence_quality.extraction_tier` while retaining `manually_reviewed`
  for backward compatibility, allowing downstream consumers to preserve
  the M69 review tier.

- **M69 follow-up: bounded cross-page PICO context.** The first full
  automated-review backlog pass left 21 records on the M52 extraction
  method because their terse result sentences were correctly tagged to
  pages that did not repeat the paper's population/intervention framing.
  `ke evidence-review-automate` now supplies the claim page plus page 1
  from the same paper when those pages differ. Every proposed value still
  has to pass the unchanged `verify_grounding` check against those real
  source texts; prompt labels are excluded from the grounding corpus and
  whole-paper context is not used. The widened contract is recorded as
  `m69-llm-grounded-pico-v2`, while v1 records remain recognized as
  reviewed and retain the same Evidence Quality tier. A real-corpus rerun
  grounded 11 of the 21 remaining records; the other 10 stayed byte-for-byte
  untouched. The 11 updates changed only PICO fields and review provenance,
  and all accepted quotes reverified against source text at 1.000 similarity.

- **M69 pipeline: fix-forward on Copilot's PR #239 review findings.**
  PR #239 merged with CI failing and five Copilot code-review findings
  unaddressed; two auto-merged Copilot PRs (#240, #242) fixed only the
  mypy typing error, leaving the rest live in `main`. Fixed here: (1)
  `automate_review_for_record` and the `ke evidence-review-automate`
  CLI's eligibility filter now also check `review_checklist.
  human_reviewed`, not just `extraction_method` -- per the convention
  `_build_evidence_review_queue` already documents (a manually reviewed
  record can keep its prior automated `extraction_method` as provenance),
  a genuinely human-reviewed record could otherwise be silently
  reprocessed and have `human_reviewed` flipped back to `False`. (2) the
  CLI's eligibility filter no longer blanket-excludes every
  `LLM_GROUNDED_PICO_RULES_VERSION` record regardless of whether
  `review_checklist` is actually populated, matching
  `compute_evidence_quality`'s own tiering rule. (3)
  `llm_grounded_pico.py`'s `_JSON_OBJECT_RE` no longer greedily spans
  from the first `{` to the last `}` in the raw LLM response -- bounded
  to a single flat, non-nested object, since the expected shape never
  nests. (4) `automate_review_for_record` now merges into any existing
  `review_checklist` dict instead of overwriting it outright, preserving
  unrelated keys. (5) `render_synthesis` now renders `EvidenceQuality.
  extraction_tier`'s three-way label instead of the two-way
  `manually_reviewed` boolean, so an `llm_grounded` record no longer
  reads as "automated, pending review". Live-verified against the real
  corpus: `ke evidence-review-automate --dry-run` still reports the same
  118 eligible records (the corpus currently has no record that exercises
  the fixed provenance-corruption scenario), confirming no regression.

- **M69 decision doc: two Codex-caught fixes.** Codex review on PR #237
  caught two real issues in `docs/roadmap/long_term_vision.md`'s
  "Decision: automated evidence review at scale (M69)" section, after it
  had already merged: (1) the decision described the LLM proposing
  `evidence_direction` and having it grounding-checked, but
  `evidence_direction` is a classification relative to a
  `research_question`, not source text -- it can never pass a
  substring/near-match grounding check by construction. Corrected to
  scope the LLM+grounding path to the four PICO fields only;
  `evidence_direction`/`research_question` stay on their existing
  deterministic path (`classify_evidence_direction`/
  `generate_research_question`), which already operates correctly per
  candidate. (2) `docs/evidence_intelligence_design.md`'s "real data"
  audit, which the decision cites as the scoring-tier's basis, still had
  its original M57-era numbers (155 total, 33 manual, 122 automated),
  contradicting the decision's own M68-era citation (154/36/118). Added
  a live-re-audited update note with current corpus numbers, kept
  alongside the original snapshot rather than silently overwriting it.

- **Decision: automated evidence review at scale (M69), documentation
  only.** The project owner explicitly and permanently decided that
  manual, human-read review of every evidence record does not scale to
  this project's real corpus-growth plans (M68's audit found 118 of 154
  records, 79%, already automated-and-unreviewed at today's small
  scale) and will not be relied on going forward. Updated every doc
  asserting the superseded "every record must trace to a human reading
  the source" policy to point at the new decision instead of
  contradicting it: `docs/roadmap/long_term_vision.md` (new "Decision:
  automated evidence review at scale (M69)" section with the full
  reasoning and replacement mechanism -- per-claim-candidate LLM
  extraction via the existing `OllamaLLM` client, a new grounding-check
  verifier that does not exist yet, and a new honestly-labeled
  `extraction_method` tier), `docs/future_ideas.md`'s "Reviewer
  Tooling" intro, `docs/core_interface_contract.md`'s seam description,
  `docs/roadmap.md`'s "Planned: Reviewer & Evidence Intelligence
  Tooling" section (new fifth item, M69 in progress), and
  `docs/evidence_intelligence_design.md`'s already-reserved
  extraction-rigor middle tier (now committed, not just reserved). No
  code changed in this entry -- the pipeline itself is the next
  milestone.

### Added

- **M68: automated evidence-record review, batch 1.** Continuing
  `docs/future_ideas.md`'s "Reviewer Tooling" backlog (122 automated
  `m52-evidence-classification-v1` records, unreviewed). Used `ke
  evidence-review-queue` to prioritize the top 5 tier-2 candidates, then
  read each source paper's full text (via `paper_pages`) before touching
  any field. Two records checked out as genuinely mangled: the automated
  classifier had pulled unrelated boilerplate (article metadata,
  adjacent unrelated sentences) into `population`/`intervention`/
  `comparator` fields, and one record's `claim_text` stated only a
  baseline demographic sentence, missing the paper's actual reported
  result and its negative primary endpoint entirely. Corrected PICO
  fields, `claim_text`, `result_summary`, `evidence_direction`, and
  `limitations` for 3 records against the real source text (an
  Akkermansia-muciniphila RCT, a GLP-1/chronic-venous-insufficiency
  retrospective cohort, and a SiPore21 glycaemic-control RCT), flipped
  `extraction_method` to `manual_human_review` with a populated
  `review_checklist`. Evidence Quality scores moved from largely
  boilerplate-driven values to source-grounded ones: 31->94, 69->94,
  62->69. Along the way, checked whether these (and 2 other top-5
  candidates: an SGLT2-inhibitor real-world study and a PCOS
  lifestyle-dropout trial, neither mentioning GLP-1) were off-target for
  the corpus -- they are not: `data/corpora/glp1_weight_loss/inclusion_criteria.md`
  confirms this is the "Obesity and Metabolic-Disease Therapeutics
  Corpus," scoped to obesity/T2D/metabolic-syndrome therapeutics
  generally, with GLP-1 retained only as its first named subtopic, so a
  literal-GLP-1-mention heuristic is not a valid scope proxy. Graph
  rebuilt for the 3 corrected claims only (`ke graph-build`'s M54
  incremental design skips already-persisted claims, so their stale
  `graph_claims`/`graph_claim_concepts` rows were cleared first): 3 new
  claim-concept links resolved, 151 claims unchanged, all 17
  relationship edges intact (none touch these 3 claims). Automated
  backlog: 121 -> 118 of 154 records.

### Fixed

- **`corpus_library.py`: leaked SQLAlchemy engines break Windows.** Found
  during the first live rehearsal of `ke-corpus-library-drive-backup` on
  Windows: `export_corpus_library`'s `target_engine` and
  `import_corpus_library`'s `source_engine` were never disposed, so their
  underlying SQLite file handles stayed open past each function's `with`
  block. On Windows this made `export_corpus_library_compressed`'s and
  `import_corpus_library_compressed`'s own temp-directory cleanup fail
  with `PermissionError: [WinError 32]` right after a correct export/import
  had already completed -- the same class of bug fixed for
  `sqlite_backup.py` in an earlier PR, in a different module this time.
  Both engines are now disposed in a `finally` block.

- **`corpus_library.py`: non-deterministic gzip output silently defeated
  dedup.** Found while re-verifying the fix above: `gzip.open`'s default
  header embeds the current wall-clock time, so
  `export_corpus_library_compressed` produced different compressed bytes
  -- and therefore a different SHA-256 -- for byte-for-byte identical
  content whenever two exports happened more than about a second apart.
  This directly broke `ke-corpus-library-drive-backup`'s entire
  skip-if-unchanged premise: a week with zero new papers would still have
  uploaded a "new" snapshot every run. Now exported with a fixed
  `mtime=0` gzip header so identical content always hashes identically.

### Added

- **`ke-corpus-library-drive-backup`**: relays the corpus-library snapshot
  (`ke corpus-library-export`'s output) to Google Drive instead of git,
  skipping the upload when an identical snapshot is already present. Reuses
  `ke-drive-backup-pilot`'s OAuth refresh-token auth and
  `ke-corpus-pdf-backup`'s skip-if-hash-matches dedup. Exists because
  committing a growing multi-hundred-MB snapshot to git on every corpus
  cycle permanently bloats the shared repository -- see
  `docs/corpus_library_drive_backup.md`. New allowlisted Drive destination
  `corpus_library.snapshot` in `knowledge_engine.drive_boundary`, pointing
  at a real "15 - Corpus Library" folder under the Knowledge Engine root.

- **`ke-corpus-library-drive-restore`**: the pull side of the relay above --
  lists the `corpus_library.snapshot` Drive folder, picks the most recently
  created file, and downloads and imports it via
  `import_corpus_library_compressed` (itself idempotent per paper). Skips
  the download entirely when its SHA-256 matches a local marker file
  recording the last snapshot this machine already imported, so a laptop
  that's already current downloads nothing. Live-verified against the real
  "15 - Corpus Library" snapshot: 150 real papers landed in a fresh empty
  database on first run, re-running against that same database correctly
  reported nothing to do, and running against the actual production
  database correctly deduped all 150 as already present (that snapshot was
  exported from this same database) while still exercising the real
  download and verification path. Wired into `sync_corpus_graph.ps1`,
  before `ke graph-citations-build` since it needs paper text already
  present locally.

- Ran the corpus's first real weekly discovery cycle (`ke
  discovery-cycle-run`, discovery `retstart=3550`) against a
  previously-empty `discovery_state.json`/`rejected_candidates.csv`
  pair (both seeded this run): 50 candidates discovered, 17
  deterministically accepted, 0 already in the ledger. The manual scope
  screen found all 17 were exclusions: 15 exact-PMID pagination-drift
  duplicates already present in `sources.csv` (PubMed's `sort=pub_date`
  ordering resurfacing already-included records under a new `retstart`
  offset, the same failure mode the `retstart=3000`/`retstart=3250`
  batches documented, this time caught before acquisition) and 2
  genuinely off-target (an ovarian-cancer chemoresistance/circadian-
  rhythm study, a diabetes knowledge/attitudes/practices survey naming
  no intervention). All 17 recorded in the newly-seeded
  `rejected_candidates.csv` ledger -- its first real population. Zero
  net-new papers accepted; corpus remains at 951, 49 below the
  1,000-paper cap. `discovery_state.json` advanced to
  `next_retstart: 3600` for the next cycle. See the corpus README's
  `retstart=3550` batch-history entry.

- **M65: extraction-accuracy benchmark**, closing `docs/roadmap.md`'s
  priority-list item 5. M38/M40 measured Phase 2's deterministic
  extraction pipeline's *coverage* at scale; M65 measures its *accuracy*
  against independent ground truth for the first time --
  `knowledge_engine.extraction_accuracy_benchmark` re-runs the same
  pipeline against each of the corpus's 33 genuinely human-authored
  `EvidenceRecord`s' own source papers (`extraction_method` in
  `manual_human_review`/`manual` only -- M52's automated records are
  excluded from ground truth since they template these same fields from
  this same pipeline, which would make the comparison circular) and
  compares fresh output to the promoted field values. `study_type` gets
  an exact-match rate (closed vocabulary); free-text PICO fields and
  `limitations` get presence agreement plus Jaccard token-overlap, since
  exact string equality is meaningless against human-edited prose. Run
  live against the real corpus (`scripts/m65_extraction_accuracy_benchmark.py`,
  all 33 ground-truth records resolved and benchmarked, 0 skipped):
  `study_type` exact-match 15% (real, diagnosed cause -- several
  disagreements are vocabulary granularity, not wrong answers, e.g.
  ground truth's `systematic_review_meta_analysis` vs the classifier's
  `meta_analysis`, or `retrospective_observational_cohort` vs
  `observational_study`; flagged here, not silently reconciled, pending
  an explicit decision on whether to widen the classifier's vocabulary
  or accept the mismatch), `limitations` presence-match 85%, PICO
  presence-match 73-91% per field, PICO mean token-overlap 5-17% per
  field (expected to be low -- ground truth is human-paraphrased prose,
  not the same span the deterministic extractor pulls).

- **M66: relationship graph deepening**, continuing `docs/roadmap.md`'s
  priority-list item 2. Reviewed the top 20 candidate pairs from `ke
  relationship-review-worksheet --rank-by-similarity` and authored 3
  more real `supports` records where the evidence genuinely justified
  it: `ev-glp1-semaglutide-hfref-outcomes-001` <-> the SELECT trial
  (both report semaglutide substantially reducing body weight, -8.0kg
  vs a non-GLP-1 comparator and -10.2% vs placebo respectively);
  `ev-tirzepatide-vs-semaglutide-weightloss-001` <-> a post-bariatric
  weight-regain cohort (both report substantial tirzepatide-associated
  weight loss, 14.7% and 18.1% respectively, in different populations);
  and the semaglutide/cardiometabolic-risk cohort <-> the HFrEF cohort
  (both report a comparable ~8-9kg semaglutide-associated weight-loss
  magnitude in overlapping obesity/T2D populations). Most of the
  top-ranked candidates by embedding similarity turned out to be
  spurious matches on overly generic shared concepts (`Health`,
  `Adult`, `Patients`, `Power, Psychological`) or genuinely different
  intervention/outcome domains despite high textual similarity (e.g.
  two different weight-loss drugs studied against different endpoints)
  -- left alone rather than forced into a relationship, the same
  discipline M59 established. `ke graph-build` run against the updated
  `relationship_records.jsonl`: relationship edges 11 -> 14,
  `unconfirmed_claims` 148 -> 145.

- **M67: relationship graph deepening**, continuing `docs/roadmap.md`'s
  priority-list item 2. Reviewed the next tier (ranks 21-35) from `ke
  relationship-review-worksheet --rank-by-similarity` and authored 3
  more real records: the post-bariatric tirzepatide weight-regain
  cohort <-> SURMOUNT-1's waist-to-height-ratio post-hoc analysis; the
  semaglutide cardiometabolic-risk retrospective cohort <-> the
  tirzepatide-vs-semaglutide propensity-matched comparison; and the
  STEP 5 trial <-> the PMOS (Polyendocrine Metabolic Ovarian Syndrome)
  cohort. All three were initially authored as `supports`, each citing
  a directionally-consistent secondary finding (a weight-related
  improvement) -- Codex review on PR #233 correctly caught that none of
  the three actually confirm the *target* record's own specific claim:
  SURMOUNT-1's target claim is a placebo-*relative* WHtR improvement,
  which an uncontrolled single-arm cohort cannot confirm; the
  tirzepatide-vs-semaglutide record's claim is the head-to-head
  comparison itself, which an uncontrolled semaglutide-only cohort says
  nothing about; and the PMOS record's actual research question is
  ovulatory/menstrual restoration, not body weight, which STEP 5 never
  tested. Corrected all three to `contextualizes` -- real magnitude
  context, never counted as agreement toward a claim the source
  evidence doesn't actually address, the same supports-vs-contextualizes
  discipline M59's own SURMOUNT-1/tirzepatide-vs-semaglutide edges
  already established, mis-applied here on first pass. Most of this
  tier's remaining candidates were spurious matches on generic shared
  concepts (`Patients`, `Adult`, `Risk`) or genuinely different
  intervention/outcome domains despite moderate textual similarity
  (e.g. GLP-1 receptor agonists and psoriasis, GLP-1 receptor agonists
  and rotator cuff disease) -- left alone. `ke graph-build` run against
  the corrected `relationship_records.jsonl`: relationship edges
  14 -> 17 (0 `supports`, 3 `contextualizes` added this milestone).

### Changed

- **`docs/roadmap.md`**: marked the corpus-wide Evidence Intelligence
  dashboard done under "Planned: Reviewer & Evidence Intelligence
  Tooling" -- it shipped in `knowledge-engine-web` (PR #21,
  `knowledge_engine_web/dashboard.py`, `GET /dashboard`) but this repo's
  own roadmap doc still listed it as unbuilt. Documentation sync only,
  no code change in this repo.

- **`docs/roadmap.md`** and **`docs/future_ideas.md`**: marked the
  remaining three "Planned: Reviewer & Evidence Intelligence Tooling"
  items done -- the live confidence-gauge visual (`knowledge-engine-web`
  PR #22), the "what changed" report (PR #23), and the side-by-side
  relationship-candidate compare page (`GET
  /relationship-candidates/{a}/{b}`, PR pending) -- all shipped in
  `knowledge-engine-web` but this repo's own docs still listed them as
  unbuilt or not yet scheduled. Documentation sync only, no code change
  in this repo.

- **M65 follow-up: `study_type` vocabulary-granularity question
  resolved as accepted (naming only), `classify_study_type` unchanged.**
  Investigated by running the real classifier against the actual
  parsed pages behind every M65 disagreement, not just comparing label
  strings. The `retrospective_observational_cohort`/
  `prospective_observational_cohort` naming gap is a real,
  mostly-mechanical mismatch (roughly 40% of cases have the exact
  prefix phrase in-text, collapsed under the generic `cohort_study`
  label today) mixed with unrelated coverage gaps and a precedence
  false-positive -- not cleanly fixable by renaming alone. The
  `systematic_review_meta_analysis` naming gap looked similar but is
  not: 3 of 4 ground-truth `systematic_review` records also contain
  literal "meta-analysis" wording (discussing prior meta-analyses, not
  performing one), so a co-occurrence-based widening would misclassify
  true systematic-review-only papers rather than fix the mismatch.
  Decisive factor, scoped to the naming-alias subset only:
  `evidence_intelligence.py`'s `_STUDY_DESIGN_WEIGHTS` table already
  weights both naming conventions identically, so Evidence Quality
  scoring is unaffected by that subset either way. The coverage-gap
  and precedence-false-positive cases found in the same investigation
  are **not** covered by this "no downstream effect" reasoning --
  those assign a genuinely different weight than the record's true
  design, feed straight into automated-promotion draft records via
  `run_extraction_review_for_paper`, and remain a real, open
  extraction-accuracy issue for a future milestone. See
  `docs/roadmap.md`'s Item 5 section for the full investigation.

### Fixed

- **Drive backup pilot: service accounts can't write here.** Confirmed
  live: a bare Google service account has no Drive storage quota on a
  personal (non-Workspace) account -- reads work (ACL sharing), every
  write failed with `403 storageQuotaExceeded`. Replaced the
  service-account auth just added for `ke-drive-backup-pilot` with a
  stored OAuth refresh-token credential
  (`KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS`/`--credentials`)
  that authenticates as the human account's own identity instead -- the
  one that actually owns the quota -- via the standard `refresh_token`
  grant, so routine runs still need no interactive step. New
  `knowledge_engine.google_drive_oauth_refresh` module. `ke-corpus-pdf-backup`
  still uses a service account and likely has the same latent bug,
  undiscovered because nothing had exercised a real write live -- not
  fixed here, flagged for its own follow-up.

### Added

- **Drive backup pilot: unattended-safe.** `ke-drive-backup-pilot`
  implements ambiguous-upload orphan reconciliation: on any upload
  failure, it lists the destination folder and matches candidate
  orphans by exact name, byte count, content SHA-256, and the run's own
  time window. A single match is deleted automatically before the
  failure propagates; more than one match raises a new
  `AmbiguousOrphanError` naming every candidate instead of guessing.
  Both preconditions `docs/google_drive_backup_pilot.md` gated recurring
  automation on are now met.

- **M64**: authored 4 more real `RelationshipRecord`s (2 `supports`, 2
  `contextualizes`), growing the graph from 7 to 11 relationship edges.
  Generated via `ke relationship-review-worksheet --rank-by-similarity
  --limit 15` and reviewed each pair's full PICO/`result_summary` text by
  hand: a real-world obesity/cardiometabolic cohort and Gao et al.'s
  meta-analysis each report the same body-weight-reduction direction as
  the existing STEP 5/SELECT cluster in populations that cluster did not
  test (`supports`); a head-to-head tirzepatide-vs-semaglutide comparison
  cannot directly confirm or refute a placebo-controlled finding, so it
  links to both SELECT and the SURMOUNT-1 waist-to-height-ratio analysis
  as `contextualizes` instead. While reviewing the worksheet, found and
  removed a second duplicate evidence record (see Removed below).
- **M57**: `docs/evidence_intelligence_design.md`, a deterministic,
  no-LLM confidence-scoring design -- Evidence Quality, Evidence
  Consensus, and Claim Confidence as three separate, never-collapsed
  numbers, plus corpus-relative Evidence Coverage and a
  reliability-labeled confidence-of-confidence. Scoped to exactly Stage
  3 of `ai_layer_architecture.md`'s 5-stage build sequence and exactly
  the Clinical Medicine profile, grounded in the real 155-record GLP-1
  corpus's actual fields (no `sample_size` field exists yet; `study_type`
  is free text with 18% missing; only 3 of 155 records currently
  participate in a relationship edge). Design only -- no computation
  code yet. Revised after owner review: the automated-vs-manual
  extraction-rigor gap narrowed from 40-vs-15 to 40-vs-25 points, since
  an automated record's content may be accurate even before a human
  confirms it.
- **M58**: implements M57's design -- `knowledge_engine/evidence_intelligence.py`
  (`compute_evidence_quality`, `compute_evidence_consensus`,
  `compute_claim_confidence`, `compute_evidence_coverage`,
  `render_synthesis`, all pure functions, no LLM) and `ke
  evidence-intelligence --evidence <records.jsonl> --evidence-record-id
  <id> [--output <path.md>]`. Live-verified against the real corpus:
  the STEP 5 trial claim (two `supports` edges from M56) scores
  Evidence Quality 94/100, Evidence Consensus 100/100, Claim Confidence
  96/100; a claim with no relationship edges honestly shows "not yet
  assessable" rather than a guessed score. Evidence Quality, Evidence
  Consensus, and Claim Confidence always render as three separate
  fields, never one collapsed number.
- **M59**: authored 4 more real `RelationshipRecord`s (3 `supports`, 1
  `contextualizes`), growing the graph from 3 to 7 relationship edges.
  With M56's 2+-shared-concept candidate pool exhausted (`ke
  graph-relationship-candidates --min-shared-concepts 2` now returns
  zero pairs), reviewed the remaining single-concept candidates' full
  PICO/`result_summary` text by hand: an observational obesity/
  cardiometabolic cohort, a heart-failure-with-reduced-ejection-fraction
  cohort with a real control arm, and a PMOS cohort each report the same
  body-weight-reduction direction as the existing STEP 5/Gao/SELECT
  cluster in populations that cluster did not test (`supports`); a
  head-to-head tirzepatide-vs-semaglutide comparison cannot directly
  confirm or refute a placebo-controlled finding, so it is linked as
  `contextualizes` instead. `unconfirmed_claims` drops from 152 to 148.
- **M60**: `ke relationship-review-worksheet --evidence <records.jsonl>
  [--min-shared-concepts <n>] [--limit <n>] [--offset <n>]` -- batches
  `ke graph-relationship-candidates`' exact candidate pairs into one
  worksheet with both claims' full PICO fields side by side, plus a
  fill-in-the-blank `RelationshipRecord` JSON template per pair. Removes
  the mechanical busywork of opening each evidence record separately
  (the manual assembly done by hand for every M56/M59 relationship) --
  adds no candidate-selection or ranking logic of its own, and never
  infers, scores, or suggests a relationship.
- **M61**: `ke relationship-review-worksheet --rank-by-similarity` --
  re-sorts candidates by cosine similarity of `outcome`/`result_summary`
  text (M31's local, offline `sentence-transformers` generator) instead
  of raw shared-concept count, now that the 2+-shared-concept tier is
  exhausted. Ranking only, never a relationship judgment. Live-verified
  against the real corpus: surfaced a genuinely more comparable pair
  (SELECT trial vs. an observational cardiometabolic cohort, both
  body-weight outcomes, similarity 0.75) ahead of the raw ordering's
  weaker first pick.
- **M62**: `ke evidence-review-queue --evidence <records.jsonl> [--limit <n>]`
  -- prioritizes the corpus's 122 still-automated (M52) evidence records
  for manual review by real structural signal: a record already
  touching a relationship edge ranks above one merely appearing in a
  relationship candidate pair, which ranks above everything else. Never
  a judgment about a record's own content or accuracy -- purely about
  where review effort already has visible impact.
- **M63**: `ke evidence-intelligence --format json`, the structured,
  machine-readable sibling of the existing Markdown report -- same
  Evidence Quality/Consensus/Claim Confidence/Coverage numbers as a
  versioned JSON object (`schema_version: 1`) instead of prose, for a
  consumer (starting with `knowledge-engine-ai`) that needs to parse
  results programmatically rather than scrape text. Same reasoning `ke
  evidence-report --format json` was added for; no new computation, only
  a new output shape.

### Removed

- Removed `auto-55fae17f118de202`, a duplicate evidence record: the same
  paper (DOI `10.1177/14791641261467888`) as
  `ev-tirzepatide-vs-dpp4-heart-failure-001`, extracted twice -- once by
  hand (clean, human-reviewed) and once by M52's automated pass (garbled,
  misaligned PICO fields, still `extraction_status: draft_review_required`,
  `research_question` a broken templated non-question). Same pattern as
  the SURMOUNT-1 duplicate found in M56/M59's review; found this one
  while reviewing M64's `relationship-review-worksheet` output. Kept the
  manual record. Removed its now-orphaned `graph_claims`/
  `graph_claim_concepts` rows from the local graph too -- it had no
  relationship edges to clean up.
- Removed `auto-9f4eaa1682215164`, a duplicate evidence record: the same
  paper (DOI `10.1007/s40618-026-02883-7`) as `ev-tirzepatide-surmount1-whtr-001`,
  extracted twice -- once by hand (clean, human-reviewed) and once by
  M52's automated pass (garbled, misaligned PICO fields, still
  `extraction_status: draft_review_required`, `research_question` a
  broken templated non-question). Kept the manual record, which has
  every field the automated one was missing or had wrong. Removed its
  now-orphaned `graph_claims`/`graph_claim_concepts` rows from the
  local graph too -- it had no relationship edges to clean up.

### Added

- **M56**: authored the real GLP-1 corpus's first `RelationshipRecord`s --
  3 `supports` edges linking the STEP 5 trial, Gao et al.'s meta-analysis,
  and the SELECT trial, all independently reporting the same direction
  (semaglutide reduces body weight versus placebo). Filtered from
  `ke graph-relationship-candidates`'s 308 structural candidate pairs down
  to the 3 with 2+ shared PICO-resolved concepts, each reviewed against
  the full evidence-record text before authoring a rationale -- never
  auto-accepted. `data/corpora/glp1_weight_loss/relationship_records.jsonl`
  (new), validated with `ke relationship-validate`, graph rebuilt with
  `ke graph-build --relationships`. The real corpus's `graph_claim_relationships`
  count moves from 0 to 3.

### Changed

- Reorganized `docs/`: moved 50+ milestone build logs and the original
  VS3-VS17 vertical-slice prototype narrative into `docs/history/`,
  leaving `docs/` root as living reference (architecture, design, and
  policy docs only). Added `docs/README.md` and `docs/history/README.md`
  as navigation indexes. See `docs/README.md` for the current map.

### Added

- Added the `ke corpus-import` CLI command for persisted, local-only corpus imports.
- Added pre-persistence duplicate evidence decisions with exact-duplicate skipping and
  probable-match review outcomes.
- Added linked resume and retry behavior with explicit execution and review statuses.
- Added provenance-preserving metadata preview and Crossref enrichment boundaries.
- Added a controlled 100-paper rehearsal report and deterministic scale-readiness
  assessment for the next bounded corpus rehearsal.
- Added typed expected parser and duplicate-resolution failure contracts.
- Added the controlled 500-paper rehearsal report (M14, issue #21): a fresh
  import and a linked resume against the same manifest snapshot both reconciled
  exactly with zero failures, zero issues, and a fully idempotent resume,
  yielding a `PROCEED` decision.
- Added `docs/phase2_design.md`, the implementation-ready Phase 2 design
  (mirroring `docs/phase1_design.md`'s role for Phase 1): architecture,
  extraction-record schema reuse, testing strategy, and open questions for
  automated claim/evidence extraction.
- Added the M15 Phase 2 foundation (issue #89): page/span-level extraction
  provenance. `PyMuPDFParser` now normalizes text per page and
  `ParsedPaper.pages` preserves page boundaries a document-level join used to
  discard; a new `paper_pages` table persists this so a future extracted claim
  can cite an exact `(page_number, offset)` span instead of only a page count.
  `ke evidence-validate` now validates `source_span`'s shape and requires a
  non-empty `extraction_status`, and `ke evidence`/`ke answer --evidence`/
  `ke evidence-report` display each record's real `extraction_method` instead
  of a hardcoded manual label.
- Added the M16 deterministic structured-section detection (issue #91):
  `knowledge_engine.extraction.detect_sections` locates methods/results/
  limitations-style IMRAD sections within a paper's parsed pages by
  conservative heading-pattern matching (no new dependency, no statistical
  model), returning page/offset-bounded `SectionSpan` records. Sections may
  span multiple pages. A paper with no recognizable headings simply produces
  zero sections rather than a guessed default. Not yet wired into any CLI
  command or evidence-record generation -- claim extraction against these
  spans is a later milestone.
- Added the M17 deterministic claim-candidate sentence detection (issue #94):
  `knowledge_engine.extraction.detect_claim_candidates` locates candidate
  claim sentences within a paper's `results`/`conclusion` sections (from M16)
  by conservative signal matching -- a percentage, p-value, confidence
  interval, or explicit comparative phrase -- using a deterministic,
  abbreviation-aware sentence splitter (no new dependency, no statistical
  model). A sentence with no such signal is never treated as a candidate.
  Stops short of PICO extraction, evidence-direction classification, and
  `EvidenceRecord` generation, which remain later milestones.
- Added the M18 deterministic claim framing-cue classification (issue #98):
  `knowledge_engine.extraction.classify_claim_framing` classifies each M17
  claim candidate by how its sentence frames itself relative to prior work
  the text itself references -- `contextualizes`, `contradicts`, `qualifies`,
  or `unclassified` when no such cue is present. This is deliberately not the
  evidence-record schema's `evidence_direction` field, which is defined
  relative to a `research_question` a claim candidate does not have; a
  candidate is never defaulted to a supports-equivalent label absent an
  explicit cue.
- Added the M19 draft extraction review-item generation (issue #101):
  `knowledge_engine.extraction.build_draft_evidence_items` combines a claim
  candidate, its M18 framing classification, and a paper's own `paper_id`/
  `doi`/`title` into a `DraftEvidenceItem` -- the first piece of the Evidence
  Layer. Every field with an honest deterministic source (`claim_text`,
  `result_summary`, `source_span` including the paper's `paper_id` so a
  DOI-less paper's offsets are still traceable, `source_doi`, `source_title`,
  `source_type`, `extraction_method`, `extraction_status`) is populated;
  every field requiring real judgment or external input
  (`research_question`, `evidence_direction`, PICO fields, `study_type`,
  `limitations`, `uncertainty_notes`, `confidence_note`, `provenance`) is
  explicitly `None`, never a guessed placeholder. A draft item is not a
  valid `EvidenceRecord` and is confirmed to fail
  `_validate_evidence_record`'s existing checks until a reviewer completes
  it. No CLI command, JSONL writer, or schema change.
- Added the `ke extraction-review-generate` CLI command (M20, issue #104):
  runs the full deterministic Extraction Layer pipeline (M16 section
  detection, M17 claim candidates, M18 framing classification, M19 draft
  evidence items) against one persisted paper, identified by `--paper-id`
  since a paper's `doi` is nullable and `title` is not a unique identity in
  this repository, and writes the resulting draft items to a JSONL review
  queue at `--output`. A separate, opt-in command -- never invoked by
  `corpus-import` -- so an extraction issue can never affect import
  success/failure semantics, resolving an explicitly open question in
  `docs/phase2_design.md`. A paper with zero persisted pages (pre-M15, or
  the documented `paper_pages` backfill gap) produces an explicit
  diagnostic rather than a silently empty result; zero draft items from a
  paper that does have pages is a valid, clearly reported outcome.
- Added the `ke extraction-review-promote` CLI command (M21, issue #107):
  promotes reviewer-completed draft extraction items (M20's JSONL output,
  after a human has filled in `research_question`/`evidence_direction`/etc.)
  into real `EvidenceRecord` rows, closing the extraction-to-evidence loop
  for the first time. Adds zero new judgment logic -- it validates and
  persists only what a reviewer already supplied, reusing
  `_validate_evidence_record` (the same validator `ke evidence-validate`
  uses) unchanged. Administrative fields a promotion tool -- not a
  reviewer -- owns (`schema_version`, a deterministic `evidence_record_id`,
  and default `review_status`/`review_checklist`/`review_notes`) are
  filled in automatically, never overwriting a value already supplied.
  Promotion is idempotent (re-running on the same completed input does not
  create duplicate rows) and append-only (an existing `evidence_records.jsonl`
  is never overwritten or truncated). An incomplete record is never
  promoted; it is reported with the exact validation errors and the command
  exits non-zero, while any other valid records in the same input are still
  promoted.
- Added the `ke paper-pages-backfill` CLI command (M22, issue #110):
  backfills `paper_pages` rows for papers imported before M15, exactly as
  scoped in that milestone's tracked follow-up (issue #89). Re-parses a
  paper's original local PDF using the same deterministic `PyMuPDFParser`
  normalization already trusted at import time, but only persists the
  result once the freshly computed `content_hash` matches the paper's
  already-persisted one -- a mismatch (the file at `source_path` may have
  changed since import) is reported, never silently backfilled. A missing
  source file is reported with a clear reason rather than silently
  skipped, and one paper's parse failure never aborts the rest of the
  batch. Supports `--dry-run`. Idempotent: a paper that already has pages
  is never reprocessed by a repeated run.
- Constrained `extraction_status` to a closed vocabulary (M23, issue #117):
  `ke evidence-validate` now rejects any `extraction_status` value outside
  `ALLOWED_EXTRACTION_STATUSES = {"draft_review_required",
  "draft_manual_prototype"}` -- the only two values anything in this
  codebase actually produces -- instead of accepting any non-empty string.
  Also validates `source_span.start_offset`/`end_offset` when present: both
  must be given together, as non-negative integers, with
  `start_offset < end_offset`, matching how the M19 extraction pipeline
  already populates them.
- Added the Relationship Layer's first slice (M24, issue #120): a
  human-authored evidence-relationship schema and the `ke
  relationship-validate` CLI command. Reuses `evidence_direction`'s exact
  vocabulary (`ALLOWED_RELATIONSHIP_TYPES = {"supports", "contradicts",
  "qualifies", "contextualizes"}`). Validates structurally always (required
  fields, unique `relationship_id`, allowed `relationship_type`, no
  self-referential links, non-empty `provenance`) and, when an `--evidence`
  file is given, validates referentially (both endpoints of a relationship
  must actually exist in that evidence file; a dangling reference is
  reported, never silently accepted). Automated relationship detection is
  explicitly not implemented -- `core` validates a human-supplied
  relationship's shape, never decides or suggests one itself.
- Added `extraction_runs` persistence (M25, issue #123): `ke
  extraction-review-generate` now records a durable row per invocation
  (`paper_id`, `output_path`, page/section/candidate/draft-item counts, and
  all four extraction-stage rules versions) in a new schema-version-5
  `extraction_runs` table, so a paper's extraction history can be found
  without re-reading every JSONL file the command has ever produced. `core`
  never automatically re-runs extraction on a ruleset-version change -- a
  human decides when to re-invoke the command for a given paper. No new
  `extraction_items` table: each draft item's own JSONL row already carries
  its full rules-version context, so a second database copy of the same
  data would only duplicate it.
- Added the M26 deterministic study-type classification and limitations
  extraction (issue #129): `knowledge_engine.extraction.study_design`
  classifies a paper's own stated study design (randomized controlled
  trial, meta-analysis, systematic review, cohort/case-control/
  cross-sectional/pilot/observational study) from an explicit cue in its
  Abstract or Methods section, and extracts a paper's own stated
  limitations from an explicit "Limitations" heading. Both are the first
  slice of deterministic, non-human-typed PICO-adjacent extraction (see
  `docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed Fields
  section) -- paper-intrinsic facts, not judgment relative to a research
  question, extracted the same conservative way M17/M18 extract claims: a
  missing signal produces `None`, never a guess. Wired into `ke
  extraction-review-generate`, which now populates `study_type` and
  `limitations` on every generated draft item when detected. Bumps the
  database to schema version 6: `extraction_runs` gains a fifth rules-version
  column, `study_design_rules_version`, alongside the four M25 added, and
  each draft item's own `extraction_context` gains the same field, so a
  future study-design ruleset revision doesn't leave `study_type`/
  `limitations` provenance unrecorded at either the run or item level.
- Added the M27 corpus-library snapshot (issue #133): `ke
  corpus-library-export --output <path>` copies a local database's
  paper-intrinsic content -- `papers`, their `paper_pages`/`paper_texts`,
  and the `journals`/`authors`/`keywords` they reference -- into a fresh,
  standalone SQLite file, deliberately excluding operational tables
  (`import_runs`, `extraction_runs`) that describe one machine's own
  history rather than the corpus itself. `ke corpus-library-import --input
  <path>` hydrates a local database from a snapshot; a paper whose
  `content_hash` already exists locally is skipped, so importing the same
  or an overlapping snapshot twice is idempotent, and
  journals/authors/keywords are matched by their existing natural unique
  key rather than duplicated. This exists because the working SQLite
  database is gitignored (large, environment-specific, and every session
  in this project's remote execution environment starts from a fresh
  clone), so nothing downloaded and parsed today would otherwise survive
  past the current session -- see `docs/roadmap.md`'s "Scaling beyond 500
  papers for Phase 2 tuning" section.
- Added the `ke-corpus-pdf-backup` CLI command and `docs/corpus_pdf_backup.md`:
  a skip-existing bulk backup of local corpus PDFs to the allowlisted
  `source_documents.pdf` Google Drive folder, addressing the same
  gitignored-PDFs-don't-survive-the-session gap as the corpus-library
  snapshot above, for the raw PDFs themselves. Authorizes with a
  service-account JSON key (never committed, kept outside the repository)
  exchanged for a short-lived `drive.file`-scoped OAuth token via a
  hand-rolled JWT-bearer flow (`knowledge_engine.google_drive_service_account`,
  using `cryptography` for RS256 signing) rather than the full
  `google-api-python-client`/`google-auth` SDKs, matching
  `google_drive_http.py`'s existing minimal-dependency Drive transport.
  Reuses the existing `ConstrainedDriveAdapter` for destination-ancestry and
  upload-readback verification and adds a new paginated
  `GoogleDriveHttpTransport.list_files` method; a local PDF is skipped only
  when its filename and SHA-256 both already match a Drive file, so a
  changed file with the same name is re-uploaded rather than silently
  skipped. One file's upload failure does not abort the run; the command
  uploads everything it can and reports failures in its summary.
- Grew `data/corpora/glp1_weight_loss/sources.csv` by 81 records (the first
  small automated discovery batch, `retstart=0`, toward the project owner's
  "at least a couple thousand papers" target -- 84 initially accepted, 3
  later held once a v7 adjudication-ruleset fix corrected a pediatric-scope
  gap) and committed the first
  `data/corpus_library/obesity_metabolic_disease_library.sqlite3` snapshot
  (84 papers total, including the pre-existing prototype rows) produced by
  `ke corpus-library-export`.
- Grew `sources.csv` by another 72 records (the second discovery batch,
  `retstart=250`, under the v7 pediatric-scope ruleset from the start; the
  v8/v9 correction-notice and co-occurrence rules landed afterward and this
  batch was re-adjudicated under v9, holding 1 further correction-notice
  record; a further single record, a persistent-hiccups case report whose
  abstract named type 2 diabetes only as an incidental unrelated
  comorbidity, was manually excluded after Codex review flagged it, since
  v9 deliberately reverted the automated same-sentence co-occurrence rule
  that would otherwise have caught it) and refreshed the corpus-library
  snapshot (156 papers total; a follow-up correction PR then manually
  excluded a second incidental-comorbidity false positive found by
  applying the same review to the already-merged `retstart=0` batch,
  leaving 155 papers -- see the `### Fixed` entry below).
- Grew `sources.csv` by another 86 records (the third discovery batch,
  `retstart=500`, fully under the v9 ruleset). Proactively screened all 90
  automatically accepted records for the incidental-comorbidity
  false-positive pattern (a single-patient case report whose abstract
  names a target disease term only as unrelated patient background) before
  acquisition, since v9 has no automated rule for it; found and manually
  excluded 3 further matches (TB peritonitis in a dialysis patient with
  diabetes, S. hominis endophthalmitis in a diabetic patient, and
  immune-checkpoint-inhibitor toxicity in a bladder-cancer patient with
  chronic kidney disease and diabetes -- in each case the disease term was
  purely background, unrelated to the paper's actual intervention). A
  Codex review then caught a fourth, differently-shaped false positive: a
  basic cervical-cancer biology paper whose abstract matched only because
  it used a xenograft mouse strain literally named "non-obese diabetic
  (NOD)-SCID," unrelated to metabolic disease -- excluded, and the rest of
  the batch was re-checked for the same mouse-strain-name term collision
  (one further hit, "Experimental models in diabetes research," was
  confirmed genuinely on-topic and kept). Refreshed the corpus-library
  snapshot (241 papers total, 493 authors).
- Grew `sources.csv` by another 76 records (the fourth discovery batch,
  `retstart=750`). Applied both known false-positive screens proactively
  before acquisition (incidental-comorbidity case reports and
  NOD-SCID/mouse-strain-name term collisions); found and manually excluded
  1 incidental-comorbidity match pre-acquisition, a BCGitis case report (a
  granulomatous cystitis complication of intravesical BCG therapy for
  bladder cancer) in which type 2 diabetes was purely patient background.
  No mouse-strain-name collisions found. A Codex review then caught a
  second incidental-comorbidity record the pre-acquisition screen had
  missed because its title didn't literally say "case report" (only its
  venue, "JCEM case reports," did): an adrenal-insufficiency case report
  in which obesity was one of several incidental presenting signs,
  unrelated to the paper's actual topic (long-term high-dose
  ethinylestradiol use). Excluded it and broadened the screen to also
  check venue names. Individually re-reading every case-report-style
  accepted record in the batch (rather than relying on the title-keyword
  filter alone) found one further miss: a title that names the disease
  term directly ("Case Report: Uremia secondary to acute pyelonephritis in
  a patient with type 2 diabetes mellitus") does not guarantee the mention
  is central rather than incidental -- the patient's diabetes was
  well-controlled background, unrelated to the paper's actual topic
  (glucocorticoid-treated tubulointerstitial nephritis). Excluded it; the
  remaining two "JCEM case reports" records were confirmed genuinely
  on-topic (their titles directly name tirzepatide and semaglutide as the
  intervention) and kept. Refreshed the corpus-library snapshot (317
  papers total, 718 authors).
- Grew `sources.csv` by another 70 records (the fifth discovery batch,
  `retstart=1000`). Individually read every case-report-style accepted
  record (by title or venue) and every NOD-SCID/mouse-strain-name
  collision before acquisition, per the process established in the
  `retstart=750` batch. Found and excluded 1 incidental-comorbidity match:
  a case report on apremilast treatment for a rare skin disorder (acquired
  reactive perforating collagenosis) in which type 2 diabetes was one of
  several stable, unrelated patient comorbidities. Initially judged a type
  1 diabetes multi-omics paper (referencing "non-obese diabetic (NOD)"
  mice as a real T1D research model, not an incidental term collision) as
  on-topic and kept it -- Codex reviews on the PR then caught three
  further problems this narrower check had missed: that same T1D paper
  should have been held under `exclusion_criteria.md`'s explicit "type 1
  diabetes-specific without evidence applicable to the committed Phase 1
  scope" rule regardless of the NOD-mice question; a lymphoma
  drug-resistance study matched only because "FTO" expands to "fat mass
  and obesity-associated," a gene name unrelated to metabolic disease; and
  a rare-genetic-disease EHR mapping study whose only type-2-diabetes
  mention was one incidental example finding about an unrelated disease
  (myotonic dystrophy). Excluded all three. Net: 70 of 74 automatically
  accepted records remain. Refreshed the corpus-library snapshot (387
  papers total, 871 authors).
- Grew `sources.csv` by another 106 records (the sixth discovery batch,
  `retstart=1250`, the largest yet at 111 automatically accepted). Applied
  the full false-positive screen (case-report-style rows by title or
  venue, gene/mouse-strain-name lexical collisions, type 1
  diabetes-specific titles) before acquisition, excluding 1 case report
  whose reported intervention (vagus nerve stimulation) treated a
  coexisting condition (epilepsy) rather than the diabetes named in the
  title. A Codex review on the growth PR then flagged 3 further records as
  failing basic title-scope criteria (a quality-of-life survey with no
  treatment findings, an osteoarthritis mechanism review, and a
  contrast-media safety study with obesity as an incidental risk-factor
  mention); a full manual review of the batch prompted by that finding
  identified roughly a dozen more candidates in the same shape (drugs
  studied for unrelated diseases, analytical-chemistry method papers,
  broad mechanism-only reviews, and further incidental disease mentions).
  Per the project owner's explicit direction that this corpus-building
  phase should prioritize breadth over precision for now, only the
  clear-cut cases (the Codex-flagged 3 plus one further unambiguous
  wrong-disease match, a cancer-cachexia genetics paper matching only the
  generic English phrase "a complex metabolic syndrome" rather than the
  corpus's named disease entity) were held; the remaining borderline
  mechanism/chemistry-adjacent papers were kept. Net: 106 of 111
  automatically accepted records remain. Refreshed the corpus-library
  snapshot (493 papers total, 1117 authors).
- Grew `sources.csv` by another 112 records (the seventh discovery batch,
  `retstart=1500`; 120 automatically accepted, 1 excluded as a cross-batch
  duplicate already present from `retstart=1250`). Screened only the
  clear-cut patterns going forward (per the volume-priority direction
  above), not exhaustive gray-area sweeps: excluded 5 further records --
  4 single-patient case reports where type 2 diabetes or obesity was
  purely incidental patient background unrelated to the reported condition
  (a fungal prostatitis infection, a ciliopathy genetics case, an
  incidental angiographic finding, and uremic pericarditis/cardiac
  tamponade), and 1 type 1 diabetes-specific mechanistic study held under
  `exclusion_criteria.md`'s explicit rule. A Codex review on the growth PR
  then flagged 2 further records as failing the same clear-cut patterns: a
  COVID-19-booster/influenza mortality study where obesity and diabetes
  were only incidental comorbidities in the prediction model rather than
  the studied condition, and a childhood-obesity narrative review whose
  title's "Adult" referred to a future disease burden being projected for
  a pediatric study population, not the actual (adult) subjects. Both were
  held. Net: 112 of 120 automatically accepted records remain. Refreshed
  the corpus-library snapshot (605 papers total, 1388 authors).
- Added M28 deterministic PICO extraction
  (`knowledge_engine.extraction.pico.extract_pico`): population,
  intervention, comparator, and outcome, each the first sentence matching
  an explicit cue (a numeric cohort-size clause for population;
  received/administered/randomized to/etc. for intervention;
  versus/compared with/placebo/etc. for comparator; primary outcome/
  endpoint/etc. for outcome) within Abstract/Methods (and also Results for
  comparator/outcome). Patterns were tuned by reading a real sample of the
  605-paper `glp1_weight_loss` corpus's actual abstracts rather than
  guessed speculatively -- the corpus only reached a size the project
  owner judged sufficient for this once M14's growth loop was
  deliberately stopped. No new dependency, no LLM, and the same
  absence-over-guessing discipline as M17's claim candidates and M26's
  `study_type`/`limitations`. Wired into `ke extraction-review-generate`
  alongside M16-M26's pipeline; adds
  `extraction_runs.pico_extraction_rules_version` (schema version 7).
  Promoted M26's private, unshared section-text and heading-stripping
  helpers to `knowledge_engine.extraction.sections.section_text`/
  `section_content` so this module could reuse them exactly rather than
  risk a third divergent copy -- the same lesson the
  `ClassifiedPaperRepository` bug below had just taught.
- Added M29 `ke relationship-report`, expanding the Relationship Layer
  past M24's validate-only first slice with a pure Markdown display
  layer -- not automated detection, which remains a human judgment call
  per M24's "never decide truth" boundary. A reviewer could previously
  validate a `relationships.jsonl` file but had no way to actually read
  one, since it only stores two `evidence_record_id` strings, a type, and
  a rationale. `ke relationship-report <path> --evidence
  <evidence_records.jsonl> [--output report.md]` reuses
  `relationship-validate`'s and `evidence-validate`'s checks completely
  unchanged as the sole correctness gate, refuses to render anything if
  either file is invalid or a reference is dangling, and renders each
  relationship's type and rationale next to the `claim_text`/
  `source_title`/`source_doi`/`evidence_direction` of the two evidence
  records it links. No database change -- relationships remain
  file-only, matching how evidence records themselves have always
  worked.
- Added M30, Phase 3's first milestone: a pluggable
  `knowledge_engine.vector_search` package (`VectorIndex` interface,
  `FaissVectorIndex` local implementation, `EmbeddingGenerator` interface
  with no implementation yet) and two CLI commands,
  `ke embedding-index-build --vectors <jsonl> --index-path <path>` and
  `ke vector-search --index-path <path> --query-vector <json>`. Per
  `docs/phase3_design.md`'s option 3, no embedding-generation code exists
  yet, so these commands operate on externally-supplied vectors only --
  `embedding-index-build` parses and validates a JSONL file any external
  tool produced, referentially checks every `paper_id` against the local
  database, builds/updates the FAISS index, and persists
  `Paper.embedding_model`/`embedding_id`; `vector-search` takes an
  already-embedded query vector (not free text) and returns ranked papers
  with their real metadata, explicitly labeled "vector similarity only,
  not lexical search." Added `faiss-cpu` as a new dependency (no
  PyTorch or other heavy transitive dependency); already anticipated by
  the roadmap's "local FAISS" goal, unlike the still-open
  embedding-generation dependency decision. Free-text semantic search
  remains blocked on that decision.
- Added M31: resolved `docs/phase3_design.md`'s embedding-generation
  decision as "both". Added `SentenceTransformerEmbeddingGenerator`
  (`knowledge_engine.vector_search.local_generator`, local
  `sentence-transformers` model, default `all-MiniLM-L6-v2`, fully
  offline once weights are cached) and `OpenAiEmbeddingGenerator`
  (`knowledge_engine.vector_search.openai_generator`, OpenAI's
  `/v1/embeddings` endpoint over stdlib `urllib` -- no SDK, matching
  every other outbound HTTP client in this project -- requires
  `KE_OPENAI_API_KEY`), both implementing `EmbeddingGenerator`. Added
  `ke embedding-generate --generator local|openai --output <jsonl>`,
  which embeds each paper's title/abstract (one vector per paper) and
  writes the same vectors-file format `ke embedding-index-build` already
  consumes; M30's ingestion/build/search commands are unchanged. Added
  `sentence-transformers` as a new dependency, with PyTorch pinned to the
  CPU-only wheel index (`https://download.pytorch.org/whl/cpu`) on
  Linux/Windows rather than the default GPU/CUDA build, since this
  project runs single-machine and offline and the default build pulls in
  an unused multi-gigabyte NVIDIA CUDA toolkit; macOS resolves `torch`
  from the default PyPI index instead, since the CPU-only wheel index
  publishes no macOS wheels at all (found by a Codex review on PR #155,
  which would otherwise have blocked `poetry install` on macOS entirely).
- Added M32: `ke vector-search` now accepts `--query-text <text>
  --generator local|openai [--model <name>]` as an alternative to
  `--query-vector <json>` -- embedding a free-text query live with either
  M31 generator before searching, instead of requiring every query to be
  pre-embedded out-of-band first. Exactly one of `--query-vector`/
  `--query-text` must be given; either way the query's embedding_model is
  checked against the index's recorded embedding_model before searching.
  `ke search`/`ke answer` remain lexical-only (FTS5); combining lexical
  and semantic results into one ranked list is still a separate,
  undesigned question.
- Added M33: `QdrantVectorIndex` (`knowledge_engine.vector_search.qdrant_index`),
  the second `VectorIndex` implementation, targeting a collection on an
  operator-run Qdrant server (this project does not stand one up). The
  collection is created on first use and validated against the expected
  dimension on reuse, mirroring `FaissVectorIndex.load`'s dimension check.
  Score is squared Euclidean distance, matching `FaissVectorIndex`'s
  convention exactly -- Qdrant's own Euclidean-distance score is *not*
  squared, verified empirically against `qdrant-client`'s embedded
  local-mode client since Qdrant's own docs do not state this precisely.
  Requires an `embedding_model` identifier: every point's payload records
  it, and reusing an existing *non-empty* collection is rejected unless
  its recorded model matches -- the same embedding-model-mixing bug class
  a Codex review found in the FAISS path on PR #154, found again by a
  Codex review on PR #157 before this backend ever shipped (see Fixed
  below). Added `qdrant-client` as a new dependency (small transitive footprint:
  `grpcio`, `httpx`, `numpy`, `pydantic`, `protobuf`, `portalocker`,
  `urllib3` -- no heavy ML runtime). Tests
  (`tests/test_qdrant_index.py`) inject `qdrant_client.QdrantClient(":memory:")`
  -- the client's own embedded local mode -- so the suite exercises real
  `qdrant-client` code paths deterministically without a live server.
  Scoped to the class and its tests only; CLI wiring
  (`ke embedding-index-build`/`ke vector-search` targeting a Qdrant
  collection instead of a local FAISS file) is deliberately deferred
  until a real operator need for it appears, matching how
  `docs/phase3_design.md` already framed Qdrant support before this
  milestone.
- Added M34: Europe PMC as a second automated discovery source alongside
  M14's PubMed/PMC pipeline (`docs/m34_europepmc_discovery.md`). New
  `ke europepmc-candidate-discover` and `ke europepmc-candidate-review-prepare`
  commands, backed by `knowledge_engine.europepmc_http`
  (bounded HTTPS transport, `www.ebi.ac.uk` only, mirroring `ncbi_http.py`),
  `knowledge_engine.europepmc_discovery` (single-call discovery against
  Europe PMC's `resultType=core` REST API, cursor-based pagination via
  `cursor_mark`/`next_cursor_mark` rather than PubMed's offset-based
  `retstart`), and `knowledge_engine.europepmc_candidate_review` (a
  deliberately separate, independently versioned adjudication engine --
  `EUROPEPMC_ADJUDICATION_RULES_VERSION` -- since identity anchors on DOI
  rather than PMCID and full-text location has no single official bucket
  to allowlist the way PMC's S3 bucket has). For records already in PMC,
  Europe PMC's own "PDF" is a rendered view of the exact same PMC content
  M14 already acquires via NCBI's official bucket; such candidates are
  still discovered and reported, never silently dropped, but explicitly
  rejected (`DUPLICATE_OF_PMC_PIPELINE_SCOPE`) to avoid duplicating M14's
  own pipeline through a less-official endpoint. Extracted the scope
  (`knowledge_engine.scientific_scope`) and license
  (`knowledge_engine.license_rules`) evaluation logic out of
  `candidate_review.py` into shared modules with zero behavior change
  (verified: M14's existing test suite passes unmodified), since those
  criteria are the same regardless of which pipeline found a candidate.
  Scoped to discovery and adjudication only -- not wired into acquisition,
  and does not resume corpus growth, which remains intentionally frozen at
  605 papers by the project owner's prior decision.
- Added M35: CORE as a third automated discovery source alongside M14's
  PubMed/PMC and M34's Europe PMC pipelines (`docs/m35_core_discovery.md`).
  New `ke core-candidate-discover` and `ke core-candidate-review-prepare`
  commands, backed by `knowledge_engine.core_http` (bounded HTTPS transport,
  `api.core.ac.uk` only, mirroring `europepmc_http.py`),
  `knowledge_engine.core_discovery` (single-call discovery against CORE's
  `/v3/search/works/` REST API, offset-based pagination via
  `offset`/`next_offset`, and an optional `KE_CORE_API_KEY` setting that
  raises CORE's otherwise low unauthenticated rate limit), and
  `knowledge_engine.core_candidate_review` (a third, independently
  versioned adjudication engine -- `CORE_ADJUDICATION_RULES_VERSION`).
  CORE's API never returns a license field at all (confirmed empirically by
  enumerating every key in a real response), so `evaluate_license(None)` is
  called for every candidate and always returns
  `incomplete_missing_license`: no CORE candidate can ever auto-accept, a
  deliberate and honest consequence rather than a bug to work around. PMC/
  Europe PMC overlap detection is a known, deliberate limitation for this
  milestone, since CORE's response never includes a PMCID. Scientific-scope
  and license rules are shared with M14 and M34's engines
  (`scientific_scope.py`, `license_rules.py`). Scoped to discovery and
  adjudication only -- not wired into acquisition, and does not resume
  corpus growth, which remains intentionally frozen at 605 papers by the
  project owner's prior decision.
- Added M36: Unpaywall as a fourth evidence source, but as a per-DOI
  OA-location/license *lookup tool* rather than a fifth discovery pipeline
  (`docs/m36_unpaywall_lookup.md`). Unpaywall's `/v2/search` endpoint
  returned a consistent `HTTP 500 Internal Server Error` across multiple
  distinct queries and retries at build time (confirmed empirically), so
  there was no reliable endpoint to build a `--query` discovery command
  against; its working per-DOI endpoint (`GET /v2/{doi}`) also carries no
  scientific-scope signal and no single canonical host to allowlist the
  way CORE (`core.ac.uk`) and Europe PMC (`europepmc.org`) do -- every URL
  it returns points to some third-party publisher or repository. New
  `ke unpaywall-doi-lookup` and `ke unpaywall-batch-lookup` (bounded to
  100 DOIs) commands, backed by `knowledge_engine.unpaywall_http` (bounded
  HTTPS transport, `api.unpaywall.org` only) and
  `knowledge_engine.unpaywall_lookup` (per-DOI OA-status/license evidence,
  with a small normalizer mapping Unpaywall's real `cc-by`-style license
  tokens to the format the shared `license_rules.py` expects before
  evaluating). Makes **no** accept/reject/hold decision of its own --
  intended to enrich a DOI already surfaced (and possibly `held`) by
  `pubmed_discovery.py`, `europepmc_discovery.py`, or `core_discovery.py`
  with Unpaywall's own OA-location/license evidence. Requires
  `KE_UNPAYWALL_EMAIL` (Unpaywall's usage policy requires a contact email
  on every request); the commands fail cleanly before any network access
  if it is unset. Not wired into acquisition, and does not resume corpus
  growth, which remains intentionally frozen at 605 papers by the project
  owner's prior decision.
- Grew the corpus 605 -> 677 papers via the existing M14 PMC pipeline
  (discovery retstart=1750): 250 candidates discovered, 112 deterministically
  accepted, 36 already present (query overlap, filtered before acquisition),
  76 net-new PMC OA PDFs acquired and imported via a linked resume run
  against the prior import. A Codex review on the growth PR caught 4 false
  positives the deterministic v9 ruleset let through -- a pediatric-titled
  paper whose title's forward-looking "Adult" outcome term evaded the
  pediatric check, two type 1 diabetes-specific papers, and one incidental
  dermatology case report -- excluded from `sources.csv`, and the local
  database rebuilt from the corrected manifest. The corpus is no longer
  intentionally frozen -- see `docs/roadmap.md`'s "Scaling beyond 500
  papers for Phase 2 tuning".
- Added gzip-compressed `corpus_library` snapshot support (M27):
  `export_corpus_library_compressed`/`import_corpus_library_compressed`,
  wired into `ke corpus-library-export`/`ke corpus-library-import` via a
  `.gz` output/input suffix. Growing the corpus past ~605 papers made the
  snapshot exceed GitHub's 100MB single-file push limit (137.75MB
  uncompressed at 681 papers, confirmed as real page-level text growth via
  `VACUUM`, not bloat); a first attempt to fix this by no longer
  git-committing the snapshot at all was reverted after a Codex review
  correctly pointed out that reproducing it required the raw PDFs to
  already be durably archived, which they were not (the Google Drive
  backup was itself broken -- see below). Compression (roughly 3x on this
  corpus's text, ~44MB at 677 papers) restores headroom without giving up
  git-committed durability. See `docs/m27_corpus_library.md`'s
  "Persistence policy" section.
- Added M37: `ke manual-pdf-preview`/`ke manual-pdf-manifest-draft`
  (`docs/m37_manual_pdf_preview.md`). `ke import`/`ke corpus-import` have
  always accepted any local PDF; what was missing was a way to add one
  without hand-typing a `sources.csv` row. `manual_pdf_preview.py` wires
  `PyMuPDFParser` (the same parser `ke import` already uses -- local
  title/authors/abstract/DOI/page-count/word-count extraction, no network)
  together with an optional Unpaywall (M36) DOI lookup into one small
  reviewable preview JSON, then `export_manual_pdf_manifest_draft` turns
  an approved preview into one manifest-ready CSV row (the exact
  `sources.csv` schema), refusing outright unless `license_rule_result`
  is exactly `"passed"` -- never guessed. Never touches `sources.csv`
  directly, matching `manifest_curation_cli.py`'s existing draft-only
  contract for the automated pipelines. Exported
  `normalize_unpaywall_license` from `unpaywall_lookup.py` (previously
  private) so this module normalizes a raw Unpaywall license token (e.g.
  `"cc-by"`) to `license_rules.py`'s expected format before calling
  `license_deed_url` -- caught by a live smoke test, not a unit test,
  since the original hand-authored preview fixtures used an
  already-normalized license string that never exercised the real
  `prepare_manual_pdf_preview` -> `export_manual_pdf_manifest_draft` path;
  added an end-to-end regression test that drives both functions together.
- Grew the corpus 677 -> 735 papers via the existing M14 PMC pipeline
  (discovery retstart=2000): 250 candidates discovered, 121 deterministically
  accepted, whittled to 81 across two self-audit rounds (23 excluded before
  export; 17 more of the resulting net-new candidates excluded after a
  Codex review on the growth PR caught 2 the first pass had missed and
  prompted a stricter re-check of every accepted title against
  `inclusion_criteria.md`'s explicit two-part requirement -- an approved
  scope term *and* a named therapeutic intervention, both in the title),
  40 already present (query overlap, filtered before acquisition), 41
  net-new PMC OA PDFs acquired and imported via a fresh corpus import
  (677 -> 718). The first self-audit round re-found the
  previously-documented incidental-comorbidity-case-report and
  T1D-specific patterns (6 more case reports, 1 more T1D-specific paper).
  The second round's stricter title check found 29 more records the
  ruleset had wrongly accepted -- 17 of them this batch's own net-new
  candidates, removed; 12 already present in the corpus from an earlier,
  already-merged batch, left as documented follow-up cleanup rather than
  retroactively edited by this PR -- because the target disease appeared
  only as an incidental covariate deep in an abstract about an unrelated
  primary disease (hemodialysis frailty, COPD hypoxemia, ventilator-weaning
  prediction, heart-failure diuretic resistance, park walkability), or
  because the record was a mechanism-only review, a data-quality or
  measurement-comparison methodology paper, a risk-prediction model, or a
  conceptual framework with no treatment evidence. Also documented, as a
  separate known follow-up not fixed by this batch: `PyMuPDFParser`'s
  title extraction is unreliable for some publisher PDF layouts (Cureus's
  peer-review-date banner, Frontiers' article-type header), leaving ~7% of
  the whole corpus's imported `Paper.title` values wrong (50 of 718,
  confirmed by direct query; 42 of these predate this batch) since
  `PaperRepository._build_paper` never falls back to the manifest's
  curated title. See `data/corpora/glp1_weight_loss/README.md`'s
  "Current Status" section for the full pattern breakdown.
- Fixed the `PyMuPDFParser` title-extraction gap documented above:
  `CorpusIngestionService`/`LinkedCorpusIngestionService` now pass the
  manifest row's own title (`item.title`, sourced from PubMed/PMC
  bibliographic metadata and required by `REQUIRED_CSV_HEADERS`) through
  to `PaperRepository._build_paper`/`add_parsed_paper` as
  `manifest_title`, which wins over `parsed.title` when present. The
  single-file `ke import` command has no manifest to consult and keeps
  using `parsed.title` exactly as before. A fresh corpus-import
  confirmed this fixes all 50 of the corpus's previously wrong titles
  (Cureus's "Review began MM/DD/YYYY" banner, Frontiers' "TYPE Review"
  header), not just future imports, since the fix lives in the shared
  persistence path rather than the parser itself. Regenerated the
  compressed `corpus_library` snapshot accordingly.
- Cleaned up the corpus 718 -> 706 papers: removed the dozen
  already-merged records (from earlier `retstart` batches, predating
  PR #163) matching the title-lacks-intervention pattern documented
  above -- each re-confirmed against its full abstract before removal,
  same bar as PR #163's own exclusions. Also ran the deterministic
  ruleset's `evaluate_scientific_scope` function directly against each
  excluded title/abstract and found it returns `"passed"` for every
  one: the function evaluates disease/intervention terms over
  title+abstract combined (not title-only, unlike its pediatric check)
  and its intervention-term list is generic enough to match
  incidentally in nearly any clinical abstract. Documented as an open,
  explicitly-not-acted-on follow-up in
  `data/corpora/glp1_weight_loss/README.md`, since tightening it would
  change future batches' `accepted`/`held` outcomes and could
  reclassify already-included papers if applied retroactively -- a
  corpus-inclusion-philosophy call for the project owner, not this
  cleanup. Fresh corpus-import (706 imported, 0 failed) and regenerated
  compressed `corpus_library` snapshot.
- Fixed 3 more records a Codex review on the cleanup PR caught: 2 had
  been correctly identified as false positives during the `retstart=2000`
  abstract review but were dropped by mistake when the final exclusion
  list was compiled (a transcription oversight, not a judgment error);
  the third was a third instance of the same incidental-obesity-covariate
  pattern, dating to the much earlier `retstart=500` batch, found via a
  full-corpus regex sweep the review comment prompted. Corpus: 706 ->
  704. That same sweep surfaced roughly 90 more titles with neither a
  scope term nor an intervention term present -- deliberately left
  unaudited and unremoved, since re-auditing the whole corpus's
  precision this way is exactly the kind of tightening the project
  owner asked to defer until after more milestones land. Fresh
  corpus-import (704 imported, 0 failed) and regenerated compressed
  `corpus_library` snapshot.
- Grew the corpus 704 -> 800 papers via the existing M14 PMC pipeline
  (discovery retstart=2250): 250 candidates discovered, 97
  deterministically accepted, 1 already present (query overlap,
  filtered before acquisition), 96 net-new PMC OA PDFs acquired and
  imported via a fresh corpus import. Deliberately ran with no manual
  audit layer this time, per the project owner's explicit direction to
  prioritize shipping milestone after milestone over further precision
  tightening -- and per this project's own "Working-version review
  policy" (`docs/roadmap.md`, Phase 1), which already states repository
  execution must not depend on manually reviewing individual candidates
  before a working version exists; the `retstart=2000` batch's manual
  self-audit rounds went beyond what that policy calls for. Regenerated
  the compressed `corpus_library` snapshot (~52MB, well under GitHub's
  100MB limit) and updated the corpus README's "Current Status" section.
- Fixed a real bug a Codex review on the `retstart=2250` growth PR
  caught: `Paper.doi` (`PaperRepository._build_paper`) and duplicate
  detection (`resolve_duplicate_before_persistence`) both preferred
  `parsed.doi` -- the PDF's own extracted DOI, which can be a truncated
  in-text citation (e.g. `10.1172/jci` instead of the full
  `10.1172/jci.insight.198707`) -- over the manifest's correct,
  PubMed/PMC-sourced DOI. Beyond storing the wrong DOI, this had a more
  serious consequence: a truncated parsed DOI falsely collided with an
  unrelated already-imported paper, silently routing a genuinely new
  paper to `needs_review` and dropping it from the imported corpus
  entirely, undercounting the manifest's own advertised paper count.
  Extended the same `manifest_title`-wins pattern from the M27 title fix
  to `doi`: `CorpusIngestionService`/`LinkedCorpusIngestionService` now
  pass `item.normalized_doi` through as `manifest_doi`, which wins over
  `parsed.doi` in both `_build_paper` and duplicate resolution. Added
  two regression tests: one proving `Paper.doi` prefers the manifest DOI,
  one reproducing the exact false-collision scenario end-to-end. Also
  fixed a genuine study-level duplicate the same review caught --
  consecutive-DOI Portuguese and English translations of one
  knee-arthroplasty study -- by keeping the English row. Corpus corrected
  800 -> 799; fresh corpus-import and regenerated compressed snapshot.
- Grew the corpus 799 -> 880 papers via the existing M14 PMC pipeline
  (discovery retstart=2500): 250 candidates discovered, 81
  deterministically accepted, 0 already present, 81 net-new PMC OA PDFs
  acquired and imported via a fresh corpus import. Ran the same
  no-manual-audit way as the `retstart=2250` batch, now with the
  manifest-DOI-preference fix in place: `ke corpus-import` completed
  with 880 imported, 0 failed, 0 skipped -- an exact one-to-one match
  against the manifest's 880 rows, confirming the false duplicate-DOI
  collision class of bug did not recur. Regenerated the compressed
  `corpus_library` snapshot (~60MB, still under GitHub's 100MB limit)
  and updated the corpus README's "Current Status" section.
- Fixed 13 scientific-scope false positives a Codex review on the
  `retstart=2500` growth PR caught: 2 explicitly flagged (an
  incidental-comorbidity pulmonary-infection case report, an explicitly
  type 1 diabetes-specific study) plus 11 more found by abstract-verifying
  the rest of the batch's title-level misses per the review's own
  invitation -- eating-disorders prevalence, a Prader-Willi sarcopenia
  diagnostic-tool study, a policy-only case-finding brief, an unrelated
  anal-fistula surgery study, a Weight-Adjusted-Waist-Index/brain-health
  association study, a multi-disease COVID-era review, a
  light-exposure/dementia study, an unrelated MS lifestyle-factors study,
  a hypertension/LV-geometry review, a kidney-cancer epidemiology study,
  and an arsenic-exposure/pregnancy-CVD review. All match already-
  established exclusion patterns (incidental comorbidity,
  diagnostic/measurement-only, policy-only, off-target primary disease),
  not new gray-area calls. 4 titles from the same sweep were kept after
  review (a cagrilintide mechanism study, ROHHAD syndrome, and two
  adipokine/AGE mechanism reviews under the explicit mechanism-only
  breadth-over-precision carve-out). Corpus corrected 880 -> 867; fresh
  corpus-import (867 imported, 0 failed) and regenerated compressed
  snapshot.
- Added the M34 Europe PMC acquisition service, closing the gap
  `docs/m34_europepmc_discovery.md` explicitly left open ("Acquisition ...
  is out of scope for M34 ... that is a separate, not-yet-authorized
  milestone"). Mirrors M14's `reviewed_approval.py` -> `pmc_acquisition.py`
  shape but as its own independently versioned pair matched to Europe
  PMC's real schema differences (Europe PMC ID/DOI-anchored identity
  instead of PMCID, `europepmc.org` -- Europe PMC's own hosted full-text
  repository -- as the only allowlisted PDF host instead of PMC's S3
  bucket): `europepmc_reviewed_approval.py`
  (`export_europepmc_reviewed_approvals`) re-verifies every adjudication
  rule result on each accepted worksheet record and selects an exact
  subset in worksheet order; `europepmc_reviewed_approval_cli.py` exposes
  it as a standalone `export` command; `europepmc_acquisition.py`
  (`EuropePmcOaAcquisitionService`) cross-checks every approval against
  its source candidate (DOI, license, PDF URL, plus Europe-PMC-specific
  `open_access is True`/`in_pmc is False` checks), stages every PDF to a
  temporary file, verifies the `%PDF-` signature, and commits the whole
  batch atomically -- any single failure rolls back everything staged or
  written so far, exactly like `pmc_acquisition.py`'s all-or-nothing
  contract. Wired into the CLI as `ke europepmc-oa-acquire`. Added a
  single shared `EUROPEPMC_PDF_HOST` constant to `europepmc_http.py`
  (mirroring `ncbi_http.py`'s `PMC_CLOUD_PDF_HOST` precedent) so the one
  bounded Europe PMC transport allowlists both the discovery REST API host
  and the PDF-acquisition host. Acquisition remains approval-gated and
  does not itself perform corpus ingestion -- acquired PDFs still require
  a separate, explicit `ke corpus-import` run, matching M14's own phased
  history and this project's "no step silently expands its own authority"
  pattern. A bounded live smoke test (real discover -> adjudicate ->
  export -> acquire against open-access, non-PMC preprint candidates)
  found that `europepmc.org/api/fulltextRepo`, the only PDF host this
  pipeline allowlists, consistently returns HTTP 403
  (`"PDF link has expired or is invalid"`) from this project's sandboxed
  execution environment for every candidate tried, while the REST API and
  article HTML pages both responded normally -- see
  `docs/m34_europepmc_discovery.md`'s "Known live-verification gap" for
  the full investigation. The code, tests, and host allowlisting are
  correct against the documented contract; whether the endpoint itself is
  reliably reachable for real acquisition from a non-sandboxed network is
  unverified and flagged for the project owner to re-check. Fixed two real
  bugs a Codex review on the acquisition PR caught: (1) `europepmc-oa-
  acquire` did not track a PDF's temporary file path until after it wrote
  successfully, so a mid-write `OSError` (e.g. a full disk) left an
  untracked `.tmp` file behind that every retry then rejected as an
  existing output -- fixed by registering the path before writing, mirroring
  the same not-yet-fixed pattern in M14's own `pmc_acquisition.py`; (2)
  `europepmc_reviewed_approval_cli.py`'s `export` command defaulted
  `--limit` to 500, an unreachable default since a single discovery page
  never exceeds 100 candidates, so every normal default invocation failed
  with "fewer accepted approvals" -- fixed by making `--limit` optional,
  defaulting to exporting every accepted record when omitted.
- Grew the corpus 867 -> 930 papers via the existing M14 PMC pipeline
  (discovery `retstart=2750`): 250 candidates discovered, 77
  deterministically accepted, 14 already present from query overlap, 63
  net-new PMC OA PDFs acquired and imported. Ran the same no-manual-audit
  way as the prior several batches. This batch's import used linked
  resume (`ke corpus-import ... --resume-from <parent_run_id>`) rather
  than a from-scratch fresh import, since this session's local database
  already held a completed import run for the existing 867 papers
  (restored from the committed compressed snapshot): resume mode skipped
  re-parsing those 867 already-`imported` source_ids and processed only
  the 63 new ones, reporting 63 imported, 0 failed, 867 skipped -- the
  resume-mode equivalent of the exact one-to-one reconciliation prior
  batches got from a fresh import against an empty database. Regenerated
  the compressed `corpus_library` snapshot (~60MB, still under GitHub's
  100MB limit) and updated the corpus README's "Current Status" section.
- Fixed 10 scientific-scope false positives a Codex review on the
  `retstart=2750` growth PR caught: a kidney-cancer epidemiology review,
  an ovarian-cancer/circadian-rhythm review, an unrelated multiple-
  sclerosis outcomes study, two policy-only evidence briefs, a
  Prader-Willi sarcopenia diagnostic-only study, an idiopathic
  intracranial hypertension case report, a type 2 diabetes qualitative
  well-being study naming no intervention, a diabetes knowledge/
  attitudes/practices survey naming no intervention, an alcohol-
  consumption/cancer review, and a bariatric-surgery outcomes study
  explicitly scoped to type 1 diabetes. All match already-established
  exclusion patterns (off-target primary disease, diagnostic/measurement-
  only, policy-only, no-intervention-named, type 1 diabetes-specific),
  not new gray-area calls. Removing already-imported rows required a full
  fresh reimport rather than a surgical row deletion, since this
  session's local database enforces foreign keys (`import_items.
  matched_paper_id` would block a direct `DELETE`): removed the 10 rows'
  PDFs, reinitialized the local database, and re-ran `ke corpus-import`
  against the corrected manifest -- 920 imported, 0 failed, 0 skipped, an
  exact one-to-one match. Corpus corrected 930 -> 920; regenerated the
  compressed snapshot.
- Grew the corpus 920 -> 951 papers via the existing M14 PMC pipeline
  (discovery `retstart=3000`): 250 candidates discovered, 60
  deterministically accepted, 16 already present from query overlap. Of
  the 44 remaining candidates, 3 were exact-duplicate PMIDs of the
  kidney-cancer, diabetes-KAP-survey, and alcohol/cancer false positives
  the `retstart=2750` correction had just removed from `sources.csv` --
  since removing a row doesn't add it to any persistent "already
  rejected" registry, an overlapping later batch can legitimately
  re-discover and re-accept the same PMID under the same v9 ruleset gap.
  Rather than wait for Codex to catch the same three papers twice, all 44
  candidates were checked by title against the categories the last two
  Codex reviews established (off-target primary disease with no scope/
  intervention term, policy-only or prediction-model-only papers with no
  treatment evaluated, type 1 diabetes-specific sources, no-intervention-
  named qualitative/survey studies) before acquisition. 13 matched and
  were excluded: the 3 exact duplicates plus a type 1 diabetes-specific
  adjunct-medications study, an ankle-fracture-fixation study, two
  dementia/Alzheimer's risk-factor studies, a coronary ischaemia-
  reperfusion antiplatelet/antithrombin study, a busulfan pharmacokinetics
  study, a frailty/socioeconomic-inequalities study, a type 2 diabetes
  policy model with no treatment evaluated, a bariatric-surgery weight-
  regain prediction-model study, and a qualitative-interviews study naming
  no intervention. 31 net-new PMC OA PDFs acquired and imported via
  linked resume against the same local import run (31 imported, 0 failed,
  920 skipped). Regenerated the compressed `corpus_library` snapshot
  (~61MB, still under GitHub's 100MB limit) and updated the corpus
  README's "Current Status" section.
- Fixed 8 scientific-scope false positives a Codex review on the
  `retstart=3000` growth PR caught, all failing `inclusion_criteria.md`'s
  explicit two-part title requirement (an approved scope term and a
  named therapeutic intervention): an NHANES observational obesity/
  cardiovascular-disease association study, a hospitalised-adults
  hypoglycaemia-episodes observational study, a T2D-as-covariate STEMI
  in-hospital-outcomes study (off-target primary disease), a diabetic-
  eye-disease progression study, a T2D-development sibling-pairs
  genetics study, and three primary mechanistic/model papers (a novel
  cardiovascular-kidney-metabolic-syndrome mouse model, a macrophage
  lysosomal acid lipase deletion study, an H19 lncRNA prenatal-
  programming study) naming no intervention. Several of these were
  actually flagged correctly during that PR's own proactive title screen
  but dropped when the final exclusion list was compiled -- the same
  transcription-error failure mode a much earlier batch's Codex review
  caught; the rest reflect applying the corpus's "mechanism-only
  reviews" breadth carve-out too broadly, to primary mechanistic
  *research* naming no intervention rather than the review articles the
  carve-out's own wording names. Removing already-imported rows required
  a full fresh reimport (943 imported, 0 failed, 0 skipped, an exact
  one-to-one match). Corpus corrected 951 -> 943; regenerated the
  compressed snapshot.
- Added the M38 Phase 2 extraction scale-readiness assessment: closes
  `docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning"
  section's own named, never-executed prerequisite -- M16-M28's
  deterministic extraction rules had been unit-tested against synthetic
  fixtures and exercised by hand against individual real papers, but
  detection coverage had never been measured in aggregate across the
  real corpus at scale. `knowledge_engine/extraction_corpus_report.py`
  (core aggregation logic, unit tested) plus
  `scripts/m38_extraction_corpus_report.py` (thin CLI wrapper) run the
  same deterministic pipeline `ke extraction-review-generate` runs for
  one paper, across every persisted paper, and report coverage counts --
  read-only, no draft items, extraction runs, or `EvidenceRecord` rows
  produced. Run against the real 943-paper corpus: section detection
  covers 99.7% of papers overall but only 63% for `results`/`conclusion`
  specifically; claim-candidate detection (scoped to those two section
  types) reaches 63.2%, with a diagnosed root-cause split (56% of misses
  are papers genuinely missing those section types entirely, often
  non-quantitative reviews; 44% a real recall gap traced to a concrete
  example -- `PMC13366639.pdf` -- where an inline `"Results:"` label
  never matches M16's deliberately conservative full-line-only heading
  pattern); study-type classification covers 40.6%, an expected
  consequence of an 8-design closed vocabulary against a more diverse
  real corpus; PICO fields range 45-74% individually, 23.3% for all four
  together. No extraction rule was changed -- both diagnosed gaps
  interact with corpus-inclusion-philosophy-adjacent tradeoffs reserved
  for explicit owner decision, the same way `evaluate_scientific_scope`'s
  documented weakness was flagged rather than unilaterally fixed. See
  `docs/m38_extraction_scale_assessment.md`.
- Fixed both M38-flagged extraction recall gaps, since authorized by the
  project owner. `detect_sections` (`SECTION_DETECTION_RULES_VERSION`
  v1 -> v2) now also recognizes an inline `"Label: text"` heading (e.g.
  `"Results: SGLT2 inhibitor use was associated with..."`), not just a
  heading alone on its own line, closing the exact `PMC13366639.pdf`-style
  gap M38 diagnosed; the colon requirement keeps this narrow (`"results"`
  mid-sentence, or a combined heading like `"Results and Discussion"`,
  still matches neither alternative). `classify_study_type`
  (`STUDY_DESIGN_RULES_VERSION` v1 -> v2) grew its closed vocabulary by
  five designs -- `narrative_review`, `cross_over_trial`,
  `retrospective_study`, `case_series`, `case_report` -- ordered so the
  existing more-specific patterns still win. Re-running the M38 report
  after the section-detection fix alone surfaced an unplanned regression:
  every PICO field's coverage dropped (population 425 -> 364, intervention
  563 -> 510, comparator 695 -> 665, outcome 533 -> 503, all-four
  220 -> 184), because a structured abstract's inline `"Background: ...
  Methods: ... Results: ... Conclusion: ..."` layout used to stay one
  undivided `abstract` span that every PICO field already scanned, and now
  correctly splits into `methods`/`results`/`conclusion` fragments PICO's
  original section scoping never covered. Fixed by widening `extract_pico`
  (`PICO_EXTRACTION_RULES_VERSION` v1 -> v2) so population/intervention
  also scan `results` and comparator/outcome also scan `conclusion`. Final
  re-measurement against the same 943-paper corpus: results-section
  detection 63.1% -> 72.4%, conclusion-section detection 64.4% -> 75.6%,
  claim candidates 63.2% -> 72.0%, study type classified 40.6% -> 43.7%,
  PICO all-four-fields 23.3% -> 26.2% -- every signal improved or held
  steady. See `docs/m38_extraction_scale_assessment.md`'s "Resolved
  follow-up" section.
- Added the M39 lexical+semantic search fusion (Phase 3): closes
  `docs/phase3_design.md`'s last open design question, how `ke search`
  (lexical, FTS5) and `ke vector-search` (semantic, FAISS) results combine
  into one ranked list. `knowledge_engine/search_fusion.py` implements
  Reciprocal Rank Fusion (RRF) -- a paper's fused score is
  `sum(1 / (k + rank))` across every ranking it appears in, `k = 60` --
  needing only each system's rank position, not their incomparable raw
  scores (bm25 vs squared L2 distance), so a paper found by both signals
  naturally outranks one found by only one with no cross-system weight to
  tune. A new `ke fused-search <query-text>` command runs both retrieval
  signals against the same free-text query and fuses them;
  `ke search`/`ke answer`/`ke vector-search` are unchanged and remain
  available separately. Live-smoke-tested against a subset of the real
  943-paper corpus: papers matching both signals (e.g. the SELECT and
  STEP 5 semaglutide trials) ranked above single-signal matches as
  expected.
- Added the M40 extraction-review batch generation: the real corpus has
  exactly two `EvidenceRecord` rows, both hand-authored before any
  automated extraction existed, because `ke extraction-review-generate`
  (M19/M20) had only ever run against one paper at a time -- the
  deterministic extraction pipeline, built and (M38/its follow-up)
  measured at scale, had never actually been used to generate the real
  corpus's draft-evidence-item review queue, the material a human
  reviewer works from to promote real evidence. Factored the single-paper
  command's pipeline invocation into
  `knowledge_engine/extraction_review_batch.py`
  (`run_extraction_review_for_paper`, shared by both commands so they
  can't drift apart) plus `run_batch_extraction_review` for
  orchestration, and added a new `ke extraction-review-batch-generate`
  CLI command that writes one combined JSONL queue (every item carries
  its own `source_span.paper_id`, so items stay traceable without
  per-paper files). Still not validated evidence -- `ke
  extraction-review-promote` keeps refusing any item missing a
  human-supplied `research_question`/`evidence_direction`, unchanged. A
  paper with no persisted pages, or whose extraction run cannot be
  recorded, is skipped and reported rather than aborting the whole batch.
  Run against the real 943-paper corpus: 13,588 draft evidence items
  across 943 papers (679 with at least one, 264 with none, 0 skipped for
  missing pages).
- Fixed two performance bugs found by that first live run, both only
  visible at real-corpus scale:
  - The batch command initially reused `_record_extraction_run`, which
    calls `_local_database().initialize()` internally -- reconstructing a
    fresh SQLAlchemy engine and re-running schema migration/FTS setup on
    every one of 943 calls instead of once. Rewrote the command to open a
    single database session for the whole batch.
  - `knowledge_engine/sentence_split.py`'s `_ends_with_abbreviation`
    searched all of `text[:match.start()]` on every candidate sentence
    boundary -- a prefix that grows with the boundary's position in the
    document -- even though only the trailing word or two can ever match
    an abbreviation. Quadratic in document length, latent since
    M17/M28 shipped: a single real ~180K-character paper took 30+ seconds
    in `extract_pico` alone. Bounded the search to a fixed 40-character
    trailing window (results unchanged; no abbreviation or two-word
    combination in the list comes close to that length). Combined, both
    fixes took the real-corpus run from over 20 minutes to 21 seconds.
- Added the M41 reference knowledge layer's first slice:
  `docs/reference_knowledge_layer_design.md` sketched three options
  (stored open-license textbooks, live lookups against free APIs, or
  both) for grounding a paper's claim text against background scientific
  knowledge (mechanisms, lab techniques, chemistry terms) it assumes but
  never restates -- something this project's extraction pipeline has had
  no equivalent for. M41 builds the sketch's recommended live-lookup
  path: a new `ke reference-lookup <term>` command and
  `knowledge_engine/reference_lookup.py`
  (`reference_lookup_http.py`'s `UrllibWikipediaTransport` mirrors
  `unpaywall_http.py`'s host-allowlisted transport pattern) query
  Wikipedia's public REST summary API live for a term's title,
  description, plain-language extract, source URL, and license (always
  `CC BY-SA` when found, a license family `license_rules.py` already
  recognizes), or return `found: false` if Wikipedia has no article --
  never a guess. Explicitly background context, not evidence: never
  routed through `EvidenceRecord` promotion, and never merged into the
  evidence corpus's own search commands (`ke search`/`ke answer`/
  `ke vector-search`/`ke fused-search`). No API key required, unlike
  Unpaywall's `KE_UNPAYWALL_EMAIL`. Every result records its own
  `retrieved_at` timestamp alongside the page's `page_last_modified`, plus
  Wikipedia's own stable `revision` ID and a `permanent_url`
  (`{source_url}?oldid={revision}`) -- added after Codex review noted
  `page_last_modified` (second-resolution) and `source_url` (Wikipedia's
  always-current canonical URL) don't alone pin down the exact content a
  lookup returned -- the reproducibility hook a future consumer citing a
  lookup's result would need, without this milestone needing to build
  caching speculatively ahead of an actual consumer. Live-verified against
  real terms
  (`semaglutide`, `SGLT2 inhibitor`, the `Mercury` disambiguation page,
  and a not-found term) before writing the parser and again after. See
  `docs/m41_reference_lookup.md`.
- Added the M42 reference knowledge layer's second live-lookup source:
  `ke rxnorm-lookup <term>` and `knowledge_engine/rxnorm_lookup.py` query
  NLM's public RxNav REST API (`https://rxnav.nlm.nih.gov/REST/`) to
  resolve a drug name to its own RxNorm concept -- RxCUI, canonical name,
  term type (`"IN"` ingredient, `"BN"` brand name, etc.), and synonym --
  plus its underlying ingredient concept(s), via a dedicated
  host-allowlisted transport (`rxnorm_http.py`'s `UrllibRxNavTransport`,
  since RxNav is a distinct NLM host from the literature-scoped
  `ncbi_http.py`). Chosen as the second source (over MeSH/PubChem/
  UniProt) because it needs no API key and closes a concrete gap M41's
  Wikipedia lookup leaves open for this corpus: a generic drug name
  (e.g. "semaglutide") and its brand name (e.g. "Ozempic") get different
  top-level RxCUIs -- RxNorm's own model correctly keeps a brand product
  and its ingredient distinct -- but resolve to the same `ingredients`
  entry via RxNav's `related.json?tty=IN` relationship, which is what a
  caller compares to recognize them as the same underlying drug;
  Wikipedia's title-matching lookup has no equivalent. Codex review on
  PR #179 caught that the first version of this milestone claimed that
  normalization without actually following the ingredient relationship
  (the top-level `rxcui` was returned unchanged for both names); fixed
  before merge by adding the `related.json` call and `ingredients` field,
  with a regression test asserting `semaglutide` and `Ozempic` resolve
  to the same `ingredients` entry and a combination-drug brand
  ("Glyxambi") resolves to more than one. Explicitly background context,
  not evidence: never routed through `EvidenceRecord` promotion, never
  merged into the evidence corpus's own search commands. RxNorm's
  concept-search permalink is already keyed to a specific RxCUI, so
  (unlike M41's Wikipedia `revision`/`permanent_url` fields) `source_url`
  alone is a stable citation target here. Live-verified against real
  terms (`semaglutide`, `Ozempic`, `empagliflozin`, `insulin`,
  `Glyxambi`, and mechanism-class terms RxNorm correctly does not match,
  like "SGLT2 inhibitor" and "GLP-1") before writing the parser and again
  after. See `docs/m42_rxnorm_lookup.md`.
- Added the M43 reference knowledge layer's third live-lookup source:
  `ke mesh-lookup <term>` and `knowledge_engine/mesh_lookup.py` query
  NCBI's public E-utilities API (`db=mesh`) to resolve a term to its
  canonical NLM MeSH descriptor -- MeSH ID, preferred heading, scope
  note (definition), and entry-term synonyms -- reusing `ncbi_http.py`'s
  existing `UrllibNcbiTransport` directly, since `eutils.ncbi.nlm.nih.gov`
  is already allowlisted for literature discovery (no new transport
  module needed, unlike M42's RxNorm lookup, which required one because
  RxNav is a different host). Chosen as the third source over PubChem
  because it closes a gap neither Wikipedia (prose) nor RxNorm
  (drug-only) does: NLM's own controlled vocabulary for diseases,
  procedures, and biomedical concepts generally. MeSH's `esearch` proved
  to be a full-text search, not an exact-match lookup -- live-verified
  that searching "obesity" returns 37 loosely related candidates whose
  first result ("Anti-Obesity Agents") is the wrong concept, and that
  "SGLT2 inhibitor"/"GLP-1 receptor agonist" each return a true
  descriptor record alongside a near-duplicate "pharmacological-action"
  record sharing the same entry terms -- so the service resolves a term
  only when exactly one candidate is both a true descriptor
  (`ds_recordtype == "descriptor"`) and has the queried term as one of
  its own entry-term synonyms, matched case-insensitively, never the
  closest guess. Confirmed correct for "obesity" -> "Obesity" (MeSH ID
  D009765) and "type 2 diabetes" -> "Diabetes Mellitus, Type 2" (MeSH ID
  D003924, matched via an entry-term synonym since the query doesn't
  match the canonical heading's word order), and confirmed correctly
  `found: false` for "GLP-1 receptor agonist" (singular), since MeSH
  only records the plural entry term. Explicitly background context,
  not evidence: never routed through `EvidenceRecord` promotion, never
  merged into the evidence corpus's own search commands. Live-verified
  against real terms before writing the parser and again after. Codex
  review on PR #182 caught two further gaps before merge: (1) the
  original `esearch` call fetched only the first 20 candidates, when
  "obesity" alone reports 37 (and "cancer" reports 409), so a term
  ranked below the cutoff would falsely resolve to `found: false`; fixed
  by checking `esearch`'s own reported total against what was actually
  fetched (bounded to 200) and declining to resolve rather than
  searching a partial window. (2) the original match logic returned the
  first exact match found while scanning candidates, silently picking
  one if more than one true descriptor happened to share the same exact
  entry term -- contradicting the code's own "resolves only when exactly
  one candidate matches" claim; fixed by collecting every exact match
  and requiring precisely one, treating two-or-more the same as
  zero (`found: false`). See `docs/m43_mesh_lookup.md`.
- Added the M44 reference knowledge layer's fourth and, per the design
  doc's original candidate list, last named live-lookup source: `ke
  pubchem-lookup <term>` and `knowledge_engine/pubchem_lookup.py` query
  NLM/NCBI's public PubChem PUG REST API to resolve a chemical compound
  name to its PubChem Compound ID (CID) and structured chemical
  identifiers -- title, IUPAC name, molecular formula, molecular weight,
  and canonical SMILES -- through a new dedicated, host-allowlisted
  transport (`pubchem_http.py`'s `UrllibPubchemTransport`), since
  `pubchem.ncbi.nlm.nih.gov` is a distinct NLM/NCBI host from both
  `eutils.ncbi.nlm.nih.gov` (M43's MeSH lookup) and `rxnav.nlm.nih.gov`
  (M42's RxNorm lookup). Chosen as the fourth source because it fills a
  gap none of the first three cover: real chemical-structure data (a
  compound's molecular formula, weight, and SMILES string), not just a
  normalized name or a controlled medical-concept vocabulary. Two real
  API behaviors were verified live (`curl`) before writing the parser:
  requesting the `CanonicalSMILES` property (PubChem's older, still
  publicly documented name) returns the result under a *different*
  response key, `ConnectivitySMILES` -- PubChem renamed the property
  internally but left the old request-parameter name aliased without
  renaming the response key to match -- so this module requests
  `ConnectivitySMILES` directly rather than relying on that alias; and
  PubChem indexes whatever name strings were actually deposited
  alongside real compounds, not a curated concept vocabulary --
  querying "GLP-1 receptor agonist" (a mechanism class, not a specific
  drug) resolves to a real, specific compound (CID 177864544) rather
  than an empty result, and this module reports that rather than
  guessing what a caller "probably" meant. `MolecularWeight` is
  tolerated as either a JSON string or number, matching a real variance
  observed in API responses, with a dedicated regression test.
  Explicitly background context, not evidence: never routed through
  `EvidenceRecord` promotion, never merged into the evidence corpus's
  own search commands. Live-verified against real compounds
  (`metformin`, `semaglutide`, `empagliflozin`) and a not-found name
  before writing the parser and again after, via the built CLI. Codex
  review on PR #183 caught two further real gaps before merge: (1) a
  name resolving to more than one compound (live-verified: "estrogen"
  returns two distinct CIDs, 21628493 and 12115739) was silently
  resolved to whichever entry PubChem listed first; fixed to decline
  (`found: false`) whenever more than one candidate matches, the same
  posture M43 uses for ambiguous MeSH matches. (2) the license field
  labeled every result a blanket U.S. government public-domain work, but
  PubChem aggregates data from many external depositors (live-verified:
  CID 4091/metformin's own PubChem-hosted description is sourced from
  ChEBI, not NCBI); fixed to state that provenance is mixed and reuse
  terms should be verified source-by-source rather than asserting a
  specific reuse right. See `docs/m44_pubchem_lookup.md`.
- Added the M45 reviewer-aid annotation step for the reference knowledge
  layer: a new `ke extraction-review-annotate` command reads the draft
  evidence items `ke extraction-review-generate`/
  `extraction-review-batch-generate` already produce and attaches a
  `reference_context` object to each one, built only from PICO fields
  M28's deterministic extraction already populated --
  `intervention`/`comparator` through M42's RxNorm lookup (both name a
  drug or treatment), `population`/`outcome` through M43's MeSH lookup
  (both describe a medical concept). Wires three of
  `docs/reference_knowledge_layer_design.md`'s Addendum items at once: a
  term with no reference-layer match is written out as `found: false`,
  never silently omitted (item 2, coverage-gap flag); every embedded
  result keeps its own `source_url`/`license`/`retrieved_at` (item 3,
  provenance-footer discipline); a reviewer sees the definition inline in
  the same file they edit to add `research_question`/`evidence_direction`,
  before running `ke extraction-review-promote` (item 4, reviewer aid).
  Deliberately a separate, opt-in step from generation: `ke
  extraction-review-generate`/`-batch-generate` must stay network-free
  even at the corpus's real scale (M40: 13,588 draft items across 943
  papers), so annotation is a reviewer-initiated command run against the
  specific paper(s) actually under review. Codex review on PR #184 caught
  two real gaps before merge: (1) the first version passed a PICO field's
  entire raw value to RxNorm's/MeSH's exact-match lookups, assuming M28
  stores an isolated term; re-sampling the real 951-paper corpus showed
  real field values are routinely entire multi-line, citation-laden
  paragraphs (live-verified: passing a full sentence to RxNorm's
  exact-name endpoint returns nothing, even though the drug name alone
  resolves immediately), so the original version returned `found: false`
  for nearly every real draft item. Fixed by scanning a small, bounded
  set of single-word candidates (first 30 tokens, stopwords dropped,
  capped at 20 per field) from the raw text against the unchanged
  exact-match lookups, declining (`found: false`) when more than one
  distinct concept resolves among the candidates tried -- the same
  ambiguity discipline M43/M44 established -- rather than guessing which
  one is "the" term. Live-verified against the real corpus after the fix:
  a comparator field naming both "semaglutide" and "placebo" together
  correctly declines; a fisetin-supplementation paper's
  `comparator`/`population` fields correctly resolve "fisetin" (RxCUI
  2667741) and "screening" (MeSH `D008403`) across every draft item drawn
  from that paper. (2) an empty result queue left a `--force`-targeted
  output file untouched instead of clearing it, risking a stale prior
  run's records being mistaken for current; fixed to always overwrite the
  output path, even when there is nothing to write. With identical
  candidate terms cached within one run, network calls are bounded to the
  number of distinct candidates actually tried, not items -- measured
  honestly, not fast: roughly 30 distinct RxNorm and 30 distinct MeSH
  terms for a single real paper's full draft-item set, on the order of a
  minute or more of network calls. Never touches
  `research_question`/`evidence_direction`, and never changes `ke
  extraction-review-promote`'s existing refusal to promote a record
  missing either. See `docs/m45_extraction_review_annotate.md`.
- Added `docs/core_interface_contract.md`, the `v0.6.0` release
  milestone's "consumable interface" deliverable written ahead of the
  graph: what a future layer (`knowledge-engine-ai` or otherwise) needs
  to configure itself against `core` and consume what it produces --
  `KE_*` environment variables, the CLI as the primary API surface, the
  Evidence Record/Relationship Record/draft-evidence-item/reference-layer
  output schemas, the corpus `sources.csv` shape, and an explicit
  stability note on what's safe to depend on before `v1.0` versus what
  isn't. Restates "the seam" (research_question/evidence_direction/
  confidence rating are never `core`'s to decide) as the one boundary
  every milestone in this repository has held to, now collected in one
  place instead of scattered across each milestone's own doc.
- Added `docs/phase4_design.md`, the implementation-ready Phase 4 design
  sketch (mirroring `docs/phase2_design.md`/`docs/phase3_design.md`'s
  role), written before any Phase 4 code. Grounded in a fresh measurement
  of the real 951-paper corpus rather than the abstract roadmap bullet:
  44% study-type coverage, 26% full-PICO coverage, 12% limitations
  coverage, 0% structured citations (citation-list parsing is real,
  unscoped prerequisite work -- `parser.py`'s `REFERENCE_HEADING_PATTERN`
  only detects where a References section starts, it does not parse
  entries). Resolves the graph backend question: relational tables in the
  existing SQLite database first, behind a `GraphRepository` interface
  mirroring `PaperRepository`, no Neo4j for the first slice -- the same
  "embedded/no-server first, dedicated backend only if a real evidenced
  need appears" sequencing Phase 3 used for FAISS before Qdrant.
  Schema sketch: `graph_concepts` (M41-M45 reference-layer resolutions and
  PICO field values), `graph_claims` (one row per *validated*
  `EvidenceRecord`, never a raw claim candidate), `graph_claim_concepts`
  (the PICO-role-tagged edges between them), `graph_claim_relationships`
  (a graph-queryable projection of M24's existing `RelationshipRecord`s,
  not a replacement for them), and `graph_citations` (designed now,
  deliberately left unpopulated until citation-list parsing is scoped and
  verified against real corpus text). Restates and holds to "the seam"
  explicitly for the phase most likely to tempt a violation of it: typed
  support/contradiction edges are stored, never compounded into a
  confidence rating by `core` itself. Codex review on PR #186 caught
  three real gaps before merge, all fixed: (1) `evidence_record_id`/
  `relationship_id` were described as SQL foreign keys, but
  `EvidenceRecord`/`RelationshipRecord` are JSONL objects with no backing
  table -- `Database` cannot create that constraint; fixed to describe
  them as plain, application-validated string references instead. (2)
  `graph_concepts` stored only identity fields, discarding the actual
  Wikipedia `extract`/MeSH `scope_note`/RxNorm/PubChem content and
  `source_url`/`license` the stated "concept nodes as reference-layer
  content" goal requires; fixed by adding `definition`/`source_url`/
  `license` columns, making a `graph_concepts` row the only durable home
  for a resolved lookup result once it's linked into the graph. (3)
  Stability Score and Tracking the Unknown were listed as Goals with no
  corresponding schema anywhere in the design; fixed by reframing them
  explicitly as this phase's motivation rather than something the first
  schema delivers, with their own schema work named as a deliberately
  deferred Open Question rather than guessed under time pressure.
- Added M46 (`docs/m46_graph_repository.md`), the first Phase 4 code: the
  `graph_concepts`/`graph_claims`/`graph_claim_concepts`/
  `graph_claim_relationships` schema (schema version 8), the
  `GraphRepository` persistence layer (`get_or_create_concept`/
  `get_or_create_claim`/`link_claim_concept`/
  `get_or_create_relationship_edge`, plus traversal queries and
  `population_counts()`), and a new `ke graph-build` CLI command that
  populates the graph from a validated `EvidenceRecord` JSONL file and an
  optional validated `RelationshipRecord` JSONL file, reusing M45's
  `annotate_draft_items` unchanged to resolve PICO fields into RxNorm/MeSH
  concept nodes. `graph_citations` remains deliberately absent, per the
  design doc's Open Questions. Live-verified against the repo's real
  committed evidence corpus (2 hand-authored records): 2 claims, 2
  concepts, 4 claim-concept edges, 0 relationship edges (no relationship
  file exists in the repo yet).
- Fixed two real, Codex-caught gaps on M46's `ke graph-build`/
  `GraphRepository` (PR #187) before merge: (1) resolved RxNorm concepts
  always persisted `definition=NULL`, discarding `name`/`term_type`/
  `synonym` even though `docs/phase4_design.md` documents `graph_concepts`
  as their only durable home -- fixed with a `_rxnorm_definition` helper
  joining those fields, live-verified against the real corpus
  (`"semaglutide; IN"`/`"placebo; IN"`). (2) `concepts_for_claim`/
  `claims_for_concept` had no `.distinct()`, so a claim linked to the same
  concept under two edge roles (which the schema's own unique constraint
  explicitly allows) returned duplicate nodes -- fixed, with a new
  regression test.
- Added M47 (`docs/m47_graph_citations.md`): the citation-list
  real-corpus verification pass `docs/phase4_design.md` called for before
  writing any parsing code, plus the resulting build. Sampling real
  reference-list text found at least three distinct citation styles
  (numbered-period, numbered-bracket, unnumbered author-year) and a rare
  (~1.6% of papers) case where `REFERENCE_HEADING_PATTERN` matches a
  spurious earlier "References" occurrence before the real bibliography
  -- but also found `graph_citations`' own schema only needs DOI-identity
  matching against papers already in the corpus, not structured
  per-entry parsing. Added `knowledge_engine/citation_extraction.py`
  (`find_cited_dois`), the `graph_citations` table (schema version 9),
  `GraphRepository.add_citation_edge`/`citations_for_paper`, and `ke
  graph-citations-build`. Live-verified against the real local
  960-paper corpus: exactly 5 intra-corpus citation edges, individually
  confirmed genuine.
- Added M48 (`docs/m48_graph_report.md`): `ke graph-report`, closing the
  read-side gap M46/M47 left open (the graph could be written to but not
  read back via the CLI). Three modes: no filter reports corpus-wide
  population counts; `--evidence-record-id` reports one claim's concepts
  (grouped by PICO edge role) and relationship edges; `--paper-id`
  reports one paper's citation edges as citer and cited. Added
  `GraphRepository.find_claim_by_evidence_id` (read-only, unlike
  `get_or_create_claim`) and `concept_edges_for_claim` (preserves edge
  role). Markdown output is escaped through a local equivalent of
  `cli.py`'s own Codex-hardened `_report_text`. Also backfilled a real,
  pre-existing gap: `ke graph-build`/`ke graph-citations-build` had never
  been exercised through a `CliRunner`-level test until this milestone
  added `tests/test_graph_cli.py` for all three commands together.
  Live-verified against the real local corpus: summary counts match
  M46/M47's own measurements exactly, and both claim- and paper-mode
  reports render real, correct detail.
- Added M49 (`docs/m49_graph_relationship_candidates.md`): `ke
  graph-relationship-candidates`, the automated relationship
  candidate-surfacing `docs/phase4_design.md`'s Open Questions deferred
  until `graph_claims`/`graph_claim_concepts` existed. Surfaces claim
  pairs sharing a PICO-resolved concept (`--min-shared-concepts` to
  raise the threshold), excluding pairs already linked by a validated
  relationship edge. Structural overlap only -- never infers, detects,
  or suggests a relationship type or rationale, the same boundary `ke
  relationship-validate` already draws. Added
  `GraphRepository.relationship_candidates`. Live-verified against the
  real local corpus: correctly surfaces the one real pair (sharing
  `semaglutide`/`placebo`) and correctly reports zero pairs once
  `--min-shared-concepts` is raised past that real count.
- Added M50 (`docs/stability_and_tracking_design.md`): the dedicated
  Stability Score / Tracking the Unknown design `docs/phase4_design.md`'s
  Open Questions deferred until the graph existed to design against.
  Adds `supersedes` as a fifth `relationship_type` (schema version 10,
  a real SQLite table rebuild since `CHECK` constraints cannot be
  altered in place) -- a newer claim explicitly revising an older one,
  reusing `RelationshipRecord`/`graph_claim_relationships` rather than a
  new table. Scopes an honest, non-inferred "gap" as a claim with zero
  relationship edges of any type. The Stability sub-score formula and a
  richer "weak evidence area" report stay explicitly out of `core`'s
  scope. Live-verified against a copy of the real corpus database: the
  version 10 migration upgraded cleanly from its actual current schema
  version, and a real `supersedes` relationship built, rendered in `ke
  graph-report`, and was correctly excluded from `ke
  graph-relationship-candidates`.
- Added M51 (`docs/m51_graph_unconfirmed_claims.md`): `ke
  graph-unconfirmed-claims`, the first concrete slice of Tracking the
  Unknown to ship -- lists every claim with zero relationship edges of
  any type, the honest, non-inferred "gap" signal M50 already decided
  on. Added `GraphRepository.unconfirmed_claims`. No `research_question`
  grouping, severity ranking, or cross-reference with `ke
  graph-relationship-candidates`'s own output -- all explicitly deferred
  per M50's Open Questions. Live-verified against the real corpus: both
  real claims list as unconfirmed before any relationship exists,
  correctly drops to zero once one real `supports` relationship is
  built between them.
- Added 15 new manually reviewed `EvidenceRecord`s to
  `data/corpora/glp1_weight_loss/evidence_records.jsonl` (17 total, up
  from 2), promoted via `ke extraction-review-promote`. Broadens the
  corpus's evidence base beyond the original narrow GLP-1/weight-loss
  question to `scientific_question.md`'s full frame -- tirzepatide,
  metformin/imeglimin, and SGLT2 inhibitors, including several
  head-to-head drug-class comparisons. `research_question` and
  `evidence_direction` were drafted from each paper's real abstract
  text and explicitly confirmed by a human reviewer before promotion,
  preserving the seam in `docs/core_interface_contract.md`: `core`
  never infers these fields itself. Also surfaced a real data-quality
  finding: `ke extraction-review-batch-generate`'s automated PICO
  extraction is unreliable at this broader corpus scale (e.g.
  `intervention` duplicating `population` verbatim on multiple papers,
  and claim_text length correlating with raw data-table leakage rather
  than substance) -- this batch was built from paper abstracts
  directly instead, not from the automated draft-item pool.
- Added a second, 4-item evidence-promotion batch to
  `data/corpora/glp1_weight_loss/evidence_records.jsonl` (21 total, up
  from 17), deliberately searched for null/mixed/negative findings to
  correct the first batch's all-`supports` skew: a UK population-level
  study finding no evidence of complication-risk change despite rising
  SGLT2-inhibitor use; a network meta-analysis finding no significant
  difference in atrial-fibrillation recurrence risk among SGLT2i,
  GLP-1RA, and DPP-4i; an RCT secondary analysis finding liraglutide
  alone did not improve physical fitness (only exercise did); and a
  systematic review finding GLP-1 receptor agonists did not
  significantly reduce the primary composite CV-death/HF-hospitalization
  outcome across the heart-failure spectrum, with dedicated HF trials
  showing directional harm. The heart-failure record is deliberately
  left in tension with two `supports`-direction semaglutide/HF records
  from the first batch rather than reconciled -- that judgment belongs
  to a human reviewer or a future synthesis layer, not to this record.
- Added a third, 7-item evidence-promotion batch to
  `data/corpora/glp1_weight_loss/evidence_records.jsonl` (28 total, up
  from 21), diversifying subtopic coverage beyond the corpus's existing
  GLP-1/SGLT2i/heart-failure-heavy records: SGLT2i versus sulfonylurea
  biliary-disease risk; DPP-4i once-weekly versus once-daily dosing
  preference; a digital weight-loss goal-difficulty pilot RCT; GLP-1RA
  real-world adherence predictors; a digital-mental-health-intervention
  systematic review for obesity; semaglutide for PMOS menstrual/ovulatory
  function; and SGLT2i effects on left ventricular global longitudinal
  strain. Two candidate papers were deliberately excluded: a narrative
  review too hedged to ground a concrete `result_summary`, and a
  population-epidemiology paper with no actual intervention/comparator
  to fit the corpus's PICO frame.
- Added a "Known Gap" section to `docs/phase2_design.md` documenting the
  `claim_text`/table-data-leakage problem found while building the
  evidence-promotion batches above: `PyMuPDFParser` discards page layout
  geometry, so a multi-row table with no real sentence-terminal punctuation
  becomes one giant "sentence" that trips a claim-candidate signal pattern
  and gets dumped verbatim into `claim_text`. A length- or blank-line-
  density-based patch was investigated and rejected (real long sentences
  and short table dumps are interleaved throughout the length distribution,
  not cleanly separable). `fitz.Page.find_tables()` was tested directly
  against the three worst real table-dump examples in the corpus and caught
  2 of 3 by page and bounding box; the third (a borderless table) was
  missed, matching PyMuPDF's own suggestion to evaluate the `pymupdf_layout`
  package for better detection. Flagged, not fixed here: a real fix needs a
  schema change to persist per-page table regions and a full re-parse of
  all 960 already-ingested papers, matching this project's established
  practice of flagging a well-diagnosed, schema-sized gap for explicit
  owner decision rather than starting a corpus-wide re-parse unilaterally.
- Added table-region detection to fix the `claim_text`/table-data-leakage
  gap above, additively: `PyMuPDFParser` now calls `page.find_tables()`
  per page and populates a new `ParsedPage.table_text`/`paper_pages.table_text`
  (schema v11) field without ever altering `ParsedPage.text` or any offset
  computed against it, preserving source-span traceability. A new
  `knowledge_engine.extraction.table_filter.is_table_derived` helper (with
  empirically-tuned length and word-overlap thresholds) excludes a
  candidate sentence from `detect_claim_candidates`/`extract_pico`/
  `extract_limitations` only when it is long and overlaps heavily with a
  detected table's text; `pico.py`/`study_design.py` were refactored to
  scan sections per-page (matching `claims.py`'s existing precedent) so
  each candidate sentence can be checked against the right page's table
  text. A new `ke paper-pages-table-text-backfill` command re-parses
  already-ingested papers' original PDFs (reusing the M22
  content-hash-verified backfill machinery) to populate `table_text`
  without touching persisted `text`/offsets. Run against the real corpus:
  951 / 960 papers backfilled (9 missing source files, 0 hash mismatches,
  0 parse failures); 1,173 / 14,182 pages across 370 papers had a table
  detected. Full-corpus `ke extraction-review-batch-generate` output went
  from 13,969 to 13,668 draft items (301 table-derived candidates
  excluded); the two largest known table-dump leaks (5,099 and 4,870
  characters) are gone, while a borderless-table case `find_tables()`
  cannot detect remains a documented, honest limitation.
- Populated the real Phase 4 knowledge graph for the first time: `ke
  graph-build`/`ke graph-citations-build` existed since M46/M47 but had
  only ever been exercised against copies of the corpus during
  development, leaving `data/knowledge_engine.sqlite3`'s own
  `graph_claims`/`graph_concepts`/`graph_claim_concepts`/
  `graph_claim_relationships`/`graph_citations` tables at zero rows.
  Validated against a copy first (`graph-build` makes live RxNorm/MeSH
  calls to resolve PICO fields into concepts), then ran both commands
  against the real database, then re-ran `graph-build` after growing the
  evidence base (see the batch-4 entry below) so the merged state
  reflects the current evidence base rather than an immediately-stale
  snapshot -- `get_or_create_claim` makes this safe to re-run, verified
  idempotent on a copy first (re-running against all 33 records produced
  33 claims, not 61). Final real totals: 33 claims, 13 concepts (7 MeSH,
  6 RxNorm), 32 claim-concept edges, 5 intra-corpus citation edges
  (`graph-citations-build` scans every persisted paper's own reference
  list regardless of evidence linkage, so this is already
  full-960-paper-corpus scale, matching M47's original measurement
  exactly). 0 relationship edges, since no validated `RelationshipRecord`
  file exists yet in this repo.
- Added a fourth evidence-promotion batch to
  `data/corpora/glp1_weight_loss/evidence_records.jsonl` (33 total, up
  from 28): the SELECT cardiovascular-outcomes trial's large-scale,
  4-year semaglutide weight-loss result (supports); a GLP-1RA-based-
  therapy-versus-lifestyle waist-circumference meta-analysis whose own
  subgroup comparison was not statistically significant despite each
  arm being independently significant (qualifies); a postbiotic
  (pasteurized Akkermansia muciniphila) RCT whose primary, pre-
  registered whole-body-insulin-sensitivity endpoint was null in the
  intention-to-treat population despite positive exploratory subgroup
  signals, including increased endogenous GLP-1 excursion (contradicts);
  a real-world, manufacturer-co-authored tirzepatide patient-motivation
  and access-barrier survey (contextualizes); and a migrant-women
  diabetes-prevention lifestyle-intervention systematic review whose own
  authors rate certainty of evidence low to moderate (qualifies). Each
  record was built by reading the paper's real stored text directly
  (not the automated draft-item pool), following batch 3's practice.
- Added M52, automated `research_question`/`evidence_direction`
  classification, removing the mandatory human-confirmation step
  batches 1-4 above required. The project owner judged that step a
  bottleneck disproportionate to its accuracy benefit (every hand-built
  batch classified correctly) and authorized automating it -- see
  `docs/core_interface_contract.md`'s "The seam" section for the full,
  honest accounting of what changed. New
  `knowledge_engine.extraction.evidence_classification` module:
  `generate_research_question` templates a draft item's own
  already-extracted PICO fields (M28) into a fixed sentence pattern,
  declining (never guessing) when a field is missing or implausibly
  long; `classify_evidence_direction` extends M18's self-referential
  framing cue patterns (`knowledge_engine.extraction.direction`) with
  null-result phrasing cues, defaulting to `supports` when no cue
  fires -- safe here specifically because the research question is
  mechanically derived from the same claim, unlike M18's original
  context. New `ke extraction-review-autoclassify` CLI command feeds
  directly into the existing, unmodified `ke extraction-review-promote`
  (which never actually verified who filled a record's fields, only
  that they were present and well-formed). Every automated record is
  honestly labeled: `extraction_method` names the ruleset version, never
  `manual_human_review`, and `review_notes` states plainly that no human
  read or confirmed it.
  Run against the real corpus: of 13,668 draft items, 2,870 (21%) were
  eligible (had all four PICO fields, each under the 300-character
  template-safety cap, plus `claim_text`/`result_summary`); direction
  distribution skewed heavily toward `supports` (2,782), reflecting
  that most result-bearing sentences carry no explicit contrast/hedge/
  null-result cue even when the underlying finding is more nuanced. A
  25-item hand-reviewed spot check found the `qualifies` (null-result)
  classification reliable (8/8 correct) and the `contextualizes`/
  `contradicts` cue reuse from M18 defensible but imperfect (some
  within-study "in contrast to" comparisons get the same label M18
  reserved for contrasting *external* prior work). The more consequential,
  honestly-reported finding: roughly a quarter of the sampled `supports`
  records were baseline-characteristic or methods-description sentences
  that M17's pre-existing claim-candidate detection flags as a "claim"
  but that do not represent a genuine intervention-effect direction --
  a known M17 limitation this module does not fix, and one this
  automated default-to-`supports` policy makes more visible rather than
  less. Applied a first bounded batch (not all 2,870 at once, since `ke
  graph-build`'s network-lookup cost scales with the whole evidence
  file, not just new records): one eligible record per paper, 123
  records across 123 distinct papers, appended to
  `data/corpora/glp1_weight_loss/evidence_records.jsonl` (156 total, up
  from 33). Re-ran `ke graph-build` against the grown evidence base
  (validated on a copy first; ~42 minutes for 156 records' worth of
  RxNorm/MeSH lookups, confirming M52's own bottleneck-consciousness
  extends to this command too -- a real follow-up item, not fixed here).
  Real graph totals: 156 claims, 78 concepts (50 MeSH, 28 RxNorm), 156
  claim-concept edges, 5 citation edges (unchanged, since citations
  don't depend on evidence), 0 relationship edges.
- Added M53, a durable rejected-PMID ledger, closing a real gap
  `docs/roadmap.md` has documented since the `retstart=3250` batch: a
  previously-rejected PMID resurfacing under a later discovery batch's
  different `retstart` offset, because `sources.csv` only records what
  is currently included, not what has already been reviewed and
  rejected. New `knowledge_engine.rejected_candidates` module: a
  per-corpus CSV keyed by `pmid`, one row per rejection with a fixed
  `reason_category` vocabulary matching this project's established
  exclusion patterns (off-target primary disease, diagnostic/
  measurement-only, no intervention named, policy/prediction-model-only,
  type-1-diabetes-specific, mechanism-only primary research, duplicate,
  other). Two new CLI commands: `ke rejected-candidates-add` appends a
  batch of already-decided rejections (never re-deciding one itself,
  the same validate-only posture as `ke evidence-validate`), never
  overwriting an existing pmid's row -- the first recorded reason wins;
  `ke rejected-candidates-check` splits a fresh discovery batch into
  net-new versus already-rejected before any review time is spent,
  reading either a raw discovery JSON's `"candidates"` list or an
  adjudication worksheet's `"items"` list. A real prerequisite for
  unattended, continuously-scheduled discovery: manually re-reading
  README history to catch a resurfacing PMID does not survive a
  pipeline nobody is watching in real time. Historical exclusions
  predating this ledger were never recorded with an exact PMID, so they
  are not backfilled -- reconstructing them by fuzzy title matching
  would risk exactly the kind of silent misidentification this ledger
  exists to prevent; a known, accepted gap, not a defect.
- Added M54, making `ke graph-build` incremental. It previously called
  `annotate_draft_items` (RxNorm/MeSH network lookups) on the *entire*
  `--evidence` file every run, re-looking-up every already-persisted
  claim's PICO fields on every subsequent run -- a real, measured
  bottleneck at real corpus scale (42 minutes for 156 records) that
  would only get worse as the evidence base grows, and would not
  survive a continuously-scheduled discovery/extraction pipeline. New
  `GraphRepository.find_claim_ids_by_evidence_ids` (bulk, read-only)
  lets `graph-build` determine, before doing any network work, which
  `evidence_record_id`s already have a `graph_claims` row -- safe to
  skip entirely, since a claim row only ever exists inside a prior
  fully-committed `graph-build` transaction (one atomic transaction;
  see `Database.session()`'s commit-at-exit/rollback-on-exception
  behavior), meaning its concept links were already resolved too.
  Live-verified against a copy of the real, now-156-record corpus
  database: re-running `graph-build` with an unchanged evidence file
  dropped from 42 minutes to 2.5 seconds, with identical final totals
  (156 claims, 78 concepts, 156 claim-concept edges, 5 citation edges).
  Also verified against the real production database directly (same
  result, no changes). New tests prove zero network calls on a
  re-run against an unchanged evidence file, and exactly one lookup
  for the one new record in a mixed already-graphed/new-record batch.
- Added M55, `ke discovery-cycle-run`, the first schedulable slice of
  continuous discovery -- see `docs/m55_discovery_cycle.md`. Chains one
  page of `pubmed-candidate-discover`, M14's existing deterministic
  scope/identity/license/full-text adjudication (unchanged), and an M53
  rejected-PMID ledger cross-check into a single command with its own
  persisted pagination state (`knowledge_engine.discovery_cycle`), ready
  for cron/systemd/any external scheduler -- concrete crontab and
  systemd timer examples are in the design doc, deliberately documented
  rather than installed, since the actual deployment host is an
  operator decision. Deliberately stops before acquisition: this
  project's own growth-batch history shows deterministic scope
  adjudication alone has a real, measured residual false-accept rate
  (roughly a fifth of "accepted" candidates in several real batches
  still needed a human/AI title screen to catch off-topic papers), a
  materially harder-to-reverse risk than M52's evidence-direction
  nuance -- an admitted-then-extracted wrong paper contaminates the
  corpus in a way this project has already paid to correct twice via
  full reimports. Each cycle instead writes a bounded
  `ready_for_scope_review` worksheet of net-new, deterministically
  accepted candidates for that same final human/AI screen before `ke
  pmc-oa-acquire` runs. Live-verified against the real PubMed/PMC APIs:
  pagination correctly resumed across cycles (retstart 0 -> 5 -> 10);
  adding a real accepted candidate's PMID to a real ledger and
  re-running the same page correctly excluded it
  (`already_in_rejected_ledger: 1`, `ready_for_scope_review: []`).
- Added `docs/ai_layer_architecture.md`, a refinement of
  `docs/ai_interface_layer_scoping.md`'s Decision Engine framing after
  further owner-side design discussion: one Research Copilot
  orchestrating Retrieval/Evidence/Analytical/Discovery intelligences
  rather than separate bots per capability, a three-way Evidence
  Quality/Consensus/Claim Confidence split (never collapsed into one
  number), Evidence Coverage and confidence-of-confidence as new
  displayed quantities, domain-specific confidence profiles (only
  Clinical Medicine is concretely groundable today), and a
  deterministic-first Statistics Auditor design. Docs only -- no code,
  no new repository, per the project owner's standing explicit
  direction that `knowledge-engine-ai` stays unopened until there is a
  validated confidence-rating formula and/or substantially more
  evidence to design it against.
- Added `--format json` to `ke evidence-report`, alongside the existing
  Markdown default. Same retrieval-plus-evidence content and matching
  logic, as a structured JSON object instead of prose, so a consumer
  (e.g. a future `knowledge-engine-ai` layer, per
  `docs/ai_layer_architecture.md`'s Retrieval Intelligence) can parse
  results programmatically through the documented `ke <command>`
  interface instead of scraping Markdown or Rich console text -- see
  `docs/core_interface_contract.md`. Live-verified against the real
  corpus: `ke evidence-report "does semaglutide reduce lean mass" --format
  json` returns ranked, source-linked papers with matched evidence
  records.

### Fixed

- Fixed `ke evidence-report --format json` producing invalid JSON when
  printed to the console (no `--output`): Rich's `Console.print` word-wraps
  text at terminal width, inserting literal newlines inside JSON string
  values on any field long enough to wrap (e.g. the report's own
  `disclaimer` field) -- silently breaking `json.loads` for any machine
  consumer, discovered while building `knowledge-engine-ai`'s first
  Retrieval Intelligence slice against it. `--output <path>` was never
  affected (it writes the file directly, bypassing Rich). The console path
  now writes JSON output raw via `sys.stdout.write`, never through Rich.
  Added a regression test asserting `json.loads` succeeds on the
  console-printed (not just file-written) output.
- Fixed a cross-field duplication bug in `knowledge_engine.extraction.pico`
  (`PICO_EXTRACTION_RULES_VERSION` v2 -> v3), found while hand-reviewing
  draft evidence items for the evidence-promotion batches above. Each of
  `population`/`intervention`/`comparator`/`outcome` used to scan
  independently for its own first cue-matching sentence; a dense clinical-
  trial sentence often satisfies more than one cue at once ("304
  participants were randomly assigned to semaglutide 2.4 mg or placebo"
  matches both the population cue and the intervention cue), so the same
  sentence ended up duplicated verbatim across two or more fields.
  Re-measured against the real corpus's 13,969-item draft-item pool: 327-781
  duplicate pairs per field-pair before the fix (11-14% of items with both
  fields populated), zero after. Extraction now proceeds in a fixed
  population -> intervention -> comparator -> outcome order and each later
  field skips sentences an earlier field already claimed, continuing to
  scan for the next distinct match -- still "the first cue-matching
  sentence, never a summary or paraphrase," just scoped to sentences not
  already spoken for. Coverage cost is small and honest: all-four-fields-
  populated draft items dropped from 36.7% to 35.8% of the same pool (128
  items out of 13,969), since some previously-duplicated fields now
  correctly resolve to `None` rather than a spurious duplicate. A
  pre-existing CLI integration test
  (`test_extraction_review_generate_populates_pico_fields`) had encoded the
  bug as expected behavior (asserting identical `intervention` and
  `comparator` values); its fixture text now uses four genuinely distinct
  cue sentences.
- Closed the two lowest-coverage Phase 2 extraction gaps
  (`STUDY_DESIGN_RULES_VERSION` v2 -> v3), grounded in reading real corpus
  samples before writing any pattern, the same standard
  `docs/m38_extraction_scale_assessment.md`'s earlier fixes were held to --
  see that doc's new "Resolved follow-up 2" section for full detail.
  `classify_study_type` widened four patterns after sampling real "none"
  papers: `randomized_controlled_trial`'s rigid fixed-order pattern now
  tolerates arbitrary RCT-descriptor word ordering within a bounded
  6-word window (e.g. "an open-label randomized and decentralized clinical
  trial"), while still requiring singular "trial" so a paper discussing
  multiple prior "randomized controlled trials" still does not match;
  `cohort_study` now also matches "cohort analysis"; `cross_sectional_study`
  now also matches "cross-sectional survey"/"cross-sectional design" (with
  up to two intervening words); `case_report` now also matches the
  canonical opening phrase "we report/describe/present a case", not just
  the literal words "case report". `extract_limitations` now falls back to
  scanning the Discussion section for explicit limitation-cue sentences
  when no dedicated "Limitations" heading was detected (a real 200-paper
  sample found 80.5% of "no limitations, has discussion" papers had at
  least one such sentence -- the heading requirement, not an absence of
  stated limitations, was the actual bottleneck), returning every
  cue-matching sentence found rather than judging which one is "the real"
  limitation. Re-measured against the real 960-paper corpus: study type
  classified 416 -> 449 papers (43.3% -> 46.8%); limitations detected
  117 -> 589 papers (12.2% -> 61.4%).
- Fixed the table-region fix above silently having zero effect on
  already-paged papers: three call sites that reconstruct an in-memory
  `ParsedPage` from persisted `PaperPage` rows (`entrypoint.py`'s
  single-paper and batch draft-generation code paths, and
  `scripts/m38_extraction_corpus_report.py`) never copied the new
  `table_text` column across, so `is_table_derived` always saw
  `table_text=None` and never excluded anything, with no error raised.
  Found only by live validation (a full-corpus backfill followed by
  regenerating draft items showed byte-for-byte identical output to the
  pre-fix baseline); not caught by any existing test, including the
  real-database end-to-end test whose own docstring says it exists to
  prove this exact `PaperPage` -> `ParsedPage` conversion, because that
  test's fixture never populated `table_text`. Fixed at all three call
  sites and covered by a new dedicated regression test, verified to fail
  without the fix (via `git stash`) and pass with it.

### Changed

- Added an addendum to `docs/reference_knowledge_layer_design.md`
  recording ten concrete ways reference-layer content (M41's Wikipedia
  lookup, M42's RxNorm lookup, and the still-unbuilt stored-textbook
  path) can shape the future AI Interface Layer's final report --
  display-only evidence grouping, coverage-gap disclosure, provenance
  labeling, reviewer aid, glossary/appendix content, and Knowledge Graph
  concept nodes -- ordered cheapest-to-build-now first rather than by
  report polish. Reaffirms the existing boundary explicitly for each
  one: none of the ten ever feed the report's confidence rating, which
  per `docs/roadmap/long_term_vision.md`'s Confidence Rating Design
  Guidance stays computed from evidence-layer signals only. Codex review
  on PR #180 caught that item 1's original wording ("group evidence
  before scoring") left a real loophole: since the compounded rating
  combines "every relevant evidence record," letting reference-layer
  grouping decide record relevance/pooling would be an indirect
  confidence input even without touching a score directly. Fixed by
  restricting item 1 to report-display grouping only, explicitly
  excluding any use of it to decide the compounding step's participant
  set (that stays the human-assigned `research_question`/
  `evidence_direction` per record, per Phase 2's existing boundary), and
  tightening the addendum's boundary paragraph to name that loophole
  directly rather than only ruling out score adjustments. Project owner
  direction: build all ten eventually, easiest first. Cross-linked from
  `docs/roadmap.md`'s Phase 2 (items 1-4), Phase 4 (item 10), and Phase 5
  (items 5-9) sections, and from `docs/roadmap/long_term_vision.md`'s
  Reference Knowledge Layer section, so the list stays discoverable from
  wherever a future milestone would actually pick one up; no new milestone
  scheduled by this addendum alone.
- Revised the corpus-growth target in `docs/roadmap.md`'s "Scaling beyond
  500 papers for Phase 2 tuning" section down from "at least a couple
  thousand papers" to a **1,000-paper hard cap**, explicitly for GitHub
  space reasons: the committed compressed `corpus_library` snapshot grows
  with the corpus, and a smaller ceiling keeps it comfortably under
  GitHub's 100MB single-file push limit rather than approaching it as
  the corpus scaled toward a couple thousand. At 943 papers (~61MB
  compressed) the corpus is already close to the new cap. Updated the
  corpus README's growth-target framing to match.
- Made Ruff the authoritative formatter and linter used by both developer commands
  and GitHub Actions.
- Unexpected parser and duplicate-resolution exceptions now propagate as systemic
  failures instead of being persisted as ordinary per-paper issue codes.
- Reconciled README, roadmap, and technical-debt documentation through M13 and named
  the controlled 500-paper rehearsal as the next bounded milestone.
- Migrated M14 PMC OA discovery and acquisition off the PMC OA Web Service API
  (`oa.fcgi`) and the PMC FTP Service, both of which NCBI is removing entirely in
  August 2026, onto NCBI's documented PMC Article Datasets Cloud Service (a public,
  world-readable S3 bucket reachable via ordinary unsigned HTTPS — no new
  dependency). This is a durable replacement, done ahead of the removal date,
  superseding the temporary `/pub/pmc/deprecated/` bridge added previously. See
  `docs/architecture/adr/0004-migrate-pmc-oa-acquisition-to-cloud-service.md`.
  Bumped the M14 adjudication ruleset to `m14-candidate-adjudication-v4` since the
  accepted PDF-URL host changed.
- Reconciled README documentation through M17: current phase, milestone history,
  and known issues now reflect Phase 2 progress (page/span provenance, structured-
  section detection, claim-candidate detection) instead of stopping at M14.

### Fixed

- Fixed `pmc_acquisition.py`'s `PmcOaAcquisitionService.acquire` not
  tracking a PDF's temporary file path until after `write_bytes`
  succeeded. A mid-write `OSError` (e.g. a full disk) left an untracked
  `.tmp` file behind that `_rollback_paths` never cleaned up, so every
  retry was then rejected by `_validate_output_directory` as an existing
  output. Found by a Codex review on the M34 Europe PMC acquisition PR
  (#168), which surfaced the identical pattern newly introduced in
  `europepmc_acquisition.py`; fixed there first, then applied the same
  fix here since this is the production M14 path real corpus growth
  depends on. Fixed by registering the temporary path before writing.
  Added a regression test that simulates a partial write failure and
  asserts the output directory ends up empty.
- Fixed M30's `embedding-index-build`/`vector-search` silently permitting
  vectors from different `embedding_model`s into the same FAISS index --
  L2 distance between vectors from incompatible embedding spaces is
  meaningless even at the same dimension, so this could rank unrelated
  vector spaces together and produce meaningless results. Found by a
  Codex review on PR #154. Fixed by adding a JSON metadata sidecar
  (`knowledge_engine.vector_search.index_metadata`) recording exactly
  which model built an index: `embedding-index-build` now rejects a
  vectors file mixing models, rejects updating an index with a different
  model than it was built with, and refuses to update an index missing
  its metadata sidecar entirely; `vector-search` refuses to search such
  an index and validates an optional `embedding_model` in the query file
  against it.
- Fixed M33's `QdrantVectorIndex` accepting any existing Qdrant collection
  with a matching dimension and Euclidean distance for reuse, even if it
  was populated with vectors from a different embedding model -- the same
  bug class as above, since same-dimension embeddings from unrelated
  models are common and L2 distance across them is meaningless. Found by
  a Codex review on PR #157, before this backend ever merged. Fixed by
  requiring an `embedding_model` identifier, recording it on every
  point's payload, and rejecting reuse of a *non-empty* collection whose
  recorded model (or unverifiable absence of one, for points inserted
  outside `add`) does not match. A genuinely empty existing collection
  has nothing to conflict with yet, so it may still be claimed by any
  model.
- Fixed `ke corpus-library-import` (M27) copying `embedding_model`/
  `embedding_id` verbatim onto an imported paper. `embedding_id` is the
  source database's own `Paper.id`, which is only unique within that one
  database -- copying it into a target database (where the imported paper
  gets a different, fresh primary key) let the imported paper silently
  claim another, unrelated paper's embedding identity, or a stale one
  nothing indexes. Found by a Codex review on PR #154. Fixed by clearing
  both fields on import; an operator must re-run `ke embedding-index-build`
  for papers after importing a snapshot, since the FAISS index file was
  never part of the snapshot's portable paper-intrinsic content anyway.
- Fixed `_build_embedding_generator` constructing
  `SentenceTransformerEmbeddingGenerator`/`OpenAiEmbeddingGenerator`
  outside any try/except, so a constructor-time `LocalEmbeddingError`/
  `OpenAiEmbeddingError` (an invalid `--model`, an empty local model name)
  propagated as an unhandled exception instead of the sanitized red-text
  + exit(1) error every other failure path in `embedding-generate`/
  `vector-search` uses. Found by a Codex review on PR #156. Fixed by
  wrapping both constructor calls in the shared helper itself, so both
  call sites get the fix.
- Fixed `_report_text` (shared by every Markdown report renderer --
  `evidence-report` and M29's `relationship-report`) only ASCII-normalizing
  free-text fields without escaping Markdown structure or collapsing
  embedded newlines. A rationale, claim text, or other reviewer-authored/
  extracted field containing an embedded `\n\n## Final Disclaimer` line
  could forge a fake report section, and ordinary text containing
  `*`/`_`/`` ` ``/`[`/`]`/`<` rendered as live Markdown formatting instead
  of the literal stored text. Found by a Codex review on PR #150. Fixed
  by collapsing embedded whitespace/newlines and escaping
  Markdown-significant characters centrally in `_report_text`, so every
  report renderer is protected at once rather than only the one Codex
  reviewed.
- Fixed the M14 candidate-adjudication ruleset (`ADJUDICATION_RULES_VERSION`)
  accepting three kinds of out-of-scope or non-primary-content sources into
  the corpus: pediatric-titled papers (v7), correction/erratum/retraction
  notices (v8), and a case report whose abstract mentioned a disease term
  only as an incidental, unrelated patient comorbidity (v8, via a
  same-sentence disease/intervention co-occurrence requirement). Re-running
  the v8 co-occurrence rule against a real 250-candidate batch showed it was
  too strict for ordinary structured/narrative scientific writing -- it
  dropped 44% of previously accepted, legitimately on-topic records -- so
  v9 reverts that specific rule while keeping the pediatric and
  correction-notice exclusions, which showed no such false-positive cost.
- Manually excluded a second incidental-comorbidity false positive from the
  already-merged `retstart=0` batch: a kidney-stone-treatment case report
  (`pmc-13262153`) whose abstract named obesity only as an unrelated patient
  comorbidity, found by applying the same review pattern that caught a
  near-identical case (a persistent-hiccups case report naming type 2
  diabetes as an incidental comorbidity) in the `retstart=250` batch. Since
  v9 deliberately has no automated rule for this pattern, both records were
  excluded by direct manual review rather than by another ruleset change.
  `sources.csv` now holds 83 sources (80 from `retstart=0`, down from 81);
  refreshed the corpus-library snapshot (83 papers, 136 authors).
- Fixed M14 bounded PubMed/PMC discovery retrying NCBI failures (including PMC
  identifier conversion) with only the steady-state request pacing interval instead
  of a real backoff; retries now use exponential backoff and failure messages
  include the HTTP status code for diagnosability.
- Fixed M14 PMC OA acquisition failing on every PDF request because NCBI relocated
  its legacy PMC FTP paths ahead of removing them in August 2026; acquisition now
  retries once against NCBI's confirmed `/pub/pmc/deprecated/` relocation, and
  failures now report the HTTP status code and failing approval for diagnosability.
- Fixed the `Quality` GitHub Actions gate silently reporting success even when lint,
  type-check, or tests failed, because piping through `tee` without `set -o
  pipefail` swallowed the real tool exit code. Also fixed every pre-existing lint
  finding, mypy error, and test failure the corrected gate now enforces, including
  a third and fourth occurrence of the single-command Typer CLI collapse bug
  (`pdf_calibration_cli.py`, `candidate_review_cli.py`) and a real SQLite backup
  bug where a naive (non-timezone-aware) timestamp left a partial, unverified
  snapshot file on disk instead of being cleaned up.
- Fixed M14 candidate adjudication accepting restricted `CC BY-NC`, `CC BY-NC-ND`,
  and `CC BY-NC-SA` licenses as if they were the fully-reusable `CC BY` license,
  because the license check used a string-prefix match instead of an exact match.
  Restricted licenses are now correctly held instead of accepted.
- Fixed M14 manifest curation leaving `license_url` and `access_date` blank and
  `expected_content_hash` unprefixed, which caused every exported row to fail
  corpus-import validation. `license_url` is now derived deterministically from
  `license_type`, `access_date` from the adjudication timestamp, and the hash is
  now written with its required `sha256:` prefix.
- Fixed the allowed-license version pattern matching any digits-and-dots string
  (e.g. `CC0 2.0`, a version that was never published) instead of a real
  Creative Commons version, which could let malformed license evidence pass
  adjudication and produce a license URL with no real deed behind it.
- Fixed `migrate_schema` verifying that every table registered in the ORM
  metadata already exists *before* creating newly-registered tables, for any
  database past schema version 0 — a table introduced by a new schema version
  (like this release's `paper_pages`) could never actually migrate onto an
  existing database; it would always raise instead. Fixed by only exempting
  tables introduced at a version newer than the database's own recorded
  version from the pre-creation check, so a genuinely new table is created
  silently while a table that was actually dropped or corrupted from an
  already-reached version still raises rather than being silently recreated
  empty.
- Fixed `ClassifiedPaperRepository` (used by `ke corpus-import`, the only
  path that has ever populated the real committed corpus) silently dropping
  M15's per-page extraction provenance: it fully overrode
  `PaperRepository.add_parsed_paper` with its own independent copy for
  exception classification, and that copy never picked up the
  `paper.pages = [...]` line M15 added to the base class. Every paper
  imported through `corpus-import` since M15 persisted zero `PaperPage`
  rows despite a correctly recorded `page_count`, silently blocking Phase 2
  extraction for the entire corpus -- found by running
  `ke extraction-review-generate` against all 605 real papers for the first
  time, which failed on every single one with "no persisted pages." Fixed
  by extracting the shared paper-construction logic into
  `PaperRepository._build_paper`, used by both overrides, so this class of
  copy-paste divergence cannot recur. Backfilled the existing local
  database with `ke paper-pages-backfill`.
- Fixed a latent bug in `Database`'s SQLite engine setup: without
  SQLAlchemy's documented pysqlite-SAVEPOINT workaround (disabling
  pysqlite's own transaction heuristics via `isolation_level=None` and
  issuing explicit `BEGIN` statements), a `session.begin_nested()`
  SAVEPOINT that completed successfully was not actually undone by a
  *later*, unrelated `session.rollback()` on the same session -- found
  by a Codex review on the M40 PR (#177) of `ke
  extraction-review-batch-generate`'s per-paper SAVEPOINT isolation, and
  confirmed with a minimal repro before and after the fix. Affects every
  existing `session.begin_nested()` use in the codebase
  (`import_runs/linked.py`, `ingestion.py`, `linked_ingestion.py`), not
  just the new command; fixed once at the engine level in
  `knowledge_engine/database.py`. Full test suite green after the change;
  re-verified against the real 943-paper corpus with identical results.

## [0.2.0-alpha.1] - 2026-07-11

### Added

- Added natural-language scientific-question retrieval with `ke answer`.
- Added curated `sources.csv` metadata overlays for retrieval results.
- Added manual JSONL evidence records with review status and checklists.
- Added structural evidence validation with `ke evidence-validate` and shared
  validation across evidence-consuming commands.
- Added DOI-matched evidence previews, evidence review status summaries, and
  local Markdown evidence reports.
- Added the GLP-1 demo corpus metadata and reproducible demo checklist.
- Documented explicit retrieval, manual-evidence, and no-synthesis boundaries.

## [0.1.0] - 2026-07-06

Initial public Phase 0 release.
