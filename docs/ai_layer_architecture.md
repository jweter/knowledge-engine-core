# AI Layer Architecture: One Research Copilot, Four Intelligences

Status: architecture guidance for the active `knowledge-engine-ai`
repository, not authorization to build every later stage at once. The original
trigger conditions have been met: core now has a real evidence corpus and
relationship graph; AI M1-M3 shipped Retrieval Intelligence, core-provided
Evidence Intelligence display, and opt-in local grounded synthesis. The
Analytical and Discovery stages below remain future work and must be earned
against the Current Project Path in `docs/roadmap.md`.

`ai_interface_layer_scoping.md` remains the historical record of the
earlier three-engine framing (Decision/Discovery/Education) and is not
deleted. This document resolves one of its "Open questions carried
forward" (bot count) and substantially extends its Decision Engine
section. Discovery and Education remain deferred even though the AI
repository and its first Retrieval slices now exist.

## The one rule that does not change

Every section below inherits `core_interface_contract.md`'s seam
without exception, restated in `ai_interface_layer_scoping.md`:

- Never sets or infers `research_question`/`evidence_direction` on a
  stored `EvidenceRecord`.
- Never invents a confidence number, quality score, or "significant
  finding" judgment not traceable to a real, cited source.
- Never presents reference-layer background (Wikipedia, RxNorm, MeSH,
  PubChem) as evidence, or lets it influence a confidence rating.
- Never auto-authors a `RelationshipRecord` without a human confirming
  it.

Everything proposed here is a way of organizing judgment work `core`
explicitly refuses to do itself -- not a way of loosening that refusal.

## One assistant, not several bots

The previous scoping doc left "two roles (chat + analyst) or three
(chat, analyst, tutor)" as an open question. **Resolved:** the
researcher should experience exactly one assistant -- a **Research
Copilot** -- that internally delegates to specialized capabilities.
Those capabilities can be exposed as expert-mode commands (`Search`,
`Analyze`, `Compare`, `Statistics`, `Evidence`, `Discover`), but they
are tools one assistant calls, never separate personalities a user has
to choose among first.

```
                         Researcher
                             │
                             ▼
                     Research Copilot
                    (conversational UI,
                     query planning)
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                   ▼
   Retrieval           Evidence            Analytical
  Intelligence        Intelligence        Intelligence
  (find papers/        (extract claims,    (statistics,
   datasets, cite       PICO, methods,      effect sizes,
   graph, semantic      limitations,        recalculation)
   search)              source spans)
          │                  │                   │
          └──────────────────┼───────────────────┘
                             ▼
                      Evidence Graph
                    (Phase 4's Knowledge
                     Graph -- M46-M51)
                             │
              ┌──────────────┼───────────────┐
              ▼               ▼               ▼
          Quality          Consensus       Stability
           Model             Model           Model
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    Confidence Framework
                     (domain-specific
                      profiles)
                              │
                              ▼
                 Synthesis / Explanation
                  (the LLM's actual job:
                   explain, never judge)
                              │
                              ▼
                    Researcher-facing answer
```

`Discovery Intelligence` (contradiction/gap surfacing, the Unknowns
Engine) sits downstream of the Evidence Graph as a fourth capability --
see "Discovery Intelligence" below. It was omitted from the diagram
above only for space; it is not lower-priority than the other three.

**The load-bearing distinction:** the LLM explains; the evidence system
judges according to explicit, inspectable rules. A model is never
allowed to read papers and emit a bare "confidence: 87%" -- that number
must decompose into named, individually-inspectable components (see
Confidence Framework below), and the LLM's role is to narrate that
decomposition, not compute it.

## Retrieval, Evidence, and Analytical Intelligence

These three map onto capabilities `core` already has real, working
building blocks for, or has explicitly scoped inputs for:

- **Retrieval Intelligence** -- semantic search (M32, M39's fused
  lexical+semantic ranking), the citation graph (M47/`graph_citations`),
  and the pluggable discovery-provider architecture (M34-M36: PubMed,
  Europe PMC, CORE, Unpaywall). Mostly orchestration of what already
  exists, not new fetch/build.
- **Evidence Intelligence** -- PICO extraction, claim text, study type,
  limitations (Phase 2, `EvidenceRecord`), plus the Relationship
  Layer's typed edges (M49-M51). Determines what the evidence *says*,
  never what it *means*.
- **Analytical Intelligence** -- new territory, detailed in "The
  Statistics Auditor" below. Deterministic wherever the paper reports
  the numbers needed for recalculation; judgment-layer only where a
  standard (CONSORT/STROBE/GRADE) must be applied to decide adequacy.

