"""Approval-gated acquisition of reviewed PMC Open Access PDFs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from knowledge_engine.ncbi_http import TransportResponse

PDF_HOST = "ftp.ncbi.nlm.nih.gov"
PDF_SIGNATURE = b"%PDF-"
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
DEFAULT_HEADERS = {
    "Accept": "application/pdf",
    "User-Agent": "knowledge-engine-core/0.2",
}


class AcquisitionError(RuntimeError):
    """Sanitized acquisition failure."""


class AcquisitionTransport(Protocol):
    """Structural transport interface used by the acquisition service."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


@dataclass(frozen=True)
class AcquisitionReceiptItem:
    """Sanitized evidence for one acquired PDF."""

    pmid: str
    pmcid: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class AcquisitionReceipt:
    """Deterministic acquisition receipt."""

    schema_version: int
    acquired_count: int
    items: tuple[AcquisitionReceiptItem, ...]

    def to_json(self) -> str:
        """Render stable JSON without private absolute paths."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class PmcOaAcquisitionService:
    """Acquire only explicitly approved PMC OA candidate PDFs."""

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
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
    ) -> AcquisitionReceipt:
        """Validate approvals, acquire PDFs atomically, and return a receipt."""

        candidates = _load_candidates(candidates_path)
        approvals = _load_approvals(approvals_path)
        plans = _build_plans(candidates, approvals)
        _validate_output_directory(output_directory, plans)

        acquired: list[AcquisitionReceiptItem] = []
        output_directory.mkdir(parents=True, exist_ok=True)
        for plan in plans:
            response = self._get_pdf(plan.pdf_url)
            if not response.body.startswith(PDF_SIGNATURE):
                raise AcquisitionError("PMC OA resource was not a PDF payload.")
            destination = output_directory / plan.filename
            temporary = output_directory / f".{plan.filename}.tmp"
            try:
                temporary.write_bytes(response.body)
                os.replace(temporary, destination)
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                raise AcquisitionError("Approved PDF could not be written.") from exc
            acquired.append(
                AcquisitionReceiptItem(
                    pmid=plan.pmid,
                    pmcid=plan.pmcid,
                    license=plan.license,
                    filename=plan.filename,
                    byte_count=len(response.body),
                    sha256=hashlib.sha256(response.body).hexdigest(),
                )
            )
        return AcquisitionReceipt(
            schema_version=1,
            acquired_count=len(acquired),
            items=tuple(acquired),
        )

    def _get_pdf(self, url: str) -> TransportResponse:
        try:
            response = self.transport.get(
                url=url,
                headers=DEFAULT_HEADERS,
                timeout_seconds=self.timeout_seconds,
                max_response_bytes=self.max_pdf_bytes,
            )
        except (OSError, TimeoutError) as exc:
            raise AcquisitionError("PMC OA PDF request failed.") from exc
        if response.status_code != 200:
            raise AcquisitionError("PMC OA PDF request returned a non-success status.")
        return response


@dataclass(frozen=True)
class _AcquisitionPlan:
    pmid: str
    pmcid: str
    license: str
    pdf_url: str
    filename: str


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink():
        raise AcquisitionError(f"{label} must not be a symbolic link.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"{label} could not be read as JSON.") from exc
    if not isinstance(value, dict):
        raise AcquisitionError(f"{label} must be a JSON object.")
    return value


def _load_candidates(path: Path) -> dict[str, dict[str, object]]:
    payload = _load_json_object(path, label="Candidate file")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise AcquisitionError("Candidate file is missing candidates.")
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("pmid"), str):
            raise AcquisitionError("Candidate file contains a malformed candidate.")
        pmid = row["pmid"]
        if pmid in result:
            raise AcquisitionError("Candidate file contains a duplicate PMID.")
        result[pmid] = row
    return result


def _load_approvals(path: Path) -> list[dict[str, object]]:
    payload = _load_json_object(path, label="Approval file")
    if payload.get("schema_version") != 1:
        raise AcquisitionError("Approval file schema_version must be 1.")
    rows = payload.get("approvals")
    if not isinstance(rows, list) or not rows:
        raise AcquisitionError("Approval file must contain at least one approval.")
    if not all(isinstance(row, dict) for row in rows):
        raise AcquisitionError("Approval file contains a malformed approval.")
    return rows


def _build_plans(
    candidates: dict[str, dict[str, object]], approvals: list[dict[str, object]]
) -> list[_AcquisitionPlan]:
    plans: list[_AcquisitionPlan] = []
    seen_pmids: set[str] = set()
    for approval in approvals:
        values = {key: approval.get(key) for key in ("pmid", "pmcid", "license", "pdf_url", "filename")}
        if not all(isinstance(value, str) and value for value in values.values()):
            raise AcquisitionError("Approval file contains incomplete approval evidence.")
        pmid = str(values["pmid"])
        if pmid in seen_pmids:
            raise AcquisitionError("Approval file contains a duplicate PMID.")
        seen_pmids.add(pmid)
        candidate = candidates.get(pmid)
        if candidate is None:
            raise AcquisitionError("Approval references an unknown PMID.")
        if candidate.get("open_access") is not True or candidate.get("status") != "oa_verified":
            raise AcquisitionError("Approval references a candidate without verified PMC OA evidence.")
        for key in ("pmcid", "license", "pdf_url"):
            if candidate.get(key) != values[key]:
                raise AcquisitionError("Approval evidence does not match the discovered candidate.")
        filename = str(values["filename"])
        if not SAFE_FILENAME.fullmatch(filename):
            raise AcquisitionError("Approval filename is not a safe PDF filename.")
        pdf_url = str(values["pdf_url"])
        parsed = urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != PDF_HOST
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise AcquisitionError("Approval PDF URL is not an allowlisted PMC OA HTTPS resource.")
        plans.append(
            _AcquisitionPlan(
                pmid=pmid,
                pmcid=str(values["pmcid"]),
                license=str(values["license"]),
                pdf_url=pdf_url,
                filename=filename,
            )
        )
    return plans


def _validate_output_directory(output_directory: Path, plans: list[_AcquisitionPlan]) -> None:
    if output_directory.is_symlink():
        raise AcquisitionError("Output directory must not be a symbolic link.")
    if output_directory.exists() and not output_directory.is_dir():
        raise AcquisitionError("Output path must be a directory.")
    for plan in plans:
        destination = output_directory / plan.filename
        temporary = output_directory / f".{plan.filename}.tmp"
        if destination.exists() or destination.is_symlink() or temporary.exists() or temporary.is_symlink():
            raise AcquisitionError("Approved PDF output already exists.")
