# Project Principles

Knowledge Engine Core is the foundation of a long-term open scientific knowledge
platform. These principles should guide technical decisions, community norms, and
future architecture.

## Ten-Year Maintainability

We are not optimizing for getting code written quickly. We are optimizing for the
project still being healthy in 10 years.

This means stable interfaces are usually better than quick hacks, documentation
belongs beside implementation, architecture should be thoughtful without becoming
prematurely abstract, and progress should happen through careful incremental
evolution.

## Science First

The project exists to improve access to scientific knowledge. Product decisions
should serve evidence, source traceability, and scientific usefulness before
novelty or convenience.

## Open Source

Core infrastructure should remain inspectable, auditable, and reusable. Public
trust depends on people being able to read the code and understand how results
are produced.

## Reproducibility

Ingestion, parsing, indexing, discovery, and future analysis should be
reproducible. A contributor should be able to rebuild a local collection and
understand what inputs produced which outputs. Federated scholarly search must
record which providers were requested, which actually completed, which degraded
or failed, and what query/filters produced the candidates.

## Transparency

The system should expose sources, assumptions, limitations, uncertainty, and
operational coverage. Future AI or ranking layers must not hide how evidence was
selected or weighted. A partial provider search must never be presented as if it
were complete.

## Testability

Core behavior should be testable offline. Each module should have clear inputs
and outputs so contributors can safely change one part of the system. Networked
provider adapters must have deterministic fixtures and keep live integration
tests separate from the offline suite.

## Human Readable Code

Readable code is a project asset. Prefer direct, typed, well-named code over
clever abstractions. Optimize only when there is evidence that optimization is
needed.

## Modular Architecture

Parsing, persistence, search, scholarly-provider discovery, metadata enrichment,
graph modeling, and AI systems should remain separable. Modules should be
replaceable without requiring the entire project to be rewritten. MCP, web UIs,
LLM harnesses, and individual scholarly APIs are interfaces or providers, not
architectural owners of Knowledge Engine.

## Backwards Compatibility When Practical

Stable file formats, CLI behavior, database schemas, and APIs should avoid
unnecessary breakage. When breaking changes are necessary, document them clearly
and provide migration guidance where possible.

## Documentation Before Optimization

If a behavior is important enough to depend on, it is important enough to
document. Documentation should explain both how the system works and why major
decisions were made.

## No Hidden Algorithms

Ranking, confidence, extraction, enrichment, discovery coverage, and future
reasoning behavior should be inspectable. Hidden scoring systems are incompatible
with scientific trust.

## Evidence Over Opinion

The project should distinguish evidence, interpretation, speculation, and
provider-reported metadata. Future features should show support, disagreement,
uncertainty, and source links rather than presenting conclusions as
unquestionable truth. Citation count, provider-generated summaries, reputation,
or popularity are never substitutes for evidence quality.

## Human Oversight

The Knowledge Engine should augment human research, not replace human judgment.
Humans remain responsible for interpreting evidence and making decisions.

## Learn Aggressively Without Losing the Project

Knowledge Engine should continuously study useful external repositories,
standards, research systems, and engineering patterns. The objective is not to
accumulate dependencies. The objective is to identify real leverage, understand
why it works, and translate it into a Knowledge Engine-native contract when it
improves our system.

For every external system considered:

1. inventory what it actually does;
2. separate capabilities we already own from genuinely new value;
3. inspect security, privacy, telemetry, licensing, maintenance, and runtime
   assumptions;
4. preserve only ideas or code that strengthen our stated mission;
5. redesign those ideas around our provenance, reproducibility, and trust
   boundaries;
6. reject convenience features that create hidden coupling or weaken scientific
   integrity;
7. document what was adopted, what was rejected, and why;
8. add measurable tests or roadmap milestones before calling the idea integrated.

External projects are comparative references and potential implementation donors,
not sources of project identity or scientific policy.

## Local-First Privacy and Minimum Necessary Egress

Research questions, unpublished material, local source files, credentials, and
research history are sensitive by default. Network access should be explicit and
bounded to the provider operation being performed. Optional provider keys belong
in secret-management/environment boundaries, not evidence records, prompts,
receipts, or logs.

Third-party analytics and telemetry are not scientific functionality. Knowledge
Engine will not silently transmit research activity, agent/harness fingerprints,
tool sequences, persistent analytics identifiers, or environment details merely
because an upstream tool does so. Any future project telemetry must be explicit,
off by default, inspectable, and unnecessary for core behavior.

## Graceful Degradation Must Be Honest

A resilient system may continue when one optional provider or model is
unavailable, but it must never hide the loss of capability. `success`,
`degraded`, `partial`, `unavailable`, `rate_limited`, and `disabled` are different
states and should remain distinguishable wherever they affect scientific
coverage or user trust.

The system should preserve useful deterministic results when optional AI or
network capabilities fail, while exposing exactly what could not be completed.

## Provenance Survives Normalization

Normalization exists to make information interoperable, not to erase where it
came from. When multiple scholarly providers describe the same work, Knowledge
Engine may establish a canonical identity while retaining every provider
observation, identifier, timestamp, and material disagreement. A search index,
LLM summary, normalized object, or third-party API response is never allowed to
replace the historical evidence needed to reconstruct how the system reached a
result.

## The Vision Is a Direction, Not a Finish Line

A complete release is a milestone, not a terminal state. Scientific knowledge,
software capabilities, research methods, standards, models, and user needs will
continue to change. The project should therefore maintain two simultaneous
horizons:

- a concrete buildable roadmap with explicit exit criteria; and
- an open-ended improvement horizon that repeatedly asks what became possible,
  what remains weak, what assumptions have expired, and what can now be made
  more accurate, reproducible, secure, useful, or scalable.

New ideas should not destabilize current work merely because they are exciting.
They should enter through documented evaluation, measured value, and deliberate
sequencing. Continuous evolution is a standing requirement; uncontrolled scope
expansion is not.
