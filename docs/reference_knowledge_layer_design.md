# Reference Knowledge Layer Design (Sketch)

Status: This was a design sketch, written before any implementation --
the same role `docs/phase3_design.md` played before M30. **M41 has since
built the live-lookup path's first slice** (a live lookup against
Wikipedia's REST summary API, `ke reference-lookup` -- see
`docs/m41_reference_lookup.md`), confirming the "third option" section
below's recommendation that live lookup was the better starting point.
The stored-textbook path remains unbuilt and still needs the licensing
and storage decisions below actually made before any code assumes a
title list -- nothing here authorizes starting that path.

## Motivation

Every milestone so far has grown one thing: a corpus of primary-research
papers on one topic (GLP-1/weight loss), plus the deterministic pipeline
that extracts claims, study design, and PICO fields from them. That
pipeline -- and any future reasoning layer built on top of it (the
`knowledge-engine-ai` package `docs/roadmap/long_term_vision.md`
describes) -- reads those papers the way a domain expert does: assuming a
background of chemistry, biochemistry, microbiology, physics, pharmacology,
and lab-technique knowledge the paper itself never restates. A paper
reporting "reduced HbA1c via GLP-1 receptor agonism, assessed by ELISA"
does not explain what a GLP-1 receptor is, what agonism means
mechanistically, or what ELISA measures and how. A human domain expert
fills those gaps from years of textbook-level training; this project's
extraction pipeline and any future reasoning layer currently have no
equivalent to draw on.

A reference knowledge layer -- open-license textbooks and reference
material across the foundational sciences a biomedical paper assumes --
closes that gap. Not as evidence (a textbook chapter is not a primary
research finding and must never be treated as one), but as grounding
context: the same distinction a domain expert draws between "what this
paper found" and "what I already know going in."

## What this is not

This is not an extension of the existing paper corpus, and it does not
reuse that corpus's pipeline wholesale:

- No claim extraction, study-design classification, or PICO extraction --
  those are M16-M28's answer to "what did this primary-research paper
  find," a question that does not apply to a chemistry textbook chapter.
- No `EvidenceRecord` promotion path. A definition or mechanism
  explanation from a textbook is never itself an `EvidenceRecord`, and
  `ke extraction-review-promote`'s existing human-review gate is not
  the right tool for it either -- textbook content isn't a claim awaiting
  a research_question/evidence_direction, it's reference material with a
  different shape entirely.
