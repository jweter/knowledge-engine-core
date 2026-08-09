# Future AI Orchestration Plan

Status: forward-looking design document for `knowledge-engine-ai`, not
authorization to build every milestone below at once -- same posture
`ai_layer_architecture.md` states for itself. This document extends
that document's new "Orchestration: a multi-agent pattern for the
Research Copilot" section rather than replacing it; read that section
first. Where the two disagree, this document's contract-first framing
is the more disciplined restatement and should be treated as the
current thinking.

**Provenance note:** this document was drafted from the project
owner's detailed relay of a team-authored orchestration plan, not from
the original file directly -- the shared download link did not resolve
to an accessible URL in this session. Everything below matches what
was actually described (the four contracts, the sixteen-block count
with the fourteen individually named risks, the eleven `AI-O*`
milestones, the Skeptic worker's exact reporting language, the
routing hierarchy). Where the source material named "16 meaningful
architecture blocks" but only enumerated the "most important" 14, this
document carries exactly those 14 and flags the count gap explicitly
rather than inventing the other two -- see "Design risks and
mitigations" below. If the original file becomes available, reconcile
this document against it and remove this note.

## The core insight: contracts, not a framework

The biggest conclusion from this planning work is a course correction
on `ai_layer_architecture.md`'s own "Orchestration" section: **do not
build a generic multi-agent framework next.** Build four durable
domain contracts instead, and let agents, deterministic code, Ollama,
external providers, or whatever orchestration framework is popular
next execute against those contracts as replaceable engines underneath
them:

- **`ResearchPlan`** -- what needs to be investigated. The typed output
  of classifying a research question: scope, required capabilities
  (literature search, existing-corpus search, PICO comparison,
  contradiction search, statistical verification, citation audit),
  and constraints.
- **`ResearchSession`** -- the persistent investigation. Named and
  scoped identically to the `ResearchSession` design in
  `ai_layer_architecture.md`'s Orchestration section (question, scope,
  criteria in force, search strategies run, sources considered and
  rejected, evidence surfaced, contradictions found, calculations
  performed, unresolved questions, agent-action log). This document
  does not redefine it, only assigns it a contract number below
  (AI-O2).
- **`ResearchTask`** -- one bounded piece of work within a session
  (e.g. "search PubMed for X," "recompute this trial's effect size,"
  "search for contradicting evidence to claim Y"). The unit an
  Orchestrator hands to a worker and a worker reports back against.
- **`ResearchEvent`** -- the audit trail of exactly what happened: which
  task ran, which engine executed it (deterministic code, a specific
  local model, an external provider), what it read, what it produced,
  and how long it took. Every arrow in `ai_layer_architecture.md`'s
  orchestration diagram becomes one or more `ResearchEvent` rows, not
  an untraced side effect.

**Why contracts instead of a framework:** LangGraph, AutoGen, the
OpenAI Agents SDK, kube-coder, or whatever framework is popular a year
from now can all become interchangeable execution engines *underneath*
these four contracts, instead of becoming the architecture of
Knowledge Engine itself. Swapping the framework that fulfills a
`ResearchTask` should never require touching the Evidence Graph, the
Evidence Record schema, or a researcher-facing feature -- see
"Framework lock-in" in the design-risks section below. This also
matches current agent-engineering guidance: match system complexity to
the task rather than defaulting to autonomous multi-agent systems, and
give agent systems explicit evaluation, since tool use, intermediate
state, and multi-step execution produce failure modes ordinary
response testing does not catch.

## Framework-agnostic execution model

A `ResearchTask` is fulfilled by whichever engine is adequate for it,
selected by the routing hierarchy below -- never by a framework
default:

```
Can deterministic code answer this task?
        | no
Can the smallest adequate local model do it reliably?
        | no
Can a stronger local model do it?
        | insufficient
Optional, explicitly configured external provider
```

