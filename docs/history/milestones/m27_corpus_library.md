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
artifact instead of session-local scratch state -- see "Persistence
policy" below for how that stays true as the corpus grows past what a raw
SQLite file can fit under GitHub's push limit.

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
ke corpus-library-export --output data/corpus_library/<name>.sqlite3.gz
ke corpus-library-import --input data/corpus_library/<name>.sqlite3.gz
```

A `.gz` suffix writes/reads a gzip-compressed snapshot
(`export_corpus_library_compressed`/`import_corpus_library_compressed` in
`corpus_library.py`); any other suffix uses the plain, uncompressed form.
`.gz` is the convention for anything meant to be committed -- see
"Persistence policy" below. Export fails if the output file already
exists -- delete it first, or export to a new path. Import is idempotent:
a paper whose `content_hash` already exists locally is skipped, never
duplicated, and journals/authors/keywords are matched by their existing
natural unique key (name/value) rather than re-created. A snapshot's own
primary keys are never reused, since they are not portable across
databases.

## Growing the library

The corpus itself grows through the existing M14 pipeline (discovery ->
adjudication -> curated `sources.csv` rows -> `ke corpus-import` ->
extraction), reusing the already-committed
`data/corpora/glp1_weight_loss/` corpus definition -- its own README
already documents this exact intent: *"M14 builds the first 500-paper
working corpus from verified PMC Open Access records across obesity and
metabolic-disease therapeutics."*

## Persistence policy: the snapshot is compressed to stay committable

Earlier in the corpus's growth (up through 605 papers), the
`corpus_library` snapshot was committed to git alongside `sources.csv`,
refreshed after every growth batch -- see `CHANGELOG.md`'s many "Refreshed
the corpus-library snapshot" entries for that history. Growing the corpus
to 681 papers (the retstart=1750 M14 batch) made that snapshot 137.75 MB,
over GitHub's 100 MB single-file push limit (confirmed via `VACUUM`: this
is real page-level text growth, not bloat). At the time, the corpus was
targeting "at least a couple thousand papers" (`docs/roadmap.md`), so this
was not a one-time size accident -- and that projected scale is exactly
why `docs/roadmap.md` later revised the target down to a 1,000-paper hard
cap, explicitly to keep this compressed snapshot comfortably under
GitHub's limit rather than repeatedly re-fighting this same size problem
as the corpus grew further.

The first fix attempted here was to stop committing the snapshot at all,
treating it as a cache reproducible on demand from `sources.csv` plus the
raw PDFs. A Codex review on the growth PR correctly caught the flaw in
that plan: reproducing the snapshot requires the raw PDFs to actually be
durably available, and at the time this repository's Google Drive PDF
archive (see above) was itself broken (`403 storageQuotaExceeded` --
service accounts have no storage quota outside a genuine Shared Drive). A
fresh clone would have had no way to rebuild anything beyond the three
hand-authored historical records. "Easy to rebuild" was true in principle
but not in the state the repository was actually in.

The real fix is compression, not abandoning commitment.
`export_corpus_library_compressed`/`import_corpus_library_compressed`
gzip/gunzip the snapshot around the same table-copying logic
`export_corpus_library`/`import_corpus_library` already use -- this
corpus's page-level text compresses roughly 3x (137.75MB -> ~44MB at 677
papers), which restores real headroom under GitHub's cap without touching
what data a snapshot holds. `data/corpus_library/*.sqlite3` remains
gitignored (an uncompressed snapshot is still useful as a fast local
scratch file within a session), but `data/corpus_library/*.sqlite3.gz` is
committed and refreshed after every growth batch, same as before 681
papers. This will need revisiting again once the corpus grows enough that
even the compressed file approaches 100MB -- sharding by paper-ID range is
the most likely next step, not abandoning git persistence, given how much
this Codex review demonstrated that mattered.
