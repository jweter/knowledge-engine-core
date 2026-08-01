# M48 Phase 4: ke graph-report

## Purpose

M46 and M47 built the Phase 4 knowledge graph's write path (`ke
graph-build`, `ke graph-citations-build`) but left it read-only from the
database directly -- no CLI command could show a human what either
command had actually populated. Every other write-producing pipeline
step in this project pairs with a corresponding read/report command
(`ke evidence` + `ke evidence-report`, `ke relationship-validate` + `ke
relationship-report`, `ke extraction-review-generate` + the review
workflow itself). M48 closes that gap for the graph: `ke graph-report`.

## What it does

Three modes, chosen by which option is supplied:

- **No filter** -- the graph's current, actual corpus-wide population
  counts (concepts by source, claims, claim-concept edges, relationship
  edges, citation edges). The same numbers `ke graph-build`/`ke
  graph-citations-build` already print as their own run summary, now
  available as a standalone, re-runnable report.
- **`--evidence-record-id <id>`** -- one claim's linked concepts, grouped
  by PICO edge role (`population`/`intervention`/`comparator`/`outcome`),
  and its relationship edges, labeled by direction (`source`/`target`)
  and the other claim's own `evidence_record_id`. Exits with a clear
  error (not a "not found" report) if the ID has no graph claim yet.
- **`--paper-id <id>`** -- one paper's citation edges from `ke
  graph-citations-build`, split into what it cites and what cites it,
  each entry naming the paper on the other side and the matched DOI's
  surrounding raw text. Exits with a clear error if the paper ID doesn't
  exist.

Supplying both `--evidence-record-id` and `--paper-id` together is
rejected outright -- they read two different halves of the graph (claim
concepts/relationships vs. paper citations) and mixing them in one
report would blur which half a given section came from.

Purely a display layer: every mode reads through `GraphRepository`'s
existing methods unchanged, never writes to the graph, and never infers
or computes anything the graph does not already store.

## What was added to GraphRepository

- **`find_claim_by_evidence_id`** -- a read-only claim lookup by
  `evidence_record_id`. Deliberately separate from `get_or_create_claim`:
  a report command must treat an unrecognized ID as "not found," not
  silently promote it into a new, empty claim row.
- **`concept_edges_for_claim`** -- returns `(edge_role, concept)` pairs
  instead of `concepts_for_claim`'s bare concept list, so the report can
  group a claim's concepts by which PICO field produced each edge.

## Markdown-escaping discipline

`ke graph-report`'s free-text fields (concept labels, citation snippets,
relationship rationales) are escaped through a local
`_graph_report_text` helper before being written into Markdown headings
or body text. This mirrors `knowledge_engine.cli`'s own `_report_text`
exactly -- the same function `evidence-report`/`relationship-report`
share, hardened by a real Codex finding on the original
`relationship-report` addition (a value containing `"\n## Final
Disclaimer"` could otherwise inject a fake report section) and a
follow-up Codex finding that GFM strikethrough (`~`) was still missing
from the escape set. `entrypoint.py` does not import `cli.py`'s private
helpers (the same precedent `_read_jsonl_records` already established),
so this is a local equivalent applying the same already-learned rule,
not an independent rediscovery of it.

## Backfilled test coverage

Building `ke graph-report` surfaced a real, pre-existing gap: `ke
graph-build` and `ke graph-citations-build` (M46, M47) had repository-
and pure-function-level tests, but no test ever invoked either command
through Typer's `CliRunner` the way a real terminal session would.
`tests/test_graph_cli.py` backfills CLI-level coverage for all three
commands together, using the project's own established pattern
(`monkeypatch.setattr(entrypoint, "_local_database", lambda: database)`,
plus fake RxNorm/MeSH services for `graph-build` so the test suite still
makes zero live network calls).

## Live verification against the real corpus

Run against a copy of the real local 960-paper database, after `ke
graph-build --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl`
and `ke graph-citations-build`:

- Summary mode correctly reports 2 concepts, 2 claims, 4 claim-concept
  edges, 0 relationship edges, 5 citation edges -- matching M46/M47's own
  measured numbers exactly.
- `--evidence-record-id ev-glp1-step5-body-weight-week104-001` correctly
  renders its two resolved RxNorm concepts (`semaglutide` as
  `intervention`, `placebo` as `comparator`), each with the real
  `definition`/`source_reference_id` M46's Codex fix persists.
- `--paper-id 183` and `--paper-id 2` correctly render the real,
  matching citation edge from opposite sides (183 "cites" 2; 2 is "cited
  by" 183), each showing the real raw reference-list text the DOI match
  was found in.
- `--output <path.md>` writes the same content to a file instead of the
  console; an unrecognized `--evidence-record-id` or `--paper-id` exits
  non-zero with a clear message instead of a silent empty report.

## What is deliberately not built yet

- No combined "everything about this paper" mode joining its claims'
  concepts *and* its citation edges in one report -- claims are
  evidence-record-scoped and citations are paper-scoped, and the two
  don't share a join key in the schema today (`graph_claims` has no
  `paper_id` column; see `docs/phase4_design.md`'s Open Questions on
  `evidence_record_id` never becoming a real foreign key). Building that
  join would mean resolving an `EvidenceRecord`'s `source_doi` against
  `papers.doi` at report time, which is real, buildable work but a
  separate scoping decision, not bundled into this milestone.
- No JSON output mode -- `ke graph-build`/`ke graph-citations-build`'s
  own `--output` writes a small counts summary as JSON; `ke
  graph-report`'s richer per-claim/per-paper detail is Markdown only,
  matching `evidence-report`/`relationship-report`'s own precedent.
