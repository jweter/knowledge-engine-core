"""Approval-gated acquisition of reviewed Europe PMC Open Access PDFs.

Mirrors `pmc_acquisition.py`'s "stage every PDF, commit the whole batch, roll
back completely on any failure" contract for M34's Europe PMC pipeline, but
validates against that pipeline's own identity (Europe PMC ID, DOI-anchored)
and PDF host (`europepmc.org`, Europe PMC's own hosted full-text repository
-- the closest analogue to PMC's official S3 bucket that M14 acquires from)
rather than retrofitting the PMC-specific module.
"""

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

from knowledge_engine.europepmc_http import (
    EUROPEPMC_PDF_HOSTS,
    EUROPEPMC_PLUS_HOST,
    TransportResponse,
)

PDF_SIGNATURE = b"%PDF-"
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
DEFAULT_HEADERS = {
    "Accept": "application/pdf",
    "User-Agent": "knowledge-engine-core/0.2",
}


class EuropePmcAcquisitionError(RuntimeError):
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
class EuropePmcAcquisitionReceiptItem:
    """Sanitized evidence for one acquired PDF."""

    europepmc_id: str
    doi: str
    license: str
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class EuropePmcAcquisitionReceipt:
    """Deterministic acquisition receipt."""

    schema_version: int
    acquired_count: int
    items: tuple[EuropePmcAcquisitionReceiptItem, ...]

    def to_json(self) -> str:
        """Render stable JSON without private absolute paths."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class EuropePmcOaAcquisitionService:
    """Acquire only explicitly approved Europe PMC OA candidate PDFs."""

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
        expected_count: int | None = None,
    ) -> EuropePmcAcquisitionReceipt:
        """Validate approvals, stage every PDF, commit the batch, and return a receipt."""

        if expected_count is not None and (isinstance(expected_count, bool) or expected_count < 1):
            raise EuropePmcAcquisitionError("Expected acquisition count must be at least 1.")

        candidates = _load_candidates(candidates_path)
        approvals = _load_approvals(approvals_path, expected_count=expected_count)
        plans = _build_plans(candidates, approvals)
        if expected_count is not None and len(plans) != expected_count:
            raise EuropePmcAcquisitionError(
                "Approval plan count does not match the expected acquisition count."
            )
        _validate_output_directory(output_directory, plans)

        output_directory.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[_AcquisitionPlan, Path, EuropePmcAcquisitionReceiptItem]] = []
        attempted_temp_paths: list[Path] = []
        committed: list[Path] = []
        try:
            for ordinal, plan in enumerate(plans, start=1):
                response = self._get_pdf(
                    plan.pdf_url, europepmc_id=plan.europepmc_id, ordinal=ordinal
                )
                if not response.body.startswith(PDF_SIGNATURE):
                    raise EuropePmcAcquisitionError("Europe PMC OA resource was not a PDF payload.")
                temporary = output_directory / f".{plan.filename}.tmp"
                attempted_temp_paths.append(temporary)
                temporary.write_bytes(response.body)
                staged.append(
                    (
                        plan,
                        temporary,
                        EuropePmcAcquisitionReceiptItem(
                            europepmc_id=plan.europepmc_id,
                            doi=plan.doi,
                            license=plan.license,
                            filename=plan.filename,
                            byte_count=len(response.body),
                            sha256=hashlib.sha256(response.body).hexdigest(),
                        ),
                    )
                )

            for plan, temporary, _ in staged:
                destination = output_directory / plan.filename
                os.replace(temporary, destination)
                committed.append(destination)
        except EuropePmcAcquisitionError:
            _rollback_paths(temp_paths=attempted_temp_paths, committed=committed)
            raise
        except OSError as exc:
            _rollback_paths(temp_paths=attempted_temp_paths, committed=committed)
            raise EuropePmcAcquisitionError("Approved PDF batch could not be committed.") from exc

        items = tuple(item for _, _, item in staged)
        return EuropePmcAcquisitionReceipt(schema_version=1, acquired_count=len(items), items=items)

    def _get_pdf(self, url: str, *, europepmc_id: str, ordinal: int) -> TransportResponse:
        try:
            response = self.transport.get(
                url=url,
                headers=DEFAULT_HEADERS,
                timeout_seconds=self.timeout_seconds,
                max_response_bytes=self.max_pdf_bytes,
            )
        except (OSError, TimeoutError) as exc:
            raise EuropePmcAcquisitionError(
                f"Europe PMC OA PDF request failed for approval {ordinal} ({europepmc_id})."
            ) from exc
        if response.status_code != 200:
            raise EuropePmcAcquisitionError(
                f"Europe PMC OA PDF request returned a non-success status "
                f"({response.status_code}) for approval {ordinal} ({europepmc_id})."
            )
        return response


@dataclass(frozen=True)
class _AcquisitionPlan:
    europepmc_id: str
    doi: str
    license: str
    pdf_url: str
    filename: str


def _rollback_paths(
    *,
    temp_paths: list[Path],
    committed: list[Path],
) -> None:
    rollback_failed = False
    for path in committed:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    for temporary in temp_paths:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            rollback_failed = True
    if rollback_failed:
        raise EuropePmcAcquisitionError("Approved PDF batch rollback failed.")


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink():
        raise EuropePmcAcquisitionError(f"{label} must not be a symbolic link.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EuropePmcAcquisitionError(f"{label} could not be read as JSON.") from exc
    if not isinstance(value, dict):
        raise EuropePmcAcquisitionError(f"{label} must be a JSON object.")
    return value


def _load_candidates(path: Path) -> dict[str, dict[str, object]]:
    payload = _load_json_object(path, label="Candidate file")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise EuropePmcAcquisitionError("Candidate file is missing candidates.")
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("europepmc_id"), str):
            raise EuropePmcAcquisitionError("Candidate file contains a malformed candidate.")
        europepmc_id = row["europepmc_id"]
        if europepmc_id in result:
            raise EuropePmcAcquisitionError("Candidate file contains a duplicate Europe PMC id.")
        result[europepmc_id] = row
    return result


def _load_approvals(path: Path, *, expected_count: int | None) -> list[dict[str, object]]:
    payload = _load_json_object(path, label="Approval file")
    if payload.get("schema_version") != 1:
        raise EuropePmcAcquisitionError("Approval file schema_version must be 1.")
    rows = payload.get("approvals")
    if not isinstance(rows, list) or not rows:
        raise EuropePmcAcquisitionError("Approval file must contain at least one approval.")
    if not all(isinstance(row, dict) for row in rows):
        raise EuropePmcAcquisitionError("Approval file contains a malformed approval.")

    selected_count = payload.get("selected_count")
    if selected_count is not None and (
        not isinstance(selected_count, int)
        or isinstance(selected_count, bool)
        or selected_count != len(rows)
    ):
        raise EuropePmcAcquisitionError("Approval selected count does not reconcile.")
    if expected_count is not None and (
        selected_count != expected_count or len(rows) != expected_count
    ):
        raise EuropePmcAcquisitionError(
            "Approval file does not contain the expected selected count."
        )
    return rows


def _build_plans(
    candidates: dict[str, dict[str, object]],
    approvals: list[dict[str, object]],
) -> list[_AcquisitionPlan]:
    plans: list[_AcquisitionPlan] = []
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    seen_filenames: set[str] = set()
    for approval in approvals:
        values = {
            key: approval.get(key)
            for key in ("europepmc_id", "doi", "license", "pdf_url", "filename")
        }
        if not all(isinstance(value, str) and value for value in values.values()):
            raise EuropePmcAcquisitionError("Approval file contains incomplete approval evidence.")
        europepmc_id = str(values["europepmc_id"])
        doi = str(values["doi"])
        if europepmc_id in seen_ids:
            raise EuropePmcAcquisitionError("Approval file contains a duplicate Europe PMC id.")
        if doi in seen_dois:
            raise EuropePmcAcquisitionError("Approval file contains a duplicate DOI.")
        seen_ids.add(europepmc_id)
        seen_dois.add(doi)
        candidate = candidates.get(europepmc_id)
        if candidate is None:
            raise EuropePmcAcquisitionError("Approval references an unknown Europe PMC id.")
        if candidate.get("open_access") is not True:
            raise EuropePmcAcquisitionError(
                "Approval references a candidate without verified open-access evidence."
            )
        if candidate.get("in_pmc") is not False:
            raise EuropePmcAcquisitionError(
                "Approval references a candidate that is not out of PMC's own pipeline scope."
            )
        for key in ("doi", "license", "pdf_url"):
            if candidate.get(key) != values[key]:
                raise EuropePmcAcquisitionError(
                    "Approval evidence does not match the discovered candidate."
                )
        filename = str(values["filename"])
        if not SAFE_FILENAME.fullmatch(filename):
            raise EuropePmcAcquisitionError("Approval filename is not a safe PDF filename.")
        if filename in seen_filenames:
            raise EuropePmcAcquisitionError("Approval file contains a duplicate PDF filename.")
        seen_filenames.add(filename)
        pdf_url = str(values["pdf_url"])
        parsed = urlsplit(pdf_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in EUROPEPMC_PDF_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise EuropePmcAcquisitionError(
                "Approval PDF URL is not an allowlisted Europe PMC OA HTTPS resource."
            )
        if parsed.hostname == EUROPEPMC_PLUS_HOST and (
            not parsed.path.startswith("/download/")
            or not parsed.path.lower().endswith(".pdf")
            or parsed.query
            or parsed.fragment
        ):
            raise EuropePmcAcquisitionError(
                "Approval PDF URL is not an allowlisted Europe PMC Plus download."
            )
        plans.append(
            _AcquisitionPlan(
                europepmc_id=europepmc_id,
                doi=doi,
                license=str(values["license"]),
                pdf_url=pdf_url,
                filename=filename,
            )
        )
    return plans


def _validate_output_directory(output_directory: Path, plans: list[_AcquisitionPlan]) -> None:
    if output_directory.is_symlink():
        raise EuropePmcAcquisitionError("Output directory must not be a symbolic link.")
    if output_directory.exists() and not output_directory.is_dir():
        raise EuropePmcAcquisitionError("Output path must be a directory.")
    for plan in plans:
        destination = output_directory / plan.filename
        temporary = output_directory / f".{plan.filename}.tmp"
        if (
            destination.exists()
            or destination.is_symlink()
            or temporary.exists()
            or temporary.is_symlink()
        ):
            raise EuropePmcAcquisitionError("Approved PDF output already exists.")
