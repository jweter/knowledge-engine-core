# Roadmap

This file is the roadmap index. Phase-specific notes live in `docs/roadmap/`.

These phases describe the near-term, buildable work inside
`knowledge-engine-core` itself. `docs/roadmap/long_term_vision.md` describes
the larger, multi-package ecosystem this roadmap builds toward -- including
the future `knowledge-engine-ai` layer that will eventually consume the
Evidence Records (Phase 2) and Knowledge Graph (Phase 4) this roadmap
produces. Each phase below stays deliberately scoped to what `core` alone
should own; anything that requires judgment about what evidence means, not
just locating and validating it, is out of scope here by design -- see the
long-term vision doc for where that responsibility lives instead.

## Phase 0: Local Source Vault

- Import PDFs.
- Extract text and best-effort metadata.
- Store papers, authors, journals, keywords, and full text.
- Search with SQLite FTS5.
- Run fully offline.
- Establish open-source project hygiene, governance files, issue templates, and
  automated quality checks.

"Run fully offline" and "local source vault" describe `core`'s own engineering
properties, not the shape of the finished product -- see
`docs/roadmap/long_term_vision.md`'s "The Finished Product Is Not an Offline
PDF Archive" section.

## Phase 1: Focused Scientific Corpus

- Choose one domain, such as obesity and metabolic disease.
- Import 500 to 1,000 legally available papers through bounded rehearsals.
- Improve metadata extraction with Crossref or PubMed adapters.
- Add citation metadata.
- Add deduplication reports and import manifests.
- Define legal corpus inclusion rules and source provenance requirements.
- Add a repeatable corpus ingestion workflow.
- Use `docs/phase1_design.md` as the detailed design reference.

The current GLP-1 vertical slice is a retrieval and manual evidence-display
prototype. See `docs/vertical_slice.md` and
`docs/glp1_vertical_slice_demo_checklist.md`. Those files record historical
prototype work and do not impose a current manual-review prerequisite.

### Working-version review policy

Repository execution must not depend on the project owner manually reviewing
individual candidates, PDFs, metadata rows, licenses, duplicate decisions, or
manifest fields before a working version exists. Deterministic automation must
accept, reject, hold, retry, or exclude each record with preserved evidence.
Held records are automatically deferred from acquisition and do not block the
remaining accepted batch. Human evaluation is reserved for working-version
acceptance, release validation, and optional post-release quality audits.

### Completed Phase 1 milestones

- **M6** defined the Phase 1 corpus-ingestion architecture.
- **M7** implemented versioned manifest validation and local-file readiness checks.
- **M8** added durable import-run, item, issue, and manifest-snapshot persistence.
- **M9** connected validated local PDFs to persisted import runs and atomic
  paper/FTS persistence while preserving item-level continuation.
- **M10** added duplicate evidence decisions, linked resume/retry behavior, and
  explicit execution/review status semantics.
- **M11** added provenance-preserving metadata preview and Crossref enrichment
  boundaries without silently overwriting canonical data.
- **M12** completed the controlled 100-paper rehearsal and sanitized reporting.
- **M13** assessed scale readiness and conditionally authorized one controlled
  500-paper rehearsal with explicit measurement and stop conditions.
- **Pre-M14 maintenance** reconciled repository state, made Ruff the authoritative
  quality tool, and hardened fresh and linked ingestion error boundaries.