- Not a replacement for, or expansion of, the 1,000-paper corpus cap
  `docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning"
  section already fixed for GitHub space reasons. That cap is about the
  primary-evidence corpus specifically; a reference layer is a separate
  concern with its own storage answer (see Open Questions).

## Candidate content

Subject to the licensing discipline below being applied per-title, not
assumed:

- **Chemistry, Biology, Microbiology, Anatomy & Physiology, Physics**:
  OpenStax publishes CC-BY 4.0 textbooks in exactly these subjects --
  the same license family this project's existing `license_rules.py`
  already recognizes and accepts for PMC papers, which is a meaningful
  head start on the adjudication logic this layer would need.
- **Organic chemistry, biochemistry**: LibreTexts hosts CC-BY and
  CC-BY-SA modules in these subjects, but licensing there is set
  per-module, not per-site -- some LibreTexts content is CC-BY-NC-SA,
  which this project's existing rules already reject for the paper
  corpus and would need to reject here too.
- **Pharmacology, lab techniques, general clinical reference**: less
  consolidated than the above. NCBI Bookshelf hosts many full-text
  books, but "free to read on NCBI" is not the same claim as "carries a
  reuse license" -- this project already draws exactly that distinction
  for PMC's open-access subset (see `docs/m14_*` license-adjudication
  history) and would need to draw it here with the same rigor, book by
  book, not as a blanket assumption.

No specific title list is authorized by this document. It names
subject areas and known open-license publishers as a starting point for
that per-title review, not a pre-approved acquisition list.

## Architecture sketch

1. **A separate manifest, not `sources.csv`.** Books have book-level
   metadata (title, subject, edition, license, publisher, source URL)
   that doesn't map onto a paper's DOI/PMCID/publication_year fields. A
   parallel `reference_sources.csv` (or equivalent) keeps the two
   corpora's provenance records distinct rather than forcing one schema
   to describe two different kinds of source.
2. **Chapter/section-level import, not whole-book blobs.** Mirroring
   M15's `paper_pages` precedent (page-level provenance so a claim can
   cite an exact span), a reference lookup should be able to cite "OpenStax
   Biochemistry, Chapter 12.3" precisely, not just "some textbook, somewhere."
3. **A separate index -- and real new persistence/search work, not a
   drop-in reuse.** Only the lowest-level pieces of M30-M39's stack are
   actually generic: `VectorIndex` (FAISS/Qdrant) and `fuse_rankings`
   (RRF) operate on arbitrary vectors and paper_id rankings with no
   paper-specific assumptions. Everything above that layer is coupled to
   `Paper`: `SearchService` joins SQLite's `paper_search` FTS table
   directly to the `papers` table; `_paper_embedding_text` reads
   `Paper.title`/`Paper.abstract`; `embedding-index-build` validates
   every vector's `paper_id` through `PaperRepository`; `fused-search`
   looks up and prints paper metadata for its results. A reference-layer
   implementation cannot just point these commands at a second index --
   it needs its own persistence and search services (a
   `ReferenceSectionRepository`-equivalent, a reference-scoped
   `SearchService` counterpart) or a generalized document abstraction
   `Paper`-specific code migrates onto, either of which is real,
   unbuilt work, not something this design gets for free. Whatever form
   it takes, it must stay a genuinely **separate** index from the
   evidence corpus's, not merged into it -- blending the two would let a
   textbook definition surface as if it were paper-derived evidence,
   exactly the epistemic distinction this whole project has been careful
   to preserve (`ke answer`'s own disclaimer: "No scientific synthesis
   has been performed").
4. **Consumers, not owners, of the content.** The near-term use is
   grounding: given a term or mechanism a paper's claim text names, look
   it up in the reference layer for context. The longer-term use is
   feeding Phase 4's Knowledge Graph concept nodes (a "GLP-1 receptor
   agonism" concept node linked to its textbook definition, distinct from
   the paper-level evidence nodes that cite it) and, eventually, the
   `knowledge-engine-ai` layer's synthesis step.

## A third option: live lookup instead of stored text

Storing full textbooks is not the only way to get this grounding. Several
free, no-storage-needed APIs cover real slices of the same background
knowledge:

- **NLM/NCBI's own APIs** (RxNorm for drug/pharmacology terminology, MeSH
  for medical-concept hierarchy, PubChem for chemical compound data) --
  free, mostly no API key required, and this project already has NCBI
  HTTP infrastructure (`ncbi_http.py`, `UrllibNcbiTransport`) a live
  lookup could extend rather than duplicate.
- **Wikipedia/Wiktionary** -- free, CC-BY-SA (a license family this
  project's `license_rules.py` already recognizes), and closer to actual
  textbook-style explanatory prose than the structured-data APIs above.
- **UniProt** -- free API for protein/biochemistry data.

This mirrors a decision this project has already made once: M31's
`EmbeddingGenerator` offers both a `local` (offline, no per-query cost)
and an `openai` (external API, network-dependent) option behind the same
interface, with the tradeoff labeled explicitly rather than picked for
the user. A live-lookup reference option would follow the same shape.

**This is not a departure from the project's direction -- it's aligned
with it.** `docs/roadmap/long_term_vision.md`'s "The Finished Product Is
Not an Offline PDF Archive" section is explicit that Phase 0's "run fully
offline" describes `core`'s own engineering property for the primary
evidence pipeline specifically -- testable, reproducible, safe to run in
isolation -- not a claim about the finished ecosystem, which that same
document calls "a live, AI-powered search and discovery engine." A
reference layer that queries live sources is a natural, forward-looking
piece of exactly that end state, not an exception to a permanent offline
mandate. Building it live-first, rather than defaulting to stored PDFs
out of habit, is arguably the more consistent choice given where this
project is headed.

The real engineering question a live-lookup reference layer raises is
narrower than "offline vs. online": it's whether anything that consumes
a live-looked-up definition needs it to be reproducible later (a term's
definition can change, or an API can go down, between two runs). Where
that matters -- e.g. if a future extraction or reasoning step cites a
looked-up definition as part of its own provenance -- the fix is
ordinary engineering (caching or snapshotting the response actually
used, the same way this project already records `embedding_model` and
rules-version fields for reproducibility elsewhere), not a reason to
avoid live lookup altogether. It also doesn't fully substitute for
stored text on its own terms: RxNorm/MeSH/PubChem return structured
facts and identifiers, not the explanatory prose or worked mechanisms an
actual textbook chapter has; Wikipedia's prose comes closer, but with
encyclopedia framing rather than textbook depth.

Not a replacement for the stored-textbook option above -- a third,
independently viable path, and likely the better starting point: it
sidesteps the storage and per-title licensing questions below entirely,
and fits the live, connected direction this project is actually building
toward.

**Built in M41** (`ke reference-lookup`, `knowledge_engine/
reference_lookup.py`), against Wikipedia specifically -- see
`docs/m41_reference_lookup.md` for what it does, why Wikipedia was
picked first over RxNorm/MeSH/PubChem/UniProt, and what remains
deliberately unbuilt (caching, extraction-pipeline integration, and the
other named sources).

## Open questions (owner decisions, not resolved here)

- **Storage and hosting** (only applies to the stored-text option above;
  live lookup sidesteps this entirely). A handful of full textbooks
  plausibly runs to hundreds of MB or more -- likely too large to live in
  this git repo the way the (already space-capped) paper corpus does.
  Candidates: a separate `knowledge-engine-reference` package/repo (the
  multi-package ecosystem `docs/roadmap/long_term_vision.md` already
  anticipates this shape of split); an external cache downloaded and
  verified at setup time rather than committed; or storing only
  extracted/chunked text rather than source PDFs. Not decided here.
- **Stored text vs. live lookup vs. both.** The two approaches answer
  different needs (deep, citable, reproducible chapters vs. broad,
  zero-storage, always-available facts) and are not mutually exclusive,
  but which one to build first is an explicit owner decision, not a
  default.
- **Exact title list and per-title license verification.** Real work,
  not a formality -- the existing PMC license-adjudication history in
  this project found real edge cases (CC-BY-NC misclassified as
  acceptable, license fields silently absent) that only surfaced from
  checking real sources rather than trusting a category label.
- **Import/extraction granularity.** Chapter, section, or paragraph --
  affects both citation precision and index size.
- **Whether this is a new phase or a cross-cutting layer.** It doesn't
  fit neatly inside Phase 2 (evidence) or Phase 4 (graph) alone; it's
  probably best framed as its own initiative that both draw on, not a
  sub-task of either.

## What this does not do (yet)

Names a direction, not a commitment. No title has been selected, no
license has been verified, no storage decision has been made, and no
code exists. The next real step is the project owner picking a first
candidate subject and title so the licensing/storage questions above can
be answered concretely instead of in the abstract.
