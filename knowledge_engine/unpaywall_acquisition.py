"""Validation-gated acquisition for direct PDFs resolved by Unpaywall.

Unpaywall is a locator, not a content host. Provider-returned URLs therefore
never become arbitrary network authority. This module only admits direct PDF
URLs on full-text hosts that Core already treats as reviewed acquisition
boundaries, after an exact DOI lookup and reusable-license check.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.unpaywall_lookup import (
    UnpaywallLookupResult,
    normalize_unpaywall_license,
)
from knowledge_engine.utils import normalize_doi

PDF_SIGNATURE = b"%PDF-"
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
DEFAULT_HEADERS = {
    "Accept": "application/pdf",
    "User-Agent": "knowledge-engine-core/0.2",
}

# Unpaywall may report arbitrary publisher/repository destinations. Only hosts
# already used as reviewed full-text acquisition boundaries elsewhere in Core
# are admitted here. This is intentionally narrower than the Internet.
UNPAYWALL_PDF_HOSTS = frozenset(
    {
        "pmc.ncbi.nlm.nih.gov",
        "pmc-oa-opendata.s3.amazonaws.com",
        "europepmc.org",
        "plus.europepmc.org",
        "core.ac.uk",
    }
)


class UnpaywallAcquisitionError(RuntimeError):
    """Sanitized Unpaywall resolution or PDF-acquisition failure."""


@dataclass(frozen=True)
class UnpaywallPdfResponse:
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
    ) -> UnpaywallPdfResponse: ...


class UnpaywallLookup(Protocol):
    def lookup(self, doi: str) -> UnpaywallLookupResult: ...


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
        raise UnpaywallAcquisitionError("Unpaywall-resolved PDF redirects are not permitted.")


class UrllibUnpaywallPdfTransport:
    """Bounded no-redirect transport for the explicit Unpaywall PDF host set."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> UnpaywallPdfResponse:
        _validate_pdf_url(url)
        request = Request(url, headers=dict(headers), method="GET")
        opener = build_opener(_NoRedirectHandler())
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                return UnpaywallPdfResponse(
                    status_code=response.status,
                    body=_read_bounded(response, max_response_bytes=max_response_bytes),
                    headers=dict(response.headers.items()),
                )
        except HTTPError as error:
            return UnpaywallPdfResponse(
                status_code=error.code,
                body=_read_bounded(error, max_response_bytes=max_response_bytes),
                headers=dict(error.headers.items()),
            )
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError from error
            raise OSError("Unpaywall-resolved PDF transport failed.") from error


@dataclass(frozen=True)
class UnpaywallResolvedPdf:
    doi: str
    landing_url: str | None
    pdf_url: str
    license: str
    source_host: str


class UnpaywallDoiResolver:
    """Re-resolve exact DOIs through Unpaywall immediately before acquisition."""

    def __init__(self, lookup: UnpaywallLookup) -> None:
        self.lookup = lookup

    def resolve_dois(self, dois: tuple[str, ...]) -> tuple[UnpaywallResolvedPdf, ...]:
        if not dois:
            raise UnpaywallAcquisitionError("Unpaywall DOI resolution requires at least one DOI.")
        resolved: list[UnpaywallResolvedPdf] = []
        seen: set[str] = set()
        for raw_doi in dois:
            doi = normalize_doi(raw_doi)
            if not doi or doi in seen:
                raise UnpaywallAcquisitionError(
                    "Unpaywall DOI resolution request is invalid or duplicated."
                )
            seen.add(doi)
            try:
                result = self.lookup.lookup(doi)
            except (OSError, RuntimeError, ValueError) as exc:
                raise UnpaywallAcquisitionError("Unpaywall DOI lookup failed.") from exc
            record = result.record
            if not result.found or record is None or normalize_doi(result.doi) != doi:
                raise UnpaywallAcquisitionError("Unpaywall did not resolve the requested DOI.")
            license_name = normalize_unpaywall_license(record.best_oa_location_license)
            pdf_url = record.best_oa_location_pdf_url
            if (
                record.is_oa is not True
                or not license_name
                or evaluate_license(license_name) != "passed"
                or not pdf_url
            ):
                raise UnpaywallAcquisitionError(
                    "Unpaywall did not provide reusable-license direct-PDF evidence."
                )
            _validate_pdf_url(pdf_url)
            host = urlsplit(pdf_url).hostname
            if host is None:
                raise UnpaywallAcquisitionError("Unpaywall direct-PDF host was missing.")
            resolved.append(
                UnpaywallResolvedPdf(
                    doi=doi,
                    landing_url=record.best_oa_location_url,
                    pdf_url=pdf_url,
                    license=license_name,
                    source_host=host,
                )
            )
        return tuple(resolved)


