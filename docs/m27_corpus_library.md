# M27 Corpus Library Snapshot

## Purpose

This repository's remote execution environment starts every session from a
fresh clone; `data/` (the working SQLite database) and `work/` (discovery/
acquisition scratch files) are both gitignored on purpose -- large,
environment-specific, and regenerable. That means nothing downloaded, parsed,
or imported in one session survives into the next unless it is explicitly
persisted somewhere durable.

`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning" section
names the underlying need: tuning M16-M26's deterministic extraction rules
against real data requires a real corpus, not the two hand-authored evidence
records currently committed. `ke corpus-library-export`/`ke
corpus-library-import` make that corpus a persisted, git-committable
artifact instead of session-local scratch state.

## What is (and is not) in a snapshot

A snapshot copies exactly the tables that hold paper-intrinsic content:
`journals`, `authors`, `keywords`, `papers`, `paper_authors`,
`paper_keywords`, `paper_texts`, `paper_pages`. It deliberately excludes
`import_runs`/`import_items`/`import_issues`, `extraction_runs`, and
`manifest_snapshots` -- those describe *this* database's own operational
history (when a command ran, against which ruleset, on which machine), not
the corpus itself. Re-running the relevant `ke` command regenerates them
locally; a snapshot of one machine's run history has no meaning on another's.

Raw PDF files are **not** part of a snapshot and are never committed to git.
A corpus of a few thousand papers is plausibly multiple gigabytes of binary
data -- GitHub hard-caps individual files at 100MB and strongly discourages
multi-GB repositories, and this is an offline-first, local-only codebase
with no existing cloud-storage dependency to build one on. Per the project
owner's decision, raw PDFs are archived to Google Drive instead (the
project's existing Drive workspace, "10 - Source Documents" folder), as a
zip archive per acquisition batch. This is an operational step taken
directly against Google Drive, not new `core` code -- `core` has an
existing, deliberately narrow Google Drive backup pilot
(`docs/google_drive_backup_pilot.md`) for SQLite database backups
specifically, and its own docs are explicit that "any expansion beyond
backup transport and recovery support requires a dedicated roadmap decision
or ADR." Repurposing it for bulk PDF archival was intentionally avoided.

## Commands

```bash
ke corpus-library-export --output data/corpus_library/<name>.sqlite3
ke corpus-library-import --input data/corpus_library/<name>.sqlite3
```

Export fails if the output file already exists -- delete it first, or
export to a new path. Import is idempotent: a paper whose `content_hash`
already exists locally is skipped, never duplicated, and
journals/authors/keywords are matched by their existing natural unique key
(name/value) rather than re-created. A snapshot's own primary keys are
never reused, since they are not portable across databases.

## Growing the library

The corpus itself grows through the existing M14 pipeline (discovery ->
adjudication -> curated `sources.csv` rows -> `ke corpus-import` ->
extraction), reusing the already-committed
`data/corpora/glp1_weight_loss/` corpus definition -- its own README
already documents this exact intent: *"M14 builds the first 500-paper
working corpus from verified PMC Open Access records across obesity and
metabolic-disease therapeutics."* `ke corpus-library-export` is run
periodically as that corpus grows, and the resulting snapshot is committed
so every clone of the repository has the same tuning corpus without
re-running discovery and acquisition from scratch.
