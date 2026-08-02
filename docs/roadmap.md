# Roadmap

This file is the roadmap index. Phase-specific notes live in `docs/roadmap/`.

These phases describe the near-term, buildable work inside
`knowledge-engine-core` itself. `docs/roadmap/long_term_vision.md` describes
the larger, multi-package ecosystem this roadmap builds toward -- including
the future `knowledge-engine-ai` layer that will eventually consume the
Evidence Records (Phase 2) and Knowledge Graph (Phase 4) this roadmap
produces. Each phase below stays deliberately scoped to what `core` alone
should own; anything that requires judgment about what evidence means, not
just locating and validating it, is out of scope here by design -- see the
long-term vision doc for where that responsibility lives instead.

One section, Reference Knowledge Layer, sits between Phase 2 and Phase 3
but is not itself a numbered phase: it is cross-cutting background-context
tooling `core` has already built (M41-M45), not a stage this roadmap
completes and moves past.

## Phase 0: Local Source Vault

- Import PDFs.
- Extract text and best-effort metadata.
- Store papers, authors, journals, keywords, and full text.
- Search with SQLite FTS5.
- Run fully offline.
- Establish open-source project hygiene, governance files, issue templates, and
  automated quality checks.

"Run fully offline" and "local source vault" describe `core`'s own engineering
properties, not the shape of the finished product -- see
`docs/roadmap/long_term_vision.md`'s "The Finished Product Is Not an Offline
PDF Archive" section.

## Phase 1: Focused Scientific Corpus

- Choose one domain, such as obesity and metabolic disease.
- Import 500 to 1,000 legally available papers through bounded rehearsals.
- Improve metadata extraction with Crossref or PubMed adapters.
- Add citation metadata.
- Add deduplication reports and import manifests.
- Define legal corpus inclusion rules and source provenance requirements.
- Add a repeatable corpus ingestion workflow.
- Use `docs/phase1_design.md` as the detailed design reference.

The current GLP-1 vertical slice is a retrieval and manual evidence-display
prototype. See `docs/history/vertical_slice/vertical_slice.md` and
`docs/history/vertical_slice/glp1_vertical_slice_demo_checklist.md`. Those files record historical
prototype work and do not impose a current manual-review prerequisite.

### Working-version review policy

Repository execution must not depend on the project owner manually reviewing
individual candidates, PDFs, metadata rows, licenses, duplicate decisions, or
manifest fields before a working version exists. Deterministic automation must
accept, reject, hold, retry, or exclude each record with preserved evidence.
Held records are automatically deferred from acquisition and do not block the
remaining accepted batch. Human evaluation is reserved for working-version
acceptance, release validation, and optional post-release quality audits.

### Completed Phase 1 milestones

- **M6** defined the Phase 1 corpus-ingestion architecture.
- **M7** implemented versioned manifest validation and local-file readiness checks.
- **M8** added durable import-run, item, issue, and manifest-snapshot persistence.
- **M9** connected validated local PDFs to persisted import runs and atomic
  paper/FTS persistence while preserving item-level continuation.
- **M10** added duplicate evidence decisions, linked resume/retry behavior, and
  explicit execution/review status semantics.
- **M11** added provenance-preserving metadata preview and Crossref enrichment
  boundaries without silently overwriting canonical data.
- **M12** completed the controlled 100-paper rehearsal and sanitized reporting.
- **M13** assessed scale readiness and conditionally authorized one controlled
  500-paper rehearsal with explicit measurement and stop conditions.
- **Pre-M14 maintenance** reconciled repository state, made Ruff the authoritative
  quality tool, and hardened fresh and linked ingestion error boundaries.
- **M14** migrated PMC OA discovery and acquisition to NCBI's Cloud Service ahead
  of the August 2026 FTP/`oa.fcgi` removal, fixed a license-adjudication defect
  that had been silently accepting restricted `CC BY-NC`/`-ND`/`-SA` variants,
  and completed the controlled 500-paper rehearsal (issue #21) with a `PROCEED`
  decision: a fresh import and a linked resume against the same manifest
  snapshot both reconciled exactly, with zero failures, zero issues, and a fully
  idempotent resume. See `docs/history/milestones/m14_500_paper_rehearsal_report.md`.
- **M34** added Europe PMC as a second automated discovery source, alongside
  M14's PubMed/PMC pipeline -- `ke europepmc-candidate-discover` and
  `ke europepmc-candidate-review-prepare`, with their own adjudication engine
  (`europepmc_candidate_review.py`, `EUROPEPMC_ADJUDICATION_RULES_VERSION`)
  since identity and full-text evidence work differently for Europe PMC than
  for PMC. A follow-up change added the matching acquisition step
  (`europepmc_reviewed_approval.py`, `europepmc_acquisition.py`,
  `ke europepmc-oa-acquire`), mirroring M14's own phased discovery-then-
  acquisition history. A bounded live smoke test found that
  `europepmc.org`'s hosted PDF endpoint, the only host this pipeline
  allowlists, returns HTTP 403 from this project's sandboxed execution
  environment for every candidate tried -- documented as a known
  live-verification gap, not silently assumed working. See
  `docs/history/milestones/m34_europepmc_discovery.md`.
- **M35** added CORE as a third automated discovery source -- `ke
  core-candidate-discover` and `ke core-candidate-review-prepare`, with
  their own adjudication engine (`core_candidate_review.py`,
  `CORE_ADJUDICATION_RULES_VERSION`). CORE's API never returns a license
  field (verified empirically), so every CORE candidate's license rule is
  `incomplete_missing_license` and no CORE candidate can ever auto-accept --
  a deliberate, honest consequence documented in `docs/history/milestones/m35_core_discovery.md`,
  not a bug. Scoped to discovery and adjudication only -- **not** wired into
  acquisition. (M14's own PubMed/PMC pipeline, separately, has continued
  growing the corpus toward the "Scaling beyond 500 papers for Phase 2
  tuning" target below; CORE candidates specifically are not part of that
  growth.)
- **M36** added Unpaywall as a fourth evidence source, but as a per-DOI
  OA-location/license *lookup tool* rather than a fifth discovery pipeline
  -- `ke unpaywall-doi-lookup` and `ke unpaywall-batch-lookup`. Unpaywall's
  topic-search API was confirmed broken (`HTTP 500` on every query tried)
  at build time, so there is no reliable endpoint to build a `--query`
  discovery command against; its working per-DOI endpoint also carries no
  scientific-scope signal and no single canonical host to allowlist. Makes
  no accept/reject/hold decision -- pure evidence for a human reviewing a
  DOI already surfaced by another pipeline. See
  `docs/history/milestones/m36_unpaywall_lookup.md`.
- **M37** added `ke manual-pdf-preview`/`ke manual-pdf-manifest-draft`,
  closing the "no door is closed" manual-PDF-upload path's real gap: not
  that manual PDFs couldn't be imported (they always could), but that
  adding one meant hand-typing a `sources.csv` row. `PyMuPDFParser` (the
  same parser `ke import` already uses) extracts title/authors/DOI/
  page-count locally; a found DOI can optionally be checked against
  Unpaywall (M36) for OA/license evidence. The manifest-draft step refuses
  to produce a row unless license evidence already passed -- never
  guesses. See `docs/history/milestones/m37_manual_pdf_preview.md`.

### M14: Controlled 500-paper rehearsal

M14 is one controlled 500-paper rehearsal under the M13 entry, measurement, stop,
reconciliation, resume, and artifact-hygiene conditions. Issue #21 is the
authoritative rehearsal tracker; it completed with a `PROCEED` decision (see
`docs/history/milestones/m14_500_paper_rehearsal_report.md`). Persistence failure classification in
issue #22 must be complete before repeated large-run failure evidence is treated
as diagnostic. The rehearsal must not introduce new architecture solely to
collect one run's measurements.

The M14 corpus scope is **Obesity and Metabolic-Disease Therapeutics**. The
original GLP-1 weight-loss question remains the first named subtopic, but the
rehearsal may include legally reusable treatment evidence for overweight, type 2
diabetes, metabolic syndrome, metformin, SGLT2 inhibitors, dual incretin
therapies, and other explicitly allowlisted interventions within this same
Phase 1 domain. Scope expansion must never weaken license, provenance,
identifier, duplicate, or full-text validation.

M14 proceeds through explicit stages:

1. bounded PubMed/PMC candidate discovery within the committed obesity and
   metabolic-disease therapeutics scope;
2. deterministic, evidence-preserving candidate adjudication for scientific scope,
   identifier consistency, reusable-license basis, approved full-text location, and
   duplicate risk;
3. explicit `accepted`, `rejected`, or `held` decision records that remain separate
   from raw discovery output; held records are automatically deferred and discovery
   continues without waiting for manual resolution;
4. bounded acquisition of accepted files with sanitized receipts;
5. reconciliation to exactly 500 accepted rows and matching approved local PDFs;
6. preflight validation, fresh import, linked resume, and sanitized evidence.

Automated acceptance or rejection is permitted only when repository-defined rules
produce complete, non-conflicting evidence. Every decision must record reason codes,
provider provenance, the adjudication-rules version, and the evidence used. A record
must be held rather than guessed when identity, licensing, scientific relevance,
full-text eligibility, or duplicate status remains ambiguous. Discovery providers
must remain separate evidence categories; metadata from PubMed, PMC, Crossref,
OpenAlex, Europe PMC, or publishers must not be silently collapsed into one trust
category. Held and rejected records never authorize acquisition and never require
owner intervention before the working-version acceptance review.

If one query or subtopic cannot supply enough accepted records, discovery may
continue through measured query revisions inside the committed M14 domain. Each
revision must preserve its query, offset, rules version, decision counts, and
provider provenance. Unrelated scientific domains require a separate roadmap
amendment rather than silent corpus mixing.

### M34: Europe PMC, a second discovery source

The project owner asked for more automated discovery sources and pipelines
beyond M14's PubMed/PMC-only pipeline. M34 adds Europe PMC as the second one
-- see `docs/history/milestones/m34_europepmc_discovery.md` for the full design, and
`knowledge_engine/europepmc_discovery.py` /
`knowledge_engine/europepmc_candidate_review.py` for the implementation.
Deliberately scoped to what Europe PMC adds beyond PMC: for records already
in PMC, Europe PMC's own "PDF" is just a rendered view of the exact same PMC
content M14 already acquires via NCBI's official S3 bucket, so those
candidates are still discovered (never silently dropped) but explicitly
rejected as out of this pipeline's scope
(`DUPLICATE_OF_PMC_PIPELINE_SCOPE`), rather than duplicating M14's own
pipeline through a less-official endpoint. Scientific-scope and license
rules are shared with M14's engine (`scientific_scope.py`,
`license_rules.py`) so the same corpus-inclusion criteria apply regardless
of which pipeline found a candidate.

