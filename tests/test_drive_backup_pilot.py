from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from knowledge_engine.drive_adapter import DriveFileMetadata, DriveFolderMetadata
from knowledge_engine.drive_backup_pilot import (
    AmbiguousOrphanError,
    DriveBackupPilotError,
    run_drive_backup_pilot,
)
from knowledge_engine.drive_boundary import KNOWLEDGE_ENGINE_DRIVE_ROOT_ID
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers = Message()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class FakeDriveTransport:
    def __init__(
        self,
        *,
        fail_manifest_upload: bool = False,
        corrupt_download: bool = False,
        fail_delete_ids: set[str] | None = None,
        ambiguous_snapshot_upload: bool = False,
        duplicate_orphan: bool = False,
    ) -> None:
        self.files: dict[str, bytes] = {}
        self.metadata: dict[str, DriveFileMetadata] = {}
        self.deleted_file_ids: list[str] = []
        self.fail_manifest_upload = fail_manifest_upload
        self.corrupt_download = corrupt_download
        self.fail_delete_ids = fail_delete_ids or set()
        # Simulates a request that actually wrote to Drive but whose response
        # the client never received: the file really exists (so a real
        # `list_files` would see it) even though `upload_bytes` raises.
        self.ambiguous_snapshot_upload = ambiguous_snapshot_upload
        self.duplicate_orphan = duplicate_orphan

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return DriveFolderMetadata(folder_id, (KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,), True)

    def _store(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        file_id = f"file-{len(self.metadata) + 1}"
        self.files[file_id] = payload
        self.metadata[file_id] = DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            created_time=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        return file_id

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        if self.fail_manifest_upload and name.endswith(".manifest.json"):
            raise RuntimeError("simulated manifest upload failure")
        if self.ambiguous_snapshot_upload and not name.endswith(".manifest.json"):
            self._store(parent_folder_id=parent_folder_id, name=name, payload=payload)
            if self.duplicate_orphan:
                self._store(parent_folder_id=parent_folder_id, name=name, payload=payload)
            raise RuntimeError("simulated ambiguous upload failure (write landed, response lost)")
        return self._store(parent_folder_id=parent_folder_id, name=name, payload=payload)

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        return self.metadata[file_id]

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]:
        return [entry for entry in self.metadata.values() if folder_id in entry.parent_ids]

    def download_bytes(self, file_id: str) -> bytes:
        if self.corrupt_download:
            return b"not-a-sqlite-database"
        return self.files[file_id]

    def delete_file(self, file_id: str) -> None:
        self.deleted_file_ids.append(file_id)
        if file_id in self.fail_delete_ids:
            raise RuntimeError("simulated delete failure")
        self.files.pop(file_id, None)
        self.metadata.pop(file_id, None)


def _source_database(tmp_path: Path) -> Path:
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as database:
        database.execute("PRAGMA user_version = 4")
        database.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY)")
        database.execute("INSERT INTO papers DEFAULT VALUES")
    return source


def test_pilot_uploads_snapshot_and_manifest_then_restores(tmp_path: Path) -> None:
    transport = FakeDriveTransport()

    snapshot_id, manifest_id = run_drive_backup_pilot(
        source_database=_source_database(tmp_path),
        output_directory=tmp_path / "bundle",
        production_commit="abc123",
        transport=transport,
    )

    assert transport.files[snapshot_id].startswith(b"SQLite format 3")
    manifest = json.loads(transport.files[manifest_id])
    assert manifest["production_commit"] == "abc123"
    assert manifest["table_counts"] == {"papers": 1}
    assert transport.deleted_file_ids == []


def test_manifest_upload_failure_deletes_snapshot(tmp_path: Path) -> None:
    transport = FakeDriveTransport(fail_manifest_upload=True)

    with pytest.raises(DriveBackupPilotError, match="uploaded files were removed"):
        run_drive_backup_pilot(
            source_database=_source_database(tmp_path),
            output_directory=tmp_path / "bundle",
            production_commit="abc123",
            transport=transport,
        )

    assert transport.deleted_file_ids == ["file-1"]
    assert transport.files == {}


