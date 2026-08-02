# Corpus library Drive restore

`ke-corpus-library-drive-restore` is the pull side of
`docs/corpus_library_drive_backup.md`'s push: it lists the allowlisted
`corpus_library.snapshot` Google Drive folder, picks the most recently
created file, and downloads and imports it into the local database via
`import_corpus_library_compressed` (the same function `ke
corpus-library-import` uses) -- unless this machine already imported it.

It exists because the backup tool only pushes. Nothing previously pulled a
newly grown corpus back down to a laptop; this closes that gap.

## Authorization

Same OAuth refresh-token credential as `ke-drive-backup-pilot` and
`ke-corpus-library-drive-backup` -- see `docs/google_drive_backup_pilot.md`'s
"Authorization" section for how to obtain one.

```bash
export KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS=/path/outside/repo/drive-oauth-refresh.json
ke-corpus-library-drive-restore \
  --database /private/path/knowledge-engine.sqlite \
  --output-dir /private/path/corpus-library-restore
```

`--credentials /path/to/refresh-credentials.json` works in place of the
environment variable.

## Source

The exact source is the allowlisted `corpus_library.snapshot` logical name
from `knowledge_engine.drive_boundary` -- the same destination the backup
tool uploads to. No folder ID can be supplied on the command line;
`ConstrainedDriveAdapter.verify_destination` walks the live folder's parent
chain before listing or downloading anything and fails closed if it is not
beneath the approved Knowledge Engine Drive root.

## Picking the snapshot to restore

Old snapshots are not pruned from Drive, so the folder can hold more than
one file over time. This tool lists all of them and picks the one with the
most recent `createdTime` -- always the newest corpus-library content, never
an arbitrary or oldest match.

## Skip-unchanged behavior

After picking the newest snapshot, its SHA-256 (stored in Drive's file
metadata at upload time) is compared against a small local marker file
(`last_imported.sha256`, inside `--output-dir`) recording the hash of the
last snapshot this machine actually imported. A match skips the download
entirely -- a laptop that syncs daily and finds no new corpus growth
downloads nothing, the same skip-if-hash-matches spirit as the push side,
just mirrored for pulls. The marker is only written after a successful
import, so a failed or interrupted run does not falsely mark a snapshot as
already handled.

Even when nothing was previously imported, downloading is not the end of the
story: `import_corpus_library_compressed` is idempotent per paper (a content
hash already present locally is skipped, not reprocessed), so re-running
this tool against the same snapshot -- with a stale or missing marker -- is
still safe, just not free (it re-downloads a potentially large file to learn
that nothing new is inside it).

## Verification boundary

The downloaded bytes are hashed and compared against the SHA-256 recorded in
Drive's file metadata before anything is imported, matching this project's
general rule of never trusting provider metadata as proof of content by
itself (see `docs/google_drive_backup_pilot.md`'s "Verification boundary").

## Not implemented

This only restores corpus-library content (papers, journals, authors,
keywords, paper text/pages) -- not the full production database, and not any
of this machine's own operational history (import runs, extraction runs),
which `import_corpus_library_compressed` deliberately never copies. It does
not delete or prune old snapshots from Drive.
