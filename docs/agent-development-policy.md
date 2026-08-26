# Agent Development Policy

This document governs scheduled and autonomous engineering work on
`knowledge-engine-core`. It exists so a fresh, isolated agent run — with no
memory of any prior conversation — can pick this repository up cold and work
it correctly: which PR to merge, which to repair, what to build next, and
where the boundaries are.

`docs/project_principles.md` states the project's values (ten-year
maintainability, provenance, transparency, honest degradation). This document
is the operational contract that turns those values into a repeatable
scheduled-run procedure.

The repository-root `AGENTS.md` is the short agent entry point. For any work
that touches Ask, Research Sessions, Web/AI/Core orchestration, answer
streaming/versioning, release gates, scheduling, caching, or user-visible
latency, agents must also read
`docs/roadmap/progressive_answer_pipeline.md`. The adopted product behavior is
one continuous research run that matures `Draft -> Sourced -> Verified -> Deep`:
an immediately useful answer first, then progressively stronger evidence,
verification, and deep research. This requirement must not be reconstructed
from conversation memory or silently replaced by a separate fast-vs-deep mode.

## 1. Knowledge Engine is a three-repository family

`knowledge-engine-core` is one of three repositories that together form one
coordinated system:

- `knowledge-engine-core` (this repo) — ingestion, discovery, the evidence
  graph, and the `ke` CLI. The CLI is the only supported interface; there is
  no HTTP API and no importable `knowledge_engine` package for other
  processes (see `docs/core_interface_contract.md`).
- `knowledge-engine-web` — a read-only web front end. Reads Core's SQLite
  database directly via SQLAlchemy reflection (never imports
  `knowledge_engine`), and increasingly also shells out to `ke` through
  `knowledge-engine-ai`'s `ke_client.py` boundary module.
- `knowledge-engine-ai` — the judgment/orchestration layer. Owns the one
  supported process boundary for invoking `ke` as a subprocess
  (`knowledge_engine_ai/ke_client.py`); Web depends on this repo rather than
  calling `ke` directly.

Treat this as one coordinated software system, not three unrelated products.
Priorities and requirements for all three come from each repository's own
current documentation, issues, PRs, and roadmap — never invented, and never
imported wholesale from an unrelated project (Rocksmith, Everward, or
anything else) merely because it appeared in another conversation.

### 1a. Before changing a shared contract

Before merging a Core change that alters anything Web or AI consume —
CLI command names/flags, `--output` JSON shape, database schema, the
federated-discovery ledger/coverage contract, or any other cross-repo
interface — identify the consumers first:

```text
Core -> Web (direct SQLite reflection)
Core -> AI (ke_client.py subprocess wrapper)
AI  -> Web (knowledge-engine-ai as a Python dependency)
```

Then determine whether the change is backward compatible.

**Safe case:** Core adds a new optional field to a JSON payload or a new CLI
flag with a default. Existing Web/AI code that ignores the unknown field or
omits the new flag keeps working. Proceed normally.

**Dangerous case:** Core renames or removes a field/flag an existing Web or
AI code path depends on. Do not merge this blind. Identify every consumer,
prepare the dependent Web/AI changes (even if they land as separate PRs in
those repos), verify compatibility, and merge in a dependency-safe order —
Core's backward-compatible half first if one exists, or coordinate the merge
order explicitly. Do not knowingly leave the three-repository family in a
broken cross-repository state after a merge.

