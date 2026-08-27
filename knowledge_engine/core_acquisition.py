"""Validation-gated acquisition of CORE-hosted PDFs.

CORE discovery is intentionally not enough to authorize a download: CORE's API
has no per-work license field.  Callers must therefore supply explicit reusable
license evidence, while this service independently reconciles that approval to a
fresh CORE candidate and only fetches CORE's own HTTPS download host.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from knowledge_engine.core_discovery import CORE_PDF_HOST, CoreCandidate, CoreDiscoveryService
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.utils import normalize_doi

PDF_SIGNATURE = b"%PDF-"
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
DEFAULT_HEADERS = {
    "Accept": "application/pdf",
    "User-Agent": "knowledge-engine-core/0.2",
}


class CoreAcquisitionError(RuntimeError):
    """Sanitized CORE resolution or PDF-acquisition failure."""


class TransportResponse(Protocol):
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class AcquisitionTransport(Protocol):
    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse: ...


class _ReadableResponse(Protocol):
    headers: Message

    def read(self, amt: int = -1) -> bytes: ...


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
        raise CoreAcquisitionError("CORE PDF redirects are not permitted.")


class CorePdfHttpResponse:
    def __init__(self, *, status_code: int, body: bytes, headers: Mapping[str, str]) -> None:
        self.status_code = status_code
        self.body = body
        self.headers: Mapping[str, str] = dict(headers)


class UrllibCorePdfTransport:
    """Bounded, no-redirect HTTPS transport for CORE's own PDF mirror."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != CORE_PDF_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise OSError("CORE PDF transport rejected an unsupported URL.")
        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                body = _read_bounded(response, max_response_bytes=max_response_bytes)
                return CorePdfHttpResponse(
                    status_code=response.status,
                    body=body,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            body = _read_bounded(error, max_response_bytes=max_response_bytes)
            return CorePdfHttpResponse(
                status_code=error.code,
                body=body,
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("CORE PDF transport failed.") from error


def _read_bounded(response: _ReadableResponse, *, max_response_bytes: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared > max_response_bytes:
            raise OSError("CORE PDF response exceeded the configured size limit.")
    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise OSError("CORE PDF response exceeded the configured size limit.")
    return body


class CoreDoiResolver:
    """Refresh exact DOI identity through CORE without trusting stale search rows."""

    def __init__(self, discovery: CoreDiscoveryService) -> None:
        self.discovery = discovery

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[CoreCandidate, ...]:
        resolved: list[CoreCandidate] = []
        seen: set[str] = set()
        for raw_doi in dois:
            doi = normalize_doi(raw_doi)
            if not doi or doi in seen:
                raise CoreAcquisitionError("CORE DOI resolution request is invalid or duplicated.")
            seen.add(doi)
            result = self.discovery.discover(f'doi:"{doi}"', limit=10)
            matches = tuple(
                candidate
                for candidate in result.candidates
                if candidate.doi is not None and normalize_doi(candidate.doi) == doi
            )
            if len(matches) != 1:
                raise CoreAcquisitionError(
                    "CORE DOI resolution did not produce exactly one matching work."
                )
            resolved.append(matches[0])
        return tuple(resolved)


@dataclass(frozen=True)
class CoreAcquisitionApproval:
    core_id: str
    doi: str
    license: str
    pdf_url: str
    filename: str


@dataclass(frozen=True)
class CoreAcquisitionReceiptItem:
    core_id: str
    doi: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class CoreAcquisitionReceipt:
    schema_version: int
    acquired_count: int
    items: tuple[CoreAcquisitionReceiptItem, ...]


class CoreOaAcquisitionService:
    """Acquire a reconciled batch of explicitly licensed CORE-hosted PDFs atomically."""

    def __init__(
        self,
        transport: AcquisitionTransport,
        *,
        timeout_seconds: float = 30.0,
        max_pdf_bytes: int = 100_000_000,
    ) -> None:
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_pdf_bytes = max_pdf_bytes

    def acquire(
        self,
        *,
        candidates: tuple[CoreCandidate, ...],
        approvals: tuple[CoreAcquisitionApproval, ...],
        output_directory: Path,
    ) -> CoreAcquisitionReceipt:
        if not approvals or len(candidates) != len(approvals):
            raise CoreAcquisitionError("CORE approval count does not reconcile with candidates.")
        by_id = {candidate.core_id: candidate for candidate in candidates}
        if len(by_id) != len(candidates):
            raise CoreAcquisitionError("CORE candidates contain duplicate work identifiers.")

        seen_filenames: set[str] = set()
        for approval in approvals:
            candidate = by_id.get(approval.core_id)
            if candidate is None:
                raise CoreAcquisitionError("CORE approval references an unknown work identifier.")
            if (
                candidate.doi is None
                or normalize_doi(candidate.doi) != normalize_doi(approval.doi)
                or candidate.pdf_url != approval.pdf_url
                or candidate.pdf_host != CORE_PDF_HOST
            ):
                raise CoreAcquisitionError(
                    "CORE approval evidence does not match the refreshed work."
                )
            if evaluate_license(approval.license) != "passed":
                raise CoreAcquisitionError("CORE approval lacks a supported reusable license.")
            parsed = urlsplit(approval.pdf_url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != CORE_PDF_HOST
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443)
            ):
                raise CoreAcquisitionError(
                    "CORE approval URL is not an allowlisted HTTPS resource."
                )
            if (
                not SAFE_FILENAME.fullmatch(approval.filename)
                or approval.filename in seen_filenames
            ):
                raise CoreAcquisitionError("CORE approval filename is unsafe or duplicated.")
            seen_filenames.add(approval.filename)

        if output_directory.is_symlink() or (
            output_directory.exists() and not output_directory.is_dir()
        ):
            raise CoreAcquisitionError("CORE output path must be a normal directory.")
        for approval in approvals:
            destination = output_directory / approval.filename
            temporary = output_directory / f".{approval.filename}.tmp"
            if (
                destination.exists()
                or destination.is_symlink()
                or temporary.exists()
                or temporary.is_symlink()
            ):
                raise CoreAcquisitionError("CORE PDF output already exists.")

        output_directory.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[Path, Path, CoreAcquisitionReceiptItem]] = []
        committed: list[Path] = []
        attempted_temp_paths: list[Path] = []
        try:
            for ordinal, approval in enumerate(approvals, start=1):
                try:
                    response = self.transport.get(
                        url=approval.pdf_url,
                        headers=DEFAULT_HEADERS,
                        timeout_seconds=self.timeout_seconds,
                        max_response_bytes=self.max_pdf_bytes,
                    )
                except (OSError, TimeoutError) as exc:
                    raise CoreAcquisitionError(
                        f"CORE PDF request failed for approval {ordinal}."
                    ) from exc
                if response.status_code != 200:
                    raise CoreAcquisitionError(
                        f"CORE PDF request returned a non-success status ({response.status_code})."
                    )
                if not response.body.startswith(PDF_SIGNATURE):
                    raise CoreAcquisitionError("CORE resource was not a PDF payload.")
                temporary = output_directory / f".{approval.filename}.tmp"
                destination = output_directory / approval.filename
                attempted_temp_paths.append(temporary)
                temporary.write_bytes(response.body)
                staged.append(
                    (
                        temporary,
                        destination,
                        CoreAcquisitionReceiptItem(
                            core_id=approval.core_id,
                            doi=normalize_doi(approval.doi),
                            license=approval.license,
                            filename=approval.filename,
                            byte_count=len(response.body),
                            sha256=hashlib.sha256(response.body).hexdigest(),
                        ),
                    )
                )
            for temporary, destination, _ in staged:
                os.replace(temporary, destination)
                committed.append(destination)
        except CoreAcquisitionError:
            _rollback(attempted_temp_paths, committed)
            raise
        except OSError as exc:
            _rollback(attempted_temp_paths, committed)
            raise CoreAcquisitionError("CORE PDF batch could not be committed.") from exc

        return CoreAcquisitionReceipt(
            schema_version=1,
            acquired_count=len(staged),
            items=tuple(item for _, _, item in staged),
        )


def _rollback(temporaries: list[Path], committed: list[Path]) -> None:
    rollback_failed = False
    for path in committed:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    for path in temporaries:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise CoreAcquisitionError("CORE PDF batch rollback failed.")
