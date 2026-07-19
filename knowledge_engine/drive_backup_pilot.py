"""Manual Google Drive backup-and-restore pilot."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Protocol

from knowledge_engine.drive_adapter import (
    ConstrainedDriveAdapter,
    DriveFileMetadata,
    DriveFolderMetadata,
)
from knowledge_engine.drive_boundary import resolve_drive_destination
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport
from knowledge_engine.sqlite_backup import create_sqlite_backup, verify_restored_snapshot


class DriveBackupPilotError(RuntimeError):
    """Sanitized backup-pilot failure."""


class DownloadingDriveTransport(Protocol):
    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata: ...

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str: ...

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata: ...

    def download_bytes(self, file_id: str) -> bytes: ...

    def delete_file(self, file_id: str) -> None: ...


def run_drive_backup_pilot(
    *,
    source_database: Path,
    output_directory: Path,
    production_commit: str,
    transport: DownloadingDriveTransport,
) -> tuple[str, str]:
    """Upload and restore one verified bundle, compensating partial remote writes."""

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
    try:
        adapter = ConstrainedDriveAdapter(transport)
        snapshot_upload = adapter.upload(
            destination=resolve_drive_destination("database_backups.sqlite"),
            name=snapshot.name,
            payload=snapshot.read_bytes(),
        )
        uploaded_file_ids.append(snapshot_upload.file_id)
        manifest_upload = adapter.upload(
            destination=resolve_drive_destination("database_backups.integrity_reports"),
            name=manifest_path.name,
            payload=manifest_bytes,
        )
        uploaded_file_ids.append(manifest_upload.file_id)

        with tempfile.TemporaryDirectory(prefix="ke-drive-restore-") as temporary_directory:
            restored = Path(temporary_directory) / snapshot.name
            restored.write_bytes(transport.download_bytes(snapshot_upload.file_id))
            verify_restored_snapshot(snapshot_path=restored, manifest=manifest)
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
    parser = argparse.ArgumentParser(
        description="Run one explicit Knowledge Engine Drive backup pilot."
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--production-commit", required=True)
    arguments = parser.parse_args()
    token = os.environ.get("KNOWLEDGE_ENGINE_GOOGLE_DRIVE_ACCESS_TOKEN", "")
    transport = GoogleDriveHttpTransport(access_token=token)
    snapshot_id, manifest_id = run_drive_backup_pilot(
        source_database=arguments.database,
        output_directory=arguments.output_dir,
        production_commit=arguments.production_commit,
        transport=transport,
    )
    print(f"Verified Drive backup pilot: snapshot={snapshot_id} manifest={manifest_id}")


if __name__ == "__main__":
    main()
