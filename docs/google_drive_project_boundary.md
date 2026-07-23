# Google Drive project boundary

The connected personal Google Drive is an independent backup and human-accessible project workspace. It is not the live transactional database and the SQLite database must never be operated directly from a synchronized Drive folder.

## Approved root

- Folder name: `10 - Source Documents`
- Folder ID: `1p_-8Rc_g-D_-VHt0D_s4CQnfH2upL5Xh`

This repository originally recorded a different root (a planned `Knowledge
Engine` folder, ID `1ygxvhp7eEmU55LkmyrE0G3XjUMkagUjX`) that live testing
(2026-07-23) found unreachable -- it was never actually created or shared in
the real Drive. `10 - Source Documents` is the actual top-level folder the
project owner created and shared, and is now the approved root. Other
logical destinations under `DRIVE_FOLDER_IDS` besides `source_documents` and
`source_documents.pdf` have not been independently re-verified against the
live Drive tree and may need the same correction before their first real
use.

All Knowledge Engine Drive writes must target a logical destination defined in `knowledge_engine.drive_boundary.DRIVE_FOLDER_IDS`. Callers must not accept an arbitrary folder ID, URL, or free-form path from an ingestion record.

## Enforcement model

1. Business logic requests a logical destination such as `database_backups.sqlite` or `acquisition_evidence.receipts`.
2. `resolve_drive_destination()` returns the verified folder ID and approved root ID.
3. A future Drive adapter verifies the destination folder metadata is still a descendant of the approved root before each write.
4. Uploads use immutable timestamped or content-addressed names.
5. Credentials remain external secrets and are never committed.

The static map prevents accidental broad writes. Runtime ancestry verification remains required because folders can be moved in Drive after repository configuration is committed.

## Storage boundaries

Drive is suitable for database snapshots, integrity reports, acquisition evidence, approved source documents, extracted artifacts, ingestion reports, and controlled exports. It is not suitable as a multi-writer database, queue, transaction coordinator, or mutable object identity system.

Public sharing is limited to the `exports.public` destination. The root and all other destinations remain private by default. Quarantined documents must remain under `source_documents.quarantined` and must not be promoted automatically.

## Backup workflow

1. Create a consistent local SQLite backup or PostgreSQL logical dump.
2. Calculate SHA-256 and database counts.
3. Create a backup manifest and integrity report.
4. Upload immutable files to the allowlisted backup destinations.
5. Read back metadata and verify size/hash where supported.
6. Periodically perform a restore test.

This repository increment records the boundary only. It does not add OAuth credentials or automatic Drive uploads.