This is the same posture `ai_layer_architecture.md`'s Statistics
Auditor and M2's opt-in local Ollama synthesis already take, extended
into a formal, always-asked routing question for every task rather
than a one-off design choice for one feature. Cloud inference becomes
an optional escalation path a deployment can enable, never a
structural dependency -- the whole architecture should benchmark real
against Qwen/Gemma/similar models through Ollama and route by measured
capability, not by assumed capability.

**This is a real operational cost, not a free optimization** -- see
`ai_layer_architecture.md`'s existing caveat on the routing ladder
(N models to keep pulled, consistent, and individually debuggable).
Prototype against one bounded task before adopting it as a blanket
policy across every worker role.

## The Skeptic worker's evidentiary honesty requirement

`ai_layer_architecture.md` already makes the Skeptic/Contradiction
Worker a mandatory pre-synthesis step, not optional
contradiction-counting. This document adds the specific reporting
discipline that makes that step trustworthy rather than merely
present: when the Skeptic worker searches the Evidence Graph and
bounded new literature for counterevidence and finds none, it must
report exactly that search's limits, never a universal negative:

> No aligned contradictory evidence was found within the searched
> scope.

**Never:**

> There is no contradictory evidence.

The first sentence is a true, falsifiable claim about what was
searched. The second is an unearned claim about the state of the
world's evidence, and this project's evidence-coverage discipline
(`ai_layer_architecture.md`'s Evidence Coverage metric,
`docs/roadmap/long_term_vision.md`'s Confidence Rating Design
Guidance) already exists specifically to prevent exactly this kind of
overclaim elsewhere in the system. The Skeptic worker inherits that
same discipline rather than becoming a silent exception to it.

## Design risks and mitigations

The source planning material documented 16 meaningful architecture
risks and stated that none makes the vision impractical. Only the 14
"most important" were individually named when this document was
drafted (see the provenance note above) -- carried here verbatim in
substance, not invented:

1. **Agent error compounding.** One hallucination must not become
   trusted simply because three downstream agents repeat it.
   Mitigation: source-linked structured state (Evidence Records,
   `ResearchEvent` provenance) plus independent verification at each
   handoff, not agent-to-agent trust.
2. **Prompt injection from papers/websites.** Scientific documents are
   untrusted data, not trusted instructions, the moment they are
   retrieved. Mitigation: least-privilege tools per worker, and no
   worker may gain authority (e.g. the ability to write, acquire, or
   escalate) from text found inside a retrieved document. OWASP's
   agentic-AI guidance specifically names prompt injection,
   over-permissioned tools, memory, and multi-agent interactions as
   major attack surfaces for exactly this class of system.
3. **Local inference vs. public deployment.** Ollama is an excellent
   $0/private development path but not this project's eventual
   multi-user serving architecture. Mitigation: keep the model-provider
   interface abstract now, so a future serving layer is a new
   implementation behind an existing seam, not a rewrite.
4. **Context-window scaling.** The corpus will not always fit in a
   prompt -- 5,000 papers cannot be shoved into an LLM's context.
   Mitigation: hierarchical evidence compression that retains IDs and
   provenance at every compression level, so a compressed summary is
   always traceable back to its source records.
5. **Corpus bias masquerading as consensus.** A corpus that happens to
   contain mostly agreeing studies is not the same as scientific
   consensus. Mitigation: Consensus and Coverage are reported as
   separate, never-merged metrics -- consistent with
   `ai_layer_architecture.md`'s existing Evidence Consensus/Evidence
   Coverage split.
6. **Cross-domain quality scoring.** There is no single scientifically
   legitimate evidence rubric across clinical trials, chemistry
   experiments, physics, psychology, and ML research. Mitigation:
   common framework dimensions (quality, consensus, confidence,
   coverage) with domain-specific profiles underneath, matching
   `ai_layer_architecture.md`'s existing "Domain-specific confidence
   profiles" section and its "revisit once a second-domain corpus
   exists" gate.
7. **Circular AI graph reasoning.** If AI proposes a graph edge and a
   later AI step treats that edge as independent evidence, the system
   can reinforce its own interpretations rather than accumulate real
   evidence. Mitigation: every generated relationship carries
   provenance marking it as AI-proposed, and AI-proposed edges can
   never count as an independent evidence vote in confidence or
   consensus scoring -- only human-confirmed `RelationshipRecord`s do,
   matching `core_interface_contract.md`'s existing rule that nothing
   auto-authors a `RelationshipRecord` without human confirmation.
