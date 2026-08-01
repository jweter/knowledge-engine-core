# Evidence Intelligence Design: A Deterministic Confidence-Scoring Formula

Status: design doc, not yet implemented. This is the document
`docs/ai_layer_architecture.md` and `docs/ai_interface_layer_scoping.md`
both named as their own trigger condition for finally opening real work
-- "a validated confidence-rating formula design grounded in real data,"
alongside the project owner explicitly asking for it. Both hold now: the
GLP-1 corpus has 155 validated `EvidenceRecord`s and 3 real
`RelationshipRecord`s (M56), and this document was requested directly.

This document proposes **Stage 3 of `ai_layer_architecture.md`'s
5-stage build sequence -- Evidence Intelligence** -- and nothing past
it. It does not propose Stage 1 (Research Copilot chat), Stage 2
(automated extraction), Stage 4 (Statistics Auditor), or Stage 5
(Discovery Intelligence). It scopes exactly one domain profile,
Clinical Medicine, per that document's "concretely buildable today:
exactly one profile" finding -- the only domain with a real corpus and
real PICO/study-type fields.

## Verifying this holds true to what was sketched out earlier

Before proposing a formula, here is an explicit check against both
prior documents, so this design doesn't quietly drift from them:

| Prior commitment | Where it's honored below |
|---|---|
| Confidence is three separate numbers that must never collapse (`ai_layer_architecture.md`, "Confidence is three numbers, not one") | Evidence Quality, Evidence Consensus, Claim Confidence are computed and stored as three distinct fields; never averaged into one on-disk value. |
| Evidence Coverage must be surfaced explicitly | Included as a corpus-relative count, not a fraction of an unknowable universe (see "Evidence Coverage" below -- a real constraint this document resolves). |
| Confidence-of-confidence / reliability labels | Every Claim Confidence ships with a reliability label (`insufficient`/`low`/`moderate`/`high`), driven by relationship-edge count and record completeness, not a bare point estimate. |
| Extraction confidence must never share a scale with assessment confidence | This document computes **only** assessment-layer scores (Evidence Quality, Consensus, Claim Confidence) from already-stored `EvidenceRecord` fields. It does not touch or invent an extraction-accuracy score -- that would be a different, unbuilt metric (how sure are we the PDF was read correctly), out of scope here. |
| Ground the rubric in a named, citable standard, not an invented one (`ai_interface_layer_scoping.md`, Discovery Engine section) | Evidence Quality's study-type weighting is GRADE-inspired (study design as the primary quality determinant), named explicitly below, not an arbitrary number. |
| The seam: never invent a number not traceable to a real source; never auto-author a `RelationshipRecord`; never set/infer `research_question`/`evidence_direction` | The formula only reads already-stored, human-authored fields. It computes derived numbers from them; it does not write back into `EvidenceRecord` or `RelationshipRecord`, and it never creates a relationship edge. |
| Domain-specific profiles, not a universal rubric | Every weight below is labeled `clinical_medicine_v1` and is explicitly not proposed as portable to another field. |
| Synthesis: the LLM explains, never computes (`ai_layer_architecture.md`, "the load-bearing distinction") | See "Synthesis, without an LLM" below -- v1 deliberately uses a deterministic template, not a model call, so the load-bearing rule is honored without yet opening the separate question of whether/how an LLM gets integrated at all. |

## What the real data actually supports (and doesn't)

`ai_layer_architecture.md` explicitly warns against inventing a number
not traceable to a real source. Auditing the actual corpus before
proposing weights surfaced real constraints this document must respect:

- **`sample_size` is not a stored field.** An earlier sketch of this
  formula (informal, in conversation) assumed sample size would feed
  Evidence Quality. It does not exist in `EvidenceRecord` today -- the
  record schema (see `ke evidence-validate`'s schema and any record in
  `data/corpora/glp1_weight_loss/evidence_records.jsonl`) has no such
  field. Using it would mean inventing a number. **Corrected:** v1
  excludes sample size entirely. `ai_interface_layer_scoping.md`
  already anticipated this gap -- "does this paper state a sample size"
  is closer to deterministic Phase 2 extraction than AI-layer judgment,
  and is named there as a possible future `core`-side enhancement, not
  something to fake here.
- **`study_type` is free text, not a controlled vocabulary, and is
  missing on 28 of 155 records (18%).** The 127 populated values fall
  into 13 distinct strings (`randomized_controlled_trial`,
  `meta_analysis`, `systematic_review_meta_analysis`,
  `systematic_review`, `cohort_study`,
  `retrospective_observational_cohort`,
  `prospective_observational_cohort`, `observational_study`,
  `cross_sectional_study`, `retrospective_study`, `pilot_study`,
  `case_report`, `cross_over_trial`). A quality formula needs a mapping
  table (below), and the 28 missing-study-type records must honestly
  degrade to "insufficient data," not receive a guessed mid-tier score.
