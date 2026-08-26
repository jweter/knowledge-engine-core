# Evolving Vision Principles

Status: standing future-facing guidance, 2026-08-25.

`docs/founding_vision.md` remains the preserved historical statement of why the
Knowledge Engine exists. `docs/roadmap/long_term_vision.md` translates that
mission into the current multi-package architecture. This document adds a third
horizon: how the vision should continue to evolve after any particular release or
roadmap is completed.

## A finished release is not a finished Knowledge Engine

The Knowledge Engine should eventually reach coherent, complete product releases,
but it should never treat a release as the end of the project. Human knowledge,
research practice, scholarly infrastructure, model capability, and software
engineering will keep changing.

The long-term operating model is therefore:

```text
build a trustworthy capability
        |
        v
measure it in real use
        |
        v
identify failure modes and missing leverage
        |
        v
study better external ideas and new research
        |
        v
translate useful advances into our own contracts
        |
        v
verify that they improve the system without weakening trust
        |
        +-------------------------------> repeat
```

The system should become more capable over time without becoming less
understandable.

## Permanent improvement questions

At regular architecture and roadmap reviews, ask across every layer:

### Scientific quality

- Are we retrieving the right evidence, or merely more evidence?
- Can search coverage be measured rather than assumed?
- Are contradictory, null, negative, correction, and retraction signals visible?
- Can a user reconstruct why a claim, relationship, or synthesis exists?
- Are provider metadata and actual source-paper evidence clearly distinguished?
- What important evidence classes or research domains remain systematically
  under-covered?

### Discovery

- Are we searching enough independent scholarly indexes?
- Can identifier resolution and citation/reference traversal find evidence that
  keyword search misses?
- Can the system rerun a research question later and explain what changed?
- Can it identify missing experiments, unresolved contradictions, weakly explored
  populations, or unstable conclusions?
- Can a broad source library serve questions that were not anticipated when the
  corpus was built?

### Evidence and reasoning

- Can more claims be represented as typed, inspectable structures rather than
  prose-only summaries?
- Are analytical calculations deterministic wherever they can be?
- Are confidence and coverage decomposed into inspectable inputs rather than one
  opaque score?
- Does the Research ISA specify what would count as sufficient coverage,
  contradiction review, citation integrity, and completion for a given task?
- Does AI remain constrained to grounded interpretation rather than becoming the
  hidden source of facts?

### Architecture

- Can every provider, model, search backend, storage layer, and interface be
  replaced without rewriting the scientific core?
- Are networked capabilities behind explicit typed boundaries?
- Is the source of truth separate from derived indexes, caches, summaries, and
  generated narratives?
- Are we adding abstractions because measured complexity requires them, or merely
  because they are fashionable?

### Security and privacy

- What leaves the machine and why?
- Is every external request necessary for the task?
- Can optional telemetry, analytics, or model calls be disabled without breaking
  scientific functionality?
- Are secrets excluded from prompts, evidence, logs, and committed files?
- Are external papers, webpages, repositories, and metadata always treated as
  untrusted data rather than instructions?

### Reliability and operations

- Does partial failure remain visible?
- Can we distinguish unavailable, rate-limited, disabled, degraded, and failed
  capabilities?
- Can a run be resumed, reproduced, compared, and audited?
- Do we know when provider data, corpora, indexes, models, or public snapshots were
  last refreshed?
- Can we recover from data loss without relying on an opaque external service?

### Product and user experience

- Does the user see the distinction between source evidence, deterministic
  analysis, AI synthesis, and speculation?
- Can a researcher move from a broad question to the exact evidence quickly?
- Are uncertainty and search limitations visible without forcing users to read
  internal logs?
- Can experts inspect details while non-experts still receive clear explanations?
- Is the public interface teaching users how to reason with evidence rather than
  merely delivering answers?
- Does every search produce useful value as early as responsibly possible while
  allowing the same answer to mature into a deeper, better-supported result?
- Can rapid multi-topic searching remain responsive without throwing away the
  option of deeper work on the result the user keeps exploring?

### Performance and cost

- Are cheap deterministic methods doing work that does not need an LLM?
- Are local models used where privacy, repetition, or cost makes them the better
  tool?
- Are expensive models reserved for tasks where measured reasoning quality
  justifies the cost?
- Are caches, batching, deduplication, incremental refresh, and source-aware
  scheduling reducing unnecessary work?
- Can the project scale up without forcing a paid service into the critical path?
- Is time-to-first-useful-answer measured independently from time-to-verified and
  time-to-deep-research completion?
- Can active user attention increase research priority without ever changing the
  scientific weight, truth status, or confidence of evidence?

### Open-source ecosystem learning

- What new projects solve a problem we also have?
- Which parts are genuinely better than ours?
- Which assumptions, telemetry, licensing, runtime coupling, or architecture
  should be rejected?
