"""Manual Google Drive backup-and-restore pilot."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Protocol

from knowledge_engine.drive_adapter import ConstrainedDriveAdapter
from knowledge_engine.drive_boundary import resolve_drive_destination
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport
from knowledge_engine.sqlite_backup import create_sqlite_backup, verify_restored_snapshot


class DownloadingDriveTransport(Protocol):
    def get_folder_metadata(self, folder_id: str): ...
    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str: ...
    def get_file_metadata(self, file_id: str): ...
    def download_bytes(self, file_id: str) -> bytes: ...


def run_drive_backup_pilot(
    *,
    source_database: Path,
    output_directory: Path,
    production_commit: str,
    transport: DownloadingDriveTransport,
) -> tuple[str, str]:
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

    adapter = ConstrainedDriveAdapter(transport)
    snapshot_upload = adapter.upload(
        destination=resolve_drive_destination("database_backups.sqlite"),
        name=snapshot.name,
        payload=snapshot.read_bytes(),
    )
    manifest_upload = adapter.upload(
        destination=resolve_drive_destination("database_backups.integrity_reports"),
        name=manifest_path.name,
        payload=manifest_bytes,
    )

    with tempfile.TemporaryDirectory(prefix="ke-drive-restore-") as temporary_directory:
        restored = Path(temporary_directory) / snapshot.name
        restored.write_bytes(transport.download_bytes(snapshot_upload.file_id))
        verify_restored_snapshot(snapshot_path=restored, manifest=manifest)
    return snapshot_upload.file_id, manifest_upload.file_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one explicit Knowledge Engine Drive backup pilot.")
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