8. **Canonical evidence mutation.** Agents must not silently rewrite
   the scientific record. Mitigation: agents propose revisions to
   Evidence Records; a human confirms before a canonical record
   changes -- the same seam already enforced for `RelationshipRecord`s
   extends to any agent-proposed edit of an existing `EvidenceRecord`.
9. **Evaluation drift.** Changing a model or a prompt must not be
   declared an improvement because one example answer looks better.
   Mitigation: retrieval, citation, grounding, contradiction-recall,
   and workflow benchmarks run before and after any model/prompt
   change, with results compared, not eyeballed.
10. **Cost explosion.** Ten agents each making five calls destroys the
    "$0 AI" property quickly even with only local models running,
    purely from latency and compute contention. Mitigation: the
    deterministic-code-first, smallest-adequate-model-next routing
    hierarchy above applies to every task, not just externally-billed
    ones.
11. **Memory poisoning.** A model-generated summary is not scientific
    memory and must never be treated as a source. Mitigation: Evidence
    Records and their source documents are the only durable memory;
    summaries are regenerable presentation, not stored fact.
12. **Pseudo-replication.** Multiple publications describing the same
    underlying trial (e.g. a primary paper plus several secondary
    analyses) must not become multiple independent votes toward
    consensus. Mitigation: shared-trial identity must be tracked and
    consensus/coverage scoring must collapse same-trial records to one
    independent unit of evidence.
13. **Publication bias.** The system can identify indicators and gaps
    (e.g. via the Unknowns Engine) but cannot infer that unpublished
    contradicting research does not exist -- absence of evidence in
    the corpus is not evidence of absence in the world. Mitigation:
    this limitation is stated explicitly wherever coverage or
    consensus is reported, not implied away, matching
    `ai_layer_architecture.md`'s own "What is out of reach, named
    explicitly" section, which already names unreliable
    publication-bias detection as out of reach.
14. **Framework lock-in.** Knowledge Engine must own its scientific
    workflow contracts (the four contracts above); agent frameworks
    remain replaceable adapters underneath them, never the
    architecture itself -- this is the load-bearing reason the four
    contracts exist in the first place, not an afterthought.

*(The source material's count of 16 total blocks exceeds the 14 named
above; the remaining two were not individually described when this
document was drafted. Do not assume they are covered by the above --
reconcile against the original file if/when it becomes available.)*

## Build progression

Eleven milestones, deliberately ordered so the exciting,
least-grounded material (autonomous discovery and hypothesis
generation) comes last, matching `ai_layer_architecture.md`'s existing
"Autonomous hypothesis generation and experiment design... come after
all five stages, not before" posture and its Stage 5 gate ("Discovery
Intelligence remains gated by adequate analytical inputs and
relationship coverage"):

- **AI-O1: `ResearchPlan` contract.** Define and validate the typed
  output of classifying a research question.
- **AI-O2: Durable `ResearchSession`.** Persist an investigation's
  state outside the prompt window -- the concrete implementation of
  `ai_layer_architecture.md`'s `ResearchSession` design.
- **AI-O3: Deterministic orchestrator over existing `core`/`ai`
  tools.** No new AI capability -- wire the four contracts around
  capabilities that already exist (M32/M39 search, M69 extraction, the
  Evidence Graph) before adding any new model call.
- **AI-O4: Local LLM query planner.** The first genuinely new AI
  capability in this sequence, and the routing ladder's first
  prototype candidate per `ai_layer_architecture.md`'s existing note.
- **AI-O5: Parallel retrieval + contradiction search.** Concurrent
  `ResearchTask` fan-out (plain `asyncio.TaskGroup`, no new
  infrastructure, per `ai_layer_architecture.md`'s "What this borrows"
  section) across Discovery, Retrieval, and Contradiction workers.