- Can we learn the idea and implement a smaller, cleaner Knowledge Engine-native
  version?
- If code is reused, are attribution and license obligations clear?

## Progressive answers are the default interaction model

A Knowledge Engine query should be one continuous research run, not a forced
choice between a fast chatbot answer and a separate deep-research product.
Whenever a responsible preliminary answer can be produced, the system should
show it immediately and then progressively strengthen that same result as
retrieval, sourcing, verification, contradiction review, and deeper analysis
complete.

The canonical maturity path is:

```text
Draft -> Sourced -> Verified -> Deep
```

These labels describe what has actually completed. They are not cosmetic quality
badges. A Draft is useful but preliminary. Sourced means evidence has been
attached. Verified means the relevant release/Research ISA gates have passed.
Deep means the system invested additional discovery and analytical effort beyond
the verified minimum.

This interaction model establishes several permanent principles:

- **Time-to-useful-answer is a first-class metric.** Scientific rigor should not
  require an empty page while the entire research pipeline finishes.
- **Depth is progressive, not preselected.** The user should not need to decide
  how much research is necessary before seeing the first result.
- **User attention may schedule compute, never truth.** Remaining on a result,
  opening its evidence, or explicitly asking the engine to keep researching may
  increase that run's priority. Those signals must never increase evidence
  weight or confidence.
- **Rapid search remains fast.** A user may ask several unrelated questions in
  succession and receive the fast stage for each. Background/deep work should be
  deprioritized or resumed intelligently rather than blocking the next query.
- **Live updates should be stable.** New citations, evidence, limitations, and
  verified revisions should appear without constantly rewriting text underneath
  someone who is reading it.
- **Revisions remain auditable.** Later evidence may change an earlier answer;
  the system should preserve what changed and why rather than silently replacing
  history.
- **Insufficient evidence is a valid early result.** When a fast answer cannot be
  produced responsibly, the engine should say that research is still required
  instead of fabricating certainty to satisfy latency.

The implementation roadmap for this product behavior is maintained in
`docs/roadmap/progressive_answer_pipeline.md`.

## Provider-neutral research infrastructure

The review of `find-research-papers-mcp` reinforces a future in which scholarly
sources are interchangeable provider adapters behind a Knowledge Engine-owned
Discovery Broker. PubMed, Crossref, OpenAlex, Semantic Scholar, arXiv, and later
providers should contribute observations to a common evidence-acquisition flow
without owning the scientific method or user experience.

This is one instance of a broader rule:

> Interfaces should be plural; truth and provenance should remain ours.

The same rule applies to LLMs, embeddings, web hosts, databases, MCP clients,
browser tools, storage backends, and future research services.

## Search coverage as a future scientific signal

Traditional search systems often hide how many sources were searched and whether
one failed. Knowledge Engine should eventually treat discovery coverage as part
of the evidence context itself.

A future coverage model may consider:

- provider relevance to the domain;
- providers attempted/completed;
- query variants;
- publication-date reach;
- citation/reference expansion;
- identifier crosswalk coverage;
- preprint versus peer-reviewed coverage;
- language and geography limits;
- full-text versus metadata-only availability;
- provider outages and rate limits;
- recency of the search.

The immediate requirement is not to invent a coverage score. It is to persist the
facts needed to calculate and explain one later.

## Continuous evidence refresh

A research answer should be understood as a versioned state of knowledge, not a
static final response. Over time the system should be able to rerun the same
research task and report:

- newly discovered studies;
- newly available full text;
- new citations or references;
- corrections, expressions of concern, withdrawals, or retractions;
- changed contradiction patterns;
- changes in evidence quality or consensus;
- conclusions that remained stable;
- conclusions that should now be reconsidered.

This operationalizes the founding principle that knowledge is never final.

## The improvement backlog is allowed to be infinite; active work is not

The vision may keep expanding indefinitely. The active roadmap must remain
bounded.

Every proposed improvement should be placed into one of four states:

1. **Now** -- measured, scoped, and required by the current goal.
2. **Next** -- sufficiently designed to follow current work.
3. **Later** -- valuable but waiting on prerequisite capability or evidence.
4. **Watch** -- external idea/technology worth monitoring but not yet justified.

Moving an item forward requires evidence: a failure, benchmark, user need,
security requirement, cost reduction, capability gap, or clear architectural
leverage. This protects the project from both stagnation and uncontrolled scope
expansion.

## North-star outcome

The Knowledge Engine should become progressively better at helping people answer
four questions:

1. **What do we know?**
2. **Why do we think we know it?**
3. **What do we not know or disagree about?**
4. **What is the highest-value thing to learn next?**

Everything we adopt, build, remove, or redesign should make those answers more
accurate, traceable, current, useful, reproducible, and available as early as
responsibly possible.
