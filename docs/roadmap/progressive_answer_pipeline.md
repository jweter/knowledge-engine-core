# Progressive Answer Pipeline Roadmap

Status: adopted product direction, 2026-08-25.

## Canonical references

This product requirement is intentionally cross-linked so it survives isolated
agent sessions and future roadmap work:

- `docs/roadmap.md` — canonical active roadmap.
- `docs/roadmap/long_term_vision.md` — finished-product vision.
- `docs/roadmap/evolving_vision_principles.md` — standing future-facing vision.
- `docs/agent-development-policy.md` — operational contract for agents.
- `AGENTS.md` — repository-root agent entry point.

## Decision

A Knowledge Engine search should not force the user to choose between a fast
answer and deep research before they know what they need. A single search should
mature progressively from an immediately useful response into a sourced,
verified, and, when justified, deep-research result.

The canonical product states are:

```text
Draft -> Sourced -> Verified -> Deep
```

These are maturity states of one research run, not four unrelated products.
The user should receive useful information as early as possible while the system
continues to strengthen the same answer with retrieval, evidence, contradiction
review, citation validation, and deeper synthesis.

## Product behavior

### Draft

Goal: minimize time-to-first-useful-answer.

- Return a concise preliminary answer immediately when the available model and
  cached context can do so safely.
- Clearly identify the answer as preliminary/unverified when source-backed work
  has not completed.
- Do not block this stage on full literature discovery, contradiction analysis,
  or deep synthesis.
- If the question cannot be answered safely without retrieval, say so rather
  than inventing a fast answer.

### Sourced

Goal: add evidence without making the user start over.

- Retrieve relevant evidence and attach source-linked citations.
- Add important definitions, qualifiers, recent findings, and limitations.
- Preserve the original answer surface and update it progressively rather than
  replacing the page with a separate search result.
- Record discovery coverage and provider failures where available.

### Verified

Goal: make the answer defensible.

- Run Research ISA close gates appropriate to the question.
- Validate citation integrity and claim-to-evidence links.
- Search for contradictory, null, negative, qualifying, correction, and
  retraction signals when relevant.
- Separate source evidence, deterministic analysis, and AI synthesis.
- Surface uncertainty and unresolved gaps instead of hiding them behind fluent
  prose.

### Deep

Goal: continue only when the question and user interest justify the cost.

- Expand discovery breadth and citation/reference traversal.
- Compare study populations, interventions, comparators, outcomes, methods, and
  limitations where applicable.
- Perform deterministic statistical or structured analytical checks when the
  evidence supports them.
- Produce a more comprehensive synthesis and evidence map without invalidating
  the earlier useful states.

## Attention-aware research budget

User attention is a legitimate scheduling signal, but never an epistemic signal.
Staying on a page means the system may invest more compute and retrieval effort;
it does not make a claim more likely to be true.

The scheduler should eventually support behavior such as:

- active result page -> continue normal/deep enrichment;
- user scrolls into evidence or contradiction sections -> increase priority;
- explicit `Keep researching` action -> highest interactive priority;
- user navigates away -> lower background priority after the useful/sourced
  minimum is reached;
- many rapid searches -> prioritize Draft for each query, then allocate deeper
  work to actively viewed or explicitly requested runs;
- cached or previously verified evidence -> reuse it immediately while checking
  freshness asynchronously;
- abandoned runs -> preserve completed evidence and resumable state rather than
  throwing work away.

The system must not infer scientific confidence from dwell time, clicks, or
engagement. These signals control resource allocation only.

## Stable progressive UI

Live updating must not make the answer difficult to read.

The Web layer should prefer stable, append-oriented changes:

- attach citations to existing claims;
- add expandable evidence, limitations, and contradiction sections;
- show a small maturity/status indicator;
- announce meaningful updates without continually rewriting text under the
  user's cursor;
- preserve prior answer revisions so a later synthesis can be audited against
  what the user originally saw.

A representative status progression is:

```text
Answer available       [Draft]
8 sources checked      [Sourced]
Claims/citations pass  [Verified]
Deep research complete [Deep]
```

Exact timing is not a contract. The architecture should optimize latency and
quality independently rather than promising fixed second counts.

## Cross-repository responsibilities

### `knowledge-engine-web`

- Render the first useful answer as soon as it is available.
- Subscribe to research-run progress and answer-revision events.
- Preserve a stable reading experience while adding evidence and later
  revisions.
