# Long-Term Vision

Knowledge Engine aims to become an open scientific operating system for human
knowledge.

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
