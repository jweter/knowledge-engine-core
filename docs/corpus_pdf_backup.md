# Corpus PDF backup

`ke-corpus-pdf-backup` uploads local corpus PDFs to the allowlisted
`source_documents.pdf` Google Drive folder, skipping any file whose name and
SHA-256 already match what's in Drive. It exists because
`papers/corpora/*/`'s PDFs are intentionally gitignored (large, licensed,
environment-specific) and do not otherwise survive past the current session
-- see `docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning"
section.

This is a plain, repeatable bulk copy, not the manual-rehearsal-only backup
pilot documented in `docs/google_drive_backup_pilot.md` (which snapshots the
SQLite database, not PDFs, and has its own transactional cleanup and
ambiguous-failure rules).

## Authorization

Provide a Google Cloud service-account JSON key. The service account's email
must be shared as an editor on the Drive folder(s) covering the
`source_documents.pdf` destination.

Never commit the key file to the repository or write it under a path Git
tracks. Store it outside the working tree (or in an ignored path) and pass it
either as a flag or an environment variable:

```bash
ke-corpus-pdf-backup \
  --papers-dir papers/corpora/glp1_weight_loss \
  --credentials /path/outside/repo/drive-service-account.json
```

```bash
export KNOWLEDGE_ENGINE_GOOGLE_SERVICE_ACCOUNT=/path/outside/repo/drive-service-account.json
ke-corpus-pdf-backup --papers-dir papers/corpora/glp1_weight_loss
```

Internally, the key signs a short-lived JWT-bearer assertion (RFC 7523) and
exchanges it for an OAuth access token scoped to `drive.file` -- the
least-privilege Drive scope, granting access only to files and folders the
service account created or that were explicitly shared with it. The token is
minted fresh for each run and never persisted.

## Destination

The exact destination is the allowlisted `source_documents.pdf` logical name
from `knowledge_engine.drive_boundary`. No folder ID can be supplied on the
command line; `ConstrainedDriveAdapter.verify_destination` walks the live
folder's parent chain before any upload and fails closed if it is not
beneath the approved Knowledge Engine Drive root.

## Skip-existing behavior

Before uploading, the command lists every file already in the destination
folder and its stored SHA-256 (written into the upload's `appProperties` at
upload time, the same mechanism the Drive backup pilot uses for readback
verification). A local PDF is skipped only when both its filename and
content hash already match an existing Drive file; a changed file with the
same name is re-uploaded as a new object rather than silently skipped or
overwritten in place.

## Verification

Every individual upload goes through `ConstrainedDriveAdapter.upload`, which
re-reads the uploaded file's metadata and rejects the upload if the file ID,
name, parent folder, byte count, or SHA-256 does not match what was sent.

## Failure handling

A single file's upload failure does not abort the run. The command uploads
everything it can, then prints a summary (`Uploaded N; skipped M already
present; K failed.`) with each failed filename and reason, and exits
non-zero if anything failed.

## Not implemented

This is a one-way, additive push. It does not delete Drive files that no
longer have a local counterpart, does not download or restore, and does not
discover destinations beyond the one allowlisted folder.