The federated-discovery family (`knowledge_engine/federated_discovery.py`,
`federated_search_ledger.py`, `federated_result_snapshot.py`,
`provider_disagreement.py`, exposed through `ke federated-discover`) is the
current highest-traffic cross-repo surface — `knowledge-engine-web`'s
`docs/federated_discovery_transparency_roadmap.md` (WEB-FRD-#) and
`knowledge-engine-ai`'s `docs/roadmap/federated_discovery_orchestration_adoption.md`
both depend directly on what this repo's FRD-# milestones expose. Check
those two documents' own stated dependencies before changing this surface.

## 2. Source of truth and freshness

Authority order when sources disagree:

1. Verified current repository state: code, tests, CI, open PRs/issues.
2. `docs/roadmap.md` and `docs/roadmap/` — canonical direction, including
   `docs/roadmap/long_term_vision.md`,
   `docs/roadmap/evolving_vision_principles.md`, and the adopted
   `docs/roadmap/progressive_answer_pipeline.md` product contract where relevant.
3. `docs/project-status.yaml` — continuity snapshot; verify and refresh it
   every scheduled run (see section 9).
4. This document — workflow, merge policy, safety rules, escalation.
5. `docs/founding_vision.md`, `docs/project_principles.md`,
   `docs/architecture.md`, `docs/core_interface_contract.md`, and other
   current design docs relevant to the work.
6. `docs/decisions.md` and `docs/architecture/adr/` for historical rationale.
7. Conversation memory or assumptions — lowest authority. If a prior session's
   summary conflicts with verified repository state, trust the repository.

If lower-authority documentation conflicts with higher-authority repository
evidence, updating the stale documentation is part of the work, not deferred
cleanup.

## 3. Scheduled-run triage

At the start of every scheduled run, before starting substantial new roadmap
work, inspect:

- open pull requests, their CI status, and mergeability;
- unresolved blocking review threads or requested changes;
- `docs/project-status.yaml` against verified repository reality;
- `docs/roadmap.md` / `docs/roadmap/` for the current milestone;
- `docs/roadmap/progressive_answer_pipeline.md` whenever the proposed work
  affects Ask, research-session lifecycle, answer delivery, streaming,
  scheduling, caching, or user-visible latency;
- relevant architecture/design documents for the work under consideration.

Never invent repository state. If a tool cannot confirm something (CI status,
merge outcome, file contents), say so rather than guessing.

## 4. PR state machine

Existing work takes priority over new work. Classify every relevant open PR
as GREEN, FAILED, PENDING, CONFLICTED, BLOCKED, or UNCERTAIN.

### GREEN

Merge only when all of the following are true for the exact current head SHA:

- `Quality` (ruff format, ruff check, mypy, pytest) has succeeded;
- `Security - Bandit` has succeeded;
- `Security - pip-audit` has succeeded;
- `M14 Mass Discovery` has succeeded, **if and only if** it ran (it is
  path-filtered to `knowledge_engine/pubmed_batch_discovery.py`,
  `pubmed_discovery.py`, `ncbi_http.py`, and its own workflow file — most
  PRs will not trigger it, and that is not a failure);
- mergeability is resolved and the PR is mergeable;
- no unresolved blocking review comment remains;
- no material correctness, architecture, security, licensing, provenance,
  or privacy concern remains.

Merge with squash (this repository's established convention — check recent
merged PRs if in doubt). After merging, verify GitHub actually reports the
merge succeeded, then sync local `main`.

A code-review bot comment reporting it is out of quota/usage-limited
(`chatgpt-codex-connector` posting "reached your Codex usage limits" is the
recurring example) is not a blocking finding — it is the review service being
unavailable, not a review outcome. Do not treat it as needing action.

### FAILED

1. Inspect the actual failing job's logs — do not guess the cause from the
   job name alone.
2. Identify the first meaningful failure.
3. Determine root cause from evidence; reproduce locally when practical
   (`poetry run ruff format --check .`, `poetry run ruff check .`,
   `poetry run mypy knowledge_engine tests`, `poetry run pytest`).
4. Make the smallest safe correction on the existing PR branch.
5. Add or update regression tests when the defect class warrants it.
6. Push the correction and leave the PR for fresh CI — do not merge on the
   strength of local success alone.
7. Do not report a failure fixed until fresh CI evidence supports that claim.

For a significant or recurring failure, add an entry to
`docs/error_resolution_ledger.md` using its existing entry template
(area, first failing command, symptom, affected files, root cause, fix,
validation, prevention, status).

### PENDING

Do not merge. Do not duplicate the work. Do not create dependent work that
assumes a pending PR has already merged.

### CONFLICTED / BLOCKED / UNCERTAIN

Investigate. Resolve routine, evidence-supported conflicts when clearly
safe. Never force-merge merely to produce progress. Escalate only when a
genuine human decision is required (section 8).

## 5. New development selection

If no higher-priority PR needs action, select work in this order:

1. **P0** — security issue, data-loss risk, or major correctness regression.
2. **P1** — existing PR with failing CI that can be safely repaired.
3. **P2** — existing PR verified GREEN and ready to merge.
4. **P3** — blocking review feedback or merge conflict.
5. **P4** — incomplete current milestone / already-started work.
6. **P5** — highest-value authorized roadmap slice (read `docs/roadmap.md`
   and the relevant `docs/roadmap/*.md` file for the active milestone family;
   the FRD-# federated-discovery sequence and the M-# corpus/graph sequence
   are both examples of this project's own numbering conventions — continue
   the existing sequence rather than starting a competing one).
7. **P6** — refactoring, optimization, or documentation cleanup without an
   immediate blocker.

Within equal priority: unblock dependencies first, favor older blockers,
favor higher scientific/product value, and prefer the smallest coherent
implementation. At most one substantial new roadmap implementation should be
started in this repository during a single scheduled run.

## 6. Development workflow

For a new slice:

1. Read the current milestone/status in `docs/roadmap.md` and
   `docs/project-status.yaml`.
2. Read the relevant design document(s) for the surface being touched, including
   `docs/roadmap/progressive_answer_pipeline.md` for progressive-answer surfaces.
3. Define a small, falsifiable completion target.
4. Create a focused branch (this repo has used names like
   `<feature-slug>` or `<milestone>-<short-description>`; avoid `main`).
5. Implement only that target.
6. Add or update tests. New network-touching code (a new provider transport,
   a new external API call) needs both offline fixture tests and a real
   live-verification pass against the actual external service before the PR
   is opened — this project's established discipline is to distrust a
   fake-only pass and independently confirm real behavior (see recent
   `*_http.py` transports for the pattern: host-allowlisted, HTTPS-only, no
   redirects, bounded reads, and a documented live call in the PR
   description).
7. Run the full local quality gate: `poetry run ruff format --check .`,
   `poetry run ruff check .`, `poetry run mypy knowledge_engine tests`,
   `poetry run pytest`. All must be clean before opening a PR.
8. Update documentation in the same PR: the relevant `docs/roadmap/*.md`
   milestone's status paragraph, `docs/core_interface_contract.md` if the CLI
   surface changed, and `CHANGELOG.md` under `## [Unreleased]`.
9. Open one focused, **non-draft** pull request (this repository does not use
   draft PRs as a "not ready" signal — a PR is either not opened yet, or
   opened ready for review; "draft" has been explicitly rejected as
   confusing in this repository's history).
10. Leave the newly opened PR for fresh, independent CI. Do not merge in the
    same run solely because local tests passed.

## 7. Trust boundaries (do not weaken without a human decision)

These carry directly from `docs/project_principles.md` and apply to every
change, not just federated-discovery work:

- **Provenance survives normalization.** When multiple sources describe the
  same work, retain every source observation and material disagreement.
  Never let a normalized/summarized view replace the ability to reconstruct
  how a result was produced.
- **Graceful degradation must stay honest.** `success`, `partial`,
  `unavailable`, `rate_limited`, and `disabled` are different states. A
  degraded run must never be presented as if it were complete. Never infer a
  provider's status from result count alone.
- **No hidden algorithms.** Ranking, confidence, extraction, and coverage
  logic must remain inspectable — no scoring a reader cannot trace.
- **Local-first privacy.** Network access is explicit and bounded to the
  operation being performed. No credential ever enters a commit, PR body, log
  line, or committed file. Optional provider API keys are read from
  environment variables only.
- **Reproducibility.** Federated search runs are persisted to the immutable
  ledger before being returned to a caller — never let a code change make a
  search result returnable without being durably recorded first.

## 8. Human decision boundaries

Routine implementation, test, refactoring, and documentation decisions should
be made autonomously when repository evidence supports them.

Escalate to the project owner only for:

- fundamental product-direction changes;
- a major architecture change not already authorized by the roadmap;
- a new paid service or meaningful recurring cost;
- license changes;
- destructive or irreversible data migrations;
- privacy/security boundary changes;
- a credential or secret problem requiring the owner directly;
- genuinely ambiguous requirements with materially different possible
  outcomes.

Do not interrupt for routine coding judgments.

## 9. Continuity record: `docs/project-status.yaml`

`docs/project-status.yaml` is a continuity cache for scheduled automation. It
never overrides code, CI, live PR/issue state, or `docs/roadmap.md` — but it
must be kept accurate. At the start of every scheduled run, verify it against
real repository state (open PRs, corpus size, last merged milestone). At the
end of any run that changed durable project reality, update it: the active
milestone, any open PR, durable blockers, and the exact next continuation
point. Do not open a no-op PR merely to refresh its timestamp when nothing
substantive changed; do let it go stale when something did.

## 10. Truthfulness and safety

Never fabricate repository access, files, tests, CI results, issues, commits,
PR numbers, merge results, or project progress. Never expose or commit
secrets. Never merge red, pending, missing-required-check, conflicted, or
materially uncertain code. Never change unrelated files solely because they
were noticed. Prefer small, reversible, testable changes.
