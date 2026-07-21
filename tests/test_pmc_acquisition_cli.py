from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.pmc_acquisition import AcquisitionReceipt, AcquisitionReceiptItem


class FakeService:
    def __init__(self, *, create_pdf: bool = False) -> None:
        self.calls: list[tuple[Path, Path, Path]] = []
        self.create_pdf = create_pdf

    def acquire(
        self,
        *,
        candidates_path: Path,
        approvals_path: Path,
        output_directory: Path,
    ) -> AcquisitionReceipt:
        self.calls.append((candidates_path, approvals_path, output_directory))
        if self.create_pdf:
            output_directory.mkdir(parents=True, exist_ok=True)
            (output_directory / "PMC999.pdf").write_bytes(b"%PDF-1.7\nbody")
        return AcquisitionReceipt(
            schema_version=1,
            acquired_count=1,
            items=(
                AcquisitionReceiptItem(
                    pmid="222",
                    pmcid="PMC999",
                    license="CC BY",
                    filename="PMC999.pdf",
                    byte_count=12,
                    sha256="a" * 64,
                ),
            ),
        )


def test_acquisition_cli_writes_receipt_and_reports_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeService()
    monkeypatch.setattr(entrypoint, "_pmc_acquisition_service", lambda: service)
    candidates = tmp_path / "candidates.json"
    approvals = tmp_path / "approvals.json"
    receipt = tmp_path / "receipt.json"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "pmc-oa-acquire",
            "--candidates",
            str(candidates),
            "--approvals",
            str(approvals),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt),
        ],
    )

    assert result.exit_code == 0
    assert service.calls == [(candidates, approvals, tmp_path / "papers")]
    assert receipt.exists()
    assert '"acquired_count": 1' in receipt.read_text(encoding="utf-8")
    assert "no manifest rows were promoted" in result.output


def test_existing_receipt_fails_before_service_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("existing", encoding="utf-8")
    called = False

    def fail_if_called() -> FakeService:
        nonlocal called
        called = True
        raise AssertionError("service must not be created")

    monkeypatch.setattr(entrypoint, "_pmc_acquisition_service", fail_if_called)
    result = CliRunner().invoke(
        entrypoint.app,
        [
            "pmc-oa-acquire",
            "--candidates",
            str(tmp_path / "candidates.json"),
            "--approvals",
            str(tmp_path / "approvals.json"),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--receipt",
            str(receipt),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert called is False


def test_receipt_write_failure_rolls_back_acquired_pdfs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FakeService(create_pdf=True)
    monkeypatch.setattr(entrypoint, "_pmc_acquisition_service", lambda: service)
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    papers = tmp_path / "papers"

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "pmc-oa-acquire",
            "--candidates",
            str(tmp_path / "candidates.json"),
            "--approvals",
            str(tmp_path / "approvals.json"),
            "--papers-dir",
            str(papers),
            "--receipt",
            str(blocked_parent / "receipt.json"),
        ],
    )

    assert result.exit_code != 0
    assert "rolled back" in result.output
    assert not (papers / "PMC999.pdf").exists()
