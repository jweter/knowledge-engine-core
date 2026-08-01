# AI Interface Layer: Scoping Notes for the Three Future Engines

Status: a record of scoping ideas for the future `knowledge-engine-ai`
layer, discussed once Phase 4 (the Knowledge Graph) existed to actually
scope Discovery Engine against -- `docs/roadmap/long_term_vision.md`'s
own "Discovery and Education Layers" section named that as the missing
prerequisite. **This is not a design doc ready for implementation.** No
code exists for any of this, and per the project owner's explicit
direction, no new repository should be created for it yet -- the real
corpus has only 2 validated `EvidenceRecord`s today, so a
synthesis/confidence layer would be scaffolding around nothing, and the
actual confidence-rating formula is deliberately left undesigned until
there's real data to prototype it against (the same "verify against
real data before designing" discipline every `core` and
`knowledge-engine-web` milestone has followed). This document exists so
the ideas are not lost in conversation, the same reason `long_term_vision.md`
itself exists.

**Superseded in part by `docs/ai_layer_architecture.md`**, recorded
after further owner-side design discussion: it resolves this document's
"Bot count" open question below (one Research Copilot orchestrating
four internal intelligences, not two or three separate bots) and
substantially extends the Decision Engine section (three-way confidence
split, domain-specific profiles, the Statistics Auditor, Evidence
Coverage). Discovery Engine and Education Engine's sections below are
unchanged and still current. The "no new repository yet" direction
below still holds.

## The seam applies to all three engines, without exception

`core_interface_contract.md`'s "the seam" is not just a `core` boundary
-- every engine below inherits it. None of the three ever:

- Sets or infers `research_question`/`evidence_direction` on a stored
  `EvidenceRecord` -- those stay externally supplied, always.
- Invents a confidence number, a quality score, or a "significant
  finding" judgment not traceable to a real, cited source.
- Presents background/reference content (Wikipedia, RxNorm, MeSH,
  PubChem -- M41-M45) as if it were evidence, or lets it influence a
  confidence rating. That non-evidence boundary is already
  non-negotiable in `core`; nothing here loosens it.
- Auto-authors a `RelationshipRecord` without a human confirming it --
  narrowing human involvement (better candidate surfacing, pre-drafted
  rationale) is the target, not eliminating the human, per
  `long_term_vision.md`'s Minimizing Human-Typed Fields section.

## 1. Decision Engine -- "chat bot" + "data analyst bot"

Already scoped in detail by `long_term_vision.md`'s existing "The AI
Interface Layer" section: craft the actual research question with the
person, track their research history across sessions, connect a live
search to `core`'s already-validated evidence, judge what accumulated
evidence supports (agreement/disagreement/gaps, not one flattened
answer), and present a real, earned confidence rating -- two-level, per
the Confidence Rating Design Guidance (per-evidence-record confidence
from real quality signals, then compounded to question-level confidence
via the Relationship Layer's typed edges).

Proposed implementation shape discussed: two cooperating roles rather
than one monolithic bot -- a conversational interface (question
crafting, presenting synthesis, session memory) and an analytical
engine underneath it (confidence scoring, consensus weighting,
scenario/tradeoff modeling). This pairing covers most of founding_vision.md's
Layer 6 (Decision Engine) functions directly: evidence summaries,
confidence estimates, scenario modeling, tradeoff analysis.

## 2. Discovery Engine -- bounded to the corpus, not the universe

**The founding vision's literal framing is too open-ended to build
responsibly.** "Identify overlooked connections" and "propose
hypotheses" against all of human knowledge has no natural stopping
point and no way to verify against real data before writing it -- the
opposite of how every milestone in this ecosystem has actually been
built.

**Scoped-down version:** critical appraisal and gap/connection
surfacing bounded to the corpus `core` has already gathered and
validated -- not a search of everything else in the universe. Two
concrete pieces:

- **Per-paper critical-appraisal questions** (was the sample size
  adequate, was the result significant, was the methodology sound).
  These map directly onto `founding_vision.md`'s Confidence Framework:
  the Evidence Quality Score's own stated inputs are study design,
  sample size, replication, methodology, and statistical rigor. This
  is not a new idea -- it is the concrete mechanism for computing an
  input the vision docs already named but left unimplemented.
- **Corpus-bounded gap/connection surfacing.** M51's `unconfirmed_claims`
  (claims with zero relationship edges) is the first real, already-built
  raw signal for this -- Discovery Engine would be a real consumer of
  it, not a reason to build a new one. M49's `relationship_candidates`
  (claims sharing a PICO-resolved concept) is the connection-surfacing
  half.

**Constraint: ground the appraisal rubric in an established framework,
not an invented one.** Real, standard, citable critical-appraisal
checklists already exist for exactly this purpose:

- **CONSORT** -- randomized controlled trials (sample size
  justification, randomization method, blinding, dropout reporting).
- **PRISMA** -- systematic reviews and meta-analyses.
- **STROBE** -- observational studies (cohort, case-control,
  cross-sectional).
- **GRADE** -- the evidence-certainty rating framework itself, closest
  in spirit to what the Confidence Score is trying to compute.
- **Cochrane Risk of Bias tool** -- per-study bias assessment.

Applying one of these means "was the sample size adequate" has a real,
defensible standard behind it instead of an AI-invented bar -- the same
"never guess" discipline `core` has held everywhere else.

**Real seam nuance to resolve when this is actually designed, not
here:** "does this paper *state* a sample size / p-value / confidence
interval" is closer to deterministic extraction -- a fact a careful
reader could point to a specific sentence and confirm, the same
category M16-M19's claim-candidate detection and M28's PICO extraction
already work in. It could plausibly become a `core`-side Phase 2
extraction enhancement, not exclusively AI-layer work. "Is that sample
size *adequate* for this study type, per CONSORT/STROBE" requires
judging against a standard -- genuine AI-layer territory. `phase4_design.md`
and `stability_and_tracking_design.md` each drew exactly this kind of
line explicitly; this design will need to as well.

**Explicitly not in this scoped-down version:** full hypothesis
generation, experiment design, or searching/reasoning beyond what
`core` has already gathered and validated.

## 3. Education Engine -- topic explainer with progressive disclosure

**The founding vision's full framing (personalized learning paths,
prerequisite mapping, expertise tracking) is `long_term_vision.md`'s
own stated "largest outright gap between the founding vision and the
current roadmap."** Not attempting the whole thing here.

