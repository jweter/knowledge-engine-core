# n8n Cross-Project Orchestration Plan

Last reviewed: 2026-08-20
Upstream: `n8n-io/n8n`
Scope: Knowledge Engine Core/Web/AI, Rocksmith CDLC Generator, Project Everward, and future personal project automation
Integration posture: **External self-hosted orchestration/control plane; never embedded as the product core**

## Purpose

n8n is a candidate for coordinating repeated cross-project workflows that currently risk becoming bespoke glue: scheduled repository checks, issue/PR routing, agent handoffs, notifications, artifact movement, model calls, and human approval steps.

It must remain outside each project's product logic. Repositories own their own build/test/release behavior; n8n coordinates them.

## License gate

n8n's main codebase is currently source-available under its Sustainable Use License, with Enterprise-licensed portions. It is not OSI open source. The license permits internal business, personal, and non-commercial use but restricts certain ways of offering n8n functionality to third parties.

Therefore:

- use n8n as a private/internal orchestration service;
- do not bundle or white-label n8n as a customer-facing feature without a fresh license review;
- do not make customer credentials flow through n8n-backed product features unless the current license explicitly permits the intended case;
- never copy Enterprise-licensed `.ee.` code into project repositories;
- re-check license terms before commercialization of any feature materially powered by n8n.

## Architectural boundary

```text
                         +--> knowledge-engine-core CI/API/CLI
                         +--> knowledge-engine-web CI/API
GitHub / schedules ----> n8n --> knowledge-engine-ai jobs
                         +--> rocksmith-cdlc-generator workflows
                         +--> Project-Everward workflows
                         +--> notifications / human approval
```

n8n may trigger a repository-owned command or API. It must not reproduce repository domain logic inside workflow nodes.

## First target: multi-repository development loop

Candidate orchestration:

```text
scheduled trigger
  -> enumerate approved repositories
  -> inspect open PRs/checks/issues
  -> if green and policy allows: request/perform approved merge action
  -> if failing: classify and record root cause
  -> if idle: select highest-value roadmap item
  -> invoke approved coding-agent workflow
  -> branch/PR handoff
  -> record run outcome
```

Important: merge, write, or agent actions remain subject to each repository's existing authorization and CI policy. n8n does not weaken those gates.

## Workflow design rules

1. **Repository policy is authority.** Read each repo's agent-development policy/roadmap before action.
2. **Idempotency.** Every workflow run gets an immutable run ID. Replayed events must not duplicate branches, PRs, comments, or merges.
3. **Least privilege.** Use separate credentials/scopes for read, write, and deployment functions where practical.
4. **Human gates.** Keep explicit approvals for actions designated human-only by repository policy.
5. **Observability.** Persist run status, decisions, external IDs, failures, and retry count.
6. **No hidden state authority.** Durable project state belongs in GitHub/repository artifacts, not only inside n8n execution history.
7. **Fail closed.** Missing repository policy, ambiguous branch state, red CI, or unknown credentials must block destructive actions.
8. **Rate/cost controls.** Model/API calls require configured budgets and retry ceilings.

## Phased plan

### Phase 0 - Local sandbox

Deploy n8n locally/self-hosted with no production credentials. Create one read-only workflow that inventories approved repositories and reports:

- open PRs;
- CI state;
- open high-priority issues;
- last activity.

### Phase 1 - Durable run schema

Define a project-neutral execution record:

- run ID;
- repository;
- trigger;
- observed state;
- chosen action;
- policy basis;
- external action IDs;
- result;
- retry/error root cause.

Keep a sanitized summary in GitHub or another durable project-owned log where appropriate.

### Phase 2 - Notification and triage

Allow n8n to classify/report but not mutate code:

- failed CI notification;
- stale PR detection;
- priority issue surfacing;
- scheduled project summaries.

### Phase 3 - Controlled write actions

Add narrow writes only after read workflows are stable:

- issue/comment creation;
- labels/status updates;
- approved agent invocation;
- branch/PR creation through repository tooling.

Each write must be independently idempotent and auditable.

### Phase 4 - Merge automation

Only enable merge automation for repositories whose policy explicitly allows it, and only when:

- all required checks are green;
- mergeability is known and clean;
- required review/approval rules are satisfied;
- the head SHA has not changed since verification;
- no unresolved blocking review exists.

### Phase 5 - Cross-project operating dashboard

Aggregate non-sensitive status for all active repos: roadmap item, current PR, failures, last successful cycle, and next intended action.

## Secrets and deployment

- Never store credentials in workflow JSON committed to public repositories.
- Use n8n credential storage/environment secret injection.
- Keep GitHub tokens least-privileged and rotateable.
- Use local/private networking for Ollama and internal services.
- Export workflow definitions only after secret scrubbing.
- Back up n8n configuration separately from project source.

## Acceptance criteria

Adopt n8n as the cross-project orchestrator only if:

- workflows can be reproduced from versioned definitions;
- no project requires n8n to run its normal product tests/build;
- failures are visible and recoverable;
- duplicate/destructive actions are prevented;
- credentials remain out of public repositories;
- repository policy gates remain authoritative;
- n8n can be replaced later by another orchestrator without rewriting project domain logic.

## Non-goals

- embedding n8n in customer-facing products by default;
- making n8n the source of truth for roadmaps/issues;
- placing scientific reasoning, game simulation, or arrangement-generation logic inside workflow nodes;
- bypassing GitHub CI/review gates;
- using browser automation to evade platform safeguards;
- centralizing unrestricted secrets in one workflow.

## Rollback

Every orchestrated action must also be invocable through repository-native CLI/API/manual paths. Disabling n8n should stop automation but not prevent project development, testing, builds, or releases.

## Agent rule

Agents modifying orchestration must preserve repo-level policy, idempotency, audit logs, least privilege, and license boundaries. Convenience is never sufficient justification for moving domain logic out of a repository into n8n.
