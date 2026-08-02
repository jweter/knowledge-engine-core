# Google Drive backup pilot

The `ke-drive-backup-pilot` command performs one backup-and-restore rehearsal. It does not discover arbitrary Drive folders. It no longer requires an interactive step, so it is safe to invoke from a scheduler -- see "Recurring automation" below.

## Authorization

Provide a Google Cloud service-account JSON key, the same mechanism `ke-corpus-pdf-backup` uses. The service account's email must be shared as an editor on the Drive folders covering the `database_backups.*` destinations (see `docs/google_drive_project_boundary.md`). Never commit the key file to the repository or write it under a path Git tracks.

```bash
export KNOWLEDGE_ENGINE_GOOGLE_SERVICE_ACCOUNT=/path/outside/repo/drive-service-account.json
ke-drive-backup-pilot \
  --database /private/path/knowledge-engine.sqlite \
  --output-dir /private/path/backup-pilot \
  --production-commit <exact-production-commit>
```

Internally, the key signs a short-lived JWT-bearer assertion (RFC 7523) and exchanges it for a fresh, unattended-safe OAuth access token before each run -- there is no long-lived token to store, rotate, or leak. `--credentials /path/to/key.json` works in place of the environment variable.

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

An upload request can create a remote file even when the client never receives the response, so a failed upload call does not prove nothing was written. On any upload failure, the pilot itself lists the destination folder and matches candidate orphans by exact filename, byte count, application SHA-256, and this run's time window (with a clock-skew buffer):

- Exactly one match: it is confidently this run's orphan and is deleted automatically before the original failure propagates.
- No match: nothing to reconcile.
- More than one match: not this run's alone to claim -- it could include an earlier, unrelated, still-wanted upload. Nothing is deleted; the pilot raises `AmbiguousOrphanError` naming every candidate file ID for manual reconciliation instead.

## Recurring automation

Both preconditions this document previously gated recurring automation on are now met: a real pilot upload-and-restore rehearsal has succeeded, and ambiguous-upload orphan reconciliation is implemented (above). Service-account authorization (no interactive step, a fresh token minted per run) makes unattended/scheduled invocation safe. Before relying on a schedule, run one live rehearsal specifically with the service-account credential that schedule will use -- the credential that has done a real, verified rehearsal so far was a personal OAuth token, not yet the service account.