- **AI-O6: Skeptic + verifier.** The mandatory pre-synthesis
  contradiction step, with the evidentiary honesty requirement above.
- **AI-O7: Durable research-session synthesis.** Compose a cited
  answer from a `ResearchSession`'s accumulated state, not from a
  single-turn prompt.
- **AI-O8: Local model router.** Formalize the deterministic ->
  smallest-model -> stronger-model -> external-provider ladder as a
  reusable component, once AI-O4 has validated it on one workflow.
- **AI-O9: Observability + execution budgets.** Every `ResearchTask`
  execution becomes a traceable `ResearchEvent`; sessions carry
  explicit cost/time budgets so a runaway task tree cannot silently
  exhaust either. Aligned with current industry practice of treating
  handoffs, tool calls, guardrails, and model generations as
  individually traceable operations, and with OWASP's
  least-privilege-tools and explicit-approval-for-consequential-actions
  guidance for agentic systems.
- **AI-O10: Discovery Intelligence / Unknowns Engine.** Only once
  AI-O1-O9 exist and a corpus has enough reviewed evidence and
  relationship density for gap-surfacing to mean something real --
  the same gate `ai_layer_architecture.md`'s Stage 5 already states.
- **AI-O11: Hypothesis and experiment assistance.** The most
  open-ended, least-grounded capability, deliberately last.

## Relationship to `ai_layer_architecture.md`'s Orchestration section

This document refines rather than replaces that section:

- The four contracts here (`ResearchPlan`/`ResearchSession`/
  `ResearchTask`/`ResearchEvent`) are a more disciplined restatement of
  that section's informal "v0.1: Orchestrator, Retriever, Skeptic,
  Composer/Citation-Auditor -- four components" build plan. Treat the
  AI-O1-O11 sequence above as the concrete replacement for that
  section's three-step "Sequencing and the real gate" list.
- The worker-role table in that section (Orchestrator, Query Planner,
  Discovery/Retrieval Workers, Evidence Extractor/Analyst,
  Contradiction/Skeptic Worker, Statistical Worker, Source/Citation
  Auditor, Composer) still describes *what* executes; this document
  adds *how tasks reach those workers and how their results are
  recorded* (the four contracts) and *what could go wrong along the
  way* (the sixteen -- fourteen named -- design risks).
- The real gate is unchanged and restated here for emphasis: evidence-
  base thickness, not architecture. As of this document's drafting,
  GLP-1 has the only externally-audited golden map; oncology has a
  small same-session-self-audited reviewed layer; mental-health has
  none. AI-O1-O3 do not require more evidence coverage to build (they
  wire existing tools); AI-O5 onward benefit substantially from it,
  and AI-O10 is explicitly blocked without it.

## End state

The end state this document and `ai_layer_architecture.md` together
describe is considerably larger than a research chatbot: a versioned
scientific investigation engine. Ask a question today; the system
preserves exactly what evidence was available and how it was analyzed
via a durable `ResearchSession`; return weeks later and ask Knowledge
Engine what changed, why an assessment changed, what did not change,
and what remains unknown -- reconstructed from stored, source-linked
state, never from re-reading a chat transcript.

## Open questions carried forward

- **Exact `ResearchTask`/`ResearchEvent` schemas.** Named and scoped
  at a conceptual level here; field-level schema design is AI-O1/AI-O2
  implementation work, not resolved in this document.
- **Where contract validation lives.** Whether `ResearchPlan`/
  `ResearchSession`/`ResearchTask`/`ResearchEvent` are `core`-side
  models (like `EvidenceRecord`) or `knowledge-engine-ai`-side is an
  open package-boundary question, in the same spirit as
  `ai_layer_architecture.md`'s existing "Package split" open question.
- **The full 16-block risk list.** Reconcile against the original
  source file once its content is available; only 14 named risks are
  captured here (see the provenance note and the design-risks
  section).
- **Execution-budget defaults for AI-O9.** No specific cost/time
  ceilings are proposed here; these should be set from measured
  real-workload data once AI-O3 gives a deterministic-orchestrator
  baseline to measure against.
