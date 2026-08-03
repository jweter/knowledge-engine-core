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
- **Stages 4 and 5 are not started.** Current Project Path goals 2 and 3 -- a
  golden retrieval benchmark and one complete GLP-1 evidence map -- are the
  prerequisites for beginning Analytical Intelligence responsibly.

Autonomous hypothesis generation and experiment design -- the most
exciting and least-grounded items on the founding vision's original
list -- deliberately come after all five stages, not before, matching
`ai_interface_layer_scoping.md`'s "not attempting the whole thing here"
posture toward Discovery Engine's most open-ended framing.

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