- **Only 3 of 155 evidence records currently participate in any
  `RelationshipRecord`** (M56's three `supports` edges, all
  GLP-1/semaglutide body-weight claims). This means Evidence Consensus
  and Claim Confidence will land in an explicit "insufficient
  relationship data" state for roughly 152 of 155 records at launch.
  That is not a bug to hide -- it is the honest current state of the
  corpus, and the reliability label exists specifically to surface it
  rather than paper over it with a fabricated middle score.
- **`extraction_method` and `extraction_status` are a real, already-populated
  quality signal.** 33 records are `manual_human_review` /
  `draft_manual_prototype`, each with a fully populated
  `review_checklist` (`source_verified`, `doi_verified`,
  `source_span_present`, `limitations_recorded`, `uncertainty_recorded`,
  `no_synthesis_language`, all `true`). 122 records are
  `m52-evidence-classification-v1` / `draft_review_required` -- an
  automated pass with no `review_checklist` populated at all
  (`ready_for_secondary_review` is unset, not `false`-and-confirmed).
  This is real, present, deterministic signal for Evidence Quality that
  requires no invention.
- **9 of 155 records have an empty or missing `limitations` list.**
  Also real, usable signal (per-record, deterministic, no judgment
  required beyond "is this field populated").

## Evidence Quality (per `EvidenceRecord`)

Answers: *how trustworthy is this evidence record on its own, before
comparing it to anything else?* Computed once per record, from fields
already on that record.

Three deterministic components, each independently inspectable:

1. **Study-design weight** (0-40 points), from `study_type` mapped
   through a GRADE-inspired tier table -- study design is GRADE's
   primary starting point for certainty, which is the closest existing
   named standard, per `ai_interface_layer_scoping.md`'s own framing of
   GRADE as "closest in spirit to what the Confidence Score is trying
   to compute":

   | Tier | `study_type` values | Points |
   |---|---|---|
   | Systematic synthesis | `systematic_review_meta_analysis`, `meta_analysis`, `systematic_review` | 40 |
   | Controlled trial | `randomized_controlled_trial`, `cross_over_trial` | 35 |
   | Prospective observational | `prospective_observational_cohort`, `cohort_study` | 25 |
   | Retrospective / cross-sectional | `retrospective_observational_cohort`, `retrospective_study`, `cross_sectional_study`, `observational_study` | 15 |
   | Uncontrolled / descriptive | `pilot_study`, `case_report` | 5 |
   | Missing | `study_type` is `null` | 0, and the record is flagged `study_type_missing` on output |

   This table is explicitly `clinical_medicine_v1`-scoped and not
   proposed as portable.

2. **Extraction rigor** (0-40 points), from `extraction_method` /
   `extraction_status` / `review_checklist`:
   - Manual review with a fully-populated, all-true `review_checklist`
     (today: the 33 `manual_human_review` records): 40 points.
   - Automated extraction pending review (`draft_review_required`, no
     `review_checklist`): 15 points -- present and usable, but
     unverified.
   - (Reserved, not populated by any record today: a future
     `ready_for_secondary_review: true` + populated checklist state on
     an automated record would score between these two -- not
     designed further here since no record currently reaches it.)

3. **Completeness penalty** (0 to -10 points): -5 if `limitations` is
   empty or missing, -5 if `uncertainty_notes` is empty or missing.
   Present, deterministic fields; a genuinely thin record should score
   lower than a fully documented one.

**Evidence Quality = study-design weight + extraction rigor +
completeness penalty, clamped to [0, 100], scaled ×1.25 after summing
(max raw is 80).** Displayed as `Evidence Quality: 74/100 (Controlled
trial, manually reviewed)` -- always with the tier name attached, never
a bare number, so the score is inspectable at a glance without opening
the record.

## Evidence Consensus (per claim, across its `RelationshipRecord` edges)

Answers: *how consistently does the literature actually agree, for
claims that have been compared to each other at all?*

Computed only from **existing `RelationshipRecord`s** -- this document
proposes no new relationship inference, matching the seam's "never
auto-author a `RelationshipRecord`" rule and M56's precedent of
manual-only relationship authorship. For a given evidence record,
gather every `RelationshipRecord` where it appears as `source` or
`target`:

- **0 or 1 edges: `insufficient_relationship_data`.** No consensus
  number is computed or displayed -- showing one would imply agreement
  data that doesn't exist. This is the state for ~152 of today's 155
  records.
- **2+ edges:** count `supports` vs. `contradicts` (`qualifies` and
  `contextualizes` are noted but excluded from the agree/disagree
  ratio -- they narrow applicability, they don't state agreement or
  disagreement; `supersedes` removes the older claim from the
  denominator entirely, per its Stability/Tracking design in
  `docs/stability_and_tracking_design.md`). Evidence Consensus =
  `supports / (supports + contradicts) × 100`, e.g. 3 supports, 0
  contradicts today → `100/100` for the three M56-linked claims, with
  the edge count always displayed alongside the percentage (`Evidence
  Consensus: 100/100 (3 of 3 relationships agree)`) so "100%" is never
  misread as unanimous across the literature rather than across the 3
  edges actually recorded.