def test_restore_failure_deletes_manifest_then_snapshot(tmp_path: Path) -> None:
    transport = FakeDriveTransport(corrupt_download=True)

    with pytest.raises(DriveBackupPilotError, match="uploaded files were removed"):
        run_drive_backup_pilot(
            source_database=_source_database(tmp_path),
            output_directory=tmp_path / "bundle",
            production_commit="abc123",
            transport=transport,
        )

    assert transport.deleted_file_ids == ["file-2", "file-1"]
    assert transport.files == {}


def test_cleanup_failure_is_reported_without_hiding_residue(tmp_path: Path) -> None:
    transport = FakeDriveTransport(
        fail_manifest_upload=True,
        fail_delete_ids={"file-1"},
    )

    with pytest.raises(DriveBackupPilotError, match="cleanup is incomplete"):
        run_drive_backup_pilot(
            source_database=_source_database(tmp_path),
            output_directory=tmp_path / "bundle",
            production_commit="abc123",
            transport=transport,
        )

    assert transport.deleted_file_ids == ["file-1"]
    assert set(transport.files) == {"file-1"}


def test_ambiguous_upload_reconciles_single_orphan(tmp_path: Path) -> None:
    transport = FakeDriveTransport(ambiguous_snapshot_upload=True)

    with pytest.raises(DriveBackupPilotError, match="uploaded files were removed"):
        run_drive_backup_pilot(
            source_database=_source_database(tmp_path),
            output_directory=tmp_path / "bundle",
            production_commit="abc123",
            transport=transport,
        )

    assert transport.deleted_file_ids == ["file-1"]
    assert transport.files == {}


def test_ambiguous_upload_with_multiple_candidates_requires_manual_reconciliation(
    tmp_path: Path,
) -> None:
    transport = FakeDriveTransport(ambiguous_snapshot_upload=True, duplicate_orphan=True)

    with pytest.raises(AmbiguousOrphanError, match="2 matching"):
        run_drive_backup_pilot(
            source_database=_source_database(tmp_path),
            output_directory=tmp_path / "bundle",
            production_commit="abc123",
            transport=transport,
        )

    assert transport.deleted_file_ids == []
    assert set(transport.files) == {"file-1", "file-2"}


def test_created_at_or_after_excludes_stale_timestamps() -> None:
    from knowledge_engine.drive_backup_pilot import _created_at_or_after

    threshold = datetime(2026, 1, 1, tzinfo=UTC)
    assert _created_at_or_after("2026-01-01T00:00:01Z", threshold) is True
    assert _created_at_or_after("2025-12-31T23:59:59Z", threshold) is False
    assert _created_at_or_after("not-a-timestamp", threshold) is False


def test_http_transport_uses_authorization_and_parses_folder() -> None:
    requests: list[Request] = []

    def opener(request: Request) -> FakeResponse:
        requests.append(request)
        return FakeResponse(
            json.dumps(
                {
                    "id": "folder-id",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [KNOWLEDGE_ENGINE_DRIVE_ROOT_ID],
                    "trashed": False,
                }
            ).encode()
        )

    metadata = GoogleDriveHttpTransport(
        access_token="runtime-token", opener=opener
    ).get_folder_metadata("folder-id")

    assert metadata.is_folder is True
    assert requests[0].get_header("Authorization") == "Bearer runtime-token"
    assert "fields=id%2CmimeType%2Cparents%2Ctrashed" in requests[0].full_url


def test_http_transport_deletes_exact_file() -> None:
    requests: list[Request] = []

    def opener(request: Request) -> FakeResponse:
        requests.append(request)
        return FakeResponse(b"")

    GoogleDriveHttpTransport(access_token="runtime-token", opener=opener).delete_file("file/id")

    assert requests[0].method == "DELETE"
    assert requests[0].get_header("Authorization") == "Bearer runtime-token"
    assert "/files/file%2Fid?" in requests[0].full_url
