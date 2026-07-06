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

Ingestion, parsing, indexing, and future analysis should be reproducible. A
contributor should be able to rebuild a local collection and understand what
inputs produced which outputs.

## Transparency

The system should expose sources, assumptions, limitations, and uncertainty.
Future AI or ranking layers must not hide how evidence was selected or weighted.

## Testability

Core behavior should be testable offline. Each module should have clear inputs
and outputs so contributors can safely change one part of the system.

## Human Readable Code

Readable code is a project asset. Prefer direct, typed, well-named code over
clever abstractions. Optimize only when there is evidence that optimization is
needed.

## Modular Architecture

Parsing, persistence, search, metadata enrichment, graph modeling, and future AI
systems should remain separable. Modules should be replaceable without requiring
the entire project to be rewritten.

## Backwards Compatibility When Practical

Stable file formats, CLI behavior, database schemas, and APIs should avoid
unnecessary breakage. When breaking changes are necessary, document them clearly
and provide migration guidance where possible.

## Documentation Before Optimization

If a behavior is important enough to depend on, it is important enough to
document. Documentation should explain both how the system works and why major
decisions were made.

## No Hidden Algorithms

Ranking, confidence, extraction, enrichment, and future reasoning behavior should
be inspectable. Hidden scoring systems are incompatible with scientific trust.

## Evidence Over Opinion

The project should distinguish evidence, interpretation, and speculation. Future
features should show support, disagreement, uncertainty, and source links rather
than presenting conclusions as unquestionable truth.

## Human Oversight

The Knowledge Engine should augment human research, not replace human judgment.
Humans remain responsible for interpreting evidence and making decisions.