A follow-up change added the matching acquisition step -- see
`docs/history/milestones/m34_europepmc_discovery.md`'s Acquisition section and its "Known
live-verification gap" note. Growing the corpus via Europe PMC candidates
specifically (as opposed to M14's own PubMed/PMC pipeline, which has
continued growing the corpus toward the "Scaling beyond 500 papers for
Phase 2 tuning" target below) remains a separate decision for the project
owner to make explicitly, the same way M13/M14's own scale-up was.

### M35: CORE, a third discovery source

The project owner asked to keep adding automated discovery sources without
pausing for permission at each step. M35 adds CORE
(https://core.ac.uk) as the third one -- see `docs/history/milestones/m35_core_discovery.md`
for the full design, and `knowledge_engine/core_discovery.py` /
`knowledge_engine/core_candidate_review.py` for the implementation. CORE
aggregates open-access content broadly (not just biomedical literature),
using offset-based pagination and an optional API key
(`KE_CORE_API_KEY`) that raises its otherwise low unauthenticated rate
limit. Critically, CORE's API never returns a license field at all
(verified empirically by enumerating every key in a real response), so
`core_candidate_review.py`'s license rule is always
`incomplete_missing_license` and no CORE candidate can ever auto-accept --
every candidate that clears every other rule still lands in `held`,
pending a human visiting the original source to confirm reuse terms. PMC/
Europe PMC overlap detection is a known, deliberate limitation for this
milestone (CORE never reports a PMCID); see `docs/history/milestones/m35_core_discovery.md`.
Scientific-scope and license rules are shared with M14 and M34's engines
so the same corpus-inclusion criteria apply regardless of which pipeline
found a candidate.

**Not yet wired into acquisition.** M35 only builds the discovery/
adjudication capability for CORE specifically; using it to actually grow
the corpus further is a separate decision for the project owner to make
explicitly, the same way M13/M14's own scale-up was (see "Scaling beyond
500 papers for Phase 2 tuning" below for the growth that has happened, via
M14's own pipeline).

### M36: Unpaywall, an evidence lookup tool rather than a fourth discovery pipeline

The project owner asked to keep adding evidence sources, naming Unpaywall
explicitly, without pausing for permission at each step. Unlike M14/M34/M35,
M36 does not add a `--query` discovery pipeline: Unpaywall's `/v2/search`
endpoint returned a consistent `HTTP 500` across multiple distinct queries
and retries at build time (confirmed empirically, not assumed), and its
working per-DOI endpoint carries no scientific-scope signal and no single
canonical host to allowlist the way CORE and Europe PMC do. See
`docs/history/milestones/m36_unpaywall_lookup.md` for the full design, and
`knowledge_engine/unpaywall_lookup.py` for the implementation.

Instead, M36 adds `ke unpaywall-doi-lookup` and `ke unpaywall-batch-lookup`:
given one or more DOIs already surfaced by another pipeline (e.g. a `held`
Europe PMC or CORE candidate), it queries Unpaywall's per-DOI endpoint and
reports OA status, best OA location, license (normalized from Unpaywall's
own `cc-by`-style tokens and evaluated via the shared `license_rules.py`),
and every OA location on file. It makes **no** accept/reject/hold decision
-- that stays the responsibility of whichever pipeline's held candidate
this evidence is being used to re-examine. Requires `KE_UNPAYWALL_EMAIL`
(Unpaywall's usage policy requires a contact email on every request; this
project does not bake in a default for every installation).

**Not wired into acquisition or corpus growth** -- Unpaywall is a lookup
tool for evidence a human is already examining, not a discovery pipeline
with its own accept/reject/hold decisions to acquire from (see "Scaling
beyond 500 papers for Phase 2 tuning" below for the growth that has
happened, via M14's own pipeline).

### Scaling beyond 500 papers for Phase 2 tuning

Phase 2's automated extraction (M16-M25) was built and unit-tested against
synthetic fixtures; M38 (see Phase 2's "Completed Phase 2 milestones"
below) closed the "never run at scale against real papers" half of this
gap, measuring deterministic-extraction coverage across the full
943-paper real corpus for the first time and finding two concrete,
diagnosed recall gaps (structured-section heading matching, study-type's
closed vocabulary), both since authorized and fixed (see M38's roadmap
entry below and `docs/history/milestones/m38_extraction_scale_assessment.md`'s "Resolved
follow-up" section for the fixes and the re-measured numbers). **M40**
closed most of the other half: `ke extraction-review-batch-generate` ran
the same deterministic pipeline `ke extraction-review-generate` runs for
one paper across all 943, producing 13,588 draft evidence items (679
papers with at least one, 264 with none) -- the actual review queue a
human works from to promote real `EvidenceRecord`s, which had simply never
been generated before. The real corpus still has exactly two
`EvidenceRecord` rows -- M40 generated the review material, it did not
promote anything; `ke extraction-review-promote` still refuses any item
missing a human-supplied `research_question`/`evidence_direction`, and
that promotion step remains entirely manual by design. M40's first live
run against the real corpus also found and fixed a latent quadratic-time
bug in `knowledge_engine/sentence_split.py` (a single ~180K-character
paper took 30+ seconds; see CHANGELOG) -- exactly the kind of gap this
project's "run it at real scale" discipline exists to catch.
The project owner's initial target was "at least a
couple thousand papers"; that was revised down to **1,000 papers as a
hard cap**, explicitly for GitHub space reasons -- the committed
compressed `corpus_library` snapshot (see below) grows with the corpus,
and a smaller committed ceiling keeps it comfortably under GitHub's
100MB single-file push limit with headroom to spare, rather than
approaching it as the corpus scales toward a couple thousand. Following
the M12->M13->M14 precedent, this needs its own scale-readiness
assessment -- measured stop conditions and license/provenance validation
re-checked at the new scale -- before a bounded discovery/acquisition
run, not an unbounded scale-up.

M27 (issue #133) addressed the other half of this gap: nothing downloaded
survived past a session before, since this project's remote execution
environment starts from a fresh clone every session and the working
database is gitignored. `ke corpus-library-export`/`ke
corpus-library-import` make the corpus's paper-intrinsic content (not raw
PDFs -- those are archived to Google Drive instead, per the project
owner's decision) a persisted, git-committable snapshot -- see
`docs/history/milestones/m27_corpus_library.md`. Past ~605 papers the snapshot exceeds
GitHub's 100MB single-file limit uncompressed; a `.gz` output path
compresses it (roughly 3x on this corpus's page-level text), restoring
headroom without giving up git-committed durability. Actually growing the
corpus toward the owner's 1,000-paper cap remains ongoing operational
work using this tooling plus the existing M14 pipeline, not itself
scheduled as a numbered milestone. At 951 papers (~64MB compressed) the
corpus is already close to that cap; the remaining headroom (49 papers)
is small enough that further growth batches should land close to the
ceiling rather than assume the multi-batch runway earlier "couple
thousand" planning implied. The retstart=3250 batch (943 -> 951) also
surfaced two real limitations worth naming for future batches. First,
PubMed's `sort=pub_date` pagination is not stable across different
calendar days -- newer papers indexed between batches shift what a
given `retstart` offset points to, so 16 of that batch's 50 discovered
candidates turned out to already be in the corpus under an earlier
retstart's results; caught by comparing new candidates' `source_id`s
against `sources.csv` before merging, not by the automated discovery/
adjudication pipeline itself, which only deduplicates PMIDs within a
single run. Second, and more serious -- caught by Codex review on the
growth PR, not by that same manual check -- comparing only against
`sources.csv`'s currently-*included* rows missed that a PMID can also
be a previously-*rejected* record resurfacing under a new retstart
offset: 6 of the batch's remaining 33 scope-passed candidates were
exact PMID matches for papers `data/corpora/glp1_weight_loss/README.md`
already documents as manually excluded from the `retstart=3000` batch
(a bariatric weight-regain prediction model, a T2D/STEMI in-hospital-
outcomes study, a diabetic-eye-disease progression study, a T2D
sibling-pairs genetics study, a coronary ischaemia-reperfusion
antiplatelet study, and a T2D policy-life-expectancy model), and a
closer re-read of the same established exclusion patterns (in
particular "diagnostic/measurement-only, no treatment evaluated" and
"off-target primary disease, target disease only an incidental
covariate") caught 3 more the initial scope pass missed. This project
has now hit this exact failure mode -- a previously-rejected PMID
resurfacing under a later batch's different retstart offset -- at both
`retstart=3000` and `retstart=3250`; `sources.csv` only records what is
currently included, not a durable ledger of what has already been
reviewed and rejected. **M53** built that ledger:
`knowledge_engine.rejected_candidates` (a per-corpus CSV keyed by
`pmid`, one row per rejection with a fixed `reason_category` vocabulary
matching the exclusion patterns established above) plus two CLI
commands -- `ke rejected-candidates-add` appends a batch of
already-decided rejections (never re-deciding one itself, the same
validate-only posture as `ke evidence-validate`), never overwriting an
existing pmid's row; `ke rejected-candidates-check` splits a fresh
discovery batch into net-new versus already-rejected before any review
time is spent, reading either a raw discovery JSON's `"candidates"` list
or an adjudication worksheet's `"items"` list. This is a real
prerequisite for unattended, continuously-scheduled discovery (see the
Long-Term Vision doc's live, connected end state) -- rediscovering the
same README history by hand does not survive a discovery pipeline
nobody is reading output from in real time. Historical exclusions
predating this ledger were never recorded with an exact PMID (only
prose descriptions in `README.md`), so they are not backfilled --
reconstructing them by fuzzy title matching would risk exactly the kind
of silent misidentification this ledger exists to prevent; the ledger
starts capturing rejections from this point forward, a known, accepted
gap, not a defect. **M55** (`docs/history/milestones/m55_discovery_cycle.md`) built the
schedulable orchestration this prerequisite unblocked: `ke
discovery-cycle-run` chains one page of `pubmed-candidate-discover`,
M14's existing deterministic adjudication, and an M53 ledger check into
a single command with its own persisted pagination state, ready to be
invoked by cron/systemd/any scheduler. It deliberately stops before
acquisition -- deterministic scope adjudication alone has a measured,
real residual false-accept rate (see this section's own `retstart=3000`/
`retstart=3250` history above), a materially different, harder-to-
reverse risk than M52's evidence-direction nuance, so each cycle writes
a bounded worksheet for the same human/AI scope screen this project has
always required before `ke pmc-oa-acquire`. Live-verified against the
real PubMed/PMC APIs: pagination correctly resumed across cycles, and a
real PMID added to the ledger was correctly excluded on a repeat run of
the same page. **M56** authored the real corpus's first
`RelationshipRecord`s: 3 `supports` edges (STEP 5 trial, Gao et al.'s
meta-analysis, and the SELECT trial, all reporting the same direction
for semaglutide versus placebo on body weight), filtered from `ke
graph-relationship-candidates`'s 308 structural candidate pairs down to
the 3 with 2+ shared PICO-resolved concepts and reviewed against each
record's full text before authoring a rationale. The graph's
`relationship_edges` count moves from 0 to 3 -- the first real, non-zero
number the "Unconfirmed Claims"/Tracking-the-Unknown report and
`knowledge-engine-web`'s corresponding pages have ever shown. **M59**
grew this to 7 edges: with the 2+-shared-concept candidate pool
exhausted by M56 (`ke graph-relationship-candidates --min-shared-concepts
2` returns zero pairs), reviewed the remaining single-concept
(`semaglutide`) candidates' full PICO/`result_summary` text by hand and
authored 4 more records -- 3 `supports` (an observational
obesity/cardiometabolic cohort, a heart-failure-with-reduced-ejection-
fraction cohort with a real control arm, and a PMOS cohort, all reporting
the same body-weight-reduction direction in populations STEP 5/Gao/SELECT
did not test) and 1 `contextualizes` (a head-to-head tirzepatide-vs-
semaglutide comparison, which compares against an active drug rather
than placebo and so cannot directly confirm or refute the existing
`supports` cluster, but adds real magnitude context). `unconfirmed_claims`
drops from 152 to 148. Every candidate considered but not used (drug-name
overlap only, on a genuinely different outcome -- e.g. BNP, menstrual
function as a *primary* endpoint) was left alone rather than forced into
a relationship it would misrepresent. **M60** added
`ke relationship-review-worksheet`, batching that same manual-review
work: it assembles N candidate pairs' full PICO fields side by side plus
a fill-in-the-blank `RelationshipRecord` template, so a review session
isn't limited to opening one evidence record at a time -- the exact
mechanical assembly done by hand for every M56/M59 relationship. Adds no
candidate-selection or ranking logic of its own; still 100% human
judgment on whether, and how, two claims relate.

### Supporting operator durability

The Google Drive backup subsystem is supporting operator infrastructure for
protecting local SQLite backup bundles during the M14-era rehearsal work. It does
not change corpus inclusion, discovery, approval, acquisition, parsing,
deduplication, provenance, or import semantics. It should remain optional,
operator-controlled, and independently documented. Any expansion beyond backup
transport and recovery support requires a dedicated roadmap decision or ADR.

Detailed milestone records include:

- `docs/history/milestones/m6_phase1_corpus_ingestion_plan.md`
- `docs/history/milestones/m7_manifest_validation_foundation.md`
- `docs/history/milestones/m8_import_run_persistence.md`
- `docs/history/milestones/m9_small_ingestion_pilot.md`
- `docs/history/milestones/m10_duplicate_detection_resumability_plan.md`
- `docs/history/milestones/m10_operational_contract.md`
- `docs/history/milestones/m10_release_notes.md`
- `docs/history/milestones/m12_100_paper_rehearsal.md`
- `docs/history/milestones/m13_scale_readiness_decision.md`
- `docs/history/milestones/m14_500_paper_rehearsal_report.md`
- `docs/history/audit_remediation_register.md`

## Phase 2: Evidence Records

- Extract claims, methods, results, limitations, and evidence quality markers.
- Keep every generated structure traceable to source text spans.
- Add automated validation and optional post-working-version human audit workflows.
- Use `docs/phase2_design.md` as the detailed design reference. Its first
  concrete prerequisite, page/span-level extraction provenance, is implemented
  (see `docs/technical_debt.md`). Extraction methodology was decided as
  rule-based pattern matching combined with structured-section heuristics, no
  new dependency; see the design doc's Extraction Methodology section.
- Evidence Records originally stopped short of automated,
  research-question-relative judgment: assigning a `research_question`,
  classifying `evidence_direction` against it, and any real confidence
  *rating* (beyond the existing free-text `confidence_note` field) were
  left for a human reviewer to supply, as the deliberate seam where the
  future `knowledge-engine-ai` layer plugs in; see
  `docs/roadmap/long_term_vision.md`'s AI Interface Layer section. **M52**
  revisited the `research_question`/`evidence_direction` half of that
  seam specifically: after four evidence-promotion batches all built by
  hand-reading the source paper and classifying correctly, the project
  owner judged the mandatory human-confirmation step a bottleneck
  disproportionate to its accuracy benefit and authorized automating it.
  `ke extraction-review-autoclassify` now templates `research_question`
  deterministically from a draft item's own already-extracted PICO
  fields, and classifies `evidence_direction` deterministically by
  extending M18's framing-cue patterns with null-result phrasing, safe
  to default to `supports` in the absence of a cue *because* the
  research question is now mechanically derived from the same claim's
  own fields, not an externally supplied one. The confidence-*rating*
  half of the seam is unchanged and remains entirely out of `core`'s
  scope -- see `docs/core_interface_contract.md`'s "The seam" section
  for the full, honest accounting of what changed and what did not.
- PICO fields (population, intervention, comparator, outcome),
  `study_type`, and `limitations` are a different case: paper-intrinsic
  facts, not judgment relative to a research question, so deterministic,
  non-human-typed extraction was prioritized for them rather than an
  indefinitely deferred human-review field -- see
  `docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed Fields
  section. `study_type`/`limitations` shipped in M26; full PICO
  extraction shipped in M28, once the corpus described above under
  Phase 1 was large enough to tune against and the project owner decided
  605 papers was sufficient to stop growing it further.
- `docs/reference_knowledge_layer_design.md`'s Addendum (items 1-4) names
  four reference-layer integration points buildable here without waiting
  on Phase 4/5: drug identity normalization for report-*display*
  grouping only, never for deciding which records get pooled into a
  question's confidence rating (on M42's `ingredients` field), a
  coverage-gap disclosure flag for terms with no reference-layer match,
  provenance-footer discipline for any reference text surfaced anywhere,
  and a reviewer aid surfacing definitions inline around
  `ke extraction-review-promote`. None of them touch the confidence
  rating, including indirectly through the compounding step's
  participant set -- see that section for the precise boundary, tightened
  after Codex review on PR #180. **Items 2-4 shipped in M45**
  (`ke extraction-review-annotate`, see `docs/history/milestones/m45_extraction_review_annotate.md`):
  a new command attaches RxNorm/MeSH reference context directly onto
  draft evidence items before a reviewer runs
  `ke extraction-review-promote`.

### Completed Phase 2 milestones

M16-M28 built and unit-tested Phase 2's deterministic extraction pipeline
against synthetic fixtures. M38 and M40 below are the two milestones that
later ran that pipeline against the real corpus at scale for the first time.

- **M38** closed the "Scaling beyond 500 papers for Phase 2 tuning" gap's
  own named prerequisite: measured M16-M28's deterministic extraction
  coverage in aggregate across the real corpus at scale for the first
  time (943 papers), rather than only unit-tested fixtures and individual
  by-hand `ke extraction-review-generate` runs.
  `knowledge_engine/extraction_corpus_report.py` (core, tested) plus
  `scripts/m38_extraction_corpus_report.py` (thin CLI wrapper) run the
  same pipeline across every persisted paper and report coverage counts,
  read-only -- no draft items, extraction runs, or `EvidenceRecord` rows
  produced. Findings: section detection covers 99.7% of papers overall
  but only 63% for `results`/`conclusion` specifically; claim-candidate
  detection (scoped to those two section types) reaches 63.2% of papers,
  with a diagnosed root cause split (56% missing the scoped sections
  entirely -- often genuinely non-quantitative reviews; 44% a real recall
  gap traced to a concrete example where an inline `"Results:"` label
  never matches M16's deliberately conservative full-line-only heading
  pattern); study-type classification covers 40.6%, an expected
  consequence of an 8-design closed vocabulary against a more diverse
  real corpus; PICO fields range 45-74% individually, 23.3% for all four
  together. Both diagnosed gaps were flagged, not fixed, pending explicit
  owner decision, the same way `evaluate_scientific_scope`'s documented
  weakness was flagged rather than unilaterally fixed -- **since
  authorized and fixed**: `detect_sections` now also recognizes an inline
  `"Label: text"` heading (not just alone on its own line);
  `classify_study_type`'s vocabulary grew by five designs
  (narrative_review, cross_over_trial, retrospective_study, case_series,
  case_report); and PICO's own section scoping was widened to offset a
  regression the section-detection fix otherwise introduced (structured
  abstracts that used to stay one scanned `abstract` blob now correctly
  split into fragments PICO's original scoping didn't cover). Re-measured
  after the fix: results-section detection 63.1% -> 72.4%,
  conclusion-section detection 64.4% -> 75.6%, claim candidates 63.2% ->
  72.0%, study type classified 40.6% -> 43.7%, PICO all-four-fields 23.3%
  -> 26.2% -- every signal improved or held steady. See
  `docs/history/milestones/m38_extraction_scale_assessment.md`.
- **M40** ran the deterministic extraction-review pipeline at scale for
  the first time, producing the real corpus's actual draft-evidence-item
  review queue -- the real corpus had exactly two `EvidenceRecord` rows,
  both hand-authored before any automated extraction existed, because
  `ke extraction-review-generate` (M19/M20) had only ever been run one
  paper at a time. `knowledge_engine/extraction_review_batch.py`
  (`run_extraction_review_for_paper` -- factored out of the single-paper
  CLI command so both share one pipeline implementation --
  `run_batch_extraction_review`) plus a new `ke
  extraction-review-batch-generate` CLI command run the same pipeline
  across every persisted paper into one combined JSONL queue (every item
  carries its own `source_span.paper_id`, so items stay traceable without
  per-paper files). Still not validated evidence: `ke
  extraction-review-promote`'s human-review gate is unchanged. Run
  against the real 943-paper corpus: 13,588 draft items across 943
  papers (679 with at least one, 264 with none, 0 skipped for missing
  pages). The first live run also found a latent quadratic-time bug in
  `knowledge_engine/sentence_split.py`'s abbreviation check -- a single
  ~180K-character paper took 30+ seconds -- fixed by bounding the check
  to a fixed trailing window instead of the whole growing prefix; the
  full corpus run dropped from over 20 minutes to 21 seconds.

## Reference Knowledge Layer

Not one of the numbered phases above -- a cross-cutting layer giving the
extraction pipeline and future AI Interface Layer the background context
(drug names, medical terminology, chemical structure) a primary-research
paper always assumes but never restates. Corresponds to
`knowledge-engine-reference` in the long-term ecosystem; see
`docs/roadmap/long_term_vision.md` and
`docs/reference_knowledge_layer_design.md`. M41-M44 built four
independent live-lookup sources; M45 wired three of the design doc's
Addendum items into Phase 2's review workflow, so it depends on Phase 2
existing first. Always background context, never evidence -- none of it
is routed through `EvidenceRecord` promotion or the confidence rating.

### Completed Reference Knowledge Layer milestones

- **M41** built the reference knowledge layer's first slice --
  `docs/reference_knowledge_layer_design.md`'s sketch named the gap this
  closes: a paper's claim text names terms and mechanisms (e.g. "GLP-1
  receptor agonism", "SGLT2 inhibitor") a domain expert already knows but
  the extraction pipeline has no equivalent grounding for. A new
  `ke reference-lookup <term>` command and
  `knowledge_engine/reference_lookup.py` query Wikipedia's public REST
  summary API live -- no stored corpus, no API key, content under CC
  BY-SA (a license family `license_rules.py` already recognizes) --
  and return the term's title, description, plain-language extract,
  source URL, and license, or `found: false` if Wikipedia has no
  article. Explicitly background context, not evidence: never routed
  through `EvidenceRecord` promotion, and never merged into the evidence
  corpus's own search commands. Live-verified against real terms
  (`semaglutide`, `SGLT2 inhibitor`, a disambiguation page, a not-found
  term) before and after building the parser. See
  `docs/history/milestones/m41_reference_lookup.md`.
- **M42** added a second live-lookup reference source, NLM's RxNorm API,
  alongside M41's Wikipedia lookup. A new `ke rxnorm-lookup <term>`
  command and `knowledge_engine/rxnorm_lookup.py` resolve a drug name to
  its own RxNorm concept (RxCUI, canonical name, term type, and synonym)
  plus its underlying ingredient concept(s) (an `ingredients` list, via
  RxNav's `related.json?tty=IN` relationship) through a dedicated
  host-allowlisted transport (`rxnorm_http.py`'s `UrllibRxNavTransport`,
  since RxNav is a distinct NLM host from the literature-scoped
  `ncbi_http.py`). Chosen as the second source because it needs no API
  key and closes a gap Wikipedia's title-matching lookup leaves open for
  this corpus specifically: a generic name (e.g. "semaglutide") and its
  brand name (e.g. "Ozempic") get different top-level RxCUIs -- RxNorm's
  own model correctly keeps those distinct -- but resolve to the *same*
  `ingredients` entry, which is what a caller compares to recognize them
  as the same underlying drug. Codex review on PR #179 caught that the
  first version of this milestone claimed that normalization without
  actually following the ingredient relationship (the top-level `rxcui`
  was returned unchanged either way); fixed before merge by adding the
  `related.json` call, verified live that `semaglutide` and `Ozempic`
  then share one `ingredients` entry, and that a combination-drug brand
  ("Glyxambi") resolves to more than one. Explicitly background context,
  not evidence, with the same non-`EvidenceRecord` boundary M41 drew.
  See `docs/history/milestones/m42_rxnorm_lookup.md`.
- **M43** added a third live-lookup reference source, NLM's MeSH
  database, alongside M41's Wikipedia lookup and M42's RxNorm lookup. A
  new `ke mesh-lookup <term>` command and `knowledge_engine/
  mesh_lookup.py` resolve a term to its canonical MeSH descriptor (MeSH
  ID, preferred heading, scope note/definition, and entry-term
  synonyms) via NCBI's public E-utilities API (`db=mesh`), reusing
  `ncbi_http.py`'s existing `UrllibNcbiTransport` directly -- no new
  transport module needed, since `eutils.ncbi.nlm.nih.gov` is already
  allowlisted for literature discovery. Chosen as the third source
  because it fills a gap neither Wikipedia (prose) nor RxNorm
  (drug-only) closes: NLM's own controlled vocabulary for diseases,
  procedures, and biomedical concepts generally. MeSH's `esearch` is a
  full-text search, not an exact-match lookup -- live-verified that
  searching "obesity" returns 37 loosely related candidates whose first
  result ("Anti-Obesity Agents") is the wrong concept entirely, so the
  service resolves a term only when exactly one candidate is both a
  true MeSH descriptor record and has the queried term as one of its
  own entry-term synonyms (case-insensitive exact match), never the
  closest guess -- confirmed correct for "obesity" -> "Obesity" (MeSH
  ID D009765), "type 2 diabetes" -> "Diabetes Mellitus, Type 2" (MeSH ID
  D003924), and confirmed correctly `found: false` for "GLP-1 receptor
  agonist" (singular), since MeSH only records the plural entry term.
  Explicitly background context, not evidence, with the same
  non-`EvidenceRecord` boundary M41/M42 drew. See
  `docs/history/milestones/m43_mesh_lookup.md`.
- **M44** added a fourth live-lookup reference source, NLM/NCBI's
  PubChem PUG REST API, alongside M41's Wikipedia lookup, M42's RxNorm
  lookup, and M43's MeSH lookup. A new `ke pubchem-lookup <term>`
  command and `knowledge_engine/pubchem_lookup.py` resolve a chemical
  compound name to its PubChem Compound ID (CID) and structured
  chemical identifiers -- title, IUPAC name, molecular formula,
  molecular weight, and canonical SMILES -- through a dedicated
  host-allowlisted transport (`pubchem_http.py`'s
  `UrllibPubchemTransport`, since `pubchem.ncbi.nlm.nih.gov` is a
  distinct NLM/NCBI host from both `eutils.ncbi.nlm.nih.gov` and
  `rxnav.nlm.nih.gov`). Chosen as the fourth and, per the design doc's
  "third option" section, last named live-lookup candidate because it
  fills a gap none of the first three cover: real chemical-structure
  data, not just a normalized name or a controlled vocabulary. Two real
  API behaviors were verified live before writing the parser: requesting
  the `CanonicalSMILES` property returns the result under a *different*
  response key, `ConnectivitySMILES` (PubChem renamed the property
  internally but left the old request-parameter name aliased), so this
  module requests `ConnectivitySMILES` directly; and PubChem indexes
  whatever name strings were actually deposited alongside real
  compounds, not a curated concept vocabulary -- "GLP-1 receptor
  agonist" (a mechanism class) resolves to a real, specific compound
  (CID 177864544) rather than an empty result, and this module reports
  that rather than guessing what a caller "probably" meant. `Molecular
  Weight` is tolerated as either a JSON string or number, matching a
  real variance observed in API responses. Codex review on PR #183
  caught two further real gaps before merge: (1) a name resolving to
  more than one compound (live-verified: "estrogen" returns two distinct
  CIDs) was silently resolved to whichever entry came first; fixed to
  decline (`found: false`) whenever more than one candidate matches,
  the same posture M43 uses for ambiguous MeSH matches. (2) the license
  field labeled every result a blanket U.S. government public-domain
  work, but PubChem aggregates data from many external depositors
  (live-verified: CID 4091/metformin's own description is sourced from
  ChEBI, not NCBI); fixed to state that provenance is mixed and reuse
  terms should be verified source-by-source. Explicitly background
  context, not evidence, with the same non-`EvidenceRecord` boundary
  M41/M42/M43 drew. See `docs/history/milestones/m44_pubchem_lookup.md`.
- **M45** wired three of `docs/reference_knowledge_layer_design.md`'s
  Addendum items (2-4) into the Phase 2 review workflow: a new `ke
  extraction-review-annotate` command reads the draft evidence items `ke
  extraction-review-generate`/`extraction-review-batch-generate` already
  produce and attaches a `reference_context` object to each one, built
  only from PICO fields M28's deterministic extraction already
  populated -- `intervention`/`comparator` through M42's RxNorm lookup
  (both name a drug or treatment), `population`/`outcome` through M43's
  MeSH lookup (both describe a medical concept). A term with no
  reference-layer match is written out as `found: false`, never silently
  omitted (item 2); every embedded result keeps its own
  `source_url`/`license`/`retrieved_at` (item 3); a reviewer sees the
  definition inline in the same file they edit to add
  `research_question`/`evidence_direction`, before running `ke
  extraction-review-promote` (item 4). Deliberately a separate, opt-in
  step from generation: `ke extraction-review-generate`/
  `-batch-generate` must stay network-free even at the corpus's real
  scale (M40: 13,588 draft items across 943 papers), so annotation is a
  reviewer-initiated command run against the specific paper(s) actually
  under review. Codex review on PR #184 caught that the first version
  passed a PICO field's whole raw value to RxNorm's/MeSH's exact-match
  lookups on the incorrect assumption that M28 stores an isolated term;
  re-sampling the real corpus showed real field values are routinely
  entire multi-line, citation-laden paragraphs, so the original version
  returned `found: false` for nearly every real draft item. Fixed by
  scanning a small, bounded set of single-word candidates (first 30
  tokens, stopwords dropped, capped at 20 per field) from the raw text
  against the unchanged exact-match lookups, declining (`found: false`)
  when more than one distinct concept resolves among the candidates
  tried -- the same ambiguity discipline M43/M44 established -- rather
  than guessing which one is "the" term. Live-verified against the real
  corpus after the fix: a comparator field naming both "semaglutide" and
  "placebo" together correctly declines; a fisetin-supplementation
  paper's `comparator`/`population` fields correctly resolve "fisetin"
  (RxCUI 2667741) and "screening" (MeSH `D008403`) across every draft
  item drawn from that paper. A second Codex finding on the same PR
  caught that an empty result queue left a `--force`-targeted output file
  untouched instead of clearing it; fixed to always overwrite the output
  path, even when there is nothing to write. With identical candidate
  terms cached within one run, network calls are bounded to the number of
  distinct candidates actually tried, not items -- but measured honestly,
  not fast: live-verified at roughly 30 distinct RxNorm and 30 distinct
  MeSH terms for a single real paper's full draft-item set, on the order
  of a minute or more of network calls. Never touches
  `research_question`/`evidence_direction`, and never changes `ke
  extraction-review-promote`'s existing refusal to promote a record
  missing either. See `docs/history/milestones/m45_extraction_review_annotate.md`.

## Phase 3: Search Plus Semantics

- Add embeddings using a pluggable vector index. (Done, M30: FAISS.)
- Support local FAISS and server-backed Qdrant. (Both implemented -- FAISS
  M30, Qdrant M33 (`QdrantVectorIndex`, not yet wired into the CLI
  commands -- no operator need for that has appeared).)
- Keep lexical search as a transparent baseline. Unchanged: `ke search`/
  `ke answer` remain FTS5-only; `ke vector-search` is a separate command.
- Use `docs/phase3_design.md` as the detailed design reference. Its
  embedding-generation decision -- a new-dependency and offline-posture
  choice for the project owner, the same way Phase 2's extraction
  methodology was decided before any extraction code was written -- is
  resolved as of M31: **both** a local (`sentence-transformers`) and an
  external-API (OpenAI) `EmbeddingGenerator` are implemented. **M30**
  implemented the retrieval side first: a pluggable `VectorIndex`
  interface, a local FAISS backend, and two CLI commands
  (`ke embedding-index-build`, `ke vector-search`) operating on
  externally-supplied vectors. **M31** added `ke embedding-generate
  --generator local|openai`, which produces the same vectors file those
  M30 commands already consume. **M32** wired `ke vector-search
  --query-text` to embed a free-text query live with either generator,
  removing the "queries must be pre-embedded" friction M30/M31
  deliberately left in place. **M33** added `QdrantVectorIndex`, the
  second `VectorIndex` implementation the roadmap named from the start,
  targeting an operator-run Qdrant server -- usable via direct Python
  import today; CLI wiring is a future step. **M39** closed the last open
  Phase 3 design question: combining lexical (`ke search`/`ke answer`) and
  semantic (`ke vector-search`) results into one ranked list. A new
  `ke fused-search <query-text>` command runs both retrieval signals
  against the same free-text query and combines the two ranked paper_id
  lists with Reciprocal Rank Fusion (`knowledge_engine/search_fusion.py`) --
  a paper found by both signals outranks one found by only one, with no
  arbitrary cross-system weight to tune. `ke search`/`ke answer`/
  `ke vector-search` are unchanged; `fused-search` is additive. See
  `docs/phase3_design.md`'s Open Questions.

## Phase 4: Knowledge Graph

- Model concepts, claims, citations, support, contradiction, and uncertainty.
- Add Neo4j or another graph backend behind a repository interface.
- Corresponds to `knowledge-engine-graph` in the long-term ecosystem; see
  `docs/roadmap/long_term_vision.md`.
- **`docs/phase4_design.md`** is the implementation-ready design sketch,
  written before any Phase 4 code, mirroring `docs/phase2_design.md`/
  `docs/phase3_design.md`'s role for their phases. Grounded in a fresh
  measurement of the real 951-paper corpus (44% study-type coverage, 26%
  full-PICO coverage, 0% structured citations -- citation extraction is
  real, unscoped prerequisite work, not yet built). Resolves the graph
  backend question: relational tables in the existing SQLite database
  first, behind a `GraphRepository` interface, no Neo4j for the first
  slice -- mirroring Phase 3's own FAISS-before-Qdrant sequencing
  (embedded/no-server first; a dedicated graph database added later only
  if a real, evidenced need for graph-native traversal appears).
- This is also the natural home for `docs/roadmap/long_term_vision.md`'s
  Stability Score (claim revision history) and Tracking the Unknown
  (missing experiments, weak-evidence areas, and unanswered questions as
  first-class, graph-shaped entities) -- neither has a path before the
  graph exists to hold them.
- `docs/reference_knowledge_layer_design.md`'s Addendum (item 10) names
  reference-layer definitions (M41 Wikipedia, M42 RxNorm, or the
  still-unbuilt stored-textbook path) as future content for Graph
  concept nodes, distinct from the paper-level evidence nodes that cite
  them -- the same distinction the Architecture sketch section above
  already drew before any Graph code existed.
- **M46 (`docs/history/milestones/m46_graph_repository.md`)** builds the first Phase 4 code:
  the `graph_concepts`/`graph_claims`/`graph_claim_concepts`/
  `graph_claim_relationships` schema (version 8) exactly as designed,
  the `GraphRepository` persistence layer, and `ke graph-build`, which
  populates the graph from a validated `EvidenceRecord` file (reusing
  M45's `annotate_draft_items` unchanged for PICO-to-concept resolution)
  and an optional validated `RelationshipRecord` file. Live-verified
  against the repo's real, if small, committed evidence corpus (2
  records): 2 claims, 2 concepts, 4 claim-concept edges. `graph_citations`
  remains deferred, unscoped work.
- **M47 (`docs/history/milestones/m47_graph_citations.md`)** did the citation-list
  real-corpus verification pass the design doc called for, then built
  `graph_citations` (schema version 9) and `ke graph-citations-build`.
  Sampling real reference lists found at least three distinct citation
  styles plus PDF-extraction noise -- too much for a naive parser -- but
  also found the schema only needs DOI-identity matching against papers
  already in the corpus, which needs no per-entry parsing at all. Run
  against the real 960-paper local corpus: exactly 5 intra-corpus
  citation edges, individually verified as genuine.
- **M48 (`docs/history/milestones/m48_graph_report.md`)** closed the read-side gap M46/M47
  left open: `ke graph-build`/`ke graph-citations-build` could write to
  the graph but nothing could read it back via the CLI. `ke graph-report`
  adds a corpus-wide summary mode plus per-claim (concepts by PICO role,
  relationship edges) and per-paper (citation edges, as citer and cited)
  detail modes, purely a display layer over `GraphRepository`. Also
  backfilled a real, pre-existing test gap: M46/M47's CLI commands had
  never been exercised through a `CliRunner`-level test until this
  milestone added `tests/test_graph_cli.py` for all three commands
  together.
- **M49 (`docs/history/milestones/m49_graph_relationship_candidates.md`)** built the
  automated relationship candidate-surfacing `docs/phase4_design.md`'s
  Open Questions deferred until `graph_claims`/`graph_claim_concepts`
  existed: `ke graph-relationship-candidates` surfaces claim pairs
  sharing a PICO-resolved concept, with a pair already linked by a
  validated relationship edge excluded. Structural overlap only -- it
  never infers, detects, or suggests a relationship type or rationale,
  the same boundary `ke relationship-validate` already draws; that
  judgment call stays entirely with the human reviewer. Live-verified
  against the real corpus's 2 validated `EvidenceRecord`s: correctly
  surfaces the one real pair sharing 2 concepts (`semaglutide`,
  `placebo`), and correctly reports 0 pairs when
  `--min-shared-concepts` is raised past that real count.
- **M50 (`docs/stability_and_tracking_design.md`)** wrote the dedicated
  follow-up design `docs/phase4_design.md`'s Open Questions deferred for
  Stability Score and Tracking the Unknown, then built the one part of
  it that needed no further owner decision: `supersedes`, a fifth
  `RelationshipRecord`/`graph_claim_relationships` type -- a newer claim
  explicitly revising an older one, reusing 100% of the existing
  relationship machinery rather than a new table. An honest,
  non-inferred "gap" is scoped as a claim with zero relationship edges
  of any type; the actual Stability sub-score formula and a richer
  "weak evidence area" report stay explicitly out of `core`'s scope, the
  same boundary the Confidence Rating Design Guidance already draws.
  Required a real schema migration (SQLite `CHECK` constraints cannot be
  altered in place, so version 10 rebuilds `graph_claim_relationships`)
  -- live-verified against a copy of the real corpus database, which
  upgraded cleanly from its actual current schema version.
- **M51 (`docs/history/milestones/m51_graph_unconfirmed_claims.md`)** built the first
  concrete slice of `docs/founding_vision.md`'s Addendum, "Tracking the
  Unknown": `ke graph-unconfirmed-claims` lists every claim no
  relationship edge of any type touches yet, the honest, non-inferred
  "gap" signal M50 already decided on. Purely a display layer over a new
  `GraphRepository.unconfirmed_claims` outer join -- no research-question
  grouping, no severity ranking, no cross-reference with `ke
  graph-relationship-candidates`'s own output, all explicitly left for
  later per M50's own Open Questions. Live-verified against the real
  corpus: both real claims list as unconfirmed before any relationship
  exists, correctly drops to zero once one real `supports` relationship
  is built between them.

## Phase 5: Human Interface

- Add API and web repositories as separate projects.
- Provide evidence-first explanations with visible uncertainty and sources.
- This is where the future `knowledge-engine-ai`/`-web`/`-agents` layers'
  research-question crafting, evidence synthesis, and confidence rating
  (see `docs/roadmap/long_term_vision.md`) actually reach a person, on top
  of the Evidence and Knowledge Graph layers Phases 2 and 4 build.
- `docs/roadmap/long_term_vision.md`'s Discovery Engine (hypothesis
  generation, experiment suggestion) and Education Engine (adaptive
  explanations, learning paths) are not yet claimed by any phase or
  package here -- an open decision, not a silent omission.
- `docs/reference_knowledge_layer_design.md`'s Addendum (items 5-9) names
  five reference-layer report features that need a renderer to exist
  here first: inline glossary/definitions, a disambiguation guard,
  pre-synthesis term-extraction caching, a reading-level toggle, and an
  "assumed background" appendix. Same non-negotiable boundary as
  everywhere else in that addendum: none of them feed the confidence
  rating.
- `docs/ai_interface_layer_scoping.md` and `docs/ai_layer_architecture.md`
  record scoping ideas for `knowledge-engine-ai`'s Decision, Discovery,
  and Education Engines -- the latter's refined "one Research Copilot,
  four intelligences" framing, a three-way Evidence Quality/Consensus/
  Claim Confidence split, and domain-specific confidence profiles. Both
  are records of ideas, not implementation-ready designs; no code, no
  repository yet, per the project owner's explicit direction.
- **M57** (see `docs/evidence_intelligence_design.md`) is the
  implementation-ready formula both documents above named as their own
  trigger condition: a deterministic, no-LLM Evidence Quality/Consensus/
  Claim Confidence computation grounded in the real 155-record GLP-1
  corpus, scoped to exactly Stage 3 of `ai_layer_architecture.md`'s
  5-stage build sequence and exactly the Clinical Medicine profile.
  Design only in this milestone.
- **M58** implements M57's design: `knowledge_engine/evidence_intelligence.py`
  (`compute_evidence_quality`, `compute_evidence_consensus`,
  `compute_claim_confidence`, `compute_evidence_coverage`,
  `render_synthesis` -- pure functions, no LLM, no new schema) and `ke
  evidence-intelligence --evidence <records.jsonl> --evidence-record-id
  <id>`, live-verified against the real corpus (e.g. the STEP 5 trial
  claim, which has two `supports` edges from M56, scores Evidence
  Quality 94/100, Evidence Consensus 100/100, Claim Confidence 96/100;
  an unconnected claim honestly shows "not yet assessable" rather than a
  guessed number). Web rendering of these scores on the existing
  claim/evidence detail pages, and authoring more `RelationshipRecord`s
  so more of the corpus leaves the "not yet assessable" state, are
  tracked as parallel follow-on work, not part of this milestone.

## Release Milestones

- `v0.1.0`: Phase 0 local source vault, CLI, tests, docs, and repository hygiene.
- `v0.1.1`: Bug fixes and setup improvements.
- `v0.2.0-alpha.1`: GLP-1 retrieval and manual evidence vertical-slice prerelease.
- `v0.2.0`: Repeatable corpus ingestion, duplicate handling, resume/retry, metadata
  preview/enrichment, and bounded scale-rehearsal evidence.
- `v0.3.0`: Expanded metadata enrichment and citation capture.
- `v0.4.0`: Knowledge graph foundation.
- `v0.5.0`: Vector search.
- `v0.6.0`: Stabilize `core`'s Evidence and Knowledge Graph output as a
  consumable interface (not new reasoning logic in `core` itself) so the
  separately versioned `knowledge-engine-ai` package can begin its own
  reasoning experiments on top of it; see
  `docs/roadmap/long_term_vision.md`. **`docs/core_interface_contract.md`**
  documents this contract as it exists today (config, CLI surface, Evidence/
  Relationship Record schemas, reference-layer output shapes), written ahead
  of the graph so a consuming layer already knows what to expect from
  everything through Phase 3; it will need a Graph section once Phase 4
  ships.
- `v0.9.0`: Feature-complete beta.
- `v1.0.0`: Stable public release.
- Post-`v1.0.0`: `docs/roadmap/long_term_vision.md`'s Discovery Metrics
  (Time to Discovery, Knowledge Coverage, Contradiction Resolution Rate,
  and related measures) become meaningful only once the Discovery and
  Decision layers they measure exist -- named here so they are not
  forgotten, not because they are actionable before then.

## Detailed Roadmaps

- `docs/phase1_design.md`
- `docs/roadmap/phase0.md`
- `docs/roadmap/phase1.md`
- `docs/roadmap/phase2.md`
- `docs/phase3_design.md` and `docs/roadmap/phase3.md` -- design sketch and
  goals; M30 (FAISS retrieval plumbing), M31 (local + OpenAI embedding
  generators), M32 (free-text `ke vector-search --query-text`), M33
  (`QdrantVectorIndex`, not yet CLI-wired), and M39 (`ke fused-search`,
  lexical+semantic Reciprocal Rank Fusion) are implemented
- `docs/roadmap/long_term_vision.md` -- the multi-package ecosystem and final
  goal these phases build toward, including the future `knowledge-engine-ai`
  layer's role once Phase 2's Evidence Records exist
- `docs/reference_knowledge_layer_design.md` -- design sketch for a
  reference knowledge layer giving the extraction pipeline and future AI
  Interface Layer the background context a primary-research paper always
  assumes but never restates. **M41** (see the "Reference Knowledge
  Layer" section above) built the sketch's
  recommended live-lookup path's first slice, `ke reference-lookup`
  against Wikipedia; **M42** added a second slice, `ke rxnorm-lookup`
  against NLM's RxNorm API for structured drug-name normalization;
  **M43** added a third slice, `ke mesh-lookup` against NLM's MeSH
  database for medical-concept terminology; **M44** added a fourth and
  last named slice, `ke pubchem-lookup` against NLM/NCBI's PubChem PUG
  REST API for chemical-compound structure data. **M45** then wired
  three of the design doc's Addendum items (coverage-gap flag,
  provenance-footer discipline, reviewer aid) into the Phase 2 review
  workflow via `ke extraction-review-annotate`. The stored-textbook path
  (open-license chemistry/biology/microbiology/physics/pharmacology
  textbooks) remains unbuilt pending real licensing/storage decisions.
  Explicitly not evidence and not part of the paper corpus's
  1,000-paper cap. See `docs/roadmap/long_term_vision.md`'s matching
  section, `docs/history/milestones/m41_reference_lookup.md`, `docs/history/milestones/m42_rxnorm_lookup.md`,
  `docs/history/milestones/m43_mesh_lookup.md`, `docs/history/milestones/m44_pubchem_lookup.md`, and
  `docs/history/milestones/m45_extraction_review_annotate.md`. The design doc's "Addendum:
  where this plugs into the final report" section records ten concrete
  ways reference-layer content can shape the future AI Interface Layer's
  report (grouping, gap disclosure, provenance labeling, glossary/appendix
  content, Knowledge Graph concept nodes), ordered cheapest-to-build
  first, with the owner's direction to eventually build all ten --
  explicitly none of them feed the report's confidence rating, which
  stays evidence-only per Confidence Rating Design Guidance in
  `docs/roadmap/long_term_vision.md`.