@dataclass(frozen=True)
class UnpaywallAcquisitionApproval:
    doi: str
    pdf_url: str
    license: str
    filename: str


@dataclass(frozen=True)
class UnpaywallAcquisitionReceiptItem:
    doi: str
    pdf_url: str
    source_host: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class UnpaywallAcquisitionReceipt:
    schema_version: int
    acquired_count: int
    items: tuple[UnpaywallAcquisitionReceiptItem, ...]


class UnpaywallOaAcquisitionService:
    """Atomically acquire a reconciled batch of Unpaywall-resolved direct PDFs."""

    def __init__(
        self,
        transport: AcquisitionTransport,
        *,
        timeout_seconds: float = 30.0,
        max_pdf_bytes: int = 100_000_000,
        max_concurrent_downloads: int = 4,
    ) -> None:
        if isinstance(max_concurrent_downloads, bool) or max_concurrent_downloads < 1:
            raise ValueError("max_concurrent_downloads must be at least 1.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_pdf_bytes = max_pdf_bytes
        self.max_concurrent_downloads = max_concurrent_downloads

    def acquire(
        self,
        *,
        resolved: tuple[UnpaywallResolvedPdf, ...],
        approvals: tuple[UnpaywallAcquisitionApproval, ...],
        output_directory: Path,
    ) -> UnpaywallAcquisitionReceipt:
        if not approvals or len(resolved) != len(approvals):
            raise UnpaywallAcquisitionError(
                "Unpaywall approval count does not reconcile with resolved PDFs."
            )
        by_doi = {item.doi: item for item in resolved}
        if len(by_doi) != len(resolved):
            raise UnpaywallAcquisitionError("Unpaywall resolution contains duplicate DOIs.")

        seen_filenames: set[str] = set()
        for approval in approvals:
            doi = normalize_doi(approval.doi)
            current = by_doi.get(doi)
            if current is None:
                raise UnpaywallAcquisitionError("Unpaywall approval references an unknown DOI.")
            if current.pdf_url != approval.pdf_url or current.license != approval.license:
                raise UnpaywallAcquisitionError(
                    "Unpaywall approval evidence does not match current lookup evidence."
                )
            _validate_pdf_url(approval.pdf_url)
            if evaluate_license(approval.license) != "passed":
                raise UnpaywallAcquisitionError(
                    "Unpaywall approval lacks a supported reusable license."
                )
            if (
                not SAFE_FILENAME.fullmatch(approval.filename)
                or approval.filename in seen_filenames
            ):
                raise UnpaywallAcquisitionError(
                    "Unpaywall approval filename is unsafe or duplicated."
                )
            seen_filenames.add(approval.filename)

        if output_directory.is_symlink() or (
            output_directory.exists() and not output_directory.is_dir()
        ):
            raise UnpaywallAcquisitionError("Unpaywall output path must be a normal directory.")
        for approval in approvals:
            destination = output_directory / approval.filename
            temporary = output_directory / f".{approval.filename}.tmp"
            if (
                destination.exists()
                or destination.is_symlink()
                or temporary.exists()
                or temporary.is_symlink()
            ):
                raise UnpaywallAcquisitionError("Unpaywall PDF output already exists.")

        output_directory.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[Path, Path, UnpaywallAcquisitionReceiptItem]] = []
        committed: list[Path] = []
        attempted_temp_paths: list[Path] = []
        try:
            # Each approved PDF is an independent, already license/resolution-
            # gated network fetch, so bound-concurrency downloading them
            # shortens acquisition wall-clock time without changing what gets
            # approved. Only a sliding window of at most max_workers downloads
            # is ever in flight or holding a completed body in memory at once.
            # Results are still consumed in deterministic approval order
            # below, so staging, receipt ordering, and failure-ordinal
            # reporting are identical to a sequential fetch.
            max_workers = min(self.max_concurrent_downloads, len(approvals))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                in_flight: dict[int, Future[UnpaywallPdfResponse]] = {}

                def _submit(index: int) -> None:
                    approval = approvals[index]
                    in_flight[index] = executor.submit(
                        self._get_pdf, approval.pdf_url, ordinal=index + 1
                    )

                for index in range(max_workers):
                    _submit(index)
                next_unsubmitted = max_workers

                try:
                    for index, approval in enumerate(approvals):
                        current = by_doi[normalize_doi(approval.doi)]
                        response = in_flight.pop(index).result()
                        if not response.body.startswith(PDF_SIGNATURE):
                            raise UnpaywallAcquisitionError(
                                "Unpaywall-resolved resource was not a PDF payload."
                            )
                        temporary = output_directory / f".{approval.filename}.tmp"
                        destination = output_directory / approval.filename
                        attempted_temp_paths.append(temporary)
                        temporary.write_bytes(response.body)
                        staged.append(
                            (
                                temporary,
                                destination,
                                UnpaywallAcquisitionReceiptItem(
                                    doi=current.doi,
                                    pdf_url=current.pdf_url,
                                    source_host=current.source_host,
                                    license=current.license,
                                    filename=approval.filename,
                                    byte_count=len(response.body),
                                    sha256=hashlib.sha256(response.body).hexdigest(),
                                ),
                            )
                        )
                        # Only refill the submission window after the current
                        # response body is fully consumed -- submitting the
                        # next download before that point could leave
                        # max_concurrent_downloads new bodies in flight
                        # alongside this one still being processed, exceeding
                        # the documented in-memory bound by one.
                        if next_unsubmitted < len(approvals):
                            _submit(next_unsubmitted)
                            next_unsubmitted += 1
                finally:
                    for pending in in_flight.values():
                        pending.cancel()

            for temporary, destination, _ in staged:
                os.replace(temporary, destination)
                committed.append(destination)
        except UnpaywallAcquisitionError:
            _rollback(attempted_temp_paths, committed)
            raise
        except OSError as exc:
            _rollback(attempted_temp_paths, committed)
            raise UnpaywallAcquisitionError(
                "Unpaywall-resolved PDF batch could not be committed."
            ) from exc

        return UnpaywallAcquisitionReceipt(
            schema_version=1,
            acquired_count=len(staged),
            items=tuple(item for _, _, item in staged),
        )

    def _get_pdf(self, url: str, *, ordinal: int) -> UnpaywallPdfResponse:
        try:
            response = self.transport.get(
                url=url,
                headers=DEFAULT_HEADERS,
                timeout_seconds=self.timeout_seconds,
                max_response_bytes=self.max_pdf_bytes,
            )
        except (OSError, TimeoutError) as exc:
            raise UnpaywallAcquisitionError(
                f"Unpaywall-resolved PDF request failed for approval {ordinal}."
            ) from exc
        if response.status_code != 200:
            raise UnpaywallAcquisitionError(
                "Unpaywall-resolved PDF request returned a non-success status "
                f"({response.status_code})."
            )
        return response


def deterministic_pdf_filename(doi: str) -> str:
    normalized = normalize_doi(doi)
    if not normalized:
        raise UnpaywallAcquisitionError("Cannot name an Unpaywall PDF without a DOI.")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"unpaywall-{digest}.pdf"


def _validate_pdf_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in UNPAYWALL_PDF_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise UnpaywallAcquisitionError(
            "Unpaywall direct-PDF URL is outside the approved acquisition boundary."
        )


def _read_bounded(response: _ReadableResponse, *, max_response_bytes: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared > max_response_bytes:
            raise OSError("Unpaywall PDF response exceeded the configured size limit.")
    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise OSError("Unpaywall PDF response exceeded the configured size limit.")
    return body


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
        raise UnpaywallAcquisitionError("Unpaywall PDF batch rollback failed.")
