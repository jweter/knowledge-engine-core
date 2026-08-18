"""Concrete HTTPS-only transport for arXiv federated discovery lookups.

FRD-4 (see `docs/roadmap/federated_research_discovery_adoption.md`) built
`ArxivProvider` against an injected `ArxivTransport` protocol so its own
tests could use a fake transport, the same shape `crossref_provider.py`/
`crossref_http.py`, `openalex_provider.py`/`openalex_http.py`, and
`semantic_scholar_provider.py`/`semantic_scholar_http.py` already
established. This module is that transport's concrete implementation --
`export.arxiv.org` is a distinct host from every existing transport, so it
gets its own dedicated, host-allowlisted client rather than being folded
into an unrelated one.
"""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from knowledge_engine.arxiv_provider import ResponseTooLargeError as ResponseTooLargeError
from knowledge_engine.arxiv_provider import TransportResponse

ARXIV_HOST = "export.arxiv.org"


class RedirectBlockedError(OSError):
    """Raised when an arXiv response attempts an HTTP redirect."""


class _ReadableResponse(Protocol):
    headers: Message

    def read(self, amt: int = -1) -> bytes:
        """Read at most ``amt`` response bytes."""


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
        raise RedirectBlockedError("arXiv redirects are not permitted.")


class UrllibArxivTransport:
    """Fetch allowlisted arXiv API responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("arXiv transport requires HTTPS.")
        if parsed.hostname != ARXIV_HOST:
            raise OSError("arXiv transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("arXiv transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("arXiv transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())

        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return TransportResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return TransportResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("arXiv transport failed.") from error


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
            raise ResponseTooLargeError("arXiv response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("arXiv response exceeded the configured size limit.")
    return body
