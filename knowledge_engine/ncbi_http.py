"""Bounded HTTPS transport for official NCBI literature services."""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

NCBI_HOSTS = {
    "eutils.ncbi.nlm.nih.gov",
    "ftp.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "www.ncbi.nlm.nih.gov",
}


class ResponseTooLargeError(OSError):
    """Raised when an NCBI response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when an NCBI response attempts a redirect."""


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
        raise RedirectBlockedError("NCBI redirects are not permitted.")


class NcbiHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibNcbiTransport:
    """Fetch allowlisted NCBI responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> NcbiHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("NCBI transport requires HTTPS.")
        if parsed.hostname not in NCBI_HOSTS:
            raise OSError("NCBI transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("NCBI transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("NCBI transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return NcbiHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return NcbiHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("NCBI transport failed.") from error


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
            raise ResponseTooLargeError("NCBI response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("NCBI response exceeded the configured size limit.")
    return body
