"""Google Drive backup-and-restore pilot, safe for unattended/scheduled runs."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from knowledge_engine.drive_adapter import (
    ConstrainedDriveAdapter,
    DriveFileMetadata,
    DriveFolderMetadata,
    VerifiedDriveUpload,
)
from knowledge_engine.drive_boundary import DriveDestination, resolve_drive_destination
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport
from knowledge_engine.google_drive_oauth_refresh import (
    load_refresh_token_credentials,
    mint_access_token,
)
from knowledge_engine.sqlite_backup import create_sqlite_backup, verify_restored_snapshot

# Clock skew tolerance between this machine and Drive's server-recorded
# createdTime when matching orphan candidates to this run's own uploads.
_RECONCILIATION_WINDOW_BUFFER = timedelta(minutes=5)


class DriveBackupPilotError(RuntimeError):
    """Sanitized backup-pilot failure."""


class AmbiguousOrphanError(DriveBackupPilotError):
    """An ambiguous upload failure produced more than one orphan candidate.

    A request can create a remote file even when the client never receives
    the response, so a failed `adapter.upload()` call doesn't prove nothing
    was written. Reconciliation lists the destination folder and matches on
    exact name, byte count, content SHA-256, and this run's time window; a
    single match is confidently this run's orphan and gets deleted
    automatically. More than one match is not this run's alone to claim --
    it could include an earlier, unrelated, still-wanted upload -- so nothing
    is deleted and this error is raised instead, naming every candidate for
    manual reconciliation.
    """


class DownloadingDriveTransport(Protocol):
    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata: ...

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str: ...

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata: ...

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]: ...

    def download_bytes(self, file_id: str) -> bytes: ...

    def delete_file(self, file_id: str) -> None: ...


def _created_at_or_after(created_time: str, threshold: datetime) -> bool:
    try:
        created = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
    except ValueError:
        return False
    return created >= threshold


def _reconcile_ambiguous_upload(
    transport: DownloadingDriveTransport,
    *,
    destination: DriveDestination,
    name: str,
    payload: bytes,
    run_started_at: datetime,
) -> None:
    """Delete the one orphan a failed, unconfirmed upload may have left behind."""

    expected_hash = hashlib.sha256(payload).hexdigest()
    window_start = run_started_at - _RECONCILIATION_WINDOW_BUFFER
    candidates = [
        entry
        for entry in transport.list_files(destination.folder_id)
        if entry.name == name
        and entry.byte_count == len(payload)
        and entry.sha256.casefold() == expected_hash
        and _created_at_or_after(entry.created_time, window_start)
    ]
    if not candidates:
        return
    if len(candidates) > 1:
        candidate_ids = ", ".join(sorted(entry.file_id for entry in candidates))
        raise AmbiguousOrphanError(
            f"Ambiguous upload failure for {name!r} produced {len(candidates)} matching "
            f"candidate files ({candidate_ids}) -- reconcile manually before retrying."
        )
    transport.delete_file(candidates[0].file_id)


def _upload_with_reconciliation(
    adapter: ConstrainedDriveAdapter,
    transport: DownloadingDriveTransport,
    *,
    destination: DriveDestination,
    name: str,
    payload: bytes,
    run_started_at: datetime,
) -> VerifiedDriveUpload:
    """Upload one artifact; on failure, reconcile any orphan it may have left, then re-raise."""

    try:
        return adapter.upload(destination=destination, name=name, payload=payload)
    except Exception:
        _reconcile_ambiguous_upload(
            transport,
            destination=destination,
            name=name,
            payload=payload,
            run_started_at=run_started_at,
        )
        raise


def run_drive_backup_pilot(
    *,
    source_database: Path,
    output_directory: Path,
    production_commit: str,
    transport: DownloadingDriveTransport,
) -> tuple[str, str]:
    """Upload and restore one verified bundle, compensating partial remote writes."""

    run_started_at = datetime.now(UTC)
    output_directory.mkdir(parents=True, exist_ok=True)
    snapshot = output_directory / "knowledge-engine.sqlite"
    manifest_path = output_directory / "knowledge-engine.sqlite.manifest.json"
    manifest = create_sqlite_backup(
        source_path=source_database,
        snapshot_path=snapshot,
        production_commit=production_commit,
    )
    manifest_bytes = manifest.to_json_bytes()
    manifest_path.write_bytes(manifest_bytes)

    uploaded_file_ids: list[str] = []
    adapter = ConstrainedDriveAdapter(transport)
    try:
        snapshot_payload = snapshot.read_bytes()
        snapshot_upload = _upload_with_reconciliation(
            adapter,
            transport,
            destination=resolve_drive_destination("database_backups.sqlite"),
            name=snapshot.name,
            payload=snapshot_payload,
            run_started_at=run_started_at,
        )
        uploaded_file_ids.append(snapshot_upload.file_id)

        manifest_upload = _upload_with_reconciliation(
            adapter,
            transport,
            destination=resolve_drive_destination("database_backups.integrity_reports"),
            name=manifest_path.name,
            payload=manifest_bytes,
            run_started_at=run_started_at,
        )
        uploaded_file_ids.append(manifest_upload.file_id)

        with tempfile.TemporaryDirectory(prefix="ke-drive-restore-") as temporary_directory:
            restored = Path(temporary_directory) / snapshot.name
            restored.write_bytes(transport.download_bytes(snapshot_upload.file_id))
            verify_restored_snapshot(snapshot_path=restored, manifest=manifest)
    except AmbiguousOrphanError:
        raise
    except Exception as exc:
        cleanup_failed = _delete_uploaded_files(transport, uploaded_file_ids)
        if cleanup_failed:
            raise DriveBackupPilotError(
                "Google Drive backup pilot failed and remote cleanup is incomplete."
            ) from exc
        raise DriveBackupPilotError(
            "Google Drive backup pilot failed; uploaded files were removed."
        ) from exc

    return snapshot_upload.file_id, manifest_upload.file_id


def _delete_uploaded_files(
    transport: DownloadingDriveTransport,
    uploaded_file_ids: list[str],
) -> bool:
    """Delete known uploads in reverse order and report whether cleanup was incomplete."""

    cleanup_failed = False
    for file_id in reversed(uploaded_file_ids):
        try:
            transport.delete_file(file_id)
        except Exception:
            cleanup_failed = True
    return cleanup_failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Knowledge Engine Drive backup pilot.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--production-commit", required=True)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=None,
        help=(
            "Path to a stored OAuth refresh-token credentials file (client_id, "
            "client_secret, refresh_token). Defaults to "
            "KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS if not given. Not a "
            "service-account key -- see docs/google_drive_backup_pilot.md for why."
        ),
    )
    arguments = parser.parse_args()

    credentials_path = arguments.credentials
    if credentials_path is None:
        env_value = os.environ.get("KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS", "")
        credentials_path = Path(env_value) if env_value else None
    if credentials_path is None:
        raise SystemExit(
            "OAuth refresh-token credentials are required "
            "(--credentials or KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS)."
        )

    refresh_credentials = load_refresh_token_credentials(credentials_path)
    access_token = mint_access_token(refresh_credentials)
    transport = GoogleDriveHttpTransport(access_token=access_token)
    snapshot_id, manifest_id = run_drive_backup_pilot(
        source_database=arguments.database,
        output_directory=arguments.output_dir,
        production_commit=arguments.production_commit,
        transport=transport,
    )
    print(f"Verified Drive backup pilot: snapshot={snapshot_id} manifest={manifest_id}")


if __name__ == "__main__":
    main()