## Claim Confidence (the combination, never inherited from either input alone)

Answers: *given quality and consensus together, how confident should
we be right now?* Per `ai_layer_architecture.md`'s explicit example (ten
low-quality-but-agreeing studies must not produce high combined
confidence), this is a product-style combination, not a max or an
average of the two:

```
Claim Confidence = (mean Evidence Quality of participating records / 100)
                  × (Evidence Consensus / 100)
                  × 100
```

- If Evidence Consensus is `insufficient_relationship_data`, **Claim
  Confidence is not computed at all** -- displaying a number here would
  misrepresent single-source claims as having been cross-checked. The
  claim instead shows its (fully valid) Evidence Quality alone, labeled
  `Claim Confidence: not yet assessable (needs at least one more
  relationship edge)`.
- Reliability label, driven purely by input completeness, not the score
  itself: `insufficient` (fewer than 2 relationship edges, no
  confidence shown), `low` (2 edges), `moderate` (3-4 edges),
  `high` (5+ edges). This is the confidence-of-confidence signal
  `ai_layer_architecture.md` requires -- e.g. `Claim Confidence: 87/100,
  reliability: low (2 relationships)` -- never a bare point estimate.

## Evidence Coverage

`ai_layer_architecture.md` frames this against an estimated universe
size ("47 of an estimated 2,300 papers"), which this project has no
defensible way to estimate for GLP-1/weight-loss literature today --
inventing that denominator would itself violate the seam. **Scoped-down
for v1:** Evidence Coverage is corpus-relative, not universe-relative:
`Evidence coverage: 3 of 155 evidence records (2%) participate in a
confirmed relationship`. This is a real, defensible, already-computable
number (`ke graph-report` already tracks claim and relationship counts)
that still does the job -- discouraging overconfidence by making the
corpus's actual current thinness visible -- without pretending to know
how large the real literature is. A universe-relative estimate remains
a real future idea, not attempted here for lack of real data to ground
it in.

## Synthesis, without an LLM

The user's request was for the confidence gauge and synthesis both to
be real. `ai_layer_architecture.md` is explicit that "the LLM explains,
never judges" -- but that rule describes what an LLM may do *if one is
introduced*, not a requirement that one must be. Actually wiring an LLM
into `knowledge-engine-web` or `-core` is a separate, larger decision
(model choice, cost, a new dependency, hosting) that has not been made
and is out of scope for this document.

**v1 proposal: synthesis is a deterministic template over the computed
numbers**, not generated prose:

```
3 relationship(s) recorded for this claim: 3 support, 0 contradict.
Evidence Quality (mean across participating records): 78/100.
Evidence Consensus: 100/100 (3 of 3 agree).
Claim Confidence: 78/100, reliability: moderate (3 relationships).
Evidence coverage: 3 of 155 corpus records participate in a confirmed
relationship.
```

This satisfies "real, live... confidence gauge and synthesis" without
opening the LLM-integration question, keeps every displayed sentence
directly traceable to a stored field (the seam's own bar), and can be
revisited if/when an actual narrating LLM is scoped as its own
decision.

## Where this lives

Computed on read, not stored: `knowledge_engine`'s `GraphRepository`
gains a `compute_evidence_intelligence(evidence_record_id)` /
`compute_claim_confidence(claim_id)` pair of pure functions operating
on already-persisted `EvidenceRecord`/`RelationshipRecord`/graph data --
no new schema, no new stored column, no migration. This mirrors
`report_renderer.py`'s existing pattern in `knowledge-engine-web` of
deriving display content from stored data on request rather than
caching a derived value that could drift from its source. A new `ke
evidence-intelligence <evidence_record_id>` CLI command exposes it the
same way `ke graph-report` already exposes other derived views, and
`knowledge-engine-web`'s existing claim/evidence detail pages (task
#98/#103) render it directly.

## Explicitly out of scope for this document

- The Statistics Auditor (Stage 4) -- recomputing reported effect
  sizes/CIs. Needs its own design doc when taken up.
- Stability Score / evidence lifecycle tracking beyond what
  `supersedes` already removes from the consensus denominator --
  `docs/stability_and_tracking_design.md` owns that in more depth.
- Any second domain profile -- no second real corpus exists yet.
- Any LLM integration for synthesis -- deliberately deferred above.
- Automated relationship inference -- would violate the seam; M56's
  precedent (human-authored only) stands.
- A universe-relative Evidence Coverage estimate -- no defensible
  denominator exists yet.

## When this needs revisiting

Real triggers, matching both predecessor documents' own posture: a
second `RelationshipRecord`-authoring milestone that meaningfully grows
past today's 3 edges (changing which records leave the
`insufficient_relationship_data` state), a decision to add `sample_size`
as a Phase 2 extraction field, or a decision to actually integrate an
LLM for synthesis (a separate scoping conversation, not implied by this
document).
