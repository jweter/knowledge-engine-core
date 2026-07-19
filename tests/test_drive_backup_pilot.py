from __future__ import annotations

import hashlib
import json
import sqlite3
from email.message import Message
from pathlib import Path
from urllib.request import Request

from knowledge_engine.drive_adapter import DriveFileMetadata, DriveFolderMetadata
from knowledge_engine.drive_backup_pilot import run_drive_backup_pilot
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
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.metadata: dict[str, DriveFileMetadata] = {}

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return DriveFolderMetadata(folder_id, (KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,), True)

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        file_id = f"file-{len(self.files) + 1}"
        self.files[file_id] = payload
        self.metadata[file_id] = DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        return file_id

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        return self.metadata[file_id]

    def download_bytes(self, file_id: str) -> bytes:
        return self.files[file_id]


def test_pilot_uploads_snapshot_and_manifest_then_restores(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    with sqlite3.connect(source) as database:
        database.execute("PRAGMA user_version = 4")
        database.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY)")
        database.execute("INSERT INTO papers DEFAULT VALUES")
    transport = FakeDriveTransport()

    snapshot_id, manifest_id = run_drive_backup_pilot(
        source_database=source,
        output_directory=tmp_path / "bundle",
        production_commit="abc123",
        transport=transport,
    )

    assert transport.files[snapshot_id].startswith(b"SQLite format 3")
    manifest = json.loads(transport.files[manifest_id])
    assert manifest["production_commit"] == "abc123"
    assert manifest["table_counts"] == {"papers": 1}


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
