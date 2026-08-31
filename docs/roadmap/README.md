# Knowledge Engine Roadmap Navigation

This directory contains the future-facing roadmap and vision documents that
complement the canonical active roadmap at `docs/roadmap.md`.

Start here:

- `../roadmap.md` — canonical active roadmap and current project path.
- `long_term_vision.md` — finished-product and multi-package vision.
- `evolving_vision_principles.md` — standing principles for continued evolution.
- `progressive_answer_pipeline.md` — adopted product requirement for a single
  live answer that matures `Draft -> Sourced -> Verified -> Deep` while keeping
  time-to-first-useful-answer low.
- `research_report_v1.md` — adopted cross-repository product acceptance contract:
  the final research answer must match or exceed strong scholarly-assistant
  readability while materially exceeding it in provenance, contradiction
  handling, evidence boundaries, missing-evidence disclosure, and auditability.

The progressive-answer pipeline and Research Report v1 are cross-repository
requirements spanning `knowledge-engine-web`, `knowledge-engine-ai`, and
`knowledge-engine-core`. Future roadmap work touching Ask, Research Sessions,
synthesis, verification, evidence extraction, streaming, caching, scheduling,
or answer presentation should explicitly check both documents rather than
rediscovering the requirements from conversation history.

Until Research Report v1 passes its Monster Energy / one-year blood-pressure
golden acceptance case end to end, non-blocking backend abstractions and
purely decorative UI work should not outrank work required to produce the
clear, source-grounded two-layer research report defined there.

Agents should also follow `../agent-development-policy.md` and the repository
root `AGENTS.md` entry point.