- **M14** migrated PMC OA discovery and acquisition to NCBI's Cloud Service ahead
  of the August 2026 FTP/`oa.fcgi` removal, fixed a license-adjudication defect
  that had been silently accepting restricted `CC BY-NC`/`-ND`/`-SA` variants,
  and completed the controlled 500-paper rehearsal (issue #21) with a `PROCEED`
  decision: a fresh import and a linked resume against the same manifest
  snapshot both reconciled exactly, with zero failures, zero issues, and a fully
  idempotent resume. See `docs/m14_500_paper_rehearsal_report.md`.
- **M34** added Europe PMC as a second automated discovery source, alongside
  M14's PubMed/PMC pipeline -- `ke europepmc-candidate-discover` and
  `ke europepmc-candidate-review-prepare`, with their own adjudication engine
  (`europepmc_candidate_review.py`, `EUROPEPMC_ADJUDICATION_RULES_VERSION`)
  since identity and full-text evidence work differently for Europe PMC than
  for PMC. Scoped to discovery and adjudication only -- **not** wired into
  acquisition, and does not resume corpus growth: the corpus remains
  intentionally frozen at 605 papers by the project owner's prior decision
  (see "Scaling beyond 500 papers for Phase 2 tuning" below). See
  `docs/m34_europepmc_discovery.md`.
- **M35** added CORE as a third automated discovery source -- `ke
  core-candidate-discover` and `ke core-candidate-review-prepare`, with
  their own adjudication engine (`core_candidate_review.py`,
  `CORE_ADJUDICATION_RULES_VERSION`). CORE's API never returns a license
  field (verified empirically), so every CORE candidate's license rule is
  `incomplete_missing_license` and no CORE candidate can ever auto-accept --
  a deliberate, honest consequence documented in `docs/m35_core_discovery.md`,
  not a bug. Scoped to discovery and adjudication only -- **not** wired into
  acquisition, and does not resume corpus growth: the corpus remains
  intentionally frozen at 605 papers by the project owner's prior decision.
- **M36** added Unpaywall as a fourth evidence source, but as a per-DOI
  OA-location/license *lookup tool* rather than a fifth discovery pipeline
  -- `ke unpaywall-doi-lookup` and `ke unpaywall-batch-lookup`. Unpaywall's
  topic-search API was confirmed broken (`HTTP 500` on every query tried)
  at build time, so there is no reliable endpoint to build a `--query`
  discovery command against; its working per-DOI endpoint also carries no
  scientific-scope signal and no single canonical host to allowlist. Makes
  no accept/reject/hold decision -- pure evidence for a human reviewing a
  DOI already surfaced by another pipeline. See
  `docs/m36_unpaywall_lookup.md`.

### M14: Controlled 500-paper rehearsal

M14 is one controlled 500-paper rehearsal under the M13 entry, measurement, stop,
reconciliation, resume, and artifact-hygiene conditions. Issue #21 is the
authoritative rehearsal tracker; it completed with a `PROCEED` decision (see
`docs/m14_500_paper_rehearsal_report.md`). Persistence failure classification in
issue #22 must be complete before repeated large-run failure evidence is treated
as diagnostic. The rehearsal must not introduce new architecture solely to
collect one run's measurements.

The M14 corpus scope is **Obesity and Metabolic-Disease Therapeutics**. The
original GLP-1 weight-loss question remains the first named subtopic, but the
rehearsal may include legally reusable treatment evidence for overweight, type 2
diabetes, metabolic syndrome, metformin, SGLT2 inhibitors, dual incretin
therapies, and other explicitly allowlisted interventions within this same
Phase 1 domain. Scope expansion must never weaken license, provenance,
identifier, duplicate, or full-text validation.

M14 proceeds through explicit stages:

1. bounded PubMed/PMC candidate discovery within the committed obesity and
   metabolic-disease therapeutics scope;
2. deterministic, evidence-preserving candidate adjudication for scientific scope,
   identifier consistency, reusable-license basis, approved full-text location, and
   duplicate risk;
3. explicit `accepted`, `rejected`, or `held` decision records that remain separate
   from raw discovery output; held records are automatically deferred and discovery
   continues without waiting for manual resolution;
4. bounded acquisition of accepted files with sanitized receipts;
5. reconciliation to exactly 500 accepted rows and matching approved local PDFs;
6. preflight validation, fresh import, linked resume, and sanitized evidence.

Automated acceptance or rejection is permitted only when repository-defined rules
produce complete, non-conflicting evidence. Every decision must record reason codes,
provider provenance, the adjudication-rules version, and the evidence used. A record
must be held rather than guessed when identity, licensing, scientific relevance,
full-text eligibility, or duplicate status remains ambiguous. Discovery providers
must remain separate evidence categories; metadata from PubMed, PMC, Crossref,
OpenAlex, Europe PMC, or publishers must not be silently collapsed into one trust
category. Held and rejected records never authorize acquisition and never require
owner intervention before the working-version acceptance review.

If one query or subtopic cannot supply enough accepted records, discovery may
continue through measured query revisions inside the committed M14 domain. Each
revision must preserve its query, offset, rules version, decision counts, and
provider provenance. Unrelated scientific domains require a separate roadmap
amendment rather than silent corpus mixing.

### M34: Europe PMC, a second discovery source

The project owner asked for more automated discovery sources and pipelines
beyond M14's PubMed/PMC-only pipeline. M34 adds Europe PMC as the second one
-- see `docs/m34_europepmc_discovery.md` for the full design, and
`knowledge_engine/europepmc_discovery.py` /
`knowledge_engine/europepmc_candidate_review.py` for the implementation.
Deliberately scoped to what Europe PMC adds beyond PMC: for records already
in PMC, Europe PMC's own "PDF" is just a rendered view of the exact same PMC
content M14 already acquires via NCBI's official S3 bucket, so those
candidates are still discovered (never silently dropped) but explicitly
rejected as out of this pipeline's scope
(`DUPLICATE_OF_PMC_PIPELINE_SCOPE`), rather than duplicating M14's own
pipeline through a less-official endpoint. Scientific-scope and license
rules are shared with M14's engine (`scientific_scope.py`,
`license_rules.py`) so the same corpus-inclusion criteria apply regardless
of which pipeline found a candidate.

