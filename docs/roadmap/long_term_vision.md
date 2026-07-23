# Long-Term Vision

Knowledge Engine aims to become an open scientific operating system for human
knowledge. `docs/founding_vision.md` is the project's original founding
proposal, preserved verbatim; this document translates that ambition into
the concrete, multi-package ecosystem plan below.

Long term, the ecosystem may include:

- `knowledge-engine-core`: document ingestion and local source vault
- `knowledge-engine-ai`: reasoning, synthesis, and evidence summaries
- `knowledge-engine-web`: web interface
- `knowledge-engine-api`: public API
- `knowledge-engine-agents`: research agents
- `knowledge-engine-graph`: citation and knowledge graph
- `knowledge-engine-models`: trained and evaluated models

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
belongs to a human (today) or the future `knowledge-engine-ai` layer
(eventually) only when the fact is genuinely external to the paper, or
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

## The AI Interface Layer (Future, `knowledge-engine-ai`)

`knowledge-engine-core` deliberately stops short of deciding what a piece of
evidence means for a person's actual research question -- see
`docs/phase2_design.md`'s Extraction Layer and Evidence Layer milestones
(M16-M22), which locate and validate evidence but leave `research_question`
and `evidence_direction` for a human reviewer to supply by hand, and which
explicitly exclude confidence *scoring* (beyond the existing free-text
`confidence_note` field) from Phase 2's scope. That is not a temporary gap
waiting for `core` to get smarter -- it is the deliberate seam where a future
`knowledge-engine-ai` layer plugs in.

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

This is design guidance for the future `knowledge-engine-ai` layer, not a
formula `core` implements. But it is also not free of consequences for
`core`: a rigorous confidence rating can only be as good as the quality
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

## The Discovery and Education Layers (Future, Not Yet Named)

`docs/founding_vision.md`'s six-layer architecture names two layers this
ecosystem plan has not yet given a home to:

- **Discovery Engine** (identify knowledge gaps, propose hypotheses,
  suggest experiments, estimate expected information gain). The closest
  existing hook is the Knowledge Graph (Phase 4) -- a gap is naturally
  something the graph can represent as a missing or weakly-supported edge
  -- but no phase or future package currently claims this responsibility.
  Likely home: `knowledge-engine-ai` or a dedicated
  `knowledge-engine-agents` capability, once the Knowledge Graph exists to
  identify gaps against.
- **Education Engine** (adaptive explanations, personalized learning
  paths, prerequisite mapping, expertise tracking). Not claimed by any
  phase or ecosystem package named above. This is the largest outright gap
  between the founding vision and the current roadmap -- it may need its
  own future package, or a deliberate decision that it is out of scope for
  the foreseeable roadmap. Left as an open decision here rather than a
  silent omission.

Both are explicitly deferred, not started, and not blocking any current
`core` milestone.
