# Long-Term Vision

Knowledge Engine aims to become an open scientific operating system for human
knowledge. `docs/founding_vision.md` is the project's original founding
proposal, preserved verbatim; this document translates that ambition into
the concrete, multi-package ecosystem plan below.

The active project family is:

- `knowledge-engine-core`: document ingestion and local source vault
- `knowledge-engine-ai`: retrieval and opt-in grounded synthesis, with later
  analytical and discovery stages gated by measured evidence quality
- `knowledge-engine-web`: read-only evidence and graph interface

The graph currently belongs in `core` behind `GraphRepository`. The first HTTP
boundary is also designed to live in `core` as a read-only persistent host once
its trigger is met; a separate API repository is not planned. Agents, trained
models, or a separate graph service remain possible future packages only when a
measured ownership or deployment need justifies them.

One additional layer is designed but not started:

- `knowledge-engine-reference` (sketched, not started): a foundational
  reference layer -- open-license chemistry, biology, microbiology,
  physics, biochemistry, pharmacology, and lab-technique textbooks --
  giving the extraction pipeline and the AI Interface Layer the
  background knowledge a primary-research paper always assumes but never
  restates. See `docs/reference_knowledge_layer_design.md`.

## The Finished Product Is Not an Offline PDF Archive

`docs/roadmap.md`'s Phase 0 goal of running `knowledge-engine-core` fully
offline, and its framing as a "local source vault," describe `core`'s own
engineering properties -- testable and operable without a network dependency,
safe to run in isolation -- not the shape of the product a person eventually
uses. Those properties keep `core` trustworthy and reproducible; they are not
a claim that the finished ecosystem is a local folder of hoarded PDFs someone
has to search themselves.

The finished product is a live, AI-powered search and discovery engine. A
person asks a real research question; the system searches and reasons across
the evidence `core` has validated and the connections the Knowledge Graph
(Phase 4) has modeled, and returns a report scoped to that specific
question -- with an explicit confidence rating, not just a list of matching
papers. `core` is the trustworthy, source-linked, deterministic foundation
underneath that experience; it is not the experience itself. The AI Interface
Layer described below is what turns that foundation into the product a person
actually uses.

## Guiding Idea

The system should help humans understand what is known, what is uncertain, what
is disputed, and what remains unknown.

It should preserve knowledge, evaluate evidence, connect ideas, identify
contradictions, and make research more reproducible.

## Minimizing Human-Typed Fields

Every field in the Evidence and Relationship schemas left for a human to
type by hand is a place human error can enter -- a mistyped sample size, a
wrong study-type label, a relationship authored from memory rather than
re-reading the source. The project owner's explicit preference is to
minimize this surface area over time, not accept it as permanent.

This does not change `core`'s "never decide truth" boundary; it sharpens
it. A field belongs to deterministic, automated extraction whenever the
fact it records is intrinsic to the paper's own text -- something a
careful reader could point to a specific sentence and confirm, the same
way M16-M19 already locate a claim candidate and its source span. A field
belongs to a human or `knowledge-engine-ai` only when the fact is genuinely
external to the paper, or
requires judgment about what the paper means relative to something
outside it:

- **Paper-intrinsic -- should become deterministic extraction, not stay
  human-typed:** PICO fields (population, intervention, comparator,
  outcome), `study_type`, and `limitations` are facts a paper states about
  itself, usually in predictable places (a Methods section, inclusion
  criteria, an explicit "Limitations" heading) -- the same category of
  work M16's structured-section detection and M17's signal-matching
  already do for claims. These are extraction targets `core` should build,
  not permanent human-review fields. See Confidence Rating Design Guidance
  below and `docs/phase2_design.md`'s Extraction Model.
- **Genuinely external -- correctly stays human/AI-layer territory:**
  `research_question` is not contained in any paper -- it is supplied by
  whoever is asking, and no amount of better extraction changes that.
  `evidence_direction` is defined relative to a `research_question`, so it
  inherits the same externality. A synthesized confidence *rating*
  requires judging what a question's accumulated evidence supports, which
  is reasoning, not extraction.