**Scoped-down version:** search a topic, get a Wikipedia-style summary;
ask "tell me more" to go deeper. The real data source for this already
exists and is already built -- M41-M45's Reference Knowledge Layer
(`ke reference-lookup` against Wikipedia, `ke rxnorm-lookup`, `ke
mesh-lookup`, `ke pubchem-lookup`). This is not a new fetch/build; it
is orchestrating and rendering plumbing `core` already has.

**"Tell me more" naturally splits into two trust levels that must stay
visually and structurally distinct**, mirroring the non-evidence
boundary the Reference Layer already enforces:

- **General background** (what is semaglutide, what is a GLP-1
  receptor agonist) -- from the Reference Layer, same non-evidence
  status Wikipedia/RxNorm/MeSH/PubChem content already carries
  everywhere else in this project.
- **What this project's own evidence actually found** -- from the
  Knowledge Graph (M46-M51: claims, concepts, relationships,
  citations). Drilling into this is Decision Engine territory, not
  Education Engine, and inherits that engine's full confidence-rating
  discipline -- it must never be presented at the same trust level as
  the background summary just because a user asked "tell me more" in
  the same conversation.

**Constraint:** every level of detail traceable to its real source (a
Wikipedia URL, an RxNorm ID, a MeSH ID, a PubChem CID, or an actual
evidence record) -- never invented depth just because more was asked
for.

**Open question, not resolved:** is this a distinct "Education bot," or
simply a capability of the same chat interface described in Decision
Engine above? Progressive disclosure on request is natural behavior for
any well-built conversational interface. If the latter, the AI layer
may not need a third distinct bot at all for this scoped-down version --
worth deciding when this is actually built, not guessed here.

**Explicitly not in this scoped-down version:** personalized learning
paths, prerequisite mapping, knowledge assessment/testing, or
expertise tracking across sessions.

## Open questions carried forward (owner decisions, not resolved here)

- **Bot count.** ~~Two (chat + analyst, with topic-explanation folded
  into chat) or three (chat, analyst, tutor) distinct roles -- not
  decided.~~ **Resolved by `docs/ai_layer_architecture.md`:** one
  Research Copilot, externally always a single assistant, internally
  delegating to four intelligences (Retrieval, Evidence, Analytical,
  Discovery). Topic-explanation stays folded into the Copilot rather
  than becoming a distinct Education bot, as this document's Education
  Engine section already anticipated as the likely outcome.
- **Where Discovery Engine's per-paper appraisal work actually lives.**
  Partly a `core`-side Phase 2 extraction enhancement (stated facts)
  plus AI-layer judgment (adequacy against a standard), or entirely
  AI-layer -- not decided.
- **Package split.** All three engines in one `knowledge-engine-ai`
  repository, or does Discovery/Education end up in a separate
  `knowledge-engine-agents` package, as `long_term_vision.md`'s own
  "Discovery and Education Layers" section already speculates? Not
  decided.

## When to revisit

Real trigger conditions, not a calendar date: substantially more
validated `EvidenceRecord`s than the 2 that exist today (so there is
real material to synthesize and appraise), a scoped confidence-rating
formula design grounded in real data, or the project owner explicitly
saying it is time.
