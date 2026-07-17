from __future__ import annotations

from email.message import Message
from io import BytesIO

import pytest

from knowledge_engine.crossref_http import (
    ResponseTooLargeError,
    UrllibCrossrefTransport,
    _read_bounded,
)


class FakeResponse(BytesIO):
    def __init__(self, body: bytes, *, content_length: str | None = None) -> None:
        super().__init__(body)
        headers = Message()
        if content_length is not None:
            headers["Content-Length"] = content_length
        self.headers = headers


def test_read_bounded_accepts_body_within_limit() -> None:
    response = FakeResponse(b"payload", content_length="7")

    assert _read_bounded(response, max_response_bytes=7) == b"payload"


def test_read_bounded_rejects_declared_oversized_body() -> None:
    response = FakeResponse(b"small", content_length="100")

    with pytest.raises(ResponseTooLargeError, match="configured size limit"):
        _read_bounded(response, max_response_bytes=10)


def test_read_bounded_rejects_streamed_oversized_body() -> None:
    response = FakeResponse(b"01234567890")

    with pytest.raises(ResponseTooLargeError, match="configured size limit"):
        _read_bounded(response, max_response_bytes=10)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.crossref.org/works/10.1000/example",
        "https://example.com/works/10.1000/example",
        "https://user:pass@api.crossref.org/works/10.1000/example",
        "https://api.crossref.org:444/works/10.1000/example",
    ],
)
def test_transport_rejects_unsafe_or_unsupported_urls(url: str) -> None:
    transport = UrllibCrossrefTransport()

    with pytest.raises(OSError):
        transport.get(
            url=url,
            headers={"Accept": "application/json"},
            timeout_seconds=1.0,
            max_response_bytes=100,
        )
