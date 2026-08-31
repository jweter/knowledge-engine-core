# Knowledge Engine Agent Entry Point

All coding and scheduled agents working in this repository must read and follow
`docs/agent-development-policy.md` before making changes.

For product direction, also read the current roadmap/vision documents relevant
to the work:

- `docs/roadmap.md` — canonical active roadmap.
- `docs/roadmap/long_term_vision.md` — finished-product and multi-repository vision.
- `docs/roadmap/evolving_vision_principles.md` — standing future-facing principles.
- `docs/roadmap/progressive_answer_pipeline.md` — adopted live-answer product
  requirement: one research run matures `Draft -> Sourced -> Verified -> Deep`,
  prioritizing an immediate useful answer while continuing evidence gathering,
  verification, and deep research as time/attention justify it.
- `docs/roadmap/research_report_v1.md` — adopted cross-repository product
  acceptance contract: the final research answer must match or exceed strong
  scholarly-assistant readability while materially exceeding it in provenance,
  contradiction handling, evidence boundaries, missing-evidence disclosure,
  and auditability.
- `docs/INDUSTRY_REALITY_CHECK.md` — current Core-specific gap analysis versus
  production scientific/research infrastructure expectations.

The progressive-answer and Research Report v1 requirements are not optional UX
polish. Any work touching Ask, Research Sessions, Web/AI/Core orchestration,
evidence extraction, answer streaming/versioning, release gates, scheduling,
caching, or latency must preserve those directions.

Until Research Report v1 passes its Monster Energy / one-year blood-pressure
golden acceptance case end to end, prefer work that directly enables the
structured, source-grounded report contract over additional non-blocking backend
abstractions. Core must continue to prefer missing data over invented metadata.

## Industry-quality baseline

`docs/INDUSTRY_REALITY_CHECK.md` is a durable quality-gap baseline. It does not
override verified current repository state, `docs/roadmap.md`, or authorized
architecture decisions. Use it when selecting, designing, reviewing, and
validating work:

- prefer roadmap-compatible work that closes a documented quality gap when
  priorities are otherwise comparable;
- do not treat passing CI alone as proof that integration, observability,
  performance, general-question research, service boundaries, or production
  readiness gaps are closed;
- when a major verified capability materially changes the assessment, update
  the reality check or explicitly record why the prior finding still applies;
- never let an old score override newer verified evidence.

Repository state, CI, and the source-of-truth ordering in
`docs/agent-development-policy.md` still govern implementation decisions. Do not
invent behavior that conflicts with current verified code or higher-authority
roadmap decisions.
