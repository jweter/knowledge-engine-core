from __future__ import annotations

import hashlib

import pytest

from knowledge_engine.drive_adapter import (
    ConstrainedDriveAdapter,
    DriveAdapterError,
    DriveFileMetadata,
    DriveFolderMetadata,
)
from knowledge_engine.drive_boundary import (
    DriveBoundaryError,
    DriveDestination,
    resolve_drive_destination,
)


class FakeTransport:
    def __init__(self) -> None:
        self.folders: dict[str, DriveFolderMetadata] = {}
        self.files: dict[str, DriveFileMetadata] = {}
        self.uploaded: list[tuple[str, str, bytes]] = []

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return self.folders[folder_id]

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        self.uploaded.append((parent_folder_id, name, payload))
        file_id = "uploaded-file"
        self.files[file_id] = DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        return file_id

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        return self.files[file_id]


def configured_transport(destination: DriveDestination) -> FakeTransport:
    transport = FakeTransport()
    transport.folders[destination.folder_id] = DriveFolderMetadata(
        folder_id=destination.folder_id,
        parent_ids=(destination.root_folder_id,),
        is_folder=True,
    )
    return transport


def test_upload_verifies_destination_and_readback() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = configured_transport(destination)

    result = ConstrainedDriveAdapter(transport).upload(
        destination=destination,
        name="knowledge-engine.sqlite",
        payload=b"database snapshot",
    )

    assert result.destination == destination
    assert result.byte_count == 17
    assert transport.uploaded == [
        (destination.folder_id, "knowledge-engine.sqlite", b"database snapshot")
    ]


def test_nested_ancestry_is_accepted() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = FakeTransport()
    transport.folders[destination.folder_id] = DriveFolderMetadata(
        destination.folder_id, ("intermediate",), True
    )
    transport.folders["intermediate"] = DriveFolderMetadata(
        "intermediate", (destination.root_folder_id,), True
    )

    ConstrainedDriveAdapter(transport).verify_destination(destination)


def test_destination_outside_root_fails_before_upload() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = FakeTransport()
    transport.folders[destination.folder_id] = DriveFolderMetadata(
        destination.folder_id, ("unrelated-root",), True
    )
    transport.folders["unrelated-root"] = DriveFolderMetadata("unrelated-root", (), True)

    with pytest.raises(DriveAdapterError, match="not beneath"):
        ConstrainedDriveAdapter(transport).upload(
            destination=destination,
            name="backup.sqlite",
            payload=b"snapshot",
        )
    assert transport.uploaded == []


def test_trashed_or_non_folder_destination_fails_closed() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = FakeTransport()
    transport.folders[destination.folder_id] = DriveFolderMetadata(
        destination.folder_id,
        (destination.root_folder_id,),
        False,
        True,
    )

    with pytest.raises(DriveAdapterError, match="invalid or unavailable"):
        ConstrainedDriveAdapter(transport).verify_destination(destination)


def test_readback_mismatch_fails() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = configured_transport(destination)
    adapter = ConstrainedDriveAdapter(transport)
    original_upload = transport.upload_bytes

    def corrupt_upload(*, parent_folder_id: str, name: str, payload: bytes) -> str:
        file_id = original_upload(parent_folder_id=parent_folder_id, name=name, payload=payload)
        transport.files[file_id] = DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload) + 1,
            sha256="0" * 64,
        )
        return file_id

    transport.upload_bytes = corrupt_upload  # type: ignore[method-assign]
    with pytest.raises(DriveAdapterError, match="readback"):
        adapter.upload(destination=destination, name="backup.sqlite", payload=b"snapshot")


@pytest.mark.parametrize("name", ["", " backup.sqlite", "../backup.sqlite", "a/b.sqlite"])
def test_unsafe_names_are_rejected(name: str) -> None:
    destination = resolve_drive_destination("database_backups.sqlite")
    transport = configured_transport(destination)

    with pytest.raises(DriveAdapterError, match="safe basename"):
        ConstrainedDriveAdapter(transport).upload(
            destination=destination,
            name=name,
            payload=b"snapshot",
        )


def test_raw_destination_is_rejected() -> None:
    transport = FakeTransport()
    with pytest.raises(DriveBoundaryError, match="validated"):
        ConstrainedDriveAdapter(transport).upload(  # type: ignore[arg-type]
            destination="1arbitrary",
            name="backup.sqlite",
            payload=b"snapshot",
        )
