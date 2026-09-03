from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from knowledge_engine.europepmc_acquisition import (
    EuropePmcAcquisitionError,
    EuropePmcOaAcquisitionService,
)
from knowledge_engine.europepmc_http import TransportResponse

EPMC999_URL = "https://europepmc.org/articles/EPMC999?pdf=render"
EPMC1000_URL = "https://europepmc.org/articles/EPMC1000?pdf=render"


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    """Responds by request URL, not call order.

    Downloads now run on a bounded thread pool, so two concurrent requests can
    reach ``get`` in either order; keying by URL keeps each planned PDF's
    response deterministic regardless of thread scheduling.
    """

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = dict(responses)
        self.urls: list[str] = []
        self._lock = threading.Lock()

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        del headers, timeout_seconds, max_response_bytes
        with self._lock:
            self.urls.append(url)
            return self.responses[url]


def test_acquire_requires_exact_approval_and_writes_sanitized_receipt(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=1)
    output = tmp_path / "papers"
    transport = FakeTransport({EPMC999_URL: FakeResponse(200, b"%PDF-1.7\nbody", {})})

    receipt = EuropePmcOaAcquisitionService(transport).acquire(
        candidates_path=candidates,
        approvals_path=approvals,
        output_directory=output,
        expected_count=1,
    )

    assert transport.urls == ["https://europepmc.org/articles/EPMC999?pdf=render"]
    assert (output / "europepmc-EPMC999.pdf").read_bytes().startswith(b"%PDF-")
    assert receipt.acquired_count == 1
    assert receipt.items[0].europepmc_id == "EPMC999"
    assert receipt.items[0].doi == "10.1000/example-999"
    assert receipt.items[0].filename == "europepmc-EPMC999.pdf"
    assert receipt.items[0].byte_count == 13
    assert len(receipt.items[0].sha256) == 64
    assert str(tmp_path) not in receipt.to_json()


def test_acquire_accepts_current_europepmc_plus_download(tmp_path: Path) -> None:
    pdf_url = "https://plus.europepmc.org/download/current-pdf.pdf"
    candidates = _write_candidates(tmp_path, pdf_url=pdf_url)
    approvals = _write_approvals(tmp_path, pdf_url=pdf_url, selected_count=1)
    output = tmp_path / "papers"
    transport = FakeTransport({pdf_url: FakeResponse(200, b"%PDF-1.7\nbody", {})})

    receipt = EuropePmcOaAcquisitionService(transport).acquire(
        candidates_path=candidates,
        approvals_path=approvals,
        output_directory=output,
        expected_count=1,
    )

    assert transport.urls == [pdf_url]
    assert receipt.acquired_count == 1


def test_acquire_rejects_non_download_path_on_europepmc_plus(tmp_path: Path) -> None:
    pdf_url = "https://plus.europepmc.org/account/current-pdf.pdf"
    candidates = _write_candidates(tmp_path, pdf_url=pdf_url)
    approvals = _write_approvals(tmp_path, pdf_url=pdf_url)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="Plus download"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_expected_count_mismatch_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=1)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="expected selected count"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
            expected_count=2,
        )

    assert transport.urls == []


