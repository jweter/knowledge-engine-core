"""Bounded HTTPS transport for Wikipedia's public REST summary API.

M41 adds a live-lookup reference layer -- see
`docs/reference_knowledge_layer_design.md` for the design this
implements: background grounding context (a term's plain-language
meaning), never evidence, never routed through `EvidenceRecord`
promotion. The design doc named Wikipedia's REST summary API as the
better starting point of the candidate sources it surveyed: no API key,
a single well-known endpoint shape, and content under CC BY-SA -- the
same license family `license_rules.py` already recognizes.
"""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

WIKIPEDIA_API_HOST = "en.wikipedia.org"
"""Wikipedia's REST API host (https://en.wikipedia.org/api/rest_v1/) --
public HTTPS GET requests, no API key or bearer token involved."""

WIKIPEDIA_HOSTS = {WIKIPEDIA_API_HOST}


class ResponseTooLargeError(OSError):
    """Raised when a Wikipedia response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when a Wikipedia response attempts a redirect."""


class TransportResponse(Protocol):
    """Minimal response contract consumed by the lookup service."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


class _ReadableResponse(Protocol):
    headers: Message

    def read(self, amt: int = -1) -> bytes:
        """Read at most ``amt`` bytes."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        raise RedirectBlockedError("Wikipedia redirects are not permitted.")


class WikipediaHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibWikipediaTransport:
    """Fetch allowlisted Wikipedia API responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> WikipediaHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("Wikipedia transport requires HTTPS.")
        if parsed.hostname not in WIKIPEDIA_HOSTS:
            raise OSError("Wikipedia transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("Wikipedia transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("Wikipedia transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return WikipediaHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return WikipediaHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("Wikipedia transport failed.") from error


def _read_bounded(
    response: _ReadableResponse,
    *,
    max_response_bytes: int,
) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = -1
        if declared_size > max_response_bytes:
            raise ResponseTooLargeError("Wikipedia response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("Wikipedia response exceeded the configured size limit.")
    return body
