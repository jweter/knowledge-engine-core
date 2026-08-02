# Google Drive backup pilot

The `ke-drive-backup-pilot` command performs one backup-and-restore rehearsal. It does not discover arbitrary Drive folders. It no longer requires an interactive step, so it is safe to invoke from a scheduler -- see "Recurring automation" below.

## Authorization

**Not a service-account key.** A bare Google service account has no Drive storage quota of its own on a personal (non-Google-Workspace) account. Confirmed live against this project's real Drive: the service account could *read* the destination folders fine (ordinary ACL sharing), but every upload failed with `403 storageQuotaExceeded` -- "Service Accounts do not have storage quota. Leverage shared drives, or use OAuth delegation instead." Both of Google's suggested fixes (Shared Drives, domain-wide delegation) require a paid Workspace subscription, which this project doesn't have. `ke-corpus-pdf-backup` uses a service account too and likely has the same latent problem on a real write, undiscovered because nothing had exercised it live.

Instead, provide a stored OAuth refresh-token credentials file -- the pilot authenticates as the human account's own identity (the one that actually owns the Drive quota), the same identity a personal OAuth access token already proved works, but without needing a human to re-mint a token by hand before every run:

```json
{
  "client_id": "your-client-id.apps.googleusercontent.com",
  "client_secret": "your-client-secret",
  "refresh_token": "1//your-refresh-token"
}
```

Get these once, interactively, from a self-registered OAuth client (Google Cloud Console -> APIs & Services -> Credentials -> Create Credentials -> OAuth client ID -> Desktop app), then a one-time consent flow (e.g. via OAuth Playground with "Use your own OAuth credentials" set to that client ID/secret) to capture the refresh token. Never commit this file to the repository or write it under a path Git tracks -- it is as sensitive as a password, since it never expires on its own.

```bash
export KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS=/path/outside/repo/drive-oauth-refresh.json
ke-drive-backup-pilot \
  --database /private/path/knowledge-engine.sqlite \
  --output-dir /private/path/backup-pilot \
  --production-commit <exact-production-commit>
```

Internally, the refresh token is exchanged for a fresh, short-lived access token before each run via the standard OAuth `refresh_token` grant -- there is no need to re-run the interactive consent flow for routine use. `--credentials /path/to/refresh-credentials.json` works in place of the environment variable.

If the OAuth consent screen is left in "Testing" publishing status, Google caps refresh tokens at 7 days regardless of use; if you want fewer than one manual re-consent per week, set the consent screen's publishing status to "In production" (personal single-user use does not require Google's app-verification review, though the consent screen may show an "unverified app" warning to click through once).

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

Both preconditions this document previously gated recurring automation on are now met: a real pilot upload-and-restore rehearsal has succeeded, and ambiguous-upload orphan reconciliation is implemented (above). OAuth refresh-token authorization (no interactive step for routine runs, a fresh access token minted per run) makes unattended/scheduled invocation safe. Before relying on a schedule, run one live rehearsal specifically with the stored refresh-token credential that schedule will use.
