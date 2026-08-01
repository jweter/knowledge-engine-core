# M47 Phase 4: graph_citations

## Purpose

`docs/phase4_design.md` deliberately left `graph_citations` unpopulated,
naming citation-list parsing as "a real, separate design question with
its own real-corpus verification needed before writing any
pattern-matching code" -- the same discipline M28's PICO patterns and
M45's Codex-caught term-extraction fix already went through. M47 is that
verification pass, plus the resulting build.

## What real-corpus sampling found

Sampling real papers' reference-list text directly (not guessed from the
schema alone) surfaced real structure the original design doc's schema
sketch did not depend on, but a naive parser would have gotten wrong:

- **At least three distinct citation styles are in real use**: numbered
  with a period (`"1. Author..."`, ~87% of a 60-paper random sample),
  numbered with brackets (`"[1] Author..."`, ~5%), and unnumbered
  author-year (~7%). A parser built around only one style would silently
  mishandle the others.
- **PDF-extraction line-wrap and hyphenation noise** is common inside
  entries (e.g. `"Corticosteroid-­Induced"`, soft hyphens at
  line-wrap points), which any naive text-splitting approach would need
  to tolerate.
- **`REFERENCE_HEADING_PATTERN` (`parser.py`) can match a spurious
  earlier occurrence of "References"** before the real bibliography --
  found directly in a real paper, where "References" appears twice as a
  table column header (a mechanism-summary table) before the actual
  reference list starts. Confirmed on the full real corpus: 15/960
  papers (1.6%) have no heading match at all, and the pattern's *last*
  match is a far more reliable way to locate the real bibliography than
  its first (verified on the paper with the table-header false positive:
  the last match correctly lands on its real, numbered reference list).

## The scoping decision this measurement produced

`docs/phase4_design.md`'s own `graph_citations` schema only needs
`citing_paper_id`/`cited_paper_id` -- both real foreign keys into
`papers`, populated *only* when a reference-list entry matches a paper
**already in this corpus**, never an external DOI with no corresponding
row. That means the actual job is DOI-identity matching, not full
structured entry extraction (author/title/journal/year per style) --
and DOI matching does not require locating individual entry boundaries
at all, for any of the three styles found above. Scanning the reference
section (bounded to the *last* heading match) for DOI substrings and
intersecting against the corpus's own `papers.doi` values answers the
schema's actual question directly.

**This also measured the real payoff, not just the real risk.** Running
DOI-substring matching against the full real 960-paper corpus found
exactly **5 intra-corpus citation edges** -- verified individually (e.g.
paper 183's reference list literally contains "Two-year effects of
semaglutide in adults with overweight or obesity: the STEP 5 trial. Nat
Med. (2022) 28:2083-91. doi: 10.1038/s41591-022-02026-4", matching
another paper already in the corpus by title and DOI). Five real edges
across 960 papers does not justify building a multi-format structured
entry parser for marginal additional matches -- DOI-only matching is the
right-sized first slice for this data, named explicitly as a scoping
decision rather than left as a silent gap.

## What was built

- **`knowledge_engine/citation_extraction.py`**: `find_cited_dois(raw_text)`
  finds the *last* `REFERENCE_HEADING_PATTERN` match, then returns every
  distinct `DOI_PATTERN` match in the tail as a `CitedDoi(doi,
  raw_snippet)` (both reused unchanged from `parser.py` -- no new DOI or
  heading regex). `raw_snippet` is a bounded text window around the
  match, for `graph_citations.raw_citation_text`'s audit purpose -- not a
  parsed entry boundary, since none is needed for DOI-only matching.
- **`graph_citations` table** (schema version 9): `citing_paper_id`,
  `cited_paper_id` (both real foreign keys into `papers`, per the
  original design), `raw_citation_text`, `created_at`. `CheckConstraint`
  rejects a self-citation row; `UniqueConstraint` on
  `(citing_paper_id, cited_paper_id)` keeps the command idempotent.
- **`GraphRepository.add_citation_edge`/`citations_for_paper`**, mirroring
  the existing get-or-create/traversal pattern; `population_counts()` now
  reports `citation_edges` too.
- **`ke graph-citations-build [--output <path.json>]`**: scans every
  persisted paper's own `raw_text`, matches cited DOIs against every
  other persisted paper's `doi`, and creates an edge for each match.
  Unlike `ke graph-build`, no input file and no network access are
  involved -- it operates directly on what is already in the database.

## Live verification against the real corpus

Run against a copy of the real local 960-paper database
(`data/knowledge_engine.sqlite3`, gitignored, not committed):

```
Citation build complete: 960 paper(s) scanned, 5 citation edge(s) created.
Graph totals -- concepts: 0 {}, claims: 0, claim-concept edges: 0, relationship edges: 0, citation edges: 5.
```

All 5 edges were spot-checked against the actual paper titles and DOIs
involved and are genuine, correctly-directed citations (see the module
docstring's own worked example). `concepts`/`claims`/edges from M46 are
0 in this run because `ke graph-citations-build` only touches
`graph_citations` -- it was run standalone against a fresh copy of the
corpus database, not chained after `ke graph-build`.

## What is deliberately not built yet

- No structured per-entry parsing (author/title/journal/year extraction)
  for any of the three real citation styles found -- not justified by
  the measured 5-edge real payoff; would only become worth reconsidering
  if a real future need for citation-text content beyond simple
  DOI-identity matching appears.
- No entry-boundary detection at all -- DOI-substring matching does not
  require it, for any of the three styles measured.
- No matching against a citation's DOI when a paper's own `papers.doi`
  is missing (0/960 in the real corpus today, so untested against real
  data, but the code does not assume every paper has one).
