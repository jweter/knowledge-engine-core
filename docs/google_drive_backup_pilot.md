# Manual Google Drive backup pilot

The `ke-drive-backup-pilot` command performs one explicitly initiated backup-and-restore rehearsal. It is not a scheduler and does not discover arbitrary Drive folders.

## Authorization

Provide a short-lived Google OAuth access token at runtime through `KNOWLEDGE_ENGINE_GOOGLE_DRIVE_ACCESS_TOKEN`. Never write the token to repository files, command arguments, manifests, logs, or Google Drive metadata.

The token must permit creating, reading, downloading, and deleting files in the already approved Knowledge Engine folder hierarchy. The application still verifies live ancestry before every upload.

## Command

```bash
export KNOWLEDGE_ENGINE_GOOGLE_DRIVE_ACCESS_TOKEN='runtime-token'
ke-drive-backup-pilot \
  --database /private/path/knowledge-engine.sqlite \
  --output-dir /private/path/backup-pilot \
  --production-commit <exact-production-commit>
```

The output directory must be ignored local storage. The command creates a consistent SQLite snapshot and deterministic manifest, uploads them to the exact allowlisted destinations, downloads the snapshot into a temporary directory, and performs complete restore verification.

## Drive destinations

- Snapshot: `database_backups.sqlite`
- Manifest: `database_backups.integrity_reports`

The transport does not accept destination folder IDs from the command line.

## Verification boundary

Google Drive file metadata stores the expected SHA-256 in private application properties for immediate readback. This metadata is not accepted as proof of content by itself. The pilot downloads the uploaded database and recomputes the hash, SQLite integrity result, schema version, and recognized table counts against the locally produced manifest.

## Transactional cleanup

If a known failure occurs after one or both upload responses are received, the pilot deletes the known uploaded file IDs in reverse order:

1. manifest;
2. snapshot.

This compensation applies to manifest-upload failures, download failures, and restore-verification failures. A successful pilot keeps both verified files.

If any compensating delete fails, the command reports that remote cleanup is incomplete. Operators must then reconcile the known file IDs before retrying.

## Ambiguous failures and retry

Do not automatically retry after an ambiguous upload failure. A request can create a remote file even when the client does not receive the response, so the application may not have a file ID available for compensation. Reconcile candidate orphan files by exact destination, filename, byte count, application SHA-256, and pilot time window before retrying.

Recurring automation remains prohibited until a real pilot upload and restore rehearsal succeeds and ambiguous-upload orphan reconciliation is implemented.
