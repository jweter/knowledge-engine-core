"""Bounded HTTPS transport for UniProt's public UniProtKB REST API.

M73 adds a sixth live-lookup reference source alongside M41's Wikipedia
lookup, M42's RxNorm lookup, M43's MeSH lookup, M44's PubChem lookup,
and M71's ClinicalTrials.gov lookup -- see
`docs/reference_knowledge_layer_design.md`. `rest.uniprot.org` is a
distinct host from every prior lookup's host (`eutils.ncbi.nlm.nih.gov`,
`rxnav.nlm.nih.gov`, `pubchem.ncbi.nlm.nih.gov`, `en.wikipedia.org`,
`clinicaltrials.gov`), so it gets its own dedicated, host-allowlisted
transport -- the same one-source-one-transport shape
`pubchem_http.py`/`rxnorm_http.py`/`clinicaltrials_http.py`/
`reference_lookup_http.py` already established.
"""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

UNIPROT_API_HOST = "rest.uniprot.org"
"""UniProt's public REST API host (https://rest.uniprot.org/) -- public
HTTPS GET requests, no API key or bearer token involved."""

UNIPROT_HOSTS = {UNIPROT_API_HOST}


class ResponseTooLargeError(OSError):
    """Raised when a UniProt response exceeds the configured byte limit."""


class RedirectBlockedError(OSError):
    """Raised when a UniProt response attempts a redirect."""


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
        raise RedirectBlockedError("UniProt redirects are not permitted.")


class UniProtHttpResponse:
    """Concrete immutable transport response."""

    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers)


class UrllibUniProtTransport:
    """Fetch allowlisted UniProt API responses with strict bounds."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> UniProtHttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https":
            raise OSError("UniProt transport requires HTTPS.")
        if parsed.hostname not in UNIPROT_HOSTS:
            raise OSError("UniProt transport rejected an unsupported host.")
        if parsed.username is not None or parsed.password is not None:
            raise OSError("UniProt transport rejected URL credentials.")
        if parsed.port not in (None, 443):
            raise OSError("UniProt transport rejected an unsupported port.")

        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return UniProtHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return UniProtHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("UniProt transport failed.") from error


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
            raise ResponseTooLargeError("UniProt response exceeded the configured size limit.")

    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLargeError("UniProt response exceeded the configured size limit.")
    return body