## Confidence is three numbers, not one

`docs/roadmap/long_term_vision.md`'s Confidence Rating Design Guidance
already splits confidence into per-evidence-record and compounded
question-level scores. This refines that further into three distinct,
separately-displayed quantities that must never collapse into each
other:

| Metric | Question it answers |
|---|---|
| **Evidence Quality** | How trustworthy is the evidence itself (study design, sample size, methodology)? |
| **Evidence Consensus** | How consistently does the literature agree? |
| **Claim Confidence** | Given quality *and* consensus together, how confident should we be right now? |

The reason these cannot merge: ten low-quality studies that all agree
can produce high consensus (95/100) and low quality (31/100)
simultaneously -- and claim confidence must reflect that combination
(e.g. 43/100), never inherit the higher of the two inputs. This is the
concrete mechanism `founding_vision.md`'s Confidence Framework left
unspecified when it named Evidence Quality, Consensus, Stability, and
Recency as four sub-scores of one combined estimate.

**Two further additions, both new:**

- **Evidence Coverage.** The system's corpus is never "the evidence" --
  it is *its* evidence. If the corpus holds 47 relevant papers out of
  (an estimated) 2,300 that exist, that must be surfaced explicitly
  (`Evidence coverage: 34%`, itself with its own confidence label),
  not implied away. This is a direct, concrete defense against AI
  overconfidence and belongs on every synthesized answer.
- **Confidence-of-confidence.** The assessment itself can be
  under-evidenced. When it is, show a range and a reliability label
  (`Evidence Confidence: 83, interval 72-89, assessment reliability:
  Moderate`) instead of a bare point estimate. This is recursive but
  not decorative -- it is the same "never imply more certainty than
  the evidence supports" discipline applied to the confidence
  computation itself.

**A boundary that must never blur:** *extraction* confidence (how sure
is the system that it read "n=683" correctly off the page) is not
*assessment* confidence (how sure is the system that n=683 was
adequate for this study type). The first is closer to OCR/parsing
accuracy; the second is a judgment against a named standard. Displaying
them on the same scale, or worse, the same number, would misrepresent
what kind of uncertainty is being reported.

## Domain-specific confidence profiles

**A universal confidence rubric does not work.** "Sample size = 500"
means something different in a drug trial, a physics experiment, and
an ML benchmark; "p < 0.05" means something different depending on
field norms, preregistration, and multiple-testing correction. The
Confidence Framework therefore needs a profile per field, each with its
own named inputs grounded in that field's own established standards
(CONSORT/STROBE/GRADE/Cochrane Risk of Bias for clinical medicine;
analogous, field-native checklists elsewhere) -- never an invented bar.

**Concretely buildable today: exactly one profile, Clinical Medicine.**
That is the only domain this project has a real corpus for
(`glp1_weight_loss`) and the only one with actual PICO/study-type
fields already captured in `EvidenceRecord`. Every other profile named
in discussion (epidemiology, chemistry, molecular biology, psychology,
ML, physics, engineering) is a real, structurally-sound idea with no
real data to validate it against yet -- the same "verify against real
data before designing" discipline this project has followed
everywhere, from `core`'s own milestones through `web_design.md`.
Building a second profile is a real trigger for revisiting this
document, not something to speculatively scaffold now.

## The Statistics Auditor: deterministic first

The most concrete, buildable-now piece of Analytical Intelligence.
When a paper reports enough numbers (n, mean, SD, CI, p-value, event
counts, group sizes), the system can *independently recompute* effect
size, CI, risk/odds ratio, ARR, NNT, and standardized mean difference,
then compare its recomputed value against the paper's reported value:

```
Reported effect:     -14.8 kg        Reported 95% CI:  -15.9 to -13.7
Recalculated effect: -14.76 kg       Calculated CI:     -15.91 to -13.61
Status: Consistent
```

This should be deterministic arithmetic, not an LLM guess, wherever the
inputs are actually present in the record -- the same posture `core`
already takes toward every other computed value. It also produces a
real, independent discrepancy-detection signal the Confidence Framework
can consume, distinct from anything an LLM narrates.

## Discovery Intelligence: contradictions and the Unknowns Engine

Two capabilities, both grounded in structures `core` already builds:

- **Contradiction explanation**, not just contradiction counting. M49's
  `relationship_candidates` and the Relationship Layer's `contradicts`
  edges already make "17 support, 4 contradict" a real, queryable fact.
  The new piece is explaining *why*: checking disagreeing claims'
  PICO/study-type/duration/population differences for a pattern (e.g.
  "the contradiction mostly disappears once restricted to participants
  without diabetes") -- itself inspectable, source-linked, and never
  presented as resolving the disagreement, only characterizing it.
- **The Unknowns Engine**, operationalizing `long_term_vision.md`'s
  "Tracking the Unknown" section and M51's `unconfirmed_claims` (claims
  with zero relationship edges) as a real, already-built raw signal.
  Surfacing "what do we still not know about X" as tiers (strong /
  moderate / weak / contradictory / missing evidence) and a
  highest-value open question is a direct, structured consumer of that
  signal -- not a reason to build a new one.

## What is out of reach, named explicitly

Worth stating plainly so no future design accidentally promises these:

- **A universally objective "% true" confidence number.** Achievable:
  a well-calibrated, inspectable Evidence Confidence *score*. Not
  achievable without a defensible probabilistic model and calibration
  dataset this project does not have: a literal probability that a
  claim is true. Label it `Evidence Confidence: 84/100`, never `84%
  chance this is true`.
- **Determining scientific truth.** Would violate the seam outright.
  The system estimates support, quality, agreement, replication, and
  applicability. It is not an oracle.
- **Perfect hallucination elimination.** Not solvable with current
  generative models. Mitigated, not solved, by retrieval, structured
  records, source spans, deterministic computation, and citations --
  the LLM as presentation layer over facts it did not originate, never
  the source of the facts themselves.
- **Recovering data authors never published** (raw measurements,
  unreported subgroups, failed experiments). Can be flagged as a gap;
  cannot be legitimately reconstructed.
- **Reliable publication-bias detection from published literature
  alone.** Partial at best -- the missing evidence is, by definition,
  often unavailable to detect against.
- **One evidence rubric for every scientific field.** Structurally
  unworkable; see "Domain-specific confidence profiles" above.

## Build sequence

Sits under `docs/roadmap.md`'s Phase 5 (Human Interface), alongside
`knowledge-engine-web`, not as a new numbered phase. Every stage below
is source-linked and click-through-inspectable by design (matching
`vertical_slice.md`'s existing traceability requirement, which should
survive to production unchanged):

1. **Research Copilot core.** Natural-language search, query
   decomposition into PICO-shaped structure, relevant-paper discovery,
   citation-grounded chat with individual papers. No confidence scoring
   yet.
2. **Evidence Extraction.** Automate what M28's PICO extraction and
   Phase 2 review already do by hand, always tied to source spans --
   not new judgment, throughput on existing, already-scoped work.
3. **Evidence Intelligence.** The Clinical Medicine confidence profile,
   contradiction analysis, consensus analysis, evidence lifecycle
   (Stability Score) -- the first point real per-record and
   compounded confidence numbers exist.
4. **Analytical Intelligence.** The Statistics Auditor, cross-study
   tables, sensitivity analysis, meta-analysis where the underlying
   numbers actually permit it.
5. **Discovery Intelligence.** Contradiction explanation and the
   Unknowns Engine, once there is a large enough, confidence-scored
   Evidence Graph for gap-surfacing to mean something real.

### Current progress against the sequence

- **Stage 1 is partially shipped.** `ke-ai ask` provides natural-language
  lexical retrieval and source-linked results; `--synthesize` provides one
  opt-in, local, citation-required narration. PICO query decomposition,
  multi-turn research sessions, and broader retrieval evaluation remain open.
- **Stage 2's core-side throughput path is shipped.** M69 performs per-claim,
  grounding-verified local-LLM PICO extraction while preserving deterministic
  source checks and honest provenance. This does not make AI the owner of core
  evidence records.
- **Stage 3 has real foundations, not complete coverage.** Core and web compute
  and display deterministic Evidence Quality, Consensus, Claim Confidence, and
  Coverage. AI reads those values. Sparse reviewed relationships still make
  most claims honestly not assessable at the claim-confidence level.
- **Stage 4 has a bounded core-side foundation.** The reviewed GLP-1 evidence
  map now feeds `ke evidence-map-report`, a deterministic cross-study display of
  stored PICO fields, reported results, limitations, citations, and reviewed
  relationships. `ke statistical-verify` adds the first typed numerical slice:
  manually source-audited STEP 5 and SELECT records whose explicit randomized-
  arm means reproduce their reported treatment differences with Decimal
  arithmetic. Typed numerical locators may differ from claim locators while
  remaining bound to the same DOI and reviewed Evidence Record. Version 2 adds
  one STEP 5 interval approximation from explicit arm standard errors, sample
  sizes, and a declared independent-arm normal assumption. It is compatible
  within rounding tolerance, not a reconstruction of the trial's model-based
  interval; SELECT remains display-only. An optional, separately versioned
  binary contract now verifies STEP 5's observed responder percentages and
  derives one crude risk ratio with a no-correction log-Wald interval. It keeps
  the source's adjusted odds ratio display-only and explicitly non-equivalent.
  The command does not parse statistical values from prose or assess source
  analyses. Broader sensitivity analysis, meta-analysis, and LLM narration
  remain unstarted.