- Expose maturity, source count, active verification work, and failures in clear
  user-facing language.
- Support explicit continuation controls such as `Keep researching`.

### `knowledge-engine-ai`

- Produce a bounded preliminary synthesis when appropriate.
- Continue the same Research Session through sourced, verified, and deep stages.
- Never release a later generated revision unless its stage-specific release
  gate passes.
- Treat earlier answers as versioned artifacts, not disposable chat text.
- Allow scheduling priority to change without changing the scientific criteria
  for completion.

### `knowledge-engine-core`

- Keep retrieval, Evidence Records, provenance, claim/evidence relationships,
  contradiction signals, and deterministic checks independent from UI timing.
- Persist enough run state and evidence identity for later stages to resume and
  improve an earlier answer.
- Reuse cached evidence safely while preserving freshness metadata.
- Provide deterministic progress facts; do not fabricate percentage-complete
  values when the denominator is unknown.

## Required contracts

A progressive run needs durable identifiers and monotonic stage semantics.
Future API/event design should include equivalents of:

- `research_run_id` -- stable across all stages;
- `answer_revision_id` -- immutable revision identity;
- `maturity_state` -- `draft | sourced | verified | deep`;
- `release_gate_status` -- whether the current revision may be shown;
- `sources_considered` and `sources_cited` where known;
- `verification_checks` with explicit pass/fail/unavailable state;
- `started_at`, `updated_at`, and evidence freshness metadata;
- resumable/cancelled/deprioritized execution state.

Stage transitions are one-way for a particular revision lineage unless new
evidence invalidates a prior conclusion. In that case the system creates a new
revision and explains what changed; it must not silently preserve a misleading
`Verified` label.

## Performance objectives

Time-to-useful-answer is a first-class product metric alongside evidence quality
and integrity.

Measure at least:

- time to first useful Draft;
- time to first source-linked citation;
- time to Sourced;
- time to Verified;
- time to Deep when Deep is reached;
- fraction of rapid-search sessions that obtain a useful Draft before the user
  moves on;
- cache reuse rate;
- research work abandoned before useful output;
- answer revisions blocked by release gates;
- user-visible answer churn while reading.

The system should be fast because unnecessary work is deferred or reused, not
because verification is skipped and mislabeled as complete.

## Safety and truthfulness invariants

Progressive delivery must not weaken the Knowledge Engine's existing trust
model.

1. A Draft is never presented as verified evidence.
2. Later evidence may revise an earlier answer; revisions must be visible and
   attributable.
3. User attention controls scheduling, never evidence weight or confidence.
4. Citation and Research ISA gates remain deterministic where designed to be
   deterministic.
5. Partial provider failure remains visible.
6. A fast answer that cannot be responsibly produced is replaced by an honest
   `researching / insufficient evidence yet` state.
7. Deep work may be deprioritized, paused, or resumed without losing the
   evidence already captured.

## Implementation sequence

1. **Version the answer artifact.** Give each Research Session stable run and
   revision identifiers plus an explicit maturity state.
2. **Stream deterministic progress.** Expose retrieval, evidence, citation, and
   gate events from AI/Core to Web without requiring generated prose.
3. **Ship Draft -> Sourced.** Make Web render a fast preliminary answer and add
   citations/evidence as they arrive.
4. **Ship Sourced -> Verified.** Bind the existing Research ISA and release gate
   to the visible maturity state.
5. **Add stable live-update UX.** Avoid disruptive full-answer replacement;
   preserve revisions and highlight meaningful changes.
6. **Add attention-aware scheduling.** Prioritize active/explicitly continued
   runs while guaranteeing fast-answer fairness for rapid multi-query use.
7. **Add Deep continuation.** Expand discovery and analysis only after the
   verified path is measurable and reliable.
8. **Benchmark latency and quality together.** Prevent optimization for speed
   from degrading retrieval, citation integrity, contradiction handling, or
   truthfulness.

## Exit condition

This roadmap item is complete when a single public Knowledge Engine query can
produce an immediate useful answer, visibly mature through sourced and verified
states without a page restart, optionally continue into deep research, and
remain responsive when the same user launches several unrelated searches in
rapid succession.

The long-term principle is simple:

> Fast when the user needs speed, deeper while the evidence arrives, and fully
> researched when time and attention justify it -- all as one continuous answer.
