"""Concrete HTTPS-only transport for Crossref metadata lookups."""

from __future__ import annotations

from collections.abc import Mapping
from http.client import HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from knowledge_engine.crossref_provider import TransportResponse

CROSSREF_HOST = "api.crossref.org"


class RedirectBlockedError(OSError):
    """Raised when a provider response attempts an HTTP redirect."""


class ResponseTooLargeError(OSError):
    """Raised when a provider response exceeds the configured byte limit."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: HTTPResponse,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> Request | None:
        raise RedirectBlockedError("Crossref redirects are not permitted.")


class UrllibCrossrefTransport:
    """Fetch Crossref responses with strict URL and response bounds."""

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
            raise OSError("Crossref transport requires HTTPS.")
        if parsed.hostname != CROSSREF_HOST:
            raise OSError("Crossref transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("Crossref transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("Crossref transport rejected an unsupported port.")

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
            raise OSError("Crossref transport failed.") from error


def _read_bounded(
    response: HTTPResponse | HTTPError,
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
            raise ResponseTooLargeError("Crossref response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("Crossref response exceeded the configured size limit.")
    return body
