from __future__ import annotations

import json
from email.message import Message
from urllib.request import Request

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


def _file_payload(file_id: str, name: str, sha256: str = "", size: str = "12") -> dict[str, object]:
    return {
        "id": file_id,
        "name": name,
        "parents": ["folder-id"],
        "size": size,
        "appProperties": {"knowledgeEngineSha256": sha256} if sha256 else {},
        "trashed": False,
    }


def test_list_files_returns_every_entry_on_one_page() -> None:
    requests: list[Request] = []

    def opener(request: Request) -> FakeResponse:
        requests.append(request)
        return FakeResponse(
            json.dumps(
                {
                    "files": [
                        _file_payload("file-1", "a.pdf", "hash-a"),
                        _file_payload("file-2", "b.pdf"),
                    ]
                }
            ).encode()
        )

    results = GoogleDriveHttpTransport(access_token="token", opener=opener).list_files("folder-id")

    assert [entry.name for entry in results] == ["a.pdf", "b.pdf"]
    assert results[0].sha256 == "hash-a"
    assert results[1].sha256 == ""
    assert len(requests) == 1
    assert (
        "'folder-id'+in+parents" in requests[0].full_url
        or "%27folder-id%27" in requests[0].full_url
    )


def test_list_files_follows_pagination() -> None:
    responses = [
        json.dumps(
            {"files": [_file_payload("file-1", "a.pdf")], "nextPageToken": "page-2"}
        ).encode(),
        json.dumps({"files": [_file_payload("file-2", "b.pdf")]}).encode(),
    ]
    requests: list[Request] = []

    def opener(request: Request) -> FakeResponse:
        requests.append(request)
        return FakeResponse(responses.pop(0))

    results = GoogleDriveHttpTransport(access_token="token", opener=opener).list_files("folder-id")

    assert [entry.name for entry in results] == ["a.pdf", "b.pdf"]
    assert len(requests) == 2
    assert "pageToken=page-2" in requests[1].full_url


def test_list_files_empty_folder_returns_no_entries() -> None:
    def opener(request: Request) -> FakeResponse:
        return FakeResponse(json.dumps({"files": []}).encode())

    results = GoogleDriveHttpTransport(access_token="token", opener=opener).list_files("folder-id")

    assert results == []
