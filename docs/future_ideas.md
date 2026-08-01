# Future Ideas

This document captures promising ideas without disrupting the current roadmap.
Items here are not commitments. They are a place to preserve imagination until
the project is ready to evaluate, design, prioritize, or reject them.

The purpose of the Knowledge Engine is not to replace scientists. It is to help
humanity discover, connect, verify, and build upon scientific knowledge faster
than ever before, while making every conclusion transparent and reproducible.

## AI

- Evidence-grounded paper summaries with source-linked claims.
- Claim extraction with confidence, limitations, and source text spans.
- Contradiction detection across papers.
- Hypothesis generation from cross-disciplinary patterns.
- Research assistant workflows that show uncertainty and citations by default.
- Local-first AI models for privacy-sensitive research collections.
- **Semantic-similarity relationship-candidate surfacing.** M56/M59 exhausted
  `ke graph-relationship-candidates`'s 2+-shared-concept tier by hand; the
  remaining ~300 pairs mostly share one weak concept (e.g. `placebo`, which
  matches almost any RCT) and aren't a useful triage signal anymore. M32/M39's
  existing embedding infrastructure could rank candidate pairs by actual
  `result_summary`/`outcome` text similarity instead -- still surfacing
  candidates only, never inferring or authoring a relationship itself, just a
  better ranking so a human reviewer's limited time goes to the pairs most
  likely to actually be worth reading first.
- Search/answer results optionally sorted or annotated by Evidence Quality
  (M58) as a secondary signal, never conflated with lexical/semantic
  relevance -- "show me the highest-quality evidence matching this query,"
  not "assume the top-quality result is the right answer."

## Database

- PostgreSQL backend for larger corpora and concurrent users.
- Migration strategy for long-lived local databases.
- Field-level provenance for parsed and enriched metadata.
- Versioned records for papers, metadata, claims, and extracted text.
- Import manifests, corpus manifests, and reproducible ingestion snapshots.
- Storage adapters for local disk, object storage, and institutional archives.

## UX

- Web interface for browsing corpora and import reports.
- Search result pages that separate exact keyword matches, metadata matches, and
  future semantic matches.
- Paper detail view with extracted metadata, raw text, provenance, and parser
  diagnostics.
- Corpus health dashboard showing failures, duplicates, missing metadata, and
  license status. **Partially addressed by M58's Evidence Intelligence** --
  a corpus-wide version of it (a `/intelligence` page or report showing the
  distribution of Evidence Quality scores, and how many claims sit at each
  Claim Confidence reliability tier) would extend this to the graph/evidence
  side specifically, and doubles as a good demo page.
- Contributor-friendly setup wizard for local installations.
- Research workflow views for reading lists, evidence maps, and open questions.
- A real, live confidence-gauge visual (SVG/CSS) on `knowledge-engine-web`'s
  claim detail pages, replacing the current plain table row now that M58/M1
  compute real Evidence Quality/Consensus/Claim Confidence numbers -- the
  gauge from the `roadmap` page's concept-preview mockup, but wired to
  actual data instead of illustrative content.
- A "what changed" report between two points in time (new claims, new
  relationship edges, Evidence Quality/Coverage deltas) -- a natural
  addition to the existing Reports page, and a good recurring status view
  as the corpus keeps growing.

## Reviewer Tooling (batch review throughput)

The project's two biggest real backlogs are both one-record-at-a-time
today: ~148 of 155 claims still have zero relationship edges (M56/M59
authored 7, by hand, reading full text each time), and 122 of 155
evidence records are still automated (M52) and unreviewed. Neither
backlog should ever be closed by weakening review -- every relationship
and every "reviewed" flag must still trace to a human actually reading
the source. The lever available is making each individual review faster
and batching the *mechanical* assembly work, never the judgment itself.

- **Relationship-candidate review worksheet.** A command that, for a
  batch of N candidate pairs (from `ke graph-relationship-candidates`),
  assembles one document with both claims' full PICO fields,
  `result_summary`, and `short_source_excerpt` side by side -- the exact
  assembly work I do by hand today, reading each record's JSON
  separately before deciding. Doesn't change what has to be read, just
  removes the busywork of gathering it, so a review session can get
  through more pairs in the same amount of time.
- **Semantic-similarity candidate ranking** (cross-referenced from the
  AI section above) -- since the 2+-shared-concept tier is exhausted and
  the remaining ~300 pairs are mostly weak single-concept overlaps,
  ranking them by actual embedding similarity of `result_summary`/
  `outcome` text would let a batch worksheet surface the most
  likely-to-be-real pairs first, instead of reading low-value pairs
  (two trials that share only `placebo`) before high-value ones.
- **Automated-evidence-record review queue.** A report or web page
  listing the 122 `m52-evidence-classification-v1` records, prioritized
  by real signal (already touching a relationship edge; high
  study-design tier but still unreviewed) so review effort goes to the
  records that most affect Evidence Quality/Claim Confidence scores
  first, rather than an arbitrary or alphabetical order.
- **Side-by-side web compare page** (`GET /relationship-candidates/{a}/{b}`)
  -- the same worksheet idea as a browsable page instead of a generated
  document, for reviewing from the browser rather than the CLI.

## Scientific Methods

- ~~Explicit evidence quality scoring models.~~ **Built, M57/M58** --
  `docs/evidence_intelligence_design.md`, `knowledge_engine/evidence_intelligence.py`.
- Study design classification.
- Methods, results, limitations, and population extraction.
- Reproducibility indicators and replication tracking.
- Citation context analysis.
- Distinguish claims, observations, interpretations, and speculation.
- Track unknowns, unresolved contradictions, and missing experiments.

## Infrastructure

- GitHub Actions matrix across operating systems and supported Python versions.
- Benchmark suite for ingestion, parsing, search, and database operations.
- Background workers for large corpus ingestion.
- Plugin architecture for parsers, metadata providers, and storage backends.
- Observability for import runs, parser failures, and enrichment calls.
- Release automation for changelogs, tags, and package publishing.

## Community

- Good-first-issue backlog for contributors.
- Public corpus contribution guidelines.
- Scientific advisory process for domain-specific corpora.
- Documentation for non-programmer researchers.
- Contributor recognition and project governance model.
- Templates for reporting parser failures, metadata issues, and licensing
  concerns.

## Long-Term Vision

- Open scientific knowledge graph with traceable evidence.
- Cross-disciplinary discovery engine.
- Transparent scientific reasoning system that shows sources and uncertainty.
- Educational interface for students, researchers, clinicians, and the public.
- Federated knowledge repositories maintained by universities, labs, and public
  institutions.
- A durable open-source ecosystem: core, AI, web, API, graph, agents, and models.
