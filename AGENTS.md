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

The progressive-answer requirement is not optional UX polish. Any work touching
Ask, Research Sessions, Web/AI/Core orchestration, answer streaming/versioning,
release gates, scheduling, caching, or latency must preserve that direction.

Repository state, CI, and the source-of-truth ordering in
`docs/agent-development-policy.md` still govern implementation decisions. Do not
invent behavior that conflicts with current verified code or higher-authority
roadmap decisions.
