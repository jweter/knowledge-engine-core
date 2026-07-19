# Google Drive adapter contract

The Knowledge Engine Drive integration must remain constrained to the verified project hierarchy recorded in `knowledge_engine.drive_boundary`.

## Required write sequence

1. Resolve an exact logical destination into a `DriveDestination`.
2. Fetch live folder metadata from Google Drive.
3. Traverse parent folders and prove the destination is beneath the configured Knowledge Engine root.
4. Reject trashed, missing, non-folder, cyclic, excessively deep, or unrelated destinations.
5. Upload a safe basename and non-empty byte payload.
6. Read back uploaded-file metadata.
7. Verify file ID, filename, destination parent, byte count, and SHA-256.
8. Return success evidence only after all checks pass.

The adapter does not accept raw folder IDs or Drive URLs from callers. Provider-specific OAuth and API behavior must remain behind the `DriveTransport` protocol.

## Current increment boundary

This increment provides contracts, validation, and fake-transport regression tests only. It does not include credentials, token storage, Google API dependencies, retries, resumable uploads, deletion, or a real backup upload.

## Failure semantics

Destination or readback uncertainty fails closed. A failed readback does not prove the provider upload was rolled back, so future production transport work must record the returned file ID for reconciliation and define orphan cleanup separately. It must not silently retry a non-idempotent upload without first determining whether the original object exists.

## Next step

Create a consistent SQLite snapshot and integrity manifest locally, then implement one explicit Google Drive transport for a manually initiated pilot upload to `database_backups.sqlite`. Download that file into a temporary directory, verify its SHA-256, open it with SQLite, and run integrity and count reconciliation before any recurring schedule is enabled.
