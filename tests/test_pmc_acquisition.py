from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from knowledge_engine.pmc_acquisition import AcquisitionError, PmcOaAcquisitionService


@dataclass(frozen=True)
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
    ) -> FakeResponse:
        del headers, timeout_seconds, max_response_bytes
        self.urls.append(url)
        return self.responses.pop(0)


def test_acquire_requires_exact_approval_and_writes_sanitized_receipt(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    transport = FakeTransport([FakeResponse(200, b"%PDF-1.7\nbody", {})])

    receipt = PmcOaAcquisitionService(transport).acquire(
        candidates_path=candidates,
        approvals_path=approvals,
        output_directory=output,
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


def _write_candidates(tmp_path: Path) -> Path:
    path = tmp_path / "candidates.json"
    path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "pmid": "222",
                        "pmcid": "PMC999",
                        "license": "CC BY",
                        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/example.pdf",
                        "open_access": True,
                        "status": "oa_verified",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_approvals(tmp_path: Path, *, license_name: str = "CC BY") -> Path:
    path = tmp_path / "approvals.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "approvals": [
                    {
                        "pmid": "222",
                        "pmcid": "PMC999",
                        "license": license_name,
                        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/example.pdf",
                        "filename": "PMC999.pdf",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
