# Web alpha snapshot refresh: stall root cause and fix

The "Web Alpha Snapshot Refresh" Routine (fires into this repo, then
`knowledge-engine-web`'s `scripts/refresh-alpha-snapshot.sh`) has been
stalling: it runs for several minutes, then goes idle with no commit, no
branch, no PR in either repo, and no error visible to whatever fired it.

This was reproduced manually, step by step, outside the Routine, on
2026-08-09. Two distinct problems were found; either is sufficient to
explain the symptom, and both should be fixed.

## Problem 1 (the actual crash): `data/corpus_library/*.gz` is stale

The Routine's init step, when no local working database exists, runs:

```bash
poetry run ke init
poetry run ke corpus-library-import --input data/corpus_library/obesity_metabolic_disease_library.sqlite3.gz
```

`ke init` succeeds. `ke corpus-library-import` fails in ~9 seconds with:

```
OperationalError: (sqlite3.OperationalError) no such column: paper_pages.table_text
[SQL: SELECT paper_pages.paper_id AS paper_pages_paper_id, paper_pages.page_number AS paper_pages_page_number,
paper_pages.text AS paper_pages_text, paper_pages.table_text AS paper_pages_table_text
FROM paper_pages WHERE paper_pages.paper_id IN (...) ORDER BY paper_pages.page_number]
```

`knowledge_engine/models.py` (`paper_pages.table_text`, schema v11)
declares a column that the committed
`obesity_metabolic_disease_library.sqlite3.gz` snapshot predates.
`import_corpus_library_compressed` / `import_corpus_library`
(`knowledge_engine/corpus_library.py`) unzip the snapshot into a temp file
and open it with the *current* ORM models directly -- there is no schema
migration or version check on the source side, so any snapshot exported
before a paper_pages column was added will crash the same way on import.

This alone does not explain "stalls for minutes" (it fails in seconds) --
but if the Routine's harness doesn't distinguish "script exited non-zero"
from "no-op, nothing to do" and just reports coarse completion either way,
a fast crash after several minutes of `git clone` + `poetry install` would
look exactly like what was reported: real work, then quiet.

### Fix options (pick one)

1. **Regenerate the snapshot.** From a machine/session with a current,
   fully-populated `data/knowledge_engine.sqlite3`:
   ```bash
   poetry run ke corpus-library-export --output data/corpus_library/obesity_metabolic_disease_library.sqlite3.gz
   ```
   Commit the refreshed `.gz`. Simplest fix, but reintroduces the known gap
   `docs/corpus_database_chunked_versioning.md` already documents: this
   snapshot format excludes the FTS index and embeddings, and an earlier
   version of it caused a live `/ask` bug for exactly that reason.

2. **Switch the Routine's init step to the chunked-db reassembly path**
   (recommended -- already built, tested, and confirmed working during this
   diagnosis): replace the `ke init` + `ke corpus-library-import` two-liner
   above with
   ```bash
   poetry run python tools/reassemble_corpus_database.py \
     --parts-dir data/db_parts \
     --output data/knowledge_engine.sqlite3
   ```
   This reads `data/db_parts/manifest.json`, verifies every part's SHA-256,
   the whole-file SHA-256, and `PRAGMA integrity_check`, and produces
   `data/knowledge_engine.sqlite3` directly -- no `ke init` needed first,
   and no ORM-schema mismatch is possible since it's a raw byte-for-byte
   restore, not a cross-version import. Verified live on 2026-08-09: 1,357
   papers, `integrity_check = ok`, SHA-256 matched manifest, completed in
   well under 10 seconds. This is also the path `docs/corpus_database_chunked_versioning.md`
   already documents as the current, authoritative one -- the Routine's
   instructions just haven't been updated to match.

Option 2 is the better fix: it's already the documented, tested mechanism,
it's faster, and it doesn't have the FTS/embeddings gap that made option 1
cause a live bug once before.

## Problem 2 (a slowness/timeout risk, not yet confirmed as the actual cause of a stall): full `git clone` of this repo is very slow through the session's proxy

Since the chunked-db-versioning decision (2026-08-08), this repo's history
grows by a full working-database-sized commit (currently ~529MB across 6
parts) every time `tools/split_corpus_database.py` runs, and old versions
are never pruned. During this diagnosis:

- A shallow `git clone --depth 1 --single-branch --branch main` of the
  current tree took ~55s and transferred ~242MB.
- A full (non-shallow) `git clone` -- i.e. literally what the Routine's
  step 1 says ("Clone/checkout ... at main") -- did not complete within 2
  minutes; `git fetch --unshallow` on an existing shallow clone also did
  not complete within 2 minutes. Neither produced any error, just no
  progress -- consistent with `git index-pack` still unpacking a very large
  pack.

If the Routine's step 1 does a full clone (or `fetch`/`pull` without
`--depth`) and whatever's driving it has any execution timeout, this alone
could produce the "runs for minutes, then silently stops, no commit, no
error" symptom, independent of Problem 1.

### Fix

Make the Routine's clone/checkout step shallow:

```bash
git clone --depth 1 --single-branch --branch main <repo-url>
# or, for an existing checkout:
git fetch --depth 1 origin main && git checkout main
```

The Routine never needs history -- it only reads the current tree
(`data/corpus_library/`, `data/db_parts/`, `data/corpora/`) and pushes new
commits forward from `main`, so a shallow checkout is sufficient.

## Suggested order of work

1. Apply the Problem 2 fix (shallow clone) first -- it's small, safe, and
   removes a source of open-ended hangs regardless of what else changes.
2. Apply the Problem 1 fix, option 2 (switch to `reassemble_corpus_database.py`)
   -- update the Routine's own instructions/script and, if it lives in
   this repo, whatever wraps `ke init` + `ke corpus-library-import` for
   fresh-machine bootstrap.
3. Re-run the full pipeline (this repo's `graph-build` /
   `graph-citations-build` / `evidence-report`, then
   `knowledge-engine-web`'s `scripts/refresh-alpha-snapshot.sh`) end to end
   to confirm it now produces a commit/PR in the web repo.

Diagnosis performed by clean manual reproduction of every pipeline step
outside the Routine; see the conversation this doc came from for full
command output.