- **Currently human-typed, worth re-examining:** the Relationship Layer's
  first slice (M24) requires a human to author every relationship record
  by hand -- `relationship_type`, `rationale`, and both endpoint IDs are
  all typed, not extracted. Unlike `research_question`, a relationship
  between two evidence records *can* have machine-checkable structure (do
  their claims share PICO overlap? does one paper cite the other?) even
  though deciding the relationship *type* correctly still needs care. A
  future Relationship Layer milestone should narrow, not eliminate, human
  involvement here -- surfacing candidate pairs automatically so a human
  confirms rather than composes from scratch, the same conservative
  posture M18 already uses for framing cues.

### Decision: automated evidence review at scale (M69)

**Superseded by this decision:** `docs/future_ideas.md`'s "Reviewer
Tooling" section previously stated that the automated-evidence-record
backlog "should never be closed by weakening review -- every
relationship and every 'reviewed' flag must still trace to a human
actually reading the source." That policy assumed a human reviewer's
time was the scaling constraint to work around, not a wall the project
cannot get past. It is a wall: M68's real audit found 118 of 154
evidence records (79%) already automated and unreviewed, at today's
1,000-paper corpus cap -- before any real scale-up. The project owner
has explicitly and permanently decided: manual, human-read review of
every record does not scale to this project's actual corpus-growth
plans and will not be relied on as the review mechanism going forward.
This is now a fixed constraint of the project, not an open question --
future sessions should build against it, not re-litigate it.

**What replaces the human-reading gate:** review's actual job was never
"a person's eyes touched this" for its own sake -- it was making sure a
record's `claim_text` and PICO fields are genuinely grounded in the
source paper's own text, not invented or mismatched from an unrelated
passage (exactly the bug class M68 found and fixed by hand: the
automated `m52` pipeline broadcasts one paper-level PICO extraction onto
every claim candidate in that paper, regardless of which
sentence/subgroup/section a given claim actually came from -- see
`knowledge_engine/extraction/evidence_items.py`'s
`build_draft_evidence_items` and `extraction_review_batch.py`'s
`run_extraction_review_for_paper`). `evidence_direction` is a separate
kind of fact -- a classification relative to a `research_question`, not
a span of source text -- and is not part of what "grounding" checks; see
below for why it stays on its existing deterministic path unchanged. A
verifiable, falsifiable, grounded PICO extraction satisfies the
claim-text/PICO half of that job without a human doing the reading:

- Extract per claim candidate (one call per candidate sentence,
  constrained to bounded local source context), not
  once per paper -- this alone fixes the PICO-broadcast bug, independent
  of whether the extractor is deterministic or an LLM.
