"""Bounded HTTPS transport for NLM/NCBI's public PubChem PUG REST API.

M44 adds a fourth live-lookup reference source alongside M41's Wikipedia
lookup, M42's RxNorm lookup, and M43's MeSH lookup -- see
`docs/reference_knowledge_layer_design.md`'s "third option" section,
which named PubChem as the remaining live-lookup candidate: free
chemical-compound structure and identifier data. PubChem's PUG REST API
(`pubchem.ncbi.nlm.nih.gov`) is a distinct NLM/NCBI host from both
`eutils.ncbi.nlm.nih.gov` (`ncbi_http.py`, reused directly by M43's MeSH
lookup) and `rxnav.nlm.nih.gov` (M42's RxNorm lookup), so it gets its
own dedicated, host-allowlisted transport -- the same one-source-one-
transport shape `rxnorm_http.py`/`reference_lookup_http.py` already
established.
"""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PUBCHEM_API_HOST = "pubchem.ncbi.nlm.nih.gov"
"""PubChem's PUG REST API host (https://pubchem.ncbi.nlm.nih.gov/rest/pug/)
-- public HTTPS GET requests, no API key or bearer token involved."""

PUBCHEM_HOSTS = {PUBCHEM_API_HOST}


class ResponseTooLargeError(OSError):
    """Raised when a PubChem response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when a PubChem response attempts a redirect."""


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
        raise RedirectBlockedError("PubChem redirects are not permitted.")


class PubchemHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibPubchemTransport:
    """Fetch allowlisted PubChem API responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> PubchemHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("PubChem transport requires HTTPS.")
        if parsed.hostname not in PUBCHEM_HOSTS:
            raise OSError("PubChem transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("PubChem transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("PubChem transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return PubchemHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return PubchemHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("PubChem transport failed.") from error


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
            raise ResponseTooLargeError("PubChem response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("PubChem response exceeded the configured size limit.")
    return body
