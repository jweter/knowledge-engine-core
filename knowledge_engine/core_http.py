"""Bounded HTTPS transport for the official CORE API (api.core.ac.uk)."""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

CORE_API_HOST = "api.core.ac.uk"
"""CORE's official REST API host (https://api.core.ac.uk/docs/v3), operated by
The Open University. Public HTTPS GET requests, optionally bearer-authenticated."""

CORE_HOSTS = {CORE_API_HOST}


class ResponseTooLargeError(OSError):
    """Raised when a CORE response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when a CORE response attempts a redirect."""


class TransportResponse(Protocol):
    """Minimal response contract consumed by the discovery service."""

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
        raise RedirectBlockedError("CORE redirects are not permitted.")


class CoreHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibCoreTransport:
    """Fetch allowlisted CORE API responses with strict bounds.

    Bearer-token authorization (when a caller passes an `Authorization`
    header) rides through unchanged in `headers` -- this transport has no
    special-cased credential handling, since it never inspects or logs
    header values, only the URL's scheme/host/port/embedded-credentials.
    """

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> CoreHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("CORE transport requires HTTPS.")
        if parsed.hostname not in CORE_HOSTS:
            raise OSError("CORE transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("CORE transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("CORE transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return CoreHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return CoreHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("CORE transport failed.") from error


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
            raise ResponseTooLargeError("CORE response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("CORE response exceeded the configured size limit.")
    return body
