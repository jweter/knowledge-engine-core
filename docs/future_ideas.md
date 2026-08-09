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
- **Semantic-similarity relationship-candidate surfacing (built, M61).** M56/M59 exhausted
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
  license status. The graph/evidence half is now built as
  `knowledge-engine-web`'s `/dashboard`; ingestion/license health remains a
  separate future operator view.
- Contributor-friendly setup wizard for local installations.
- Research workflow views for reading lists, evidence maps, and open questions.
- **Live confidence-gauge visual (built).** `knowledge-engine-web`'s
  claim detail pages now render the M58/M1 Evidence Quality/Consensus/Claim
  Confidence values as real data rather than the roadmap preview's
  illustrative content.
- **"What changed" report (built).** Compares two points in time (new claims, new
  relationship edges, Evidence Quality/Coverage deltas) -- a natural
  addition to the existing Reports page, and a good recurring status view
  as the corpus keeps growing.

## Reviewer Tooling (batch review throughput)

This section originally described two one-record-at-a-time backlogs using
counts that are no longer current. The relationship graph has since grown to
20 conservatively authored edges, while M69 and its bounded cross-page
follow-up grounding-verified 108 of the 118-record automated backlog and left
10 records untouched rather than forcing unsupported fields. The original
manual-review premise is **superseded by `docs/roadmap/long_term_vision.md`'s
"Decision: automated evidence review at scale (M69)":** this section
previously said neither backlog should ever be closed by "weakening
review," meaning every record had to trace to a human actually reading
the source. The project owner has since decided that does not scale to
this project's real corpus-growth plans and will not be the review
mechanism going forward -- see that decision for the full reasoning and
replacement mechanism (grounding-verified LLM extraction). The items
below that assumed a human reviewer as the bottleneck to make faster are
kept for their still-useful mechanical ideas (batching, ranking,
surfacing), but the backlog itself is now expected to close primarily
through M69's automated pipeline, not through faster human review
sessions.

- **Relationship-candidate review worksheet (built, M60).** A command that, for a
  batch of N candidate pairs (from `ke graph-relationship-candidates`),
  assembles one document with both claims' full PICO fields,
  `result_summary`, and `short_source_excerpt` side by side -- the exact
  assembly work I do by hand today, reading each record's JSON
  separately before deciding. Doesn't change what has to be read, just
  removes the busywork of gathering it, so a review session can get
  through more pairs in the same amount of time.
- **Semantic-similarity candidate ranking (built, M61)** (cross-referenced from the
  AI section above) -- since the 2+-shared-concept tier is exhausted and
  the remaining ~300 pairs are mostly weak single-concept overlaps,
  ranking them by actual embedding similarity of `result_summary`/
  `outcome` text would let a batch worksheet surface the most
  likely-to-be-real pairs first, instead of reading low-value pairs
  (two trials that share only `placebo`) before high-value ones.
- **Automated-evidence-record review queue (built, M62; superseded as
  the primary scaling mechanism by M69).** The original report listed 122
  `m52-evidence-classification-v1` records, prioritized
  by real signal (already touching a relationship edge; high
  study-design tier but still unreviewed) so review effort goes to the
  records that most affect Evidence Quality/Claim Confidence scores
  first, rather than an arbitrary or alphabetical order.
- **Side-by-side web compare page (built).** `knowledge-engine-web`'s
  `GET /relationship-candidates/{a}/{b}`, the same worksheet fields as a
  browsable page instead of a generated document.

## Scientific Methods

- ~~Explicit evidence quality scoring models.~~ **Built, M57/M58** --
  `docs/evidence_intelligence_design.md`, `knowledge_engine/evidence_intelligence.py`.
- Study design classification.
- **Cross-field methodology linking via MeSH Publication Types.** The
  graph already resolves each Evidence Record's PICO fields against
  MeSH (M43) and links claims to `graph_concepts` nodes -- that's how a
  drug/disease concept gets shared across corpora today. MeSH also
  maintains a separate, standardized branch for study design and
  methodology (Publication Types like "Randomized Controlled Trial,"
  "Meta-Analysis," "Network Meta-Analysis," "Double-Blind Method,"
  "Case-Control Studies"). Mapping each record's `study_type` onto that
  existing controlled vocabulary, instead of the free-text field it is
  today, would let the same concept-linking mechanism show which
  evidence records across *different* corpora/fields share a
  methodology -- e.g. "these 30 records across oncology, mental-health,
  and GLP-1 all use Network Meta-Analysis." That's a real link, not a
  new invention: it reuses the same MeSH-lookup infrastructure and
  `graph_concepts`/`graph_claim_concepts` tables that drug/disease
  linking already uses, just pointed at a different MeSH branch. It
  would also incidentally fix the `study_type` vocabulary fragmentation
  found live in 2026-08-09's corpus review (`meta_analysis` vs
  `systematic_review_meta_analysis` as separate, unreconciled string
  values from different extraction tiers) by giving `study_type` a real
  controlled vocabulary to normalize against.
  Caveat: MeSH's methodology vocabulary is coarse -- it would surface
  broad commonality (RCT design, meta-analysis, propensity-score
  matching) well, but not finer-grained technique-level transferability
  (e.g. a specific composite-endpoint construction method used in one
  field that another field's studies never try). That finer signal
  would need a second, more bespoke pass extracting specific
  statistical/methodological techniques as their own concept type, not
  just MeSH's coarser Publication Type tags -- more invention, but
  where the actual "this underused method would work here too" insight
  lives. Not scoped as a milestone yet -- noted here per the project
  owner's explicit "keep it as a noted idea for now, don't forget it."
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
