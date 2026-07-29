"""Bounded HTTPS transport for NLM's public RxNorm (RxNav) REST API.

M42 adds a second live-lookup reference source alongside M41's Wikipedia
lookup -- see `docs/reference_knowledge_layer_design.md`'s "third option"
section, which named NLM's RxNorm API as a candidate free, no-storage-needed
source for drug/pharmacology terminology. RxNav
(https://rxnav.nlm.nih.gov/REST/) is a distinct NLM service from the
E-utilities literature APIs `ncbi_http.py` already covers, so it gets its
own dedicated, host-allowlisted transport rather than widening
`ncbi_http.py`'s `NCBI_HOSTS` (which is scoped to literature discovery and
acquisition, not drug terminology) -- the same one-source-one-transport
shape `reference_lookup_http.py`/`unpaywall_http.py` already established.
"""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

RXNAV_API_HOST = "rxnav.nlm.nih.gov"
"""RxNav's public REST API host (https://rxnav.nlm.nih.gov/REST/) -- public
HTTPS GET requests, no API key or bearer token involved."""

RXNAV_HOSTS = {RXNAV_API_HOST}


class ResponseTooLargeError(OSError):
    """Raised when an RxNav response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when an RxNav response attempts a redirect."""


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
        raise RedirectBlockedError("RxNav redirects are not permitted.")


class RxNavHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibRxNavTransport:
    """Fetch allowlisted RxNav API responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> RxNavHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("RxNav transport requires HTTPS.")
        if parsed.hostname not in RXNAV_HOSTS:
            raise OSError("RxNav transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("RxNav transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("RxNav transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return RxNavHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return RxNavHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("RxNav transport failed.") from error


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
            raise ResponseTooLargeError("RxNav response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("RxNav response exceeded the configured size limit.")
    return body
