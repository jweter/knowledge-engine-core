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
corpus-library-import` make that corpus a reproducible artifact -- see
"Persistence policy" below for how that reproducibility is actually
achieved as the corpus grows past what git can hold as a single file.

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
metabolic-disease therapeutics."*

## Persistence policy: the snapshot is a local, regenerable cache, not a committed artifact

Earlier in the corpus's growth (up through 605 papers), the
`corpus_library` snapshot was committed to git alongside `sources.csv`,
refreshed after every growth batch -- see `CHANGELOG.md`'s many "Refreshed
the corpus-library snapshot" entries for that history. Growing the corpus
to 681 papers (the retstart=1750 M14 batch) made that snapshot 137.75 MB,
over GitHub's 100 MB single-file push limit (confirmed via `VACUUM`: this
is real page-level text growth, not bloat). Since the corpus is explicitly
targeting "at least a couple thousand papers" (`docs/roadmap.md`), this was
not a one-time size accident -- committing the snapshot as a single growing
binary file would keep failing, and worse each time.

The fix is to stop treating the snapshot as something that needs
committing at all. `sources.csv` (git-committed, kilobytes, diffable) is
already the durable, human-reviewable record of *which* papers are in the
corpus and on what evidence; the raw PDFs are durably archived to Google
Drive (see above). Both of those together are sufficient to deterministically
rebuild the snapshot at any time: `ke corpus-import` against the current
`sources.csv` (plus the archived PDFs, pulled back down locally) reproduces
the exact same working database, and `ke corpus-library-export` regenerates
the snapshot from it. Since rebuilding is cheap, deterministic, and fully
reproducible, persisting the derived binary itself in git adds size-limit
risk for no real durability benefit -- `sources.csv` and the archived PDFs
are the actual source of truth.

As of this change, `data/corpus_library/*.sqlite3` is gitignored. A local
snapshot file is still useful during a session (faster than re-running the
whole pipeline, and `ke corpus-library-import` can restore a database from
one without redoing discovery/acquisition), but it is no longer expected to
survive a fresh clone -- rebuild it locally via the commands below whenever
a session needs it.