def test_boolean_selected_count_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, selected_count=True)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="selected count does not reconcile"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_approval_mismatch_fails_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path, license_name="CC BY-SA")
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="does not match"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_duplicate_europepmc_ids_fail_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2, duplicate_id=True)
    approvals = _write_approvals(tmp_path, count=2, duplicate_id=True)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="duplicate Europe PMC id"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_in_pmc_candidate_fails_before_network(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "europepmc_id": "EPMC999",
                        "doi": "10.1000/example-999",
                        "license": "CC BY",
                        "pdf_url": "https://europepmc.org/articles/EPMC999?pdf=render",
                        "open_access": True,
                        "in_pmc": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    approvals = _write_approvals(tmp_path)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="not out of PMC's own pipeline scope"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates_path,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_unallowlisted_pdf_host_fails_before_network(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "europepmc_id": "EPMC999",
                        "doi": "10.1000/example-999",
                        "license": "CC BY",
                        "pdf_url": "https://attacker.example/EPMC999.pdf",
                        "open_access": True,
                        "in_pmc": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    approvals_path = tmp_path / "approvals.json"
    approvals_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "approvals": [
                    {
                        "europepmc_id": "EPMC999",
                        "doi": "10.1000/example-999",
                        "license": "CC BY",
                        "pdf_url": "https://attacker.example/EPMC999.pdf",
                        "filename": "europepmc-EPMC999.pdf",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="not an allowlisted"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates_path,
            approvals_path=approvals_path,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_duplicate_filenames_fail_before_network(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2)
    approvals = _write_approvals(tmp_path, count=2, duplicate_filename=True)
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="duplicate PDF filename"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=tmp_path / "papers",
        )

    assert transport.urls == []


def test_non_pdf_payload_is_rejected_without_persisting_file(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    transport = FakeTransport({EPMC999_URL: FakeResponse(200, b"<html>not pdf</html>", {})})

    with pytest.raises(EuropePmcAcquisitionError, match="not a PDF"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert not (output / "europepmc-EPMC999.pdf").exists()


def test_non_success_status_is_reported_with_status_code_and_locator(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    transport = FakeTransport({EPMC999_URL: FakeResponse(403, b"forbidden", {})})

    with pytest.raises(
        EuropePmcAcquisitionError, match=r"non-success status \(403\).*approval 1.*EPMC999"
    ):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert transport.urls == ["https://europepmc.org/articles/EPMC999?pdf=render"]
    assert not (output / "europepmc-EPMC999.pdf").exists()


def test_second_download_failure_rolls_back_entire_batch(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2)
    approvals = _write_approvals(tmp_path, count=2)
    output = tmp_path / "papers"
    transport = FakeTransport(
        {
            EPMC999_URL: FakeResponse(200, b"%PDF-1.7\nfirst", {}),
            EPMC1000_URL: FakeResponse(200, b"<html>not pdf</html>", {}),
        }
    )

    with pytest.raises(EuropePmcAcquisitionError, match="not a PDF"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert list(output.iterdir()) == []


def test_partial_write_failure_does_not_leave_a_stray_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates = _write_candidates(tmp_path)
    approvals = _write_approvals(tmp_path)
    output = tmp_path / "papers"
    transport = FakeTransport({EPMC999_URL: FakeResponse(200, b"%PDF-1.7\nbody", {})})

    original_write_bytes = Path.write_bytes

    def failing_write_bytes(self: Path, data: bytes) -> int:
        if self.name.endswith(".tmp"):
            original_write_bytes(self, data[: len(data) // 2])
            raise OSError("disk full")
        return original_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", failing_write_bytes)

    with pytest.raises(EuropePmcAcquisitionError, match="could not be committed"):
        EuropePmcOaAcquisitionService(transport).acquire(
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
    (output / "europepmc-EPMC999.pdf").write_bytes(b"existing")
    transport = FakeTransport({})

    with pytest.raises(EuropePmcAcquisitionError, match="already exists"):
        EuropePmcOaAcquisitionService(transport).acquire(
            candidates_path=candidates,
            approvals_path=approvals,
            output_directory=output,
        )

    assert transport.urls == []


def test_downloads_run_concurrently_up_to_the_bound(tmp_path: Path) -> None:
    candidates = _write_candidates(tmp_path, count=2)
    approvals = _write_approvals(tmp_path, count=2)
    output = tmp_path / "papers"
    # A 2-party barrier only releases once both PDF requests are in flight at
    # the same time; a sequential (non-concurrent) implementation would leave
    # one thread waiting alone and time out, failing this test.
    barrier = threading.Barrier(2, timeout=5)

    class BarrierTransport:
        def __init__(self) -> None:
            self.urls: list[str] = []
            self._lock = threading.Lock()

        def get(
            self,
            *,
            url: str,
            headers: Mapping[str, str],
            timeout_seconds: float,
            max_response_bytes: int,
        ) -> TransportResponse:
            del headers, timeout_seconds, max_response_bytes
            with self._lock:
                self.urls.append(url)
            barrier.wait()
            body = b"%PDF-1.7\nfirst" if url == EPMC999_URL else b"%PDF-1.7\nsecond"
            return FakeResponse(200, body, {})

    transport = BarrierTransport()

    receipt = EuropePmcOaAcquisitionService(transport, max_concurrent_downloads=2).acquire(
        candidates_path=candidates,
        approvals_path=approvals,
        output_directory=output,
    )

    assert receipt.acquired_count == 2
    assert {item.europepmc_id for item in receipt.items} == {"EPMC999", "EPMC1000"}
    # Receipt/staging order must stay deterministic (plan order) even though
    # the two downloads completed on different threads in unpredictable order.
    assert [item.europepmc_id for item in receipt.items] == ["EPMC999", "EPMC1000"]


def test_max_concurrent_downloads_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        EuropePmcOaAcquisitionService(FakeTransport({}), max_concurrent_downloads=0)

    with pytest.raises(ValueError, match="at least 1"):
        EuropePmcOaAcquisitionService(FakeTransport({}), max_concurrent_downloads=True)


def _write_candidates(
    tmp_path: Path,
    *,
    count: int = 1,
    duplicate_id: bool = False,
    pdf_url: str = "https://europepmc.org/articles/EPMC999?pdf=render",
) -> Path:
    rows = [
        {
            "europepmc_id": "EPMC999",
            "doi": "10.1000/example-999",
            "license": "CC BY",
            "pdf_url": pdf_url,
            "open_access": True,
            "in_pmc": False,
        }
    ]
    if count == 2:
        rows.append(
            {
                "europepmc_id": "EPMC999" if duplicate_id else "EPMC1000",
                "doi": "10.1000/example-1000",
                "license": "CC BY",
                "pdf_url": "https://europepmc.org/articles/EPMC1000?pdf=render",
                "open_access": True,
                "in_pmc": False,
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
    duplicate_id: bool = False,
    selected_count: int | bool | None = None,
    pdf_url: str = "https://europepmc.org/articles/EPMC999?pdf=render",
) -> Path:
    rows = [
        {
            "europepmc_id": "EPMC999",
            "doi": "10.1000/example-999",
            "license": license_name,
            "pdf_url": pdf_url,
            "filename": "europepmc-EPMC999.pdf",
        }
    ]
    if count == 2:
        rows.append(
            {
                "europepmc_id": "EPMC999" if duplicate_id else "EPMC1000",
                "doi": "10.1000/example-1000",
                "license": "CC BY",
                "pdf_url": "https://europepmc.org/articles/EPMC1000?pdf=render",
                "filename": "europepmc-EPMC999.pdf"
                if duplicate_filename
                else "europepmc-EPMC1000.pdf",
            }
        )
    payload: dict[str, object] = {"schema_version": 1, "approvals": rows}
    if selected_count is not None:
        payload["selected_count"] = selected_count
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
