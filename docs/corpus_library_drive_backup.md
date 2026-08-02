# Corpus library Drive backup

`ke-corpus-library-drive-backup` exports the local database's corpus-library
content (papers, journals, authors, keywords, paper text, paper pages -- the
same tables `ke corpus-library-export` produces) and uploads the compressed
snapshot to the allowlisted `corpus_library.snapshot` Google Drive folder,
skipping the upload entirely when an identical snapshot (by SHA-256) is
already there.

It exists because `corpus_library.py`'s snapshot was designed to be
git-committed, which was fine while the corpus was small. Committing a
growing multi-hundred-MB snapshot to git on every corpus-growth cycle
permanently bloats the shared repository for every future clone -- this is
what caused the repo-size problem the 2026-08-02 Drive-root-boundary and
service-account-quota fixes reference -- and GitHub's 100MB single-file cap
is a hard wall regardless. This tool relays the snapshot through Drive
instead, so a growing corpus never touches git history.

## Authorization

Same OAuth refresh-token credential as `ke-drive-backup-pilot` -- see
`docs/google_drive_backup_pilot.md`'s "Authorization" section for how to
obtain one. A bare service account cannot write here (confirmed live: no
Drive storage quota on a personal, non-Workspace account).

```bash
export KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS=/path/outside/repo/drive-oauth-refresh.json
ke-corpus-library-drive-backup \
  --database /private/path/knowledge-engine.sqlite \
  --output-dir /private/path/corpus-library-backup
```

`--credentials /path/to/refresh-credentials.json` works in place of the
environment variable.

## Destination

The exact destination is the allowlisted `corpus_library.snapshot` logical
name from `knowledge_engine.drive_boundary`. No folder ID can be supplied on
the command line; `ConstrainedDriveAdapter.verify_destination` walks the
live folder's parent chain before any upload and fails closed if it is not
beneath the approved Knowledge Engine Drive root.

## Skip-unchanged behavior

Before uploading, the command lists every file already in the destination
folder and its stored SHA-256. If the freshly exported snapshot's hash
matches any of them, nothing is uploaded and the command reports the
snapshot as unchanged -- the same skip-if-hash-matches pattern
`ke-corpus-pdf-backup` uses. A corpus-growth cycle that added zero new
papers uploads nothing.

## Not implemented

This is a one-way push, not a two-way sync. It does not download or import
-- the laptop-side pull of a new snapshot is a separate step (see
`sync_corpus_graph.ps1` and its corpus-library companion). It keeps every
previously uploaded snapshot in Drive; it does not prune old ones.