- Use the local model already wired up for `/ask` synthesis in
  `knowledge-engine-web`/`knowledge-engine-ai`
  (`OllamaLLM`/`LocalLLM.generate(prompt, max_tokens=...)`, a plain
  synchronous `urllib` call against Ollama's `/api/chat`, no SDK) to
  propose `population`/`intervention`/`comparator`/`outcome` from that
  local context -- the same four fields M28's per-paper `extract_pico`
  already produces, just scoped correctly this time. `claim_text` and
  `evidence_direction` are deliberately **not** LLM-proposed:
  `claim_text` is already the candidate's own sentence, unaffected by
  the broadcast bug; `evidence_direction` is a classification relative
  to a `research_question` (supports/contradicts/qualifies/
  contextualizes), not text extractable from the source, so it can
  never pass a substring/near-match grounding check by construction.
  Both stay on the existing deterministic path
  (`classify_evidence_direction`, `generate_research_question`, both in
  `knowledge_engine/extraction/evidence_classification.py`), which
  already operates correctly per candidate -- `generate_research_question`
  only needs the four (now correctly-scoped) PICO fields as input, and
  `classify_evidence_direction` only reads `claim_text`, which was never
  broadcast in the first place.
- Add a **grounding-check verifier** -- this does not exist anywhere in
  the codebase today and is the load-bearing piece: before an
  LLM-proposed field is accepted, check it is an actual substring or
  close near-match of the provided source-page text, the
  same discipline `core` already applies to `source_span`. A field that
  fails grounding is dropped (never guessed), the same "skip, don't
  invent" posture M18/M28 already established for the deterministic
  extractors.
- Label the result honestly. This is still never `manual_human_review`
  -- it gets its own `extraction_method` value (e.g.
  `llm-grounded-extraction-v1`), and `review_notes`/`provenance` state
  plainly what actually happened: an LLM proposed it, a deterministic
  check verified it against the source, no human read it. `core`'s
  honesty invariant (never claim a review happened that didn't) is
  unchanged by this decision -- only the identity of the reviewer is
  new.
- Evidence Intelligence scoring (`knowledge_engine/evidence_intelligence.py`,
  `compute_evidence_quality`) already reserved a middle extraction-rigor
  tier for exactly this case (`docs/evidence_intelligence_design.md`:
  *"a future `ready_for_secondary_review: true` + populated checklist
  state on an automated record would score between these two"*) -- a
  grounding-verified LLM record should score between raw-automated (25
  points) and human-manual (40 points), not identically to an
  unverified `m52` record.

**What does not change:** a human can still read and confirm any
record -- that path stays available and is still the highest-rigor
tier. `core`'s "never decide truth" boundary (see above) is unchanged:
grounding verification checks that extracted text traces to the source,
it does not judge whether the source itself is correct. This decision
only removes human reading as a *required* gate for a record to be
usable in the corpus at scale.

**M69 follow-up: bounded cross-page context.** The first full backlog run
left 21 terse result claims ungrounded. A source audit confirmed that their
recorded page numbers and claim offsets were correct; the missing PICO
framing was usually on page 1, not evidence of a parser/page-boundary bug.
The v2 extractor therefore provides exactly two real source pages when
they differ: the claim page and page 1 from the same paper. It still runs
the unchanged `verify_grounding` check over the raw provided text for every
proposed field, never accepts prompt labels as evidence, and never widens to
the whole paper. The follow-up grounded 11 records and left the other 10
untouched. Existing v1 records remain valid grounded-review provenance.

## The AI Interface Layer (Active Foundation, Future Stages)

`knowledge-engine-core` deliberately stops short of deciding what a piece of
evidence means for a person's actual research question -- see
`docs/phase2_design.md`'s Extraction Layer and Evidence Layer milestones
(M16-M22), which locate and validate evidence but leave `research_question`
and `evidence_direction` for a human reviewer to supply by hand, and which
explicitly exclude confidence *scoring* (beyond the existing free-text
`confidence_note` field) from Phase 2's scope. That is not a temporary gap
waiting for `core` to get smarter -- it is the deliberate seam where
`knowledge-engine-ai` now plugs in. Retrieval Intelligence and opt-in grounded
synthesis are shipped; Analytical and Discovery Intelligence remain future
stages.

In the finished, full ecosystem, an AI interface built on top of `core`'s
Evidence and Relationship Layers should:

- Help a person craft the actual research question their search is really
  asking, rather than requiring them to phrase it precisely up front.
- Track a user's research history across sessions, so follow-up questions
  build on what they already asked and were shown.
- Take a user's live search and connect it to the evidence `core` has
  validated -- rather than requiring a reviewer to have pre-authored a
  matching `research_question` on each evidence record ahead of time, as is
  necessary today.
- Judge what the accumulated evidence actually supports for that question,
  surfacing agreement, disagreement, and gaps rather than a single answer.
- Present a real confidence rating for its synthesis -- distinct from, and
  built on top of, `core`'s per-record `confidence_note` and the
  Relationship Layer's typed support/contradiction/qualification links --
  not a number `core` itself invents.

`core`'s responsibility is to make sure the evidence underneath this layer is
trustworthy, source-linked, deterministic, and never silently guessed. This
layer's responsibility is everything that requires judgment about what that
evidence means. Building this into `core` itself, or blurring the seam
between the two, is explicitly out of scope for every `core` milestone.
See `docs/core_interface_contract.md` for the concrete configuration,
CLI surface, and data schemas this layer (or any other) actually
consumes from `core` today.

### Confidence Rating Design Guidance

The confidence rating above should be a real, hard number, not a vague
qualitative label -- and it must be earned from actual per-paper quality
signals, not a naive count of how many papers say the same thing. A large,
well-designed, recent trial and a small, poorly controlled, decade-old one
must never contribute equally to an answer just because both nominally
"support" it.

This works in two levels:

1. **Per-evidence-record confidence.** Computed from signals `core`'s own
   Evidence and Relationship Layers are positioned to produce: study
   design/type and sample size (PICO fields -- an explicit near-term
   priority for deterministic, non-human-typed extraction; see Minimizing
   Human-Typed Fields above), recency (already-captured paper
   publication-date metadata), and any known
   limitations/uncertainty already recorded per evidence record. A small,
   poorly designed, or old study earns a low per-record score even when its
   stated direction agrees with the eventual answer.
2. **Compounded, question-level confidence.** For one research question, the
   AI layer combines the per-record confidence of every relevant evidence
   record -- weighted, not simply counted -- using the Relationship Layer's
   typed links (supports/contradicts/qualifies/contextualizes) to decide how
   records reinforce or offset each other, producing one aggregate rating for
   that question's report. Several strong, independent, agreeing studies
   should compound toward high confidence; a single strong study, a handful of
   weak studies, or strong agreement offset by weak contradiction should each
   produce a visibly different, lower rating -- never collapsed to the same
   number.

This is design guidance for `knowledge-engine-ai`'s future Analytical
Intelligence work, not a formula `core` implements. But it is also not free of
consequences for `core`: a rigorous confidence rating can only be as good as the quality
signals `core` chose to capture on the way there. `core`'s PICO extraction
and Relationship Layer milestones are this rating's specific future
inputs, not just organizational nice-to-haves -- they should be scoped
with this consumer in mind when their time comes.

### Stability Score (Future Input, Not Yet Captured)

`docs/founding_vision.md`'s Confidence Framework names four per-claim
sub-scores; three (Evidence Quality, Consensus, Recency) already have a
clear path to real inputs once PICO extraction and the Relationship Layer
mature. The fourth, **Stability** -- historical consistency, how often a
claim's supporting evidence has been revised -- has no path yet. Nothing
in `core` currently tracks a claim or evidence record's revision history
over time. This is a Phase 4 (Knowledge Graph)-era concern: it needs
something to revise *against*, which requires the graph to exist first.

## The Reference Knowledge Layer (Future, `knowledge-engine-reference`)

A primary-research paper is written for a domain expert and never
restates the chemistry, biochemistry, microbiology, physics,
pharmacology, or lab-technique background that expert already has. This
project's extraction pipeline, and the AI Interface Layer above
it, currently have no equivalent grounding to draw on -- they read a
claim about "GLP-1 receptor agonism, assessed by ELISA" with no more
context than the paper itself provides.

The proposed fix is a separate reference layer -- either stored
open-license textbooks, or live lookups against free APIs (NLM's
RxNorm/MeSH/PubChem, Wikipedia/Wiktionary), or both -- explicitly
**not** evidence and never routed through `EvidenceRecord` promotion:
background context a future reasoning step consults, the same way a
human expert's own training functions, not a citable finding. Live
lookup is not a departure from this project's direction: "The Finished
Product Is Not an Offline PDF Archive" above is explicit that Phase 0's
offline-by-default posture describes `core`'s own engineering property
for the primary evidence pipeline, not a claim about the finished,
live, connected ecosystem -- a live-queried reference layer fits that
end state naturally. See `docs/reference_knowledge_layer_design.md` for
the design sketch: candidate open-license sources, the live-lookup
option (likely the better starting point, since it needs no storage
decision), why it needs its own manifest and index rather than reusing
the paper corpus's, and the real open decisions (storage/hosting chief
among them, if the stored-text path is chosen) still pending explicit
owner sign-off. **M41, M42, M43, and M44 have since built the
live-lookup path's first four slices** -- `ke reference-lookup`,
querying Wikipedia's public REST API live; `ke rxnorm-lookup`, querying
NLM's RxNorm API live for structured drug-name normalization; `ke
mesh-lookup`, querying NLM's MeSH database live for medical-concept
terminology; and `ke pubchem-lookup`, querying NLM/NCBI's PubChem PUG
REST API live for chemical-compound structure data -- all background
context only, never evidence -- see `docs/history/milestones/m41_reference_lookup.md`,
`docs/history/milestones/m42_rxnorm_lookup.md`, `docs/history/milestones/m43_mesh_lookup.md`, and
`docs/history/milestones/m44_pubchem_lookup.md`. **M45** wired three of the Addendum's
buildable-now integration points into the Phase 2 review workflow: `ke
extraction-review-annotate` attaches RxNorm/MeSH reference context onto
draft evidence items before a reviewer runs `ke
extraction-review-promote` -- see
`docs/history/milestones/m45_extraction_review_annotate.md`. The stored-textbook path
remains unbuilt. `docs/reference_knowledge_layer_design.md`'s Addendum
names ten concrete ways this layer's content could shape the AI
Interface Layer's eventual report (grouping, gap disclosure, provenance
labeling, glossary/appendix content, Knowledge Graph concept nodes),
ordered cheapest-to-build first
-- explicitly none of them ever become a confidence-rating input, per
the Confidence Rating Design Guidance above.

## Tracking the Unknown

`docs/founding_vision.md`'s addendum -- that the system should explicitly
track what humanity does *not* know, not only what it does -- has no
representation in the schema today beyond the Relationship Layer's
`contradicts` type. A missing experiment, a weak-evidence area, or an
unanswered question are not currently first-class entities anywhere. Gaps
are naturally graph-shaped (a missing or weak edge), so this belongs with
the Knowledge Graph (Phase 4), not before it.

## Discovery Metrics (Post-v1.0)

`docs/founding_vision.md`'s Discovery Metrics (Time to Discovery, Time to
Understanding, Time to Validation, Knowledge Coverage, Contradiction
Resolution Rate) measure the Discovery and Decision layers' output. They
cannot be meaningfully measured before those layers exist, so this is
explicitly post-`v1.0.0` scope -- named here so it is not forgotten, not
because it is actionable now.

## The Discovery and Education Layers (Future)

`docs/founding_vision.md`'s six-layer architecture names two later layers at
different levels of architectural maturity:

- **Discovery Engine** (identify knowledge gaps, propose hypotheses,
  suggest experiments, estimate expected information gain). The closest
  existing hook is the Knowledge Graph (Phase 4) -- a gap is naturally
  something the graph can represent as a missing or weakly-supported edge
  -- and `docs/ai_layer_architecture.md` now assigns the first responsible
  implementation to `knowledge-engine-ai`'s Stage 5 Discovery Intelligence.
  It is named but not started, and remains gated by Analytical Intelligence
  and adequate relationship coverage. A future `knowledge-engine-agents`
  capability may extend it later but is not required by the current plan.
- **Education Engine** (adaptive explanations, personalized learning
  paths, prerequisite mapping, expertise tracking). Not claimed by any
  phase or ecosystem package named above. This is the largest outright gap
  between the founding vision and the current roadmap -- it may need its
  own future package, or a deliberate decision that it is out of scope for
  the foreseeable roadmap. Left as an open decision here rather than a
  silent omission.

Both remain deferred and do not block current `core` work. **See
`docs/ai_interface_layer_scoping.md`** for
scoped-down first-slice ideas for both engines, recorded once Phase 4
(the Knowledge Graph, M46-M51) gave Discovery Engine something real to
identify gaps against -- that document is a record of ideas, not a
design doc ready for implementation, and does not change either engine's
status here: still deferred and still not started. **See
`docs/ai_layer_architecture.md`** for a later refinement
of the Decision Engine framing above -- one Research Copilot
orchestrating Retrieval/Evidence/Analytical/Discovery intelligences
rather than separate bots, plus a three-way Evidence Quality/Consensus/
Claim Confidence split and domain-specific confidence profiles.
`knowledge-engine-ai` has since shipped Retrieval Intelligence,
core-provided Evidence Intelligence display, and opt-in local grounded
synthesis. Analytical and Discovery Intelligence remain gated by
`docs/roadmap.md`'s Current Project Path.
