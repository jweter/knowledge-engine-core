from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from knowledge_engine.ncbi_http import TransportResponse
from knowledge_engine.pmc_acquisition import AcquisitionError, PmcOaAcquisitionService


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        del headers, timeout_seconds, max_response_bytes
        self.urls.append(url)
        return self.responses.pop(0)


def test_acquire_requires_exact_approval_and_writes_sanitized_receipt(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=1)
    output = tmp_path / "papers"
    transport = FakeTransport([FakeResponse(200, b"%PDF-1.7\nbody", {})])

    receipt = PmcOaAcquisitionService(transport).acquire(
        candidates_path=candidates,
        approvals_path=approvals,
        output_directory=output,
        expected_count=1,
    )

    assert transport.urls == ["https://ftp.ncbi.nlm.nih.gov/pub/pmc/example.pdf"]
    assert (output / "PMC999.pdf").read_bytes().startswith(b"%PDF-")
    assert receipt.acquired_count == 1
    assert receipt.items[0].pmid == "222"
    assert receipt.items[0].pmcid == "PMC999"
    assert receipt.items[0].filename == "PMC999.pdf"
    assert receipt.items[0].byte_count == 13
    assert len(receipt.items[0].sha256) == 64
    assert str(tmp_path) not in receipt.to_json()


def test_expected_count_mismatch_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=1)
    transport = FakeTransport([])

    with pytest.raises(AcquisitionError, match="expected selected count"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
            expected_count=2,
        )

    assert transport.urls == []


def test_boolean_selected_count_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=True)
    transport = FakeTransport([])

    with pytest.raises(AcquisitionError, match="selected count does not reconcile"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_approval_mismatch_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, license_name="CC BY-SA")
    transport = FakeTransport([])

    with pytest.raises(AcquisitionError, match="does not match"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_duplicate_filenames_fail_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2)
    approvals = _write_approvals(tmp_path, count=2, duplicate_filename=True)
    transport = FakeTransport([])

    with pytest.raises(AcquisitionError, match="duplicate PDF filename"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_non_pdf_payload_is_rejected_without_persisting_file(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    transport = FakeTransport([FakeResponse(200, b"<html>not pdf</html>", {})])

    with pytest.raises(AcquisitionError, match="not a PDF"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert not (output / "PMC999.pdf").exists()


def test_second_download_failure_rolls_back_entire_batch(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2)
    approvals = _write_approvals(tmp_path, count=2)
    output = tmp_path / "papers"
    transport = FakeTransport(
        [
            FakeResponse(200, b"%PDF-1.7\nfirst", {}),
            FakeResponse(200, b"<html>not pdf</html>", {}),
        ]
    )

    with pytest.raises(AcquisitionError, match="not a PDF"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert list(output.iterdir()) == []


def test_existing_output_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    output.mkdir()
    (output / "PMC999.pdf").write_bytes(b"existing")
    transport = FakeTransport([])

    with pytest.raises(AcquisitionError, match="already exists"):
        PmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert transport.urls == []


def _write_candidates(tmp_path: Path, *, count: int = 1) -> Path:
    rows = [
        {
            "pmid": "222",
            "pmcid": "PMC999",
            "license": "CC BY",
            "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/example.pdf",
            "open_access": True,
            "status": "oa_verified",
        }
    ]
    if count == 2:
        rows.append(
            {
                "pmid": "333",
                "pmcid": "PMC1000",
                "license": "CC BY",
                "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/second.pdf",
                "open_access": True,
                "status": "oa_verified",
            }
        )
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps({"candidates": rows}), encoding="utf-8")
    return path


def _write_approvals(
    tmp_path: Path,
    *,
    license_name: str = "CC BY",
    count: int = 1,
    duplicate_filename: bool = False,
    selected_count: int | bool | None = None,
) -> Path:
    rows = [
        {
            "pmid": "222",
            "pmcid": "PMC999",
            "license": license_name,
            "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/example.pdf",
            "filename": "PMC999.pdf",
        }
    ]
    if count == 2:
        rows.append(
            {
                "pmid": "333",
                "pmcid": "PMC1000",
                "license": "CC BY",
                "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/second.pdf",
                "filename": "PMC999.pdf" if duplicate_filename else "PMC1000.pdf",
            }
        )
    payload: dict[str, object] = {"schema_version": 1, "approvals": rows}
    if selected_count is not None:
        payload["selected_count"] = selected_count
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
