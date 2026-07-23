"""Concrete Google Drive v3 transport with sanitized failures."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from email.message import Message
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from knowledge_engine.drive_adapter import DriveFileMetadata, DriveFolderMetadata

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_SHA256_PROPERTY = "knowledgeEngineSha256"


class GoogleDriveHttpError(RuntimeError):
    """Sanitized Google Drive transport failure."""


class HttpResponse(Protocol):
    headers: Message

    def read(self) -> bytes: ...

    def __enter__(self) -> HttpResponse: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


OpenUrl = Callable[[Request], HttpResponse]


@dataclass(frozen=True)
class GoogleDriveUploadMetadata:
    """Provider metadata returned after one upload request."""

    file_id: str


class GoogleDriveHttpTransport:
    """Google Drive v3 operations required by the constrained backup workflow."""

    def __init__(self, *, access_token: str, opener: OpenUrl | None = None) -> None:
        if not access_token or access_token != access_token.strip():
            raise GoogleDriveHttpError("Google Drive authorization is unavailable.")
        self._access_token = access_token
        self._opener = opener or cast(OpenUrl, urlopen)

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        payload = self._request_json(
            f"{_DRIVE_API}/files/{quote(folder_id, safe='')}?"
            + urlencode({"fields": "id,mimeType,parents,trashed", "supportsAllDrives": "true"})
        )
        return DriveFolderMetadata(
            folder_id=_required_string(payload, "id"),
            parent_ids=tuple(_string_list(payload.get("parents"))),
            is_folder=payload.get("mimeType") == _FOLDER_MIME_TYPE,
            trashed=bool(payload.get("trashed", False)),
        )

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        expected_hash = hashlib.sha256(payload).hexdigest()
        boundary = f"knowledge-engine-{secrets.token_hex(16)}"
        metadata = json.dumps(
            {
                "name": name,
                "parents": [parent_folder_id],
                "appProperties": {_SHA256_PROPERTY: expected_hash},
            },
            separators=(",", ":"),
        ).encode()
        body = b"".join(
            [
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
                metadata,
                f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
                payload,
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        response = self._request_json(
            f"{_DRIVE_UPLOAD_API}/files?"
            + urlencode({"uploadType": "multipart", "fields": "id", "supportsAllDrives": "true"}),
            method="POST",
            body=body,
            content_type=f"multipart/related; boundary={boundary}",
        )
        return _required_string(response, "id")

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]:
        """List every non-trashed file directly inside one folder."""

        results: list[DriveFileMetadata] = []
        page_token: str | None = None
        while True:
            query = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken,files(id,name,parents,size,appProperties,trashed)",
                "pageSize": "1000",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                query["pageToken"] = page_token
            payload = self._request_json(f"{_DRIVE_API}/files?" + urlencode(query))
            raw_files = payload.get("files")
            if not isinstance(raw_files, list):
                raise GoogleDriveHttpError("Google Drive returned an invalid response.")
            for entry in raw_files:
                if not isinstance(entry, dict):
                    raise GoogleDriveHttpError("Google Drive returned an invalid response.")
                results.append(_file_metadata_from_payload(cast(dict[str, object], entry)))
            next_token = payload.get("nextPageToken")
            if not isinstance(next_token, str) or not next_token:
                break
            page_token = next_token
        return results

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        payload = self._request_json(
            f"{_DRIVE_API}/files/{quote(file_id, safe='')}?"
            + urlencode(
                {
                    "fields": "id,name,parents,size,appProperties,trashed",
                    "supportsAllDrives": "true",
                }
            )
        )
        if bool(payload.get("trashed", False)):
            raise GoogleDriveHttpError("Google Drive uploaded file is unavailable.")
        return _file_metadata_from_payload(payload)

    def download_bytes(self, file_id: str) -> bytes:
        return self._request_bytes(
            f"{_DRIVE_API}/files/{quote(file_id, safe='')}?"
            + urlencode({"alt": "media", "supportsAllDrives": "true"})
        )

    def delete_file(self, file_id: str) -> None:
        """Permanently delete one known pilot upload."""

        self._request_bytes(
            f"{_DRIVE_API}/files/{quote(file_id, safe='')}?"
            + urlencode({"supportsAllDrives": "true"}),
            method="DELETE",
        )

    def _request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, object]:
        raw = self._request_bytes(url, method=method, body=body, content_type=content_type)
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GoogleDriveHttpError("Google Drive returned an invalid response.") from None
        if not isinstance(decoded, dict):
            raise GoogleDriveHttpError("Google Drive returned an invalid response.")
        return cast(dict[str, object], decoded)

    def _request_bytes(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> bytes:
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener(request) as response:
                return response.read()
        except (HTTPError, URLError, OSError):
            raise GoogleDriveHttpError("Google Drive request failed.") from None


def _file_metadata_from_payload(payload: dict[str, object]) -> DriveFileMetadata:
    properties = payload.get("appProperties")
    if not isinstance(properties, dict):
        properties = {}
    sha256 = properties.get(_SHA256_PROPERTY)
    if not isinstance(sha256, str):
        sha256 = ""
    size = payload.get("size")
    if not isinstance(size, str):
        raise GoogleDriveHttpError("Google Drive file metadata is incomplete.")
    try:
        byte_count = int(size)
    except ValueError:
        raise GoogleDriveHttpError("Google Drive file metadata is incomplete.") from None
    return DriveFileMetadata(
        file_id=_required_string(payload, "id"),
        name=_required_string(payload, "name"),
        parent_ids=tuple(_string_list(payload.get("parents"))),
        byte_count=byte_count,
        sha256=sha256,
    )


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise GoogleDriveHttpError("Google Drive metadata is incomplete.")
    return value


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GoogleDriveHttpError("Google Drive metadata is incomplete.")
    return cast(list[str], value)
