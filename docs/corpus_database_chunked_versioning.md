# Chunked corpus database versioning

## Decision

`docs/roadmap.md`'s "Decision: corpus database versioning via chunked git
commits" (2026-08-08) records the project owner's decision to version-control
`data/knowledge_engine.sqlite3` directly in this repository, split into
parts small enough to stay well under GitHub's 100MB single-file push
limit, committed and pushed like any other file -- chosen over Git LFS
(avoids ongoing quota/tooling cost) and GitHub Release assets (keeps a
plain `git clone` sufficient for a new session or contributor). The
accepted tradeoff is unbounded git-history growth: every version ever
committed stays in history forever.

## Why this is needed, and what it does not duplicate

Two mechanisms already persist parts of the corpus's state in git:

- `ke corpus-library-export` / `ke corpus-library-import`
  (`knowledge_engine/corpus_library.py`, M27) copy only paper-intrinsic
  content -- `papers`, `paper_pages`, `paper_texts`, `journals`, `authors`,
  `keywords` -- into a compressed, git-committable snapshot. It deliberately
  excludes `import_runs`/`extraction_runs`/`manifest_snapshots` (this
  machine's own operational history, meaningless on another machine) and
  says nothing about the full-text search index or embeddings.
- `evidence_records.jsonl` and `relationship_records.jsonl`
  (`data/corpora/glp1_weight_loss/`) are already git-tracked directly. The
  `graph_claims`/`graph_relationships` tables that live inside the SQLite
  database are a derived cache rebuilt from these JSONL files by `ke
  graph-build` -- not authoritative, and not something that needs its own
  versioning.

What neither mechanism captures: the FTS full-text search index (`ke
answer`/the web `/ask` route depend on it -- its absence from an earlier
committed snapshot caused a live bug, see the 2026-07-xx "Fix live /ask bug"
entry in the roadmap) and any computed embeddings (expensive, real
provider cost/time to regenerate). A full local ingestion pass -- download
PDFs, extract, fill the database -- also takes real time and real provider
traffic to redo from scratch even where every underlying source is itself
recoverable. Committing the raw database file, byte-for-byte, closes both
gaps at once without requiring the two existing mechanisms to be extended
to cover them separately.

## Tools

- `tools/split_corpus_database.py` -- takes a live `--database` path,
  produces a verified, consistent backup snapshot through SQLite's online
  backup API (`knowledge_engine.sqlite_backup.create_sqlite_backup`, the
  same mechanism the Google Drive backup pilot uses, so a concurrently
  open connection or WAL state can never produce a torn read), splits the
  snapshot into fixed-size parts (default 90,000,000 bytes, comfortably
  under GitHub's 100MB limit), and writes them plus a `manifest.json` to
  `--output-dir` (default `data/db_parts`).
- `tools/reassemble_corpus_database.py` -- reads `manifest.json` from
  `--parts-dir`, concatenates the referenced parts in order, verifies every
  part's byte count and SHA-256, the whole file's byte count and SHA-256,
  and the database's own SQLite integrity check
  (`knowledge_engine.sqlite_backup.verify_restored_snapshot`) before
  committing anything to `--output`. Refuses to overwrite an existing,
  non-matching `--output` unless `--overwrite` is passed; is a no-op if
  `--output` already matches the manifest.

Neither tool is wired into the `ke` CLI -- both follow the same
standalone-script convention as `tools/reacquire_corpus_pdfs.py` and the
other corpus-recovery tooling, since they operate on the raw database file
rather than through the application's ORM layer.

`manifest.json`'s `backup` section reuses
`knowledge_engine.sqlite_backup.SQLiteBackupManifest` verbatim (schema
version, integrity check result, and row counts for
`papers`/`sources`/`import_runs`), so reassembly verification does not
duplicate that logic.

## Operator workflow (run manually, not automated)

On the machine where the corpus was actually updated (per the project
owner's own laptop-ingestion workflow: download PDFs, check/extract them,
fill the local SQLite database):

```bash
poetry run python tools/split_corpus_database.py \
  --database data/knowledge_engine.sqlite3 \
  --output-dir data/db_parts \
  --production-commit "$(git rev-parse HEAD)"

git add data/db_parts/*
git commit -m "Update corpus database snapshot"
git push
```

On any machine that needs the working database back (a fresh session, a
different environment):

```bash
poetry run python tools/reassemble_corpus_database.py \
  --parts-dir data/db_parts \
  --output data/knowledge_engine.sqlite3
```

`data/db_parts/` is not gitignored -- only `data/*.sqlite3` (the reassembled
working file) is. Re-running `split_corpus_database.py` replaces the entire
contents of `--output-dir`, so a stale part count from an earlier, smaller
database never lingers alongside a newer split.

## Live verification

Run against this environment's real corpus database (382,287,872 bytes,
960 papers) rather than only synthetic fixtures:

- `split_corpus_database.py` produced 5 parts (4 at exactly 90,000,000
  bytes, 1 remainder at 22,287,872 bytes) plus a manifest in 22 seconds.
- `reassemble_corpus_database.py` reassembled and fully verified them
  (whole-file SHA-256, every part's SHA-256, SQLite `PRAGMA
  integrity_check` = `ok`, `papers` row count = 960) in under 10 seconds.
- Direct content comparison against the live original confirmed identical
  row counts (960) and an identical title for `papers.id = 1`.

## Status

Tooling built, tested (17 unit tests plus the live round trip above), and
documented. Actually running `split_corpus_database.py` against a
freshly-updated database and committing the resulting parts is the
project owner's own manual step on their own machine, per their described
workflow -- not run as part of landing this tooling.
