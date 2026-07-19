# Verified SQLite backup bundle

Knowledge Engine SQLite backups must be produced with SQLite's online backup API. Copying an active database file is not an approved backup method because journal/WAL state and concurrent writes can produce an inconsistent artifact.

`create_sqlite_backup` creates a new snapshot, opens it read-only, runs `PRAGMA integrity_check`, reads `PRAGMA user_version`, counts recognized core tables when present, hashes the exact bytes, and returns a deterministic manifest.

The manifest records:

- UTC creation timestamp;
- production commit supplied by the operator;
- snapshot filename and byte count;
- SHA-256;
- SQLite schema/user version;
- integrity result;
- counts for `papers`, `sources`, and `import_runs` when those tables exist.

The snapshot and manifest are separate artifacts. Generated files must not be committed. A Drive workflow will eventually upload the snapshot to `database_backups.sqlite` and the manifest to `database_backups.integrity_reports` through the constrained adapter.

## Restore gate

A downloaded snapshot is accepted only when `verify_restored_snapshot` reproduces the complete manifest. Hash, byte count, schema version, integrity result, filename, production commit, timestamp, and recognized table counts must all agree.

## Failure behavior

The producer requires a new destination and removes a partially created snapshot when creation or verification fails. It rejects missing sources, source/destination identity, existing destinations, empty or whitespace-modified production commits, and timezone-naive timestamps.

## Remaining work

This increment does not authenticate to Google Drive, upload a backup, or schedule recurring execution. The next pilot must add an explicit transport, perform one manually initiated upload/readback/download cycle, and retain restore evidence before any automation is enabled.