**Not yet wired into acquisition, and does not resume corpus growth.** The
corpus remains intentionally frozen at 605 papers by the project owner's
prior decision (see "Scaling beyond 500 papers for Phase 2 tuning" below).
M34 only builds the discovery/adjudication capability; using it to actually
grow the corpus further is a separate decision for the project owner to
make explicitly, the same way M13/M14's own scale-up was.

### M35: CORE, a third discovery source

The project owner asked to keep adding automated discovery sources without
pausing for permission at each step. M35 adds CORE
(https://core.ac.uk) as the third one -- see `docs/m35_core_discovery.md`
for the full design, and `knowledge_engine/core_discovery.py` /
`knowledge_engine/core_candidate_review.py` for the implementation. CORE
aggregates open-access content broadly (not just biomedical literature),
using offset-based pagination and an optional API key
(`KE_CORE_API_KEY`) that raises its otherwise low unauthenticated rate
limit. Critically, CORE's API never returns a license field at all
(verified empirically by enumerating every key in a real response), so
`core_candidate_review.py`'s license rule is always
`incomplete_missing_license` and no CORE candidate can ever auto-accept --
every candidate that clears every other rule still lands in `held`,
pending a human visiting the original source to confirm reuse terms. PMC/
Europe PMC overlap detection is a known, deliberate limitation for this
milestone (CORE never reports a PMCID); see `docs/m35_core_discovery.md`.
Scientific-scope and license rules are shared with M14 and M34's engines
so the same corpus-inclusion criteria apply regardless of which pipeline
found a candidate.

**Not yet wired into acquisition, and does not resume corpus growth.** The
corpus remains intentionally frozen at 605 papers by the project owner's
prior decision (see "Scaling beyond 500 papers for Phase 2 tuning" below).
M35 only builds the discovery/adjudication capability; using it to actually
grow the corpus further is a separate decision for the project owner to
make explicitly, the same way M13/M14's own scale-up was.

### M36: Unpaywall, an evidence lookup tool rather than a fourth discovery pipeline

The project owner asked to keep adding evidence sources, naming Unpaywall
explicitly, without pausing for permission at each step. Unlike M14/M34/M35,
M36 does not add a `--query` discovery pipeline: Unpaywall's `/v2/search`
endpoint returned a consistent `HTTP 500` across multiple distinct queries
and retries at build time (confirmed empirically, not assumed), and its
working per-DOI endpoint carries no scientific-scope signal and no single
canonical host to allowlist the way CORE and Europe PMC do. See
`docs/m36_unpaywall_lookup.md` for the full design, and
`knowledge_engine/unpaywall_lookup.py` for the implementation.

Instead, M36 adds `ke unpaywall-doi-lookup` and `ke unpaywall-batch-lookup`:
given one or more DOIs already surfaced by another pipeline (e.g. a `held`
Europe PMC or CORE candidate), it queries Unpaywall's per-DOI endpoint and
reports OA status, best OA location, license (normalized from Unpaywall's
own `cc-by`-style tokens and evaluated via the shared `license_rules.py`),
and every OA location on file. It makes **no** accept/reject/hold decision
-- that stays the responsibility of whichever pipeline's held candidate
this evidence is being used to re-examine. Requires `KE_UNPAYWALL_EMAIL`
(Unpaywall's usage policy requires a contact email on every request; this
project does not bake in a default for every installation).

**Not wired into acquisition, and does not resume corpus growth.** The
corpus remains intentionally frozen at 605 papers by the project owner's
prior decision (see "Scaling beyond 500 papers for Phase 2 tuning" below).

### Scaling beyond 500 papers for Phase 2 tuning

Phase 2's automated extraction (M16-M25) has been built and unit-tested
against synthetic fixtures, but never run at scale against real papers --
the real corpus currently has exactly two evidence records, both
hand-authored before automated extraction existed. Tuning deterministic
extraction rules (structured-section detection, claim-candidate signals,
and the PICO/study-type/limitations extraction named in
`docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed Fields
section) needs a real corpus large enough to reveal patterns a 500-paper
sample may not; the project owner has set an initial target of at least a
couple thousand papers. Following the M12->M13->M14 precedent, this needs
its own scale-readiness assessment -- measured stop conditions and
license/provenance validation re-checked at the new scale -- before a
bounded discovery/acquisition run, not an unbounded scale-up.

M27 (issue #133) addressed the other half of this gap: nothing downloaded
survived past a session before, since this project's remote execution
environment starts from a fresh clone every session and the working
database is gitignored. `ke corpus-library-export`/`ke
corpus-library-import` make the corpus's paper-intrinsic content (not raw
PDFs -- those are archived to Google Drive instead, per the project
owner's decision) a persisted, git-committable snapshot -- see
`docs/m27_corpus_library.md`. Actually growing the corpus to the owner's
"at least a couple thousand papers" target remains ongoing operational
work using this tooling plus the existing M14 pipeline, not itself
scheduled as a numbered milestone.

### Supporting operator durability

The Google Drive backup subsystem is supporting operator infrastructure for
protecting local SQLite backup bundles during the M14-era rehearsal work. It does
not change corpus inclusion, discovery, approval, acquisition, parsing,
deduplication, provenance, or import semantics. It should remain optional,
operator-controlled, and independently documented. Any expansion beyond backup
transport and recovery support requires a dedicated roadmap decision or ADR.

Detailed milestone records include:

- `docs/m6_phase1_corpus_ingestion_plan.md`
- `docs/m7_manifest_validation_foundation.md`
- `docs/m8_import_run_persistence.md`
- `docs/m9_small_ingestion_pilot.md`
- `docs/m10_duplicate_detection_resumability_plan.md`
- `docs/m10_operational_contract.md`
- `docs/m10_release_notes.md`
- `docs/m12_100_paper_rehearsal.md`
- `docs/m13_scale_readiness_decision.md`
- `docs/m14_500_paper_rehearsal_report.md`
- `docs/audit_remediation_register.md`

## Phase 2: Evidence Records

- Extract claims, methods, results, limitations, and evidence quality markers.
- Keep every generated structure traceable to source text spans.
- Add automated validation and optional post-working-version human audit workflows.
- Use `docs/phase2_design.md` as the detailed design reference. Its first
  concrete prerequisite, page/span-level extraction provenance, is implemented
  (see `docs/technical_debt.md`). Extraction methodology was decided as
  rule-based pattern matching combined with structured-section heuristics, no
  new dependency; see the design doc's Extraction Methodology section.
- Evidence Records deliberately stop short of automated,
  research-question-relative judgment: assigning a `research_question`,
  classifying `evidence_direction` against it, and any real confidence
  *rating* (beyond the existing free-text `confidence_note` field) are left
  for a human reviewer to supply. That is not a temporary gap -- it is the
  deliberate seam where the future `knowledge-engine-ai` layer plugs in; see
  `docs/roadmap/long_term_vision.md`'s AI Interface Layer section.
- PICO fields (population, intervention, comparator, outcome),
  `study_type`, and `limitations` are a different case: paper-intrinsic
  facts, not judgment relative to a research question, so deterministic,
  non-human-typed extraction was prioritized for them rather than an
  indefinitely deferred human-review field -- see
  `docs/roadmap/long_term_vision.md`'s Minimizing Human-Typed Fields
  section. `study_type`/`limitations` shipped in M26; full PICO
  extraction shipped in M28, once the corpus described above under
  Phase 1 was large enough to tune against and the project owner decided
  605 papers was sufficient to stop growing it further.

## Phase 3: Search Plus Semantics

- Add embeddings using a pluggable vector index. (Done, M30: FAISS.)
- Support local FAISS and server-backed Qdrant. (Both implemented -- FAISS
  M30, Qdrant M33 (`QdrantVectorIndex`, not yet wired into the CLI
  commands -- no operator need for that has appeared).)
- Keep lexical search as a transparent baseline. Unchanged: `ke search`/
  `ke answer` remain FTS5-only; `ke vector-search` is a separate command.
- Use `docs/phase3_design.md` as the detailed design reference. Its
  embedding-generation decision -- a new-dependency and offline-posture
  choice for the project owner, the same way Phase 2's extraction
  methodology was decided before any extraction code was written -- is
  resolved as of M31: **both** a local (`sentence-transformers`) and an
  external-API (OpenAI) `EmbeddingGenerator` are implemented. **M30**
  implemented the retrieval side first: a pluggable `VectorIndex`
  interface, a local FAISS backend, and two CLI commands
  (`ke embedding-index-build`, `ke vector-search`) operating on
  externally-supplied vectors. **M31** added `ke embedding-generate
  --generator local|openai`, which produces the same vectors file those
  M30 commands already consume. **M32** wired `ke vector-search
  --query-text` to embed a free-text query live with either generator,
  removing the "queries must be pre-embedded" friction M30/M31
  deliberately left in place. **M33** added `QdrantVectorIndex`, the
  second `VectorIndex` implementation the roadmap named from the start,
  targeting an operator-run Qdrant server -- usable via direct Python
  import today; CLI wiring is a future step. Combining lexical
  (`ke search`/`ke answer`) and semantic (`ke vector-search`) results into
  one ranked list remains a separate, not-yet-designed question (see
  `docs/phase3_design.md`'s Open Questions).

## Phase 4: Knowledge Graph

- Model concepts, claims, citations, support, contradiction, and uncertainty.
- Add Neo4j or another graph backend behind a repository interface.
- Corresponds to `knowledge-engine-graph` in the long-term ecosystem; see
  `docs/roadmap/long_term_vision.md`.
- This is also the natural home for `docs/roadmap/long_term_vision.md`'s
  Stability Score (claim revision history) and Tracking the Unknown
  (missing experiments, weak-evidence areas, and unanswered questions as
  first-class, graph-shaped entities) -- neither has a path before the
  graph exists to hold them.

## Phase 5: Human Interface

- Add API and web repositories as separate projects.
- Provide evidence-first explanations with visible uncertainty and sources.
- This is where the future `knowledge-engine-ai`/`-web`/`-agents` layers'
  research-question crafting, evidence synthesis, and confidence rating
  (see `docs/roadmap/long_term_vision.md`) actually reach a person, on top
  of the Evidence and Knowledge Graph layers Phases 2 and 4 build.
- `docs/roadmap/long_term_vision.md`'s Discovery Engine (hypothesis
  generation, experiment suggestion) and Education Engine (adaptive
  explanations, learning paths) are not yet claimed by any phase or
  package here -- an open decision, not a silent omission.

## Release Milestones

- `v0.1.0`: Phase 0 local source vault, CLI, tests, docs, and repository hygiene.
- `v0.1.1`: Bug fixes and setup improvements.
- `v0.2.0-alpha.1`: GLP-1 retrieval and manual evidence vertical-slice prerelease.
- `v0.2.0`: Repeatable corpus ingestion, duplicate handling, resume/retry, metadata
  preview/enrichment, and bounded scale-rehearsal evidence.
- `v0.3.0`: Expanded metadata enrichment and citation capture.
- `v0.4.0`: Knowledge graph foundation.
- `v0.5.0`: Vector search.
- `v0.6.0`: Stabilize `core`'s Evidence and Knowledge Graph output as a
  consumable interface (not new reasoning logic in `core` itself) so the
  separately versioned `knowledge-engine-ai` package can begin its own
  reasoning experiments on top of it; see
  `docs/roadmap/long_term_vision.md`.
- `v0.9.0`: Feature-complete beta.
- `v1.0.0`: Stable public release.
- Post-`v1.0.0`: `docs/roadmap/long_term_vision.md`'s Discovery Metrics
  (Time to Discovery, Knowledge Coverage, Contradiction Resolution Rate,
  and related measures) become meaningful only once the Discovery and
  Decision layers they measure exist -- named here so they are not
  forgotten, not because they are actionable before then.

## Detailed Roadmaps

- `docs/phase1_design.md`
- `docs/roadmap/phase0.md`
- `docs/roadmap/phase1.md`
- `docs/roadmap/phase2.md`
- `docs/phase3_design.md` and `docs/roadmap/phase3.md` -- design sketch and
  goals; M30 (FAISS retrieval plumbing), M31 (local + OpenAI embedding
  generators), M32 (free-text `ke vector-search --query-text`), and M33
  (`QdrantVectorIndex`, not yet CLI-wired) are implemented
- `docs/roadmap/long_term_vision.md` -- the multi-package ecosystem and final
  goal these phases build toward, including the future `knowledge-engine-ai`
  layer's role once Phase 2's Evidence Records exist