- **Stage 5 is not started.** Discovery Intelligence remains gated by adequate
  analytical inputs and relationship coverage.

Autonomous hypothesis generation and experiment design -- the most
exciting and least-grounded items on the founding vision's original
list -- deliberately come after all five stages, not before, matching
`ai_interface_layer_scoping.md`'s "not attempting the whole thing here"
posture toward Discovery Engine's most open-ended framing.

## Orchestration: a multi-agent pattern for the Research Copilot

Added 2026-08-09 from a project-owner architecture review (informed by
a third-party open-source multi-agent orchestration project's
spawn/fan-in pattern, evaluated and deliberately *not* adopted
wholesale -- see the "What this borrows, and what it explicitly does
not" subsection below). This section answers "how is the Research
Copilot's internal delegation actually implemented," which the "One
assistant, not several bots" section above named but left as an
architecture diagram, not a build plan.

**The one thing this does not change:** "one assistant, not several
bots" still holds. Everything below is internal orchestration behind
a single Research Copilot the researcher talks to -- if any of these
roles ever grows a user-facing name, personality, or a mode-picker UI,
that reopens a question this project already closed. Treat "agent" in
this section as an implementation-internal worker, never a persona.

### Proposed worker roles

| Component | Job | Maps onto |
|---|---|---|
| Orchestrator | Classify research intent, build a typed `ResearchPlan` | New -- thin coordination layer |
| Query Planner | Turn a question into search/PICO-shaped queries | Retrieval Intelligence's query decomposition (open) |
| Discovery Worker | Query PubMed/Europe PMC/CORE for new candidates | M34-M36's discovery-provider architecture (built) |
| Retrieval Worker | Search the existing Evidence Graph/vector index | M32/M39 fused search (built) |
| Evidence Extractor | Locate and structure candidate evidence | M69 LLM-grounded PICO extraction (built) |
| Evidence Analyst | Compare studies/PICO/results across records | Evidence Intelligence's contradiction/consensus analysis (open) |
| Contradiction ("Skeptic") Worker | Deliberately search for opposing evidence | Discovery Intelligence's contradiction explanation (scoped, Stage 5) |
| Statistical Worker | Recompute reported statistics -- no LLM | The Statistics Auditor (scoped above; deterministic by design) |
| Source Auditor | Verify claims actually match source spans | `source_span`/provenance discipline `core` already enforces on write; this is a *read-time* re-check |
| Composer | Produce the human-readable, cited answer | Synthesis/Explanation (M2's `--synthesize`, local, opt-in) |
| Citation Auditor | Confirm every material claim has provenance before the answer ships | New -- a final gate, not a narration step |

Nearly every row already maps onto a capability this document scoped
or `core` already built; the genuinely new pieces are the Orchestrator,
the Skeptic-as-mandatory-step reframing below, and the Citation
Auditor as an explicit final gate rather than an implicit property of
"the LLM only narrates cited facts."

### The Skeptic step is mandatory, not optional

"Discovery Intelligence: contradictions and the Unknowns Engine"
above already scopes contradiction explanation as a capability. This
section sharpens that into a build requirement: for any answer that
makes a comparative or directional claim ("does X improve Y"), the
Contradiction Worker runs *before* the Composer synthesizes an answer,
not as an optional follow-up a researcher can skip. Its brief is
adversarial by design -- given an emerging conclusion, it searches the
Evidence Graph and (bounded) new literature specifically for the
strongest counterexamples, methodological conflicts, population
differences, and endpoint differences, and that output is a required
input to the Composer, not an afterthought appended to a
already-written answer. A pipeline of Researcher &rarr; Evidence
Analyst &rarr; Skeptic &rarr; Source Auditor &rarr; Composer is a
stronger design for scientific synthesis than several agents that only
ever agree with each other.

### Persistent `ResearchSession` state

Genuinely missing today. Nothing in `core`, `web`, or `ai` currently
reconstructs "continue my GLP-1 investigation" from anything other
than raw chat history. A `ResearchSession` record -- question, scope,
inclusion/exclusion criteria in force, search strategies already run,
sources considered and rejected, evidence records surfaced,
contradictions found, calculations performed, unresolved questions,
and a log of agent actions -- would let a researcher resume an
investigation days or weeks later from stored state, not from
re-reading a transcript. This is additive to the Evidence Graph, not a
replacement for it: the Evidence Graph is what is true and
source-linked; a `ResearchSession` is what a particular investigation
has done and still needs to do. Storage location and schema are
implementation decisions for whichever package builds Stage 1's
query-decomposition work, not resolved here.

### Local-model routing, as a cost/latency ladder

Reasonable, and consistent with M2's existing opt-in local Ollama
synthesis path, but a real operational cost (N models to keep pulled,
consistent, and individually debuggable), not a free optimization.
The proposed ladder -- can Python solve this deterministically? then
can a small local model (~1.5B) solve it? then a mid-size local model
(~4-8B)? then, only as a last resort, an external model? -- should be
prototyped against one concrete workflow (the Query Planner is the
obvious first candidate, since it is bounded, has a clear
success/failure signal, and does not touch write paths) before being
adopted as a blanket policy across every worker role above.

### What this borrows, and what it explicitly does not

Borrowed: the spawn-workers-then-fan-in concurrency pattern (in this
project's case, plain `asyncio.TaskGroup` fan-out across
Discovery/Retrieval/Contradiction workers -- no new infrastructure),
and the idea of durable, queryable project memory outside the prompt
window (`ResearchSession` above, playing the same role the reference
project's SQLite-backed project memory plays for its own agents).

Not borrowed: container/Kubernetes-based agent isolation, persistent
cloud development environments, or any of the operational machinery a
reference implementation of this pattern used to let multiple
heterogeneous coding agents run in parallel isolated workspaces. That
solves a different problem (isolating untrusted, long-running
coding-agent processes from each other) than the one this project has
(orchestrating a handful of read-mostly research-workflow steps over
an already-trusted local evidence base). Revisit only if Knowledge
Engine becomes multi-user or needs isolated research workers running
concurrently against shared state -- not a near-term need.

### Sequencing and the real gate

The real blocker is not architecture, it is evidence-base thickness.
Stage 5 above is explicitly gated on "adequate analytical inputs and
relationship coverage," and that gate has not moved: as of this
entry, GLP-1 has the only externally-audited golden map (14 Evidence
Records, ~19 Relationship Records); the oncology corpus has a small,
same-session-self-audited reviewed layer (a handful of records against
over 1,500 automated drafts); mental-health has none. A Contradiction
Worker today would have almost nothing real to contradict outside
GLP-1. Recommended order:

1. Keep growing reviewed-evidence coverage and relationship density
   across corpora (already in progress -- see each corpus's README).
2. Build a minimal v0.1 in `knowledge-engine-ai` (not `core`, matching
   this document's package boundary throughout): Orchestrator,
   Retriever, Skeptic, Composer/Citation-Auditor -- four components,
   not the full eleven-row table above.
3. Split out specialized workers (Statistical Worker, dedicated
   Evidence Analyst, etc.) once the four-component version is
   reliable and there is enough reviewed evidence in a second corpus
   to exercise agreement/disagreement/population-difference cases the
   way GLP-1's golden map already does.

## Open questions carried forward (owner decisions, not resolved here)

- **Package split.** One `knowledge-engine-ai` repository for all four
  intelligences, or a split (e.g. Discovery/Education into a
  `knowledge-engine-agents` package), as `long_term_vision.md`
  speculates. This document's "one analytical framework, multiple
  modules" framing leans toward a single package, but that is a lean,
  not a decision.
- **Where Statistics Auditor's "is this adequate" judgment lives.**
  Recomputing a reported statistic is closer to deterministic
  extraction (could plausibly be a `core`-side Phase 2 enhancement);
  judging adequacy against CONSORT/STROBE/GRADE is genuine AI-layer
  territory. `ai_interface_layer_scoping.md` drew the same line for
  Discovery Engine's per-paper appraisal; unresolved here for the same
  reason.
- **Domain profiles beyond Clinical Medicine.** Real, structurally
  sound ideas with zero real data to validate against today. Revisit
  once a second-domain corpus actually exists.
- **Education Engine's status.** Still not claimed by any phase or
  package (`long_term_vision.md`'s own "largest outright gap"). Not
  addressed by this document.

## Next implementation trigger

Do not begin Analytical Intelligence because the repository now exists. Revisit
its first implementation slice after the golden-question benchmark is running
and the GLP-1/body-weight evidence map has enough reviewed relationships to
exercise agreement, disagreement, population differences, and missing evidence
against real cases. A second domain profile still waits for a second coherent
domain corpus. Education remains a separate owner decision.
