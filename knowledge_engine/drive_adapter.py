"""Constrained Google Drive adapter contracts for Knowledge Engine artifacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from knowledge_engine.drive_boundary import DriveBoundaryError, DriveDestination

MAX_ANCESTRY_DEPTH = 32


class DriveAdapterError(RuntimeError):
    """Sanitized Drive adapter failure."""


@dataclass(frozen=True)
class DriveFolderMetadata:
    """Minimal folder metadata required to verify project ancestry."""

    folder_id: str
    parent_ids: tuple[str, ...]
    is_folder: bool
    trashed: bool = False


@dataclass(frozen=True)
class DriveFileMetadata:
    """Minimal uploaded-file metadata required for readback verification."""

    file_id: str
    name: str
    parent_ids: tuple[str, ...]
    byte_count: int
    sha256: str


class DriveTransport(Protocol):
    """Provider-specific operations required by the constrained adapter."""

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata: ...

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str: ...

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata: ...


@dataclass(frozen=True)
class VerifiedDriveUpload:
    """Evidence returned only after destination and upload readback verification."""

    file_id: str
    destination: DriveDestination
    name: str
    byte_count: int
    sha256: str


class ConstrainedDriveAdapter:
    """Write only to allowlisted destinations that remain under the approved root."""

    def __init__(self, transport: DriveTransport) -> None:
        self._transport = transport

    def verify_destination(self, destination: DriveDestination) -> None:
        """Prove the live destination remains beneath its configured root."""

        if destination.folder_id == destination.root_folder_id:
            return
        current_ids = [destination.folder_id]
        visited: set[str] = set()
        for _ in range(MAX_ANCESTRY_DEPTH):
            next_ids: list[str] = []
            for folder_id in current_ids:
                if folder_id in visited:
                    continue
                visited.add(folder_id)
                metadata = self._transport.get_folder_metadata(folder_id)
                if metadata.folder_id != folder_id or not metadata.is_folder or metadata.trashed:
                    raise DriveAdapterError("Drive destination metadata is invalid or unavailable.")
                if destination.root_folder_id in metadata.parent_ids:
                    return
                next_ids.extend(metadata.parent_ids)
            if not next_ids:
                break
            current_ids = next_ids
        raise DriveAdapterError("Drive destination is not beneath the approved project root.")

    def upload(self, *, destination: DriveDestination, name: str, payload: bytes) -> VerifiedDriveUpload:
        """Upload bytes and verify the provider readback before returning success."""

        if not isinstance(destination, DriveDestination):
            raise DriveBoundaryError("Drive writes require a validated DriveDestination.")
        if not name or name != name.strip() or "/" in name or "\\" in name or name in {".", ".."}:
            raise DriveAdapterError("Drive upload name must be a safe basename.")
        if not payload:
            raise DriveAdapterError("Drive upload payload must not be empty.")

        self.verify_destination(destination)
        expected_hash = hashlib.sha256(payload).hexdigest()
        file_id = self._transport.upload_bytes(
            parent_folder_id=destination.folder_id,
            name=name,
            payload=payload,
        )
        metadata = self._transport.get_file_metadata(file_id)
        if (
            metadata.file_id != file_id
            or metadata.name != name
            or destination.folder_id not in metadata.parent_ids
            or metadata.byte_count != len(payload)
            or metadata.sha256.casefold() != expected_hash
        ):
            raise DriveAdapterError("Drive upload readback did not match the requested artifact.")
        return VerifiedDriveUpload(
            file_id=file_id,
            destination=destination,
            name=name,
            byte_count=len(payload),
            sha256=expected_hash,
        )
